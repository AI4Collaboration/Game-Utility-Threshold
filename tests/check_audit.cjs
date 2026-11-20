'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),cp=require('node:child_process');
const {Audit}=require('../web/audit-engine.js');
const output=cp.execFileSync(process.env.PYTHON||'python3',['-c',`
import json
from gut.audit_game import demo_game
from gut.oversight import exact_json
cases=[]
for setting in ('known','hidden'):
 for x in ('0','0.5','1'):
  for spread in ('0','0.3','0.35'):
   game=demo_game(setting,x,spread)
   for q in ('0','1/3','1/2','8/15','1'):
    cases.append(dict(input=[setting,x,spread,q],output=exact_json(dict(selected=game.evaluate(q),solution=game.commitment().solve(),safe_region=game.safe_region(),safety_optimum=game.safety_optimum(),thresholds=game.thresholds()))))
print(json.dumps(cases))
`],{encoding:'utf8',maxBuffer:8*1024*1024});
for(const row of JSON.parse(output))assert.deepEqual(new Audit(...row.input.slice(0,3)).state(row.input[3]),row.output,row.input.join(','));
for(const input of [['bad',0,0],['known',-1,0],['hidden',0,'.4']])assert.throws(()=>new Audit(...input));
const html=fs.readFileSync('web/audit.html','utf8'),nodes=new Map();
for(const m of html.matchAll(/<[^>]+\bid="([^"]+)"[^>]*>/g)){
 const tag=m[0],after=html.slice(m.index),select=tag.includes('<select')?after.split('</select>')[0]:'',options=[...select.matchAll(/<option value="([^"]+)"([^>]*)>/g)];
 const chosen=options.find(o=>o[2].includes('selected'))||options[0];
 nodes.set(m[1],{value:tag.match(/\bvalue="([^"]*)"/)?.[1]||chosen?.[1]||'',hidden:/\bhidden\b/.test(tag),disabled:/\bdisabled\b/.test(tag),textContent:'',innerHTML:'',listeners:{},addEventListener(k,fn){this.listeners[k]=fn;}});
}
const get=id=>{assert(nodes.has(id),id);return nodes.get(id);};
vm.runInNewContext(fs.readFileSync('web/audit.js','utf8'),{document:{getElementById:get},AuditEngine:require('../web/audit-engine.js')});
const change=(id,value,event='input')=>{get(id).value=String(value);get(id).listeners[event]();};
assert.equal(get('error').hidden,true);assert.equal((get('charts').innerHTML.match(/<svg/g)||[]).length,2);
change('punishment',0);assert.match(get('safe').textContent,/No allocation deters/);
change('setting','known','change');assert.equal(get('spread').disabled,true);assert.match(get('safe').textContent,/at least as rewarding/);
assert.equal((get('charts').innerHTML.match(/<svg/g)||[]).length,1);
get('robust').listeners.click();assert.match(get('verdict').textContent,/pays more/);
get('play').listeners.click();assert.equal(get('download').disabled,false);const first=get('outcome').textContent;
get('play').listeners.click();assert.equal(get('outcome').textContent,first);
change('seed','-1','change');get('play').listeners.click();assert.equal(get('download').disabled,true);
change('setting','hidden','change');change('punishment','.5');get('robust').listeners.click();
assert.doesNotMatch(get('charts').innerHTML,/NaN|Infinity|undefined/);
change('q','bad');assert.equal(get('play').disabled,true);assert.equal(get('error').hidden,false);
console.log('Audit: 90 exact Python/browser comparisons; UI switches, infeasibility, robust policy and reproducible rounds passed.');
