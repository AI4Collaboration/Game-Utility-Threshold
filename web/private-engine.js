(function(root, factory) {
  const api = factory(typeof module === 'object' ? require('./game-engine.js') : root.GutEngine);
  if (typeof module === 'object') module.exports = api; else root.PrivateGames = api;
})(typeof globalThis === 'object' ? globalThis : this, function(Gut) {
  'use strict';
  const f = value => { const [n,d='1'] = String(value).split('/'); return new Gut.Fraction(BigInt(n),BigInt(d)); };
  const number = value => f(value).value();
  const types = ['low','high'];
  function game(data, key) {
    if(data.schema!=='gut-private-design1-v1' || !Object.hasOwn(data.games,key)) throw Error('Unknown private game catalogue.');
    return data.games[key];
  }
  function state(data,key,index,information,kind) {
    const g=game(data,key);
    if(!Number.isInteger(index)||index<0||index>=g.config.costs.length||!['revealed','hidden'].includes(information)||!types.includes(kind)) throw Error('Invalid comparison condition.');
    const z=g.config.costs[index];
    const s=g.conditions.find(s=>s.cost===z&&s.information===information&&s.actual_type===kind);
    if(!s) throw Error('Missing exact theory condition.');
    return s;
  }
  function curves(data,key,kind) {
    const g=game(data,key), maximum=number(g.config.costs.at(-1));
    return ['row','column'].map(role=>{
      const s=state(data,key,0,'hidden',kind);
      return {role,maximum,lines:['C','D'].map((against,j)=>({against,start:number(s.gaps[role][j]),end:number(s.gaps[role][j])+maximum}))};
    });
  }
  function randomSource(seed) {
    let s=seed>>>0;
    return denominator=>{
      const n=Number(denominator), limit=4294967296-(4294967296%n);
      if(!Number.isSafeInteger(n)||n<1||n>4294967296) throw Error('Unsupported preview probability.');
      let x;
      do{s=(s+0x6D2B79F5)>>>0;let t=Math.imul(s^(s>>>15),s|1);t^=t+Math.imul(t^(t>>>7),t|61);x=(t^(t>>>14))>>>0;}while(x>=limit);
      return BigInt(x%n);
    };
  }
  function simulatePair(data,key,index,kind,seed,baseline='equilibrium') {
    if(!Number.isInteger(seed)||seed<0||seed>4294967295||!['equilibrium','always_c','always_d','uniform'].includes(baseline)) throw Error('Use a valid behavior and a whole-number seed from 0 to 4294967295.');
    const rounds=['revealed','hidden'].map(info=>{
      const s=state(data,key,index,info,kind), eq=s.equilibria, w=eq.components[0].witness, draw=randomSource(seed);
      const ps=baseline==='equilibrium'?[w.row_c,w.column_c[eq.types.indexOf(kind)]]:
        Array(2).fill({always_c:'1',always_d:'0',uniform:'1/2'}[baseline]);
      const actions=ps.map(p=>{const q=f(p);return draw(q.d)<q.n?0:1;});
      return {information:info,row_action:actions[0]?'D':'C',column_action:actions[1]?'D':'C',
        row_points:s.tables.row[actions[0]][actions[1]],column_points:s.tables.column[actions[1]][actions[0]]};
    });
    return {schema:'gut-private-preview-v1',synthetic:true,game_id:key,config_hash:game(data,key).config_hash,
      actual_type:kind,cost:game(data,key).config.costs[index],seed,baseline,
      selection:'First exact equilibrium component witness; a scripted convention, not an empirical prediction.',rounds};
  }
  return {state,curves,simulatePair,number};
});
