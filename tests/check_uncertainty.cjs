/* Independent finite-outcome enumeration, exact boundaries, missing-information
 * checks and deterministic replay. Browser and CLI use this very same engine. */
'use strict';
const assert=require('node:assert/strict'),game=require('../web/uncertainty-engine.js');
const near=(a,b)=>assert(Math.abs(a-b)<1e-9,`${a} != ${b}`);
let r=game.analyze('resource');
assert.equal(r.individual[0].threshold.root.exact,'2/7');
assert.equal(r.individual[1].threshold.root.exact,'6/11');
assert.equal(r.individual[0].firstStrict.exact,'3/10');
assert.equal(r.firstStrict.exact,'3/5');
assert.equal(r.extraDefense.exact,'3/10');
assert.equal(r.selected.margin.exact,'-27/10');
assert.equal(r.selected.worstAttack.exact,'3/4');
assert.equal(r.cautious[0].d.exact,'3/5');
assert.equal(r.valueHeadroom.exact,'-27/7');
// Enumerate actions, types, defense grid and prior independently, in integer tenths.
let cases=0;
for(const low of [0,2,4])for(const high of [4,8])for(const cost of [0,2,20])for(const prior of [0,.5,1]){
  const p={vLow:low,vHigh:high,c:cost,belief:prior,truth:prior,beliefLow:0,beliefHigh:1};
  r=game.analyze('resource',p);
  let maximum=-Infinity,optimal=[];
  for(let k=0;k<=10;k++){
    const d=k/10,rows=[low,high].map(v=>{
      const attack10=v*(10-k)-10-3*k,action=attack10>=10?'attack':'cooperate';
      return {action,human:action==='attack'?-6*(1-d)-cost*d:2-cost*d,ai:action==='attack'?attack10/10:1};
    });
    const human=(1-prior)*rows[0].human+prior*rows[1].human;
    const row=r.curve[k];near(row.human.value,human);
    near(row.ai.value,(1-prior)*rows[0].ai+prior*rows[1].ai);
    near(row.worstAttack.value,rows.some(x=>x.action==='attack')?1:0);
    for(let i=0;i<2;i++)assert.equal(row.types[i].action,rows[i].action);
    if(human>maximum+1e-9){maximum=human;optimal=[d];}else if(Math.abs(human-maximum)<1e-9)optimal.push(d);
  }
  assert.deepEqual(r.unfavorable.map(x=>x.d.value),optimal);
  near(r.unfavorable[0].human.value,maximum);cases++;
}
// Exact ties are sets, with pessimistic risk bounds, not silently cooperative.
r=game.analyze('resource',{vLow:4,vHigh:4,p:0,d:.5});
assert.deepEqual(r.selected.types[0].best,['cooperate','attack']);
assert.equal(r.selected.worstAttack.exact,'1');
assert.equal(r.firstStrict.exact,'3/5');
r=game.analyze('resource',{vLow:0,vHigh:0,a:0,b:0,p:0,r:0,riskLimit:0});
assert.equal(r.firstStrict,null);assert.deepEqual(r.cautious,[]);
assert.equal(r.extraDefense,null);assert.equal(r.valueHeadroom,null);
r=game.analyze('resource',{truth:1});assert.equal(r.truthCovered,false);
// A collapsed type distribution recovers the deterministic leader solution.
const base=require('../web/game-engine.js');
for(const v of [0,4,8]){
 const single=game.analyze('resource',{vLow:v,vHigh:v});
 const old=base.oversightState({v,r:1,a:1,p:3,b:1,w:2,h:6,c:2,d:.3});
 assert.deepEqual(single.unfavorable.map(x=>x.d),old.equilibria.stackelberg_unfavorable.map(x=>x.d));
}
// Reality is used for evaluation, not leaked into the agent/overseer's decision.
{
 const kind='resource';
 const first=game.analyze(kind,{truth:0}),second=game.analyze(kind,{truth:1});
 assert.deepEqual(first.unfavorable,second.unfavorable);
 const sim=game.simulate(kind,{}, {rounds:50,seed:0});
 assert.deepEqual(sim,game.simulate(kind,{}, {rounds:50,seed:0}));
 assert.deepEqual(sim,JSON.parse(JSON.stringify(sim)));
 assert(sim.synthetic);assert.equal(sim.liveModelCalls,false);
 assert.equal(sim.records.length,50);near(sim.summary.meanHuman.value,sim.records.reduce((s,r)=>s+r.human.value,0)/50);
 assert.equal(sim.summary.unsafeCount,sim.records.filter(r=>r.unsafe).length);
 for(const record of sim.records)assert.equal(record.regret.exact,'0');
}
for(const policy of ['maximizer','cooperate','attack'])for(const defensePolicy of ['manual','average','cautious','informed']){
 const sim=game.simulate('resource',{}, {rounds:20,policy,defensePolicy});
 for(const row of sim.records){if(policy!=='maximizer')assert.equal(row.action,policy);if(defensePolicy==='cautious'&&policy==='maximizer')assert.equal(row.action,'cooperate');}
}
for(const [kind,changes] of [['resource',{vLow:9,vHigh:2}],['resource',{d:.35}],['resource',{r:-1}],['resource',{truth:NaN}],
 ['resource',{beliefLow:.8}],['resource',{belief:1.1}],['resource',{a:Infinity}],['resource',{vLow:null}],['resource',{typo:2}]])
 assert.throws(()=>game.analyze(kind,changes));
for(const options of [{rounds:0},{rounds:10001},{seed:-1},{seed:.5},{policy:'unknown'},{tie:'unknown'},{extra:true}])
 assert.throws(()=>game.simulate('resource',{},options));
assert.throws(()=>game.simulate('resource',{vLow:0,vHigh:0,a:0,b:0,p:0,riskLimit:0},{defensePolicy:'cautious'}));
assert.throws(()=>game.analyze('wrong'));
console.log(`Resource control: ${cases} enumerated cases, interval bounds, exact ties, information boundaries and replay passed.`);
const benchmark=require('../uncertainty-experiment.cjs');
assert.equal(benchmark.run('resource',{simulation:{rounds:2}}).runs.length,12);
assert.throws(()=>benchmark.run('off-switch',{simulation:{rounds:2}}));
assert.throws(()=>game.analyze('off-switch'));
assert.throws(()=>game.simulate('off-switch'));
assert.equal(benchmark.run('resource',{config:{vLow:0,vHigh:0,a:0,b:0,p:0,riskLimit:0},simulation:{rounds:2}}).unavailable.length,3);
assert.throws(()=>benchmark.run('resource',{simulation:{policy:'attack'}}));
console.log('Resource-only offline benchmark passed.');

// A meaningful prior-uncertainty slice crosses the risk limit, not the AI's
// within-type preference. The high type alone attacks at 30% protection.
for(const upper of [.025,.05,.075]){
 const state=game.analyze('resource',{belief:.025,beliefLow:0,beliefHigh:upper,riskLimit:.05});
 assert.equal(state.selected.types[0].action,'cooperate');
 assert.equal(state.selected.types[1].action,'attack');
 near(state.selected.worstAttack.value,upper);
 assert.equal(state.cautious[0].d.exact,upper<=.05?'3/10':'3/5');
}
console.log('Prior-risk boundary changes protection without changing type-conditioned choices.');
