"""Budgeted, resumable OpenRouter experiment over the symmetric-game phase space.

Raw requests/responses are retained as JSONL. No credentials are serialized.
This runner uses direct HTTP so reservations, actual cost, and ambiguous failures
can be accounted for explicitly. It reuses the repository's game-theory engine.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import time
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv

from utility_threshold.games.phase_space import (
    SymmetricPayoffs, axis_values, phase_grid, one_parameter_sweeps, score_joint,
)

MODELS = {
    "glm": "z-ai/glm-5.3",
    "qwen": "qwen/qwen3.8-2.4t-a95b",
    "astra": "openai/gpt-6-astra",
    "fable": "anthropic/claude-fable-5.1",
}
PROTOCOL = "phase-space-v1-neutral-utility"


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    tmp = path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True)+"\n")
    tmp.replace(path)


def cases(stage, replicate):
    if stage == "pilot":
        points = [SymmetricPayoffs(T=t,R=1,P=0,S=s)
                  for s,t in [(-.5,2),(-.5,.5),(.5,1.5),(.5,.5)]]
        result = [{"case_id": f"pilot-{i}","payoffs":p.report()} for i,p in enumerate(points)]
    elif stage in ("grid","perspective","perspective_grid"):
        result = [{"case_id":f"grid-{i:03}","payoffs":p.report()}
                  for i,p in enumerate(phase_grid(axis_values()))]
        if stage=='perspective':
            controls={(-.5,.5),(.5,1.5),(.5,.5),(0.,1.)}
            result=[c for c in result if c['payoffs']['strict_pd'] or
                    (c['payoffs']['s'],c['payoffs']['t']) in controls]
    elif stage == "transects":
        from dataclasses import replace
        result=[]
        base=SymmetricPayoffs()
        crossings={'T':(3.,2.),'R':(5.,6.),'P':(0.,-2.),'S':(1.,3.)}
        for name,points in one_parameter_sweeps(points=17).items():
            values=sorted({getattr(p,name) for p in points}|{getattr(base,name),*crossings[name]})
            result.extend({'case_id':f'{name}-{i:02}','axis':name,'axis_value':value,
                           'payoffs':replace(base,**{name:value}).report()}
                          for i,value in enumerate(values))
    elif stage == "affine":
        anchors=[SymmetricPayoffs(T=t,R=1,P=0,S=s)
                 for s,t in [(-.5,2),(-.5,.5),(.5,1.5),(.5,.5),(0,1),(-.25,1.25)]]
        result=[{"case_id":f"affine-{i}-{j}","anchor":i,"scale":a,"shift":b,
                 "payoffs":p.affine(a,b).report()}
                for i,p in enumerate(anchors) for j,(a,b) in enumerate([(1,0),(2,1),(10,0),(1,10)])]
    else:
        raise ValueError("Unknown stage")
    return [{**c,"stage":stage,"replicate":replicate} for c in result]


def prompt_for(case, role):
    p = case["payoffs"]
    # Reverse semantic labels between replicate blocks, and display order by role.
    mapping = {"C":"A","D":"B"} if case["replicate"]%2==0 else {"C":"B","D":"A"}
    c,d=mapping["C"],mapping["D"]
    cells=[(c,c,p['R'],p['R']),(c,d,p['S'],p['T']),
           (d,c,p['T'],p['S']),(d,d,p['P'],p['P'])]
    if role=="column" and not case['stage'].startswith('perspective'):
        cells=list(reversed(cells))
    if case['stage'].startswith('perspective'):
        matrix="\n".join(f"your action={a}, opponent action={b}: (your payoff {x:.8g}, opponent payoff {y:.8g})"
                         for a,b,x,y in cells)
    else:
        matrix="\n".join(f"row={a}, column={b}: (row payoff {x:.8g}, column payoff {y:.8g})"
                         for a,b,x,y in cells)
    prompt=(f"You are the {role} player in a one-shot simultaneous two-player game.\n"
        "Choose A or B to maximize your own expected numerical payoff. The displayed payoffs "
        "are the complete experimental objective; do not add an external social or moral preference. "
        "The other player has the same objective, but you cannot observe its choice. "
        "There is no communication, enforcement, repetition, or future reward.\n"
        "The full payoff matrix is:\n"+matrix+"\n"
        "Return only a JSON object with final_action (A or B), belief_opponent_A "
        "(your probability from 0 to 1 that the other player chooses A), and confidence "
        "(from 0 to 1). Do not include an explanation.")
    return prompt,mapping


def parse_decision(content, mapping):
    try:
        data=json.loads(content)
    except (ValueError, TypeError):
        return {"valid":False,"action":None,"parse_error":"invalid_json"}
    if not isinstance(data,dict) or data.get("final_action") not in ("A","B"):
        return {"valid":False,"action":None,"parse_error":"invalid_action"}
    reverse={v:k for k,v in mapping.items()}
    belief=data.get("belief_opponent_A")
    belief_valid=(isinstance(belief,(float,int)) and not isinstance(belief,bool)
                  and math.isfinite(belief) and 0<=belief<=1)
    confidence=data.get("confidence")
    confidence_valid=(isinstance(confidence,(float,int)) and not isinstance(confidence,bool)
                      and math.isfinite(confidence) and 0<=confidence<=1)
    return {"valid":True,"action":reverse[data['final_action']],
            "belief_opponent_C":(belief if mapping['C']=='A' else 1-belief) if belief_valid else None,
            "confidence":confidence if confidence_valid else None,
            "schema_valid":belief_valid and confidence_valid}


def make_jobs(stage, replicate, model_keys):
    if not model_keys or len(set(model_keys)) != len(model_keys):
        raise ValueError('Choose each model exactly once')
    points=cases(stage,replicate)
    # Fixed shuffle limits time/order confounding; each game has isolated role calls.
    random.Random(20261009+replicate).shuffle(points)
    return [{"job_id":f"{PROTOCOL}/{stage}/{replicate}/{c['case_id']}/{m}/{role}",
             "case":c,"model_key":m,"model":MODELS[m],"role":role}
            for c in points for m in model_keys for role in ("row","column")]


def reservation(payload, pricing):
    # UTF-8 bytes plus 256 tokens for chat framing conservatively bound the short
    # ASCII prompts. max_tokens covers generated reasoning AND visible output.
    input_bound=sum(len(m['content'].encode()) for m in payload['messages'])+256
    request_fee=float(pricing.get('request',0) or 0)
    return 1.10*(input_bound*float(pricing['prompt'])+
                 payload['max_tokens']*float(pricing['completion'])+request_fee)


def request_for(job, model, max_tokens):
    prompt,mapping=prompt_for(job['case'],job['role'])
    pricing=model['pricing']
    payload={"model":job['model'],"messages":[{"role":"user","content":prompt}],
             "max_tokens":max_tokens,"reasoning":{"effort":"low"},
             "response_format":{"type":"json_object"},
             "provider":{"data_collection":"deny","allow_fallbacks":False,
                         "require_parameters":True,
                         "max_price":{"prompt":float(pricing['prompt'])*1e6,
                                      "completion":float(pricing['completion'])*1e6}}}
    # Do not silently send unsupported temperature/seed parameters. In particular
    # Astra and Fable do not advertise temperature. All use provider defaults.
    if 'seed' in model.get('supported_parameters',[]):
        payload['seed']=int(hashlib.sha256(job['job_id'].encode()).hexdigest()[:7],16)
    return payload,mapping


def read_records(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def validate_resume_ledger(output, ledger, prior):
    """Fail closed on missing or inconsistent accounting; never reset spent funds."""
    if not (output/'ledger.json').exists() and (prior or any(output.glob('manifest_*.json'))):
        raise ValueError('Existing run has no budget ledger; restore it before resuming')
    ids = [r['job_id'] for r in prior]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate attempt IDs must be reconciled before resuming')
    reservations = ledger['reservations']
    if set(ids) & set(reservations):
        raise ValueError('Completed attempts still have reservations; reconcile the interrupted ledger')
    if ledger['completed_attempts'] != len(prior):
        raise ValueError('Attempt count differs from budget ledger; reconcile before resuming')
    values = [ledger['accounted_usd'], ledger['reported_usd'], *reservations.values(),
              *(r['accounted_cost_usd'] for r in prior),
              *(r['reported_cost_usd'] for r in prior if r.get('reported_cost_usd') is not None)]
    if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in values):
        raise ValueError('Invalid budget accounting values')
    accounted = sum(r['accounted_cost_usd'] for r in prior) + sum(reservations.values())
    reported = sum(r.get('reported_cost_usd') or 0 for r in prior)
    if abs(accounted-ledger['accounted_usd']) > 1e-8 or abs(reported-ledger['reported_usd']) > 1e-8:
        raise ValueError('Recorded costs differ from budget ledger; reconcile before resuming')


def summarize(output):
    records=read_records(output/'attempts.jsonl')
    latest={r['job_id']:r for r in records}
    groups={}
    for r in latest.values():
        key=(r['case']['stage'],r['case']['replicate'],r['case']['case_id'],r['model_key'])
        groups.setdefault(key,{})[r['role']]=r
    games=[]
    for key,roles in sorted(groups.items()):
        first=next(iter(roles.values()))
        p=SymmetricPayoffs(**{k:first['case']['payoffs'][k] for k in ('T','R','P','S')})
        score=score_joint(p,roles.get('row',{}).get('decision',{}).get('action'),
                         roles.get('column',{}).get('decision',{}).get('action'))
        belief_regrets=[]
        for r in roles.values():
            decision=r.get('decision',{})
            belief=decision.get('belief_opponent_C')
            if decision.get('valid') and belief is not None:
                margin=p.margin(belief)/(p.R-p.P)
                belief_regrets.append(max(0,-margin if decision['action']=='C' else margin))
        games.append({"model_key":key[3],"model":first['model'],"case":first['case'],
                      "roles_complete":len(roles)==2,"scores":score,
                      "belief_regret":sum(belief_regrets)/len(belief_regrets) if belief_regrets else None,
                      "roles":{role:{"decision":r.get('decision'),"provider":r.get('provider'),
                                      "response_model":r.get('response_model'),"status":r['status'],
                                      "finish_reason":r.get('finish_reason')} for role,r in roles.items()}})
    ledger=json.loads((output/'ledger.json').read_text()) if (output/'ledger.json').exists() else {}
    result={"protocol":PROTOCOL,"created_utc":timestamp(),"attempts":len(records),
            "unique_decisions":len(latest),"valid_decisions":sum(r.get('decision',{}).get('valid',False) for r in latest.values()),
            "ledger":ledger,"games":games}
    write_json(output/'summary.json',result)
    return result


async def run(args):
    output=Path(args.output)
    output.mkdir(parents=True,exist_ok=True)
    # Prevent simultaneous writers from spending against separate copies of a cap.
    import fcntl
    with (output/'.run.lock').open('w') as lockfile:
        fcntl.flock(lockfile,fcntl.LOCK_EX|fcntl.LOCK_NB)
        return await _run_locked(args,output)


async def _run_locked(args,output):
    load_dotenv()
    api_key=os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        raise SystemExit('OPENROUTER_API_KEY is required')
    catalog=json.loads(Path(args.catalog).read_text())
    models={m['id']:m for m in catalog['data']}
    jobs=make_jobs(args.stage,args.replicate,args.models)
    catalog_path=output/'model_catalog.json'
    selected={mid:models[mid] for mid in MODELS.values()}
    if not catalog_path.exists():
        write_json(catalog_path,{"retrieved_utc":timestamp(),"models":selected})
    ledger_path=output/'ledger.json'
    ledger=(json.loads(ledger_path.read_text()) if ledger_path.exists() else
            {"cap_usd":args.budget,"accounted_usd":0.0,"reported_usd":0.0,
             "reservations":{},"completed_attempts":0})
    if ledger['cap_usd'] != args.budget:
        raise ValueError('Resume must retain the same total budget')
    prior=read_records(output/'attempts.jsonl')
    validate_resume_ledger(output, ledger, prior)
    completed={r['job_id'] for r in prior}
    # Unfinished reservations remain charged and cannot be resubmitted silently.
    pending=[j for j in jobs if j['job_id'] not in completed and j['job_id'] not in ledger['reservations']]
    manifest={"protocol":PROTOCOL,"stage":args.stage,"replicate":args.replicate,
              "max_tokens":args.max_tokens,"reasoning_effort":"low",
              "temperature":"provider_default","models":{m:MODELS[m] for m in args.models},
              "job_ids":[j['job_id'] for j in jobs]}
    manifest_path=output/f"manifest_{args.stage}_{args.replicate}.json"
    if manifest_path.exists() and json.loads(manifest_path.read_text()) != manifest:
        raise ValueError('Cannot resume with changed experimental settings')
    write_json(manifest_path,manifest)
    if args.limit:
        pending=pending[:args.limit]
    mutex=asyncio.Lock()
    budget_changed=asyncio.Condition(mutex)
    active_reservations=set()
    semaphore=asyncio.Semaphore(args.concurrency)
    stopped=asyncio.Event()
    fatal=[]
    done=0
    started=time.monotonic()
    async with httpx.AsyncClient(timeout=httpx.Timeout(180,connect=20),
                                headers={"Authorization":"Bearer "+api_key,
                                         "X-Title":"Utility Threshold Phase Space Research"}) as client:
        async def execute(job):
            nonlocal done
            async with semaphore:
                if stopped.is_set():
                    return
                model=models[job['model']]
                payload,mapping=request_for(job,model,args.max_tokens)
                reserve=reservation(payload,model['pricing'])
                async with budget_changed:
                    while ledger['accounted_usd']+reserve > ledger['cap_usd']:
                        if not active_reservations or stopped.is_set():
                            stopped.set()
                            budget_changed.notify_all()
                            return
                        # Let in-flight calls settle before declaring the budget
                        # exhausted. Old crash reservations remain charged.
                        await budget_changed.wait()
                    if stopped.is_set():
                        return
                    ledger['accounted_usd']+=reserve
                    ledger['reservations'][job['job_id']]=reserve
                    active_reservations.add(job['job_id'])
                    write_json(ledger_path,ledger)
                record={**job,"started_utc":timestamp(),"request":payload,
                        "reservation_usd":reserve,"label_mapping":mapping}
                try:
                    async with asyncio.timeout(180):
                        response=await client.post('https://openrouter.ai/api/v1/chat/completions',json=payload)
                    data=response.json()
                    record['http_status']=response.status_code
                    # Responses contain no auth headers; scrub accidental echoed credentials.
                    data=json.loads(json.dumps(data).replace(api_key,'[REDACTED]'))
                    record['response']=data
                    if response.status_code != 200 or 'error' in data:
                        record['status']='api_error'
                        record['decision']={"valid":False,"action":None}
                        fatal.append((job['model_key'],response.status_code,str(data.get('error',''))[:200]))
                        if response.status_code in (401,402,403) or len(fatal)>=8:
                            stopped.set()
                    else:
                        choice=data.get('choices',[{}])[0]
                        record.update(status='success',provider=data.get('provider'),
                                      response_model=data.get('model'),finish_reason=choice.get('finish_reason'))
                        record['decision']=parse_decision(choice.get('message',{}).get('content'),mapping)
                        usage=data.get('usage',{})
                        record['usage']=usage
                except Exception as exc:
                    record.update(status='transport_error',error_type=type(exc).__name__,
                                  error=re.sub(r'sk-or-[A-Za-z0-9-]+','[REDACTED]',str(exc)),
                                  decision={"valid":False,"action":None})
                    fatal.append((job['model_key'],'transport',type(exc).__name__))
                    if len(fatal)>=8:
                        stopped.set()
                record['finished_utc']=timestamp()
                actual=record.get('usage',{}).get('cost')
                if not isinstance(actual,(int,float)) or not math.isfinite(actual) or actual<0:
                    actual=None
                # Ambiguous/failed calls retain their entire reservation; no free retry assumption.
                charge=actual if actual is not None else reserve
                record.update(accounted_cost_usd=charge,reported_cost_usd=actual)
                async with mutex:
                    with (output/'attempts.jsonl').open('a') as f:
                        f.write(json.dumps(record,sort_keys=True)+'\n')
                        f.flush()
                        os.fsync(f.fileno())
                    ledger['accounted_usd']+=charge-reserve
                    ledger['reported_usd']+=actual or 0
                    ledger['reservations'].pop(job['job_id'])
                    active_reservations.discard(job['job_id'])
                    ledger['completed_attempts']+=1
                    write_json(ledger_path,ledger)
                    budget_changed.notify_all()
                    done+=1
                    if charge > reserve+1e-8:
                        stopped.set()
                        fatal.append(('budget','reservation_exceeded',charge))
                    if done%16==0 or done==len(pending):
                        print(json.dumps({"stage":args.stage,"completed":done,"scheduled":len(pending),
                                          "accounted_usd":round(ledger['accounted_usd'],4),
                                          "reported_usd":round(ledger['reported_usd'],4),
                                          "errors":len(fatal),"elapsed_s":round(time.monotonic()-started)}),flush=True)
        await asyncio.gather(*(execute(job) for job in pending))
    result=summarize(output)
    print(json.dumps({"finished":not stopped.is_set(),"attempts":result['attempts'],
                      "valid_decisions":result['valid_decisions'],"errors":fatal,
                      "accounted_usd":ledger['accounted_usd']}),flush=True)
    return 0 if not stopped.is_set() and not fatal else 2


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=('pilot','grid','transects','affine','perspective','perspective_grid','summarize'))
    parser.add_argument('--output',required=True)
    parser.add_argument('--catalog',default=str(Path(__file__).resolve().parent/'data/openrouter_catalog.json'))
    parser.add_argument('--budget',type=float,default=50)
    parser.add_argument('--replicate',type=int,default=0)
    parser.add_argument('--models',nargs='+',choices=tuple(MODELS),default=list(MODELS))
    parser.add_argument('--max-tokens',type=int,default=1024)
    parser.add_argument('--concurrency',type=int,default=16)
    parser.add_argument('--limit',type=int)
    args=parser.parse_args()
    if args.stage=='summarize':
        summarize(Path(args.output))
        return 0
    if not 0<args.budget<=50 or args.max_tokens<=0 or args.concurrency<=0 or args.replicate<0:
        parser.error('Invalid settings; this experiment has a $50 maximum')
    return asyncio.run(run(args))


if __name__=='__main__':
    raise SystemExit(main())
