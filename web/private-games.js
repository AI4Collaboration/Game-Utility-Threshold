'use strict';
(() => {
 const $=id=>document.getElementById('private-'+id), E=PrivateGames, fmt=v=>Number(v.toFixed(4)).toString();
 let data, selected, preview;
 const percent=v=>fmt(E.number(v)*100)+'%';
 const interval=(values,open=false)=>values[0]===values[1]?percent(values[0]):`${open?'(':'['}${percent(values[0])}, ${percent(values[1])}${open?')':']'}`;
 function clearRound(){preview=null;$('download').disabled=true;$('outcome').textContent='Ready for a fresh matched preview.';}
 function table(matrix,title){return `<div><h3>${title}</h3><table><thead><tr><th>Your / other</th><th>C</th><th>D</th></tr></thead><tbody>${matrix.map((row,i)=>`<tr><th>${i?'D':'C'}</th>${row.map(v=>`<td>${v}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;}
 function chart(curve,z){
  const w=460,h=260,l=54,r=18,t=20,b=45,vals=curve.lines.flatMap(s=>[s.start,s.end]),lo=Math.min(0,...vals)-.15,hi=Math.max(0,...vals)+.15;
  const x=v=>l+v/curve.maximum*(w-l-r),y=v=>h-b-(v-lo)/(hi-lo)*(h-b-t);
  let svg=`<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${curve.role}: C minus D points versus intervention cost"><title>${curve.role}: C minus D points</title>`;
  for(let i=0;i<5;i++){const v=lo+(hi-lo)*i/4;svg+=`<path d="M${l} ${y(v)}H${w-r}" stroke="var(--line)"/><text x="${l-7}" y="${y(v)+4}" text-anchor="end" fill="var(--muted)" font-size="12">${fmt(v)}</text><text x="${x(curve.maximum*i/4)}" y="${h-b+22}" text-anchor="middle" fill="var(--muted)" font-size="12">${fmt(curve.maximum*i/4)}</text>`;}
  svg+=`<path d="M${l} ${y(0)}H${w-r}" stroke="var(--muted)"/>`;
  curve.lines.forEach((s,i)=>{svg+=`<path d="M${x(0)} ${y(s.start)}L${x(curve.maximum)} ${y(s.end)}" fill="none" stroke="var(--${i?'rose':'mint'})" stroke-width="3" stroke-dasharray="${i?'7 4':'none'}"/>`;});
  svg+=`<path d="M${x(z)} ${t}V${h-b}" stroke="var(--text)" opacity=".6"/><text x="${w/2}" y="${h-3}" text-anchor="middle" fill="var(--muted)" font-size="12">Cost of D (points)</text></svg>`;
  return `<div><h3>${curve.role==='row'?'Row · public rewards':'Column · selected private profile'}</h3>${svg}</div>`;
 }
 function render(){
  try{
   const key=$('game').value,g=data.games[key],index=Number($('cost').value),info=$('information').value,kind=$('type').value;
   selected=E.state(data,key,index,info,kind);
   $('cost-value').textContent=fmt(E.number(selected.cost))+' points';$('parameter').textContent=g.config.private_parameter;
   $('id').textContent='Independent game ID: '+key;
   $('knowledge').textContent=info==='hidden'?'Row sees its own table plus both possible column tables and their 50/50 probabilities. Its input is identical for the low and high actual profiles.':`Row sees its own table and is told that column has the ${kind} profile. The underlying tables and cost are unchanged.`;
   $('tables').innerHTML=table(selected.tables.row,'Row points')+table(selected.tables.column,`Column points · ${kind}`);
   $('bounds').innerHTML=['row','column'].map(role=>{const t=selected.thresholds[role];return `<p><b>${role==='row'?'Row':'Column'}:</b> C strictly pays more against either action above cost <b>${t.c_strict_above}</b>. D strictly pays more against either action below <b>${t.d_strict_below}</b>${E.number(t.d_strict_below)<=0?' (no such nonnegative-cost region)':''}.</p>`;}).join('');
   const gaps=selected.gaps.row.map(E.number);
   $('verdict').textContent=gaps.every(v=>v>0)?'For row, C pays more against either action.':gaps.every(v=>v<0)?'For row, D pays more against either action.':gaps.includes(0)?'Row is exactly at a conditional threshold.':'Row’s better choice depends on the opponent.';
   $('charts').innerHTML=E.curves(data,key,kind).map(c=>chart(c,E.number(selected.cost))).join('');
   const eq=selected.equilibria,components=eq.components;
   const low=Math.min(...components.map(c=>E.number(c.row_c[0]))),high=Math.max(...components.map(c=>E.number(c.row_c[1])));
   $('equilibrium').textContent=`${info==='hidden'?'Hidden-information':'Revealed-profile'} calculation: row's equilibrium chance of C ranges from ${fmt(low*100)}% to ${fmt(high*100)}% across the solution set. This is an envelope; it need not include every intermediate policy. The exact regions below retain all mixed policies and boundaries.`;
   $('regions').innerHTML=`<table><thead><tr><th>Row: chance of C</th>${eq.types.map(k=>`<th>Column ${k}: chance of C</th>`).join('')}<th>Mean column C constraint</th></tr></thead><tbody>${components.map(c=>`<tr><td>${interval(c.row_c,c.row_open_ends)}</td>${c.column_c.map(v=>`<td>${interval(v)}</td>`).join('')}<td>${interval(c.mean_column_c)}</td></tr>`).join('')}</tbody></table>`;
   $('error').hidden=true;$('play').disabled=false;clearRound();
  }catch(error){$('error').textContent=error.message+' Previous results are stale.';$('error').hidden=false;$('play').disabled=true;$('download').disabled=true;}
 }
 ['information','type','cost'].forEach(id=>$(id).addEventListener(id==='cost'?'input':'change',render));
 $('game').addEventListener('change',()=>{if(!data.games[$('game').value])return;$('cost').max=data.games[$('game').value].config.costs.length-1;$('cost').value=0;render();});
 ['seed','baseline'].forEach(id=>$(id).addEventListener('input',clearRound));
 $('play').addEventListener('click',()=>{
  try{if($('seed').value==='')throw Error('Enter a replay seed.');preview=E.simulatePair(data,$('game').value,Number($('cost').value),$('type').value,Number($('seed').value),$('baseline').value);
   $('outcome').innerHTML=`<table><thead><tr><th>Information</th><th>Row chooses / earns</th><th>Column chooses / earns</th></tr></thead><tbody>${preview.rounds.map(r=>`<tr><td>${r.information}</td><td>${r.row_action} / ${r.row_points}</td><td>${r.column_action} / ${r.column_points}</td></tr>`).join('')}</tbody></table>`;
   $('download').disabled=false;
  }catch(error){clearRound();$('outcome').textContent=error.message;}
 });
 $('download').addEventListener('click',()=>{if(!preview)return;const url=URL.createObjectURL(new Blob([JSON.stringify(preview,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='private-game-synthetic-pair.json';a.click();URL.revokeObjectURL(url);});
 fetch('private-games.json').then(r=>{if(!r.ok)throw Error('Could not load exact theory.');return r.json();}).then(value=>{
  data=value;for(const id of ['game','information','type','cost','baseline','seed'])$(id).disabled=false;render();
 }).catch(error=>{$('error').textContent=error.message;$('error').hidden=false;$('verdict').textContent='Exact predictions unavailable.';});
})();
