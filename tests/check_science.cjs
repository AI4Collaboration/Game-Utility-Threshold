/* Exact incentive, exhaustive audit-subset, replay, and UI lifecycle checks.
 * No packages, network, model calls, or simulated browser-layout assertions.
 */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const game = require('../web/science-engine.js');
const config = (budget=1, penalty=8, policy='mixed') => ({budget, penalty, policy});

// Independently enumerate all possible audit subsets and score false reports.
// This checks the claimed inclusion probability and payoff expectation without
// relying on the seeded generator's empirical frequencies.
for (let k=0;k<=8;k++) {
  const subsets = Array.from({length:256},(_,mask)=>Array.from({length:8},(_,i)=>i).filter(i=>mask&(1<<i))).filter(s=>s.length===k);
  for (let p=0;p<=12;p++) {
    for (let changed=0;changed<8;changed++) {
      const caught=subsets.filter(s=>s.includes(changed)).length;
      const total=caught*(-p)+(subsets.length-caught)*4;
      const predicted=game.forecast(config(k,p));
      assert.equal(caught/subsets.length,predicted.detection);
      assert.equal(total/subsets.length,predicted.inflated);
      assert.equal(predicted.preferred,total<subsets.length?'accurate':total>subsets.length?'inflate':'tie');
      assert(predicted.firstStrictBudget>=0 && predicted.firstStrictBudget<=8);
      assert(game.forecast(config(predicted.firstStrictBudget,p)).margin>0);
      if(predicted.firstStrictBudget)assert(game.forecast(config(predicted.firstStrictBudget-1,p)).margin<=0);
    }
  }
}
assert.equal(game.forecast(config(2)).preferred,'tie');
assert.equal(game.forecast(config(2)).thresholdExact,'1/4');
assert.equal(game.forecast(config(3)).firstStrictBudget,3);
assert.equal(game.forecast(config(0,0)).thresholdExact,'3/4');
assert.equal(game.forecast(config(0)).detectionExact,'0');
assert.equal(game.forecast(config(8)).detectionExact,'1');
for(const policy of game.POLICIES)for(const seed of [0,1,2,3,12345,0xffffffff])for(const k of [0,1,2,3,8]) {
  const input=config(k,8,policy), round=game.makeRound(input,seed);
  assert.deepEqual(round,game.makeRound(input,seed));
  assert.deepEqual(round,JSON.parse(JSON.stringify(round)));
  assert.equal(round.auditIndices.length,k);
  assert.equal(new Set(round.auditIndices).size,k);
  assert(round.auditIndices.every(i=>i>=0&&i<8));
  const bad=round.records.filter(r=>r.actual!==r.reported);
  assert.equal(bad.length,round.action==='inflate'?1:0);
  assert.equal(round.reportedMean-round.actualMean,round.action==='inflate'?2:0);
  assert(round.records.every(r=>r.actual>=47&&r.actual<=54));
  assert.equal(round.reporterFoundError,undefined);
  assert.equal(round.reviewerFoundError,round.auditIndices.some(i=>round.records[i].actual!==round.records[i].reported));
  if(k===8)assert.equal(round.reviewerFoundError,round.action==='inflate');
  if(k===0)assert.equal(round.reviewerFoundError,false);
  if(policy==='accurate'||policy==='inflate')assert.equal(round.action,policy);
  if(policy==='maximizer')assert.equal(round.action,k<2?'inflate':'accurate');
}
for (const [policy,verdict,ai,human] of [['accurate','accept',1,3],['accurate','return',0,-2],['inflate','accept',4,-6],['inflate','return',-8,2]]) {
  const round=game.makeRound(config(3,8,policy),42), result=game.judge(round,verdict);
  assert.equal(result.aiPoints,ai);assert.equal(result.humanPoints,human-.75);
  assert.equal(result.correctVerdict,(policy==='accurate')===(verdict==='accept'));
}
for(const bad of [config(-1),config(9),config(1.5),config(NaN),config(1,-1),config(1,13),config(1,8,'unknown')])assert.throws(()=>game.forecast(bad));
for(const seed of [-1,1.5,NaN,0x100000000])assert.throws(()=>game.makeRound(config(),seed));
assert.throws(()=>game.judge(game.makeRound(config(),1),'maybe'));

// Minimal DOM for controller state, hidden answers, frozen settings and export.
const nodes=new Map(), html=fs.readFileSync('web/science.html','utf8');
for(const match of html.matchAll(/<[^>]+\bid="([^"]+)"[^>]*>/g)) {
  const tag=match[0], id=match[1];
  nodes.set(id,{value:tag.match(/\bvalue="([^"]*)"/)?.[1]||'',hidden:/\bhidden\b/.test(tag),disabled:/\bdisabled\b/.test(tag),
    textContent:'',innerHTML:'',clientWidth:330,listeners:{},classList:{toggle(){}},
    addEventListener(type,fn){this.listeners[type]=fn;},focus(){this.focused=true;},scrollIntoView(){}});
}
const node=id=>{assert(nodes.has(id),`Missing HTML element ${id}`);return nodes.get(id);};
node('policy').value='inflate';
let blobs=[], downloads=[];
class ExportURL extends URL {static createObjectURL(blob){blobs.push(blob);return 'blob:test';}static revokeObjectURL(){}}
const context=vm.createContext({ScienceGame:game,console,Blob,URL:ExportURL,Uint32Array,
  crypto:{getRandomValues(array){array[0]=12345;return array;}},setTimeout(fn){fn();},window:{addEventListener(){}},
  document:{getElementById:node,body:{appendChild(){}},createElement(){return {click(){downloads.push(this.download);},remove(){}};}}});
vm.runInContext(fs.readFileSync('web/science.js','utf8'),context);
const click=id=>node(id).listeners.click();
const input=(id,value)=>{node(id).value=String(value);node(id).listeners.input();};
(async()=>{
  assert.equal(node('preference').textContent,'Inflating pays more');
  assert.match(node('threshold').textContent,/1\/4/);
  assert.doesNotMatch(node('payoff-chart').innerHTML,/NaN|Infinity|undefined/);
  input('budget',2);assert.equal(node('preference').textContent,'Both reports pay equally');
  input('budget',8);click('start');
  assert.equal(node('round').hidden,false);assert.equal(node('outcome').hidden,true);
  assert.equal(node('truth-table').innerHTML,'');
  for(const id of ['budget','penalty','policy','start'])assert(node(id).disabled);
  click('accept');assert.equal(node('outcome').hidden,true); // No verdict before review.
  click('inspect');assert.equal(node('judgment').hidden,false);
  assert.match(node('evidence-cards').innerHTML,/Mismatch/);
  click('return');assert.equal(node('outcome').hidden,false);
  assert.equal(node('ai-score').textContent,'-8');assert.equal(node('human-score').textContent,'0');
  assert.equal(node('outcome-title').textContent,'You returned an inflated report.');
  assert.match(node('truth-table').innerHTML,/altered/);
  click('return');assert.match(node('session-summary').textContent,/1 completed round/); // No duplicate verdict.
  click('export');let data=JSON.parse(await blobs[0].text());
  assert.equal(data.liveModelCalls,false);assert.equal(data.syntheticScenarios,true);
  assert.equal(data.records.length,1);assert.equal(data.records[0].config.budget,8);
  assert.deepEqual(data.records[0].result,game.judge(data.records[0],'return'));
  click('next');assert.equal(node('round').hidden,true);
  input('budget',0);click('start');click('inspect');click('accept');
  assert.equal(node('ai-score').textContent,'+4');assert.equal(node('human-score').textContent,'-6');
  assert.match(node('lesson').textContent,/outside the sample/);
  input('budget',3);node('policy').value='accurate';node('policy').listeners.change();
  click('start');click('inspect');click('return');
  assert.equal(node('outcome-title').textContent,'You returned an accurate report.');
  assert.equal(node('ai-score').textContent,'0');assert.equal(node('human-score').textContent,'-2.75');
  click('export');data=JSON.parse(await blobs[1].text());
  assert.equal(data.records.length,3);
  assert.equal(data.records[0].config.budget,8); // Later changes do not mutate past records.
  assert.equal(data.records[1].config.budget,0);
  assert.equal(data.records[2].config.budget,3);
  for(const record of data.records) {
    const replay=game.makeRound(record.config,record.seed);
    assert.deepEqual(replay.records,record.records);assert.deepEqual(replay.auditIndices,record.auditIndices);
  }
  assert.deepEqual(downloads,['science-audit-practice.json','science-audit-practice.json']);
  input('budget',99);assert.equal(node('error').hidden,false);
  console.log('Science audit: exhaustive subset/payoff checks, replay, scoring, and UI lifecycle passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
