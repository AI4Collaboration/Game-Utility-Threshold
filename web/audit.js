'use strict';
const $=id=>document.getElementById(id),{Audit,ACTIONS,f}=AuditEngine;
const labels={abstain:'Abstain',target_a:'Violate A',target_b:'Violate B'};
const fmt=n=>Number(n.toFixed(4)).toString(),pct=n=>`${fmt(n*100)}%`;
let game,state,exactQ=null,round=null;
function plot(k){
 const start=game.evaluate(0).types[k].follower.map(x=>x.value()),end=game.evaluate(1).types[k].follower.map(x=>x.value());
 const low=Math.min(...start,...end)-.1,high=Math.max(...start,...end)+.1,w=470,h=255,l=49,r=15,t=25,b=45;
 const x=q=>l+q*(w-l-r),y=v=>h-b-(v-low)/(high-low)*(h-b-t);
 let svg=`<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${game.types[k].name} reward profile: expected action payoffs against checking chance"><title>Expected action payoffs · ${game.types[k].name}</title>`;
 for(let i=0;i<5;i++){const v=low+(high-low)*i/4;svg+=`<path d="M${l} ${y(v)}H${w-r}" stroke="#2b414d"/><text x="${l-7}" y="${y(v)+4}" text-anchor="end" fill="#a6bac5" font-size="11">${fmt(v)}</text><text x="${x(i/4)}" y="${h-b+22}" text-anchor="middle" fill="#a6bac5" font-size="11">${i*25}%</text>`;}
 ['#c5ced3','#9be3c8','#efa6ae'].forEach((color,a)=>{svg+=`<path d="M${x(0)} ${y(start[a])}L${x(1)} ${y(end[a])}" stroke="${color}" stroke-width="${a?3:1.5}" stroke-dasharray="${a?'none':'5 4'}"/>`;});
 const q=state.selected.q.value;svg+=`<path d="M${x(q)} ${t}V${h-b}" stroke="white" opacity=".6"/><text x="${w/2}" y="${h-5}" text-anchor="middle" fill="#a6bac5" font-size="11">Chance of checking A (B gets the remainder)</text></svg>`;
 return `<div><h3>${game.types[k].name+' rewards · '+pct(game.types[k].prior.value())+' current probability'}</h3>${svg}</div>`;
}
function render(){
 try{
  game=new Audit($('setting').value,$('punishment').value,$('spread').value,$('profile').value);
  state=game.state(exactQ||$('q').value);
  $('spread').disabled=true;
  $('setting-note').textContent=$('setting').value==='known'?'The defender sees the selected actual profile before choosing where to check. Rewards are identical to the hidden condition.':'The defender sees the two possibilities and their 50/50 prior. The actual profile is hidden from the experimental defender; the teaching selector below lets you compare matched rounds.';
  $('q-label').textContent=`${pct(state.selected.q.value)} (${state.selected.q.exact})`;
  $('allocation').textContent=`A: ${pct(state.selected.q.value)} · B: ${pct(1-state.selected.q.value)}. Exactly one check, not two independent checks.`;
  $('punishment-label').textContent=$('punishment').value+' points';$('spread-label').textContent='±'+$('spread').value+' points (fixed)';
  const margin=state.selected.worst_margin.value,attack=state.selected.attack_probability;
  $('verdict').textContent=margin>0?'Abstaining pays more for every profile.':margin===0?'At least one profile is exactly at a threshold.':'At least one profile can earn more by violating.';
  $('margin').textContent=fmt(margin);$('attack').textContent=attack.lower.exact===attack.upper.exact?pct(attack.lower.value):`${pct(attack.lower.value)}–${pct(attack.upper.value)}`;
  $('payoffs').innerHTML=state.selected.types.map(t=>`<tr><td>${t.name}</td>${t.follower.map(p=>`<td title="${p.exact}">${fmt(p.value)}</td>`).join('')}<td>${t.best_responses.map(a=>labels[a]).join(' / ')}</td></tr>`).join('');
  const safe=state.safe_region,opt=state.safety_optimum;
  $('safe').textContent=safe.feasible?`Abstention is at least as rewarding for every profile when checking A between ${pct(safe.interval[0].value)} and ${pct(safe.interval[1].value)}. Boundaries may be ties. Largest strict margin: ${fmt(opt.margin.value)} points.`:`No allocation deters every profile at this penalty. The best achievable smallest margin is ${fmt(opt.margin.value)} points.`;
  $('solver').textContent=['favorable','unfavorable'].map(tie=>{const s=state.solution[tie];return `${tie==='favorable'?'Defender-favorable':'Defender-unfavorable'} ties: ${fmt(s.value.value)} expected defender points; ${s.attained?`attained, e.g. check A with probability ${pct(s.witnesses[0].value)}`:'a limit only, no policy attains it'}.`;}).join(' ');
  $('charts').innerHTML=game.types.map((t,k)=>plot(k)).join('');
  $('thresholds').textContent=state.thresholds.map(t=>`${t.type}, ${t.target==='target_a'?'A':'B'}: its own checking threshold is ${t.checking_probability.exact} (${pct(t.checking_probability.value)}).`).join(' ');
  $('error').hidden=true;$('play').disabled=false;round=null;$('download').disabled=true;$('outcome').textContent='Ready. Changing information keeps the selected actual rewards unchanged. Only the check is drawn during play.';
 }catch(error){$('error').textContent=error.message+' Previous results are stale.';$('error').hidden=false;$('play').disabled=true;$('download').disabled=true;}
}
function randomSource(seed){
 let s=seed>>>0;
 const next=()=>{s=(s+0x6D2B79F5)>>>0;let t=Math.imul(s^(s>>>15),s|1);t^=t+Math.imul(t^(t>>>7),t|61);return (t^(t>>>14))>>>0;};
 return n=>{const limit=4294967296-(4294967296%n);let x;do{x=next();}while(x>=limit);return x%n;};
}
function play(){
 const seed=Number($('seed').value);
 if($('seed').value===''||!Number.isSafeInteger(seed)||seed<0||seed>4294967295){$('outcome').textContent='Use a whole-number seed from 0 to 4294967295.';round=null;$('download').disabled=true;return;}
 const draw=randomSource(seed),kind=game.types.findIndex(t=>t.name===$('profile').value),row=game.evaluate(state.selected.q.exact).types[kind],best=row.best_responses;
 const action=$('baseline').value==='maximize'?($('tie').value==='attack'?best.find(a=>a!=='abstain')||'abstain':best[0]):$('baseline').value;
 const q=f(state.selected.q.exact),inspected=draw(Number(q.d))<Number(q.n)?0:1,target=ACTIONS.indexOf(action)-1,caught=target>=0&&target===inspected,t=game.types[kind];
 const attacker=target<0?f(0):caught?t.c[target].sub(game.x):t.u[target];
 const defender=game.cost.neg().add(target<0?f(0):f(caught?['-.1','-.2'][target]:['-1','-1.2'][target]));
 round={schema:'gut-audit-browser-round-v2',synthetic:true,seed,random_generator:'mulberry32-rejection',setting:$('setting').value,punishment:game.x.toString(),spread:game.spread.toString(),q:q.toString(),baseline:$('baseline').value,tie:$('tie').value,private_type:t.name,action,inspected_target:ACTIONS[inspected+1],violation:target>=0,caught,attacker_payoff:attacker.toString(),defender_payoff:defender.toString(),theory:state};
 $('outcome').textContent=`Profile: ${t.name}. AI: ${labels[action]}. Checked: ${inspected===0?'A':'B'}. ${target<0?'No violation.':caught?'Violation detected.':'Violation went undetected.'} AI earned ${attacker.toString()} points; you earned ${defender.toString()} points. Replaying this seed and settings repeats the outcome.`;
 $('download').disabled=false;
}
for(const id of ['setting','profile','q','punishment','spread'])$(id).addEventListener(['setting','profile'].includes(id)?'change':'input',()=>{exactQ=null;render();});
for(const id of ['baseline','tie','seed'])$(id).addEventListener('change',()=>{round=null;$('download').disabled=true;$('outcome').textContent='Settings changed. Play to generate a new round.';});
$('robust').addEventListener('click',()=>{exactQ=state.safety_optimum.witnesses[0].exact;$('q').value=state.safety_optimum.witnesses[0].value;render();});
$('play').addEventListener('click',play);
$('download').addEventListener('click',()=>{if(!round)return;const url=URL.createObjectURL(new Blob([JSON.stringify(round,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='audit-synthetic-round.json';a.click();URL.revokeObjectURL(url);});
render();
