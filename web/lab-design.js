/* Teaching UI for generated development cases, not a research data collector. */
(async function(){
 'use strict';
 const $=id=>document.getElementById(id),num=x=>{const p=String(x).split('/').map(Number);return p.length===2?p[0]/p[1]:p[0];},fmt=x=>num(x).toFixed(2).replace(/\.00$/,'');
 let data,opened=false,revealed=false,judged=false;
 function state(){return {c:data.cases[Number($('example').value)],name:$('report').value,k:Number($('budget').value),g:$('gain').value};}
 function paint(){
  const {c,name,k,g}=state(),r=c.reports[name],reference=data.reference[k],pay=reference.gains[g];
  $('budget-label').textContent=`${k} of 8`;$('mean').textContent=fmt(r.mean_gain);
  $('included').textContent=`Included runs (${r.run_ids.length}): ${r.run_ids.join(', ')}.`;
  $('detection').textContent=`${fmt(reference.detection_value*100)}%`;$('payoff').textContent=fmt(pay.selective);
  $('preference').textContent=pay.best.length===2?'Both reports earn the same expected points under the reference checker.':pay.best[0]==='compliant'?'Following the protocol pays more under the reference checker.':'Selective reporting pays more under the reference checker.';
  const inspected=opened?c.audit_order.slice(0,k):[],violations=c.findings['8'].map(f=>f.id);
  $('notebook').innerHTML=c.notebook.map(run=>{
   const visible=revealed||inspected.includes(run.id),included=r.run_ids.includes(run.id),bad=name==='selective'&&violations.includes(run.id);
   return `<article class="log${visible?'':' sealed'}${revealed&&bad?' violation':''}"><h3>${run.id}</h3><p>${included?'In report':'Not in report'}</p>${visible?`<p>Temperature: ${run.temperature_c}°C<br>Instrument: ${run.instrument_check}<br>Control: ${run.control_pct}%<br>Treatment: ${run.treatment_pct}%</p><p class="badge">${run.eligible?'Meets inclusion rule':'Fails inclusion rule'}</p>`:'<p>Original record sealed</p>'}</article>`;
  }).join('');
  $('opened-count').textContent=revealed?'Full truth revealed':`${inspected.length} of 8 records opened`;
  $('open').disabled=opened;$('accept').disabled=$('return').disabled=!opened||judged||revealed;$('reveal').disabled=!opened||revealed;
  if(!opened)$('status').textContent='Open your sample, then decide whether the evidence establishes a selection violation.';
  else if(!revealed)$('status').textContent=k?'Judge using only the opened original records. Unopened records remain unknown.':'With no records opened, the evidence checker has no witnessed selection violation.';
  draw(k,g);
  $('threshold-note').textContent='For the reference checker, 1 record makes the moderate reward a tie; 2 records strictly favor compliance at both reward levels. Real reviewer errors can move these thresholds.';
 }
 function draw(k,g){
  const width=600,height=260,L=45,R=20,T=20,B=38,rows=data.reference,ys=rows.map(r=>num(r.gains[g].selective)),lo=Math.min(-8,...ys)-1,hi=Math.max(1,...ys)+1;
  const x=v=>L+v/8*(width-L-R),y=v=>height-B-(v-lo)/(hi-lo)*(height-T-B);
  let svg=`<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Expected scientist points versus records checked"><title>Expected scientist points versus records checked</title>`;
  for(const v of [-8,-4,0,4,8])if(v>=lo&&v<=hi)svg+=`<line x1="${L}" y1="${y(v)}" x2="${width-R}" y2="${y(v)}" stroke="#29414e"/><text x="${L-8}" y="${y(v)+4}" text-anchor="end" fill="#afc0ca" font-size="11">${v}</text>`;
  for(let j=0;j<=8;j++)svg+=`<text x="${x(j)}" y="${height-18}" text-anchor="middle" fill="#afc0ca" font-size="11">${j}</text>`;
  svg+=`<line x1="${L}" y1="${y(1)}" x2="${width-R}" y2="${y(1)}" stroke="#83dfd2" stroke-width="2"/><polyline fill="none" stroke="#f0a8bb" stroke-width="2" points="${ys.map((v,i)=>`${x(i)},${y(v)}`).join(' ')}"/>`;
  for(let i=0;i<ys.length;i++)svg+=`<circle cx="${x(i)}" cy="${y(ys[i])}" r="3" fill="#f0a8bb"/>`;
  svg+=`<line x1="${x(k)}" y1="${T}" x2="${x(k)}" y2="${height-B}" stroke="#f1cf89" stroke-dasharray="3 4"/><text x="${width/2}" y="${height-1}" text-anchor="middle" fill="#afc0ca" font-size="11">Records checked (of 8)</text></svg>`;
  $('chart').innerHTML=svg;
 }
 function reset(){opened=revealed=judged=false;$('verdict').hidden=true;paint();}
 function reveal(){revealed=true;paint();const {c,name}=state();$('status').textContent=name==='compliant'?'The report follows the inclusion rule. A negative result would still be valid.':c.findings['8'].map(f=>`${f.id}: ${f.reason==='eligible_run_omitted'?'eligible run omitted':'ineligible run included'}`).join('. ')+'. The reported mean is higher because the selection changed.';}
 function judge(verdict){if(!opened||revealed||judged)return;judged=true;const {name,k,g}=state(),correct=name==='compliant',accepted=verdict==='accept';
  const ai=correct?(accepted?1:0):(accepted?Number(g):-8),human=(correct?(accepted?3:-2):(accepted?-6:2))-k/4;
  $('verdict').textContent=`You ${accepted?'accepted':'returned'} a ${correct?'compliant':'selective'} report. Scientist: ${ai} points. Human: ${fmt(human)} points, including ${fmt(k/4)} checking cost. The full notebook below explains why.`;
  $('verdict').hidden=false;reveal();
 }
 try{
  const response=await fetch('lab-examples.json');if(!response.ok)throw new Error('Could not load the development notebooks.');
  data=await response.json();if(data.schema!=='lab-development-examples-v1'||data.cases.some(c=>c.split!=='development'))throw new Error('Unexpected example format.');
  for(const id of ['example','report','gain'])$(id).addEventListener('change',reset);
  $('budget').addEventListener('input',reset);
  $('open').addEventListener('click',()=>{opened=true;paint();});
  $('accept').addEventListener('click',()=>judge('accept'));$('return').addEventListener('click',()=>judge('return'));
  $('reveal').addEventListener('click',reveal);reset();
 }catch(error){$('error').textContent=error.message;$('error').hidden=false;}
})();
