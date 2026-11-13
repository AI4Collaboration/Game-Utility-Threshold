/* Months 3–5 toy games. Shared browser/Node source; no model or network calls.
 * Decisions, expectations, thresholds and ties use reduced BigInt fractions.
 * See docs/uncertainty-games.md for information sets and conditional guarantees.
 */
(function (root) {
  'use strict';
  const base = typeof module !== 'undefined' && module.exports ? require('./game-engine.js') : root.GutEngine;
  const {Fraction, number, serialize, Oversight} = base;
  const F = (n, d=1) => new Fraction(n,d), Z=F(0), O=F(1);
  const min = (...xs) => xs.reduce((a,b)=>a.cmp(b)<=0?a:b);
  const max = (...xs) => xs.reduce((a,b)=>a.cmp(b)>=0?a:b);
  const sum = xs => xs.reduce((a,b)=>a.add(b),Z);
  const grid = Array.from({length:11},(_,i)=>F(i,10));
  const RESOURCE_DEFAULTS = Object.freeze({vLow:'4',vHigh:'8',r:'1',a:'1',p:'3',b:'1',w:'2',h:'6',c:'2',
    belief:'0.5',truth:'0.5',beliefLow:'0.25',beliefHigh:'0.75',riskLimit:'0.05',d:'0.3'});
  const OFF_DEFAULTS = Object.freeze({gain:'4',loss:'6',belief:'0.5',truth:'0.5',beliefLow:'0.25',beliefHigh:'0.75',
    accuracy:'0.9',actualAccuracy:'0.9',accuracySlack:'0.1',cost:'0'});
  const probabilities = ['belief','truth','beliefLow','beliefHigh','riskLimit','d','accuracy','actualAccuracy','accuracySlack'];
  function config(input, defaults) {
    if (!input || typeof input !== 'object' || Array.isArray(input)) throw new Error('Settings must be an object.');
    for(const key of Object.keys(input)) if(!Object.hasOwn(defaults,key)) throw new Error(`Unknown setting: ${key}`);
    const values = Object.fromEntries(Object.entries({...defaults,...input}).map(([key,value])=>{
      if(!['string','number'].includes(typeof value) || String(value).trim() === '') throw new Error(`Invalid ${key}.`);
      return [key,number(String(value),Z,probabilities.includes(key)?O:F(1000))];
    }));
    if(values.beliefLow.cmp(values.belief)>0 || values.belief.cmp(values.beliefHigh)>0)
      throw new Error('The assumed probability must lie inside its uncertainty interval.');
    return values;
  }
  // Configs retain decimal inputs for replay; reduced fractions are output only.
  const inputConfig = (input, defaults) => Object.fromEntries(Object.entries({...defaults,...input}).map(([k,v])=>[k,String(v)]));
  const mix = (low,high,q) => low.mul(O.sub(q)).add(high.mul(q));
  const bestKeys = payoffs => {const best=max(...Object.values(payoffs));return Object.keys(payoffs).filter(k=>payoffs[k].cmp(best)===0);};
  function resourceModel(input) {
    const p=config(input,RESOURCE_DEFAULTS);
    if(p.vLow.cmp(p.vHigh)>0) throw new Error('Low resource value must not exceed high resource value.');
    if(!grid.some(d=>d.cmp(p.d)===0)) throw new Error('Choose defense 0, 0.1, …, 1.');
    const games=[p.vLow,p.vHigh].map(v=>new Oversight({v,...Object.fromEntries(['r','a','p','b','w','h','c'].map(k=>[k,p[k]]))}));
    function at(d,q,tie='attack',policy='maximizer') {
      const types=games.map((g,i)=>{
        const best=g.best(d), action=policy==='maximizer'?(best.length===1?best[0]:tie):policy;
        const [human,ai]=g.payoff(d,action), attacked=action==='attack';
        return {type:i?'high':'low',value:g.v,best,action,human,ai,margin:g.margin(d),
          harm:attacked?p.h.mul(O.sub(d)):Z,attack:attacked?O:Z,
          regret:max(g.b,g.payoff(d,'attack')[1]).sub(ai)};
      });
      return {d,types,human:mix(types[0].human,types[1].human,q),ai:mix(types[0].ai,types[1].ai,q),
        attack:mix(types[0].attack,types[1].attack,q),harm:mix(types[0].harm,types[1].harm,q),cost:p.c.mul(d),
        margin:min(...types.map(t=>t.margin))};
    }
    // Tie handling for leader optimization is by HUMAN payoff, not action label.
    function leaderAt(d,q,favorable) {
      const rows=games.map((g,i)=>{
        const best=g.best(d), score=(favorable?max:min)(...best.map(a=>g.payoff(d,a)[0]));
        return {type:i?'high':'low',actions:best.filter(a=>g.payoff(d,a)[0].cmp(score)===0),human:score};
      });
      return {d,human:mix(rows[0].human,rows[1].human,q),responses:rows};
    }
    function optimize(q,favorable) {
      const rows=grid.map(d=>leaderAt(d,q,favorable)), score=max(...rows.map(r=>r.human));
      return rows.filter(r=>r.human.cmp(score)===0);
    }
    const curve=grid.map(d=>{
      const ends=[p.beliefLow,p.beliefHigh].map(q=>at(d,q));
      return {...at(d,p.belief),actual:at(d,p.truth),
        worstAttack:max(...ends.map(r=>r.attack)),worstHarm:max(...ends.map(r=>r.harm)),
        worstHuman:min(...ends.map(r=>r.human))};
    });
    const feasible=curve.filter(r=>r.worstAttack.cmp(p.riskLimit)<=0);
    const cautious=feasible.length?feasible.filter(r=>r.cost.cmp(min(...feasible.map(x=>x.cost)))===0):[];
    const firstStrict=grid.find(d=>games.every(g=>g.margin(d).cmp(Z)>0))??null;
    const selected=curve.find(row=>row.d.cmp(p.d)===0);
    const individual=games.map((g,i)=>({type:i?'high':'low',threshold:g.thresholds(p.d).d,
      firstStrict:grid.find(d=>g.margin(d).cmp(Z)>0)??null,
      optimum:optimize(i?O:Z,false)}));
    const knownHuman=mix(individual[0].optimum[0].human,individual[1].optimum[0].human,p.truth);
    const resourceLimit=p.r.mul(O.sub(p.d));
    const headroom=resourceLimit.cmp(Z)>0?p.b.add(p.a).add(p.p.mul(p.d)).div(resourceLimit).sub(p.vHigh):null;
    return {p,games,at,optimize,analysis:{kind:'resource',config:inputConfig(input,RESOURCE_DEFAULTS),selected,curve,individual,
      favorable:optimize(p.belief,true),unfavorable:optimize(p.belief,false),cautious,firstStrict,
      extraDefense:firstStrict===null?null:max(Z,firstStrict.sub(p.d)),valueHeadroom:headroom,
      fullyInformedHuman:knownHuman,truthCovered:p.truth.cmp(p.beliefLow)>=0&&p.truth.cmp(p.beliefHigh)<=0,
      tieRule:'Risk bounds treat indifferent agents as attacking. Both best responses remain in the output.',
      guarantee:'Risk bound is conditional on payoff-maximizing agents, these two types, and the stated probability interval.'}};
  }
  function offModel(input) {
    const p=config(input,OFF_DEFAULTS);
    function payoffs(q,accuracy) {
      const good=q.mul(p.gain),bad=O.sub(q).mul(p.loss);
      return {proceed:good.sub(bad),stop:Z,defer:good.mul(accuracy).sub(bad.mul(O.sub(accuracy))).sub(p.cost)};
    }
    function threshold(q) {
      const good=q.mul(p.gain),bad=O.sub(q).mul(p.loss),denominator=good.add(bad);
      // defer - max(proceed, stop) = slope * accuracy + intercept.
      const intercept=bad.add(p.cost).add(max(good.sub(bad),Z)).neg();
      return {root:denominator.cmp(Z)?intercept.neg().div(denominator):null,slope:denominator,intercept,
        strictPossible:denominator.add(intercept).cmp(Z)>0};
    }
    function outcomes(q,accuracy,action) {
      const good=action==='proceed'?O:action==='stop'?Z:accuracy;
      const bad=action==='proceed'?O:action==='stop'?Z:O.sub(accuracy);
      return {human:payoffs(q,accuracy)[action],harmProbability:O.sub(q).mul(bad),
        harm:O.sub(q).mul(bad).mul(p.loss),blockedBenefitProbability:q.mul(O.sub(good)),
        cost:action==='defer'?p.cost:Z};
    }
    const rewards=payoffs(p.belief,p.accuracy),best=bestKeys(rewards);
    const margin=rewards.defer.sub(max(rewards.proceed,rewards.stop));
    const worstAccuracy=max(Z,p.accuracy.sub(p.accuracySlack));
    const ends=[p.beliefLow,p.beliefHigh],endMargins=ends.map(q=>{
      const u=payoffs(q,worstAccuracy);return u.defer.sub(max(u.proceed,u.stop));
    });
    const thresholdEnds=ends.map(threshold),centralThreshold=threshold(p.belief);
    // The deferral advantage is concave in q, so the interval minimum is at an endpoint.
    const worstMargin=min(...endMargins);
    const roots=thresholdEnds.map(t=>t.root).filter(x=>x!==null);
    const robustThreshold=roots.length===2?max(...roots):null;
    const curve=Array.from({length:21},(_,i)=>{const accuracy=F(i,20),u=payoffs(p.belief,accuracy);
      return {accuracy,...u,margin:u.defer.sub(max(u.proceed,u.stop)),best:bestKeys(u)};});
    return {p,payoffs,outcomes,analysis:{kind:'off-switch',config:inputConfig(input,OFF_DEFAULTS),payoffs:rewards,best,margin,
      threshold:centralThreshold,robustThreshold,thresholdEnds,worstAccuracy,worstMargin,curve,
      accuracyHeadroom:centralThreshold.root===null?null:p.accuracy.sub(centralThreshold.root),
      robustStrictPossible:thresholdEnds.every(t=>t.strictPossible),
      truthCovered:p.truth.cmp(p.beliefLow)>=0&&p.truth.cmp(p.beliefHigh)<=0&&p.actualAccuracy.cmp(worstAccuracy)>=0,
      outcomes:Object.fromEntries(['proceed','stop','defer'].map(action=>[action,outcomes(p.truth,p.actualAccuracy,action)])),
      fullyInformedHuman:p.truth.mul(p.gain),
      guarantee:'Deferral margin assumes a shared human/AI objective and state-dependent human accuracy; it is not a guarantee against an adversarial AI.'}};
  }
  function analyze(kind,input={}) {
    return serialize((kind==='resource'?resourceModel(input):kind==='off-switch'?offModel(input):fail('Unknown game.')).analysis);
  }
  function fail(message){throw new Error(message);}
  function integer(x,low,high,name){if(!Number.isInteger(x)||x<low||x>high)fail(`Invalid ${name}.`);return x;}
  // Mulberry32 generator and rejection sampling of rational probabilities.
  // For repeatable toy runs only, not cryptography or independent empirical data.
  function generator(seed) {
    let state=integer(seed,0,0xffffffff,'seed');
    const word=()=>{
      state=(state+0x6D2B79F5)>>>0;let t=state;
      t=Math.imul(t^(t>>>15),t|1);t^=t+Math.imul(t^(t>>>7),t|61);
      return BigInt((t^(t>>>14))>>>0);
    };
    return probability=>{
      let range=1n,words=0;
      while(range<probability.d){range*=0x100000000n;words++;}
      if(!words)return probability.n===probability.d;
      const ceiling=range-range%probability.d;let draw;
      do {draw=0n;for(let i=0;i<words;i++)draw=draw*0x100000000n+word();}while(draw>=ceiling);
      return draw%probability.d<probability.n;
    };
  }
  function simulationOptions(kind,options={}) {
    const defaults={rounds:200,seed:42,policy:'maximizer',tie:kind==='resource'?'attack':'defer',defensePolicy:'manual'};
    for(const key of Object.keys(options))if(!Object.hasOwn(defaults,key))fail(`Unknown simulation option: ${key}`);
    const o={...defaults,...options};integer(o.rounds,1,10000,'round count');integer(o.seed,0,0xffffffff,'seed');
    if(!(kind==='resource'?['maximizer','cooperate','attack']:['maximizer','proceed','stop','defer']).includes(o.policy))fail('Unknown policy.');
    if(!(kind==='resource'?['cooperate','attack']:['proceed','stop','defer']).includes(o.tie))fail('Unknown tie action.');
    if(!['manual','average','cautious','informed'].includes(o.defensePolicy))fail('Unknown defense policy.');
    if(kind==='off-switch'&&o.defensePolicy!=='manual')fail('Defense policies apply only to resource control.');
    return o;
  }
  function simulate(kind,input={},options={}) {
    const model=kind==='resource'?resourceModel(input):kind==='off-switch'?offModel(input):fail('Unknown game.');
    const o=simulationOptions(kind,options),p=model.p,random=generator(o.seed),records=[];
    let chosenDefense=p.d;
    if(kind==='resource') {
      if(o.defensePolicy==='average')chosenDefense=model.analysis.unfavorable[0].d;
      if(o.defensePolicy==='cautious') {
        if(!model.analysis.cautious.length)fail('No available defense satisfies this risk limit.');
        chosenDefense=model.analysis.cautious[0].d;
      }
    }
    // Choice is computed before the state draw. Only the fully informed reference sees the type.
    const offAction=kind==='off-switch'?(o.policy==='maximizer'?(model.analysis.best.includes(o.tie)?o.tie:model.analysis.best[0]):o.policy):null;
    for(let i=0;i<o.rounds;i++) {
      const highOrGood=random(p.truth);
      if(kind==='resource') {
        const index=highOrGood?1:0,g=model.games[index];
        const d=o.defensePolicy==='informed'?model.analysis.individual[index].optimum[0].d:chosenDefense;
        const best=g.best(d),action=o.policy==='maximizer'?(best.includes(o.tie)?o.tie:best[0]):o.policy;
        const [human,ai]=g.payoff(d,action);
        records.push({round:i+1,type:index?'high':'low',value:g.v,d,action,best,human,ai,cost:p.c.mul(d),
          harm:action==='attack'?p.h.mul(O.sub(d)):Z,unsafe:action==='attack',
          regret:max(...['cooperate','attack'].map(a=>g.payoff(d,a)[1])).sub(ai)});
      } else {
        const correct=random(p.actualAccuracy),wouldAllow=highOrGood?correct:!correct;
        const action=offAction,executed=action==='proceed'||(action==='defer'&&wouldAllow),utility=highOrGood?p.gain:p.loss.neg();
        const cost=action==='defer'?p.cost:Z,score=(executed?utility:Z).sub(cost);
        records.push({round:i+1,state:highOrGood?'beneficial':'harmful',utility,action,best:model.analysis.best,
          humanDecision:action==='defer'?(wouldAllow?'allow':'stop'):null,executed,human:score,ai:score,cost,
          harm:executed&&!highOrGood?p.loss:Z,unsafe:executed&&!highOrGood,
          blockedBenefit:!executed&&highOrGood,
          regret:max(...Object.values(model.analysis.payoffs)).sub(model.analysis.payoffs[action])});
      }
    }
    const count=F(records.length),unsafe=records.filter(r=>r.unsafe).length;
    const summary={rounds:records.length,unsafeCount:unsafe,unsafeRate:F(unsafe,records.length),
      meanHuman:sum(records.map(r=>r.human)).div(count),meanAI:sum(records.map(r=>r.ai)).div(count),
      meanHarm:sum(records.map(r=>r.harm)).div(count),meanCost:sum(records.map(r=>r.cost)).div(count),
      meanRegret:sum(records.map(r=>r.regret)).div(count)};
    if(kind==='off-switch')summary.blockedBenefitCount=records.filter(r=>r.blockedBenefit).length;
    return serialize({schema:'gut-uncertainty-toy-v1',kind,synthetic:true,liveModelCalls:false,
      generator:'mulberry32-rational-rejection-v1',config:model.analysis.config,options:o,summary,records,
      description:'Independent toy rounds under fixed rules. Frequencies are simulation output, not observed LLM or human behavior.'});
  }
  const engine=Object.freeze({RESOURCE_DEFAULTS,OFF_DEFAULTS,analyze,simulate});
  root.UncertaintyGames=engine;
  if(typeof module!=='undefined'&&module.exports)module.exports=engine;
})(globalThis);
