/* Exact browser implementation of the two-target audit subcase.
 * Uses the existing BigInt fraction library. Python agreement is tested.
 * Source rules: Blocki et al. 2013 §2; private types are our explicit extension.
 */
(function(root){
'use strict';
const E=root.GutEngine||(typeof require==='function'?require('./game-engine.js'):null);
const F=E.Fraction, f=x=>x instanceof F?x:String(x).includes('/')?new F(...String(x).split('/')):E.number(String(x),new F(-10000),new F(10000));
const Z=f(0),O=f(1),max=xs=>xs.reduce((a,b)=>a.cmp(b)>0?a:b),min=xs=>xs.reduce((a,b)=>a.cmp(b)<0?a:b);
const sum=xs=>xs.reduce((a,b)=>a.add(b),Z),val=(l,q)=>l[0].add(l[1].mul(q));
const sorted=xs=>[...new Map(xs.map(x=>[x.toString(),x])).values()].sort((a,b)=>a.cmp(b));
const ACTIONS=['abstain','target_a','target_b'];
function crossings(lines){
 const points=[Z,O];
 for(let i=0;i<lines.length;i++)for(let j=0;j<i;j++){
  const s=lines[i][1].sub(lines[j][1]);if(!s.n)continue;
  const q=lines[j][0].sub(lines[i][0]).div(s);if(q.cmp(Z)>=0&&q.cmp(O)<=0)points.push(q);
 }return sorted(points);
}
class Audit {
 constructor(setting='hidden',punishment='0.5',spread='0.3'){
  this.x=f(punishment);this.spread=f(spread);
  if(!['known','hidden'].includes(setting)||this.x.cmp(Z)<0||this.x.cmp(O)>0||this.spread.cmp(Z)<0||this.spread.cmp(f('.35'))>0)throw Error('Invalid audit parameters.');
  this.types=(setting==='known'?[['known',Z,O]]:[['low',this.spread.neg(),f('.5')],['high',this.spread,f('.5')]]).map(([name,offset,prior])=>({name,prior,u:[f('.5').add(offset),f('.4').add(offset)],c:[f('-.5'),f('-.6')]}));
  this.cost=f('.1').mul(this.x);
 }
 lines(kind,player='follower'){
  if(player==='leader')return [[this.cost.neg(),Z],[f(-1).sub(this.cost),f('.9')],[f('-.2').sub(this.cost),f(-1)]];
  const t=this.types[kind];return [[Z,Z],[t.u[0],t.c[0].sub(this.x).sub(t.u[0])],[t.c[1].sub(this.x),t.u[1].sub(t.c[1]).add(this.x)]];
 }
 evaluate(q){
  q=f(q);if(q.cmp(Z)<0||q.cmp(O)>0)throw Error('Probability must be in [0,1].');
  const types=this.types.map((t,k)=>{
   const follower=this.lines(k).map(l=>val(l,q)),leader=this.lines(k,'leader').map(l=>val(l,q));
   const best=follower.flatMap((p,a)=>p.cmp(max(follower))===0?[a]:[]);
   return {name:t.name,prior:t.prior,follower,leader,best_responses:best.map(a=>ACTIONS[a]),margin:max(follower.slice(1)).neg(),favorable:max(best.map(a=>leader[a])),unfavorable:min(best.map(a=>leader[a]))};
  });
  return {q,types,worst_margin:min(types.map(t=>t.margin)),favorable:sum(types.map(t=>t.prior.mul(t.favorable))),unfavorable:sum(types.map(t=>t.prior.mul(t.unfavorable))),attack_probability:{lower:sum(types.filter(t=>!t.best_responses.includes('abstain')).map(t=>t.prior)),upper:sum(types.filter(t=>t.best_responses.some(a=>a!=='abstain')).map(t=>t.prior))}};
 }
 solve(){
  const points=sorted(this.types.flatMap((t,k)=>[...crossings(this.lines(k)),...crossings(this.lines(k,'leader'))]));
  const evaluated=points.map(q=>this.evaluate(q)),limits={favorable:[],unfavorable:[]};
  for(let i=1;i<points.length;i++){
   const low=points[i-1],high=points[i],mid=low.add(high).div(f(2)),row=this.evaluate(mid);evaluated.push(row);
   for(const tie of Object.keys(limits)){
    let b=Z,s=Z;
    row.types.forEach((t,k)=>{
     const lines=this.lines(k,'leader'),choice=t.best_responses.map(a=>ACTIONS.indexOf(a)).find(a=>val(lines[a],mid).cmp(t[tie])===0);
     b=b.add(t.prior.mul(lines[choice][0]));s=s.add(t.prior.mul(lines[choice][1]));
    });
    limits[tie].push({q:low,side:'right',value:b.add(s.mul(low))},{q:high,side:'left',value:b.add(s.mul(high))});
   }
  }
  const result={breakpoints:points};
  for(const tie of Object.keys(limits)){
   const best=max([...evaluated.map(r=>r[tie]),...limits[tie].map(r=>r.value)]),witnesses=sorted(evaluated.filter(r=>r[tie].cmp(best)===0).map(r=>r.q));
   result[tie]={value:best,attained:!!witnesses.length,witnesses,limits:limits[tie].filter(r=>r.value.cmp(best)===0)};
  }return result;
 }
 safeRegion(slack=0){
  slack=f(slack);if(slack.cmp(Z)<0)throw Error('Slack must be nonnegative.');let low=Z,high=O;
  for(let k=0;k<this.types.length;k++)for(const [b,s] of this.lines(k).slice(1)){
   if(!s.n){if(b.cmp(slack.neg())>0)return {feasible:false,slack,interval:null};}
   else {const bound=slack.neg().sub(b).div(s);if(s.cmp(Z)>0)high=min([high,bound]);else low=max([low,bound]);}
  }return {feasible:low.cmp(high)<=0,slack,interval:low.cmp(high)<=0?[low,high]:null};
 }
 safetyOptimum(){
  const lines=this.types.flatMap((t,k)=>this.lines(k).slice(1)),points=crossings(lines),scores=points.map(q=>max(lines.map(l=>val(l,q))).neg()),best=max(scores);
  return {margin:best,witnesses:points.filter((q,i)=>scores[i].cmp(best)===0),strict_deterrence_feasible:best.cmp(Z)>0};
 }
 thresholds(){return this.types.flatMap(t=>t.u.map((u,i)=>{const q=u.div(u.sub(t.c[i]).add(this.x));return {type:t.name,target:ACTIONS[i+1],checking_probability:q,in_domain:q.cmp(Z)>=0&&q.cmp(O)<=0};}));}
 state(q){return E.serialize({selected:this.evaluate(q),solution:this.solve(),safe_region:this.safeRegion(),safety_optimum:this.safetyOptimum(),thresholds:this.thresholds()});}
}
root.AuditEngine={Audit,ACTIONS,f};if(typeof module!=='undefined')module.exports=root.AuditEngine;
})(globalThis);
