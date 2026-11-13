'use strict';
const el = id => document.getElementById(id);
const keys = ['v', 'r', 'a', 'p', 'b', 'w', 'h', 'c'];
const defaults = {v:4, r:1, a:1, p:3, b:1, w:2, h:6, c:2};
const fmt = n => Number(n.toFixed(4)).toString();
const exact = n => n.exact.includes('/') ? `${n.exact} (≈ ${fmt(n.value)})` : n.exact;
const percent = n => `${fmt(n.value * 100)}%`;
const action = a => a === 'cooperate' ? 'Cooperate' : 'Attack';
const best = actions => actions.length === 2 ? 'Both · exact tie' : action(actions[0]);
let version = 0, timer, state = null, simulation = null, simulationVersion = 0;

function query() {
  return new URLSearchParams({...Object.fromEntries(keys.map(k => [k, el(k).value])),
    d: (Number(el('defense').value) / 10).toFixed(1)});
}

function invalidateSimulation() {
  simulationVersion++;
  simulation = null;
  el('sim-results').hidden = true;
  el('download-json').disabled = el('download-csv').disabled = true;
  el('run').disabled = false;
  el('sim-status').textContent = 'Ready. Run again to use the current settings.';
}

function axes(xmax, ymin, ymax, xlabel, ylabel, height = 310) {
  const w=960, h=height, l=76, r=24, t=30, b=50;
  const x = n => l+n/xmax*(w-l-r), y = n => h-b-(n-ymin)/(ymax-ymin)*(h-b-t);
  let markup = `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${ylabel} by ${xlabel}">`;
  for (let i=0; i<=4; i++) {
    const xv=xmax*i/4, yv=ymin+(ymax-ymin)*i/4;
    markup += `<path d="M${l} ${y(yv)}H${w-r}" stroke="#29414e"/><text x="${l-10}" y="${y(yv)+4}" fill="#a4b7c2" font-size="12" text-anchor="end">${fmt(yv)}</text><text x="${x(xv)}" y="${h-b+23}" fill="#a4b7c2" font-size="12" text-anchor="middle">${fmt(xv)}</text>`;
  }
  if (ymin<=0 && ymax>=0) markup += `<path d="M${l} ${y(0)}H${w-r}" stroke="#637b87"/>`;
  markup += `<text x="${w/2}" y="${h-4}" text-anchor="middle" fill="#a4b7c2" font-size="12">${xlabel}</text><text x="${l}" y="16" fill="#a4b7c2" font-size="12">${ylabel}</text>`;
  return {markup,x,y,w,h,l,r,t,b};
}

function payoffChart(data) {
  const values = data.curve.flatMap(p => [p.ai_c.value,p.ai_a.value,0]);
  const lo=Math.min(...values), hi=Math.max(...values), pad=Math.max((hi-lo)*.15,.5);
  const g=axes(1,lo-pad,hi+pad,'Defense (0 = none, 1 = full)','AI payoff');
  let svg=g.markup;
  for (const [key,color] of [['ai_c','#83dfd2'],['ai_a','#f0a8bb']]) {
    svg += `<path d="${data.curve.map((p,i)=>`${i?'L':'M'}${g.x(p.d.value)} ${g.y(p[key].value)}`).join(' ')}" stroke="${color}" stroke-width="3" fill="none"/>`;
    const current=data.selected[key==='ai_c'?'cooperate':'attack'][1];
    svg += `<circle cx="${g.x(data.d.value)}" cy="${g.y(current.value)}" r="5" fill="${color}"><title>${key==='ai_c'?'Cooperate':'Attack'}: ${exact(current)}</title></circle>`;
  }
  const threshold=data.thresholds.d;
  if (threshold.in_domain) svg += `<path d="M${g.x(threshold.root.value)} ${g.t}V${g.h-g.b}" stroke="#f1cf89" stroke-width="2" stroke-dasharray="5 5"><title>Exact defense threshold: ${threshold.root.exact}</title></path>`;
  svg += `<path d="M${g.x(data.d.value)} ${g.t}V${g.h-g.b}" stroke="#e8eff0" opacity=".7"/><text x="${Math.max(140,Math.min(840,g.x(data.d.value)))}" y="28" fill="#e8eff0" font-size="12" text-anchor="middle">Your defense: ${percent(data.d)}</text></svg>`;
  el('payoff-chart').innerHTML=svg;
}

function phaseChart(data) {
  const m=data.map, l=76, t=25, cw=32, ch=17, w=800, h=435;
  let svg=`<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Calculated best action across resource value and penalty, at defense ${percent(data.d)}">`;
  for (const cell of m.cells) {
    const color=cell.best.length===2?'#f1cf89':cell.best[0]==='cooperate'?'#327c75':'#a85571';
    svg+=`<rect x="${l+cell.i*cw}" y="${t+(20-cell.j)*ch}" width="${cw}" height="${ch}" fill="${color}" stroke="#0c1c26" stroke-width=".5"><title>Resource value ${exact(cell.v)}; penalty ${exact(cell.p)}; ${best(cell.best)}; cooperation advantage ${exact(cell.margin)}</title></rect>`;
  }
  for (let i=0;i<=4;i++) {
    svg+=`<text x="${l+cw/2+i*5*cw}" y="${t+21*ch+22}" text-anchor="middle" fill="#a4b7c2" font-size="12">${fmt(m.vmax.value*i/4)}</text><text x="${l-10}" y="${t+ch/2+(20-i*5)*ch+4}" text-anchor="end" fill="#a4b7c2" font-size="12">${fmt(m.pmax.value*i/4)}</text>`;
  }
  const x=l+cw/2+data.parameters.v.value/m.vmax.value*20*cw;
  const y=t+ch/2+(20-data.parameters.p.value/m.pmax.value*20)*ch;
  svg+=`<circle cx="${x}" cy="${y}" r="7" fill="none" stroke="white" stroke-width="2"><title>Your resource value and penalty</title></circle><text x="${l}" y="14" fill="#a4b7c2" font-size="12">Full-defense penalty (p)</text><text x="${l+10.5*cw}" y="${h-7}" text-anchor="middle" fill="#a4b7c2" font-size="12">Resource value (v)</text></svg>`;
  el('phase-chart').innerHTML=svg;
}

function thresholds(data) {
  const names={d:'Defense d',v:'Resource value v',a:'Attack cost a',p:'Full-defense penalty p'};
  el('thresholds').innerHTML=Object.entries(data.thresholds).map(([key,row])=>{
    let message;
    if (row.root===null) {
      message={always:'Cooperation always pays more.',never:'Attack always pays more.',always_tied:'Both actions tie throughout.'}[row.cooperate_when];
      message+=' No single crossing.';
    } else {
      message=`Tie at <b>${exact(row.root)}</b>. Cooperation pays more ${row.cooperate_when} this value.`;
      if (!row.in_domain) message+=` <span class="gold">Outside ${key==='d'?'0–1':'the nonnegative range'}.</span>`;
    }
    return `<p class="note"><b>${names[key]}</b><br>${message}</p>`;
  }).join('');
  const root=data.thresholds.d.root;
  el('crossing').textContent=root===null ? 'There is no single defense crossing; see the constant comparison below.' :
    `Exact defense crossing: ${exact(root)}${data.thresholds.d.in_domain?'':' (outside 0–1)'}. First available defense where cooperation is at least as good: ${data.first_weak_defense?percent(data.first_weak_defense):'none'}. The curve is continuous; playable defenses are the 11 marked choices of the slider.`;
}

function commitment(rows) {
  return rows.map(row=>`<div class="equilibrium"><b>${percent(row.d)} defense → ${action(row.action)}</b><p>You: ${exact(row.human)} points · AI: ${exact(row.ai)} points</p><button type="button" class="small" data-defense="${row.d.value}">Try this defense</button></div>`).join('');
}

function outcomeTable(rows,data,showPlans) {
  return `<table><thead><tr><th>Defense</th><th>AI action</th><th>Your payoff</th><th>AI payoff</th>${showPlans?'<th>Supporting response plans</th>':''}</tr></thead><tbody>${rows.map(row=>`<tr class="${row.d.exact===data.d.exact?'selected':''}"><td>${percent(row.d)}</td><td>${action(row.action)}</td><td>${exact(row.human)}</td><td>${exact(row.ai)}</td>${showPlans?`<td><details><summary>${row.strategy_count} plan${row.strategy_count===1?'':'s'}</summary><p class="witness">Choose any listed response at each defense. Each combination supports this outcome:<br>${row.responses.map((a,i)=>`${percent(data.equilibria.defenses[i])}: ${a.map(action).join(' or ')}`).join(' · ')}</p></details></td>`:''}</tr>`).join('')}</tbody></table>`;
}

function render(data) {
  el('best').textContent=best(data.selected.best);
  el('margin').textContent=exact(data.selected.margin);
  el('minimum').textContent=data.first_strict_defense?percent(data.first_strict_defense):'None';
  el('selected-payoffs').innerHTML=`<table><thead><tr><th>AI chooses</th><th>You receive</th><th>AI receives</th></tr></thead><tbody>${['cooperate','attack'].map(a=>`<tr><td>${action(a)}</td><td>${exact(data.selected[a][0])}</td><td>${exact(data.selected[a][1])}</td></tr>`).join('')}</tbody></table>`;
  thresholds(data); payoffChart(data); phaseChart(data);
  el('strong').innerHTML=commitment(data.equilibria.stackelberg_favorable);
  el('weak').innerHTML=commitment(data.equilibria.stackelberg_unfavorable);
  el('spne').innerHTML=outcomeTable(data.equilibria.subgame_perfect,data,true);
  el('nash').innerHTML=outcomeTable(data.equilibria.nash,data,true);
  const supported=data.equilibria.subgame_perfect.filter(row=>row.d.exact===data.d.exact);
  el('chosen-equilibrium').textContent=supported.length ?
    `Your ${percent(data.d)} defense occurs in a credible sequential equilibrium with: ${supported.map(row=>action(row.action)).join(' or ')}.` :
    `Your ${percent(data.d)} defense is not an optimal human choice in any pure subgame-perfect equilibrium of this game.`;
}

function load(requestVersion) {
  if (requestVersion!==version) return;
  try {
    const data=GutEngine.oversightState(query());
    if (requestVersion!==version) return;
    state=data; render(data);
    el('live').hidden=false; el('live').setAttribute('aria-busy','false');
    el('error').hidden=true; el('status').textContent='Up to date · exact payoffs and solvers · calculated outcomes, not LLM observations';
  } catch (error) {
    if (requestVersion!==version) return;
    state=null; el('live').hidden=true; el('live').setAttribute('aria-busy','false');
    el('error').textContent=`Could not update: ${error.message}`; el('error').hidden=false;
    el('status').textContent='Results hidden until the settings can be calculated.';
  }
}

function schedule() {
  clearTimeout(timer); const current=++version; state=null;
  el('defense-label').textContent=`${Number(el('defense').value)*10}%`;
  el('live').hidden=true; el('live').setAttribute('aria-busy','true');
  invalidateSimulation();
  if (keys.some(k=>el(k).value==='' || !el(k).checkValidity())) {
    el('error').textContent='Enter a number from 0 to 1000 for every payoff setting.';
    el('error').hidden=false; el('status').textContent='Results hidden: check the payoff settings.';
    el('live').setAttribute('aria-busy','false'); return;
  }
  el('error').hidden=true; el('status').textContent='Calculating…';
  timer=setTimeout(()=>load(current),100);
}

function describeBaseline() {
  el('baseline-description').textContent={always_cooperate:'Always cooperate: chooses cooperation at every defense, even when attacking would pay more.',always_attack:'Always attack: attacks at every defense, even when cooperation would pay more.',payoff_maximizer:'Payoff maximizer: observes defense, compares its exact payoffs, and picks the larger one. The tie selector applies only when they are exactly equal.'}[el('baseline').value];
  el('tie').disabled=el('baseline').value!=='payoff_maximizer';
}

function runSimulation() {
  if (!state) return;
  const current=++simulationVersion, stateVersion=version, params=query();
  for (const k of ['baseline','tie','scope']) params.set(k,el(k).value);
  el('run').disabled=true; el('sim-status').textContent='Running deterministic rounds…';
  el('sim-results').hidden=true; simulation=null;
  el('download-json').disabled=el('download-csv').disabled=true;
  try {
    const data=GutEngine.oversightSimulation(params);
    if (current!==simulationVersion || stateVersion!==version) return;
    simulation=data;
    el('sim-summary').textContent=`${data.summary.rounds} independent round${data.summary.rounds===1?'':'s'} · ${data.summary.cooperate_count} cooperation choices · Average human payoff: ${exact(data.summary.mean_human)} · Average AI payoff: ${exact(data.summary.mean_ai)}.`;
    el('sim-table').innerHTML=`<table><thead><tr><th>Round</th><th>Defense</th><th>AI choice</th><th>Your payoff</th><th>AI payoff</th><th>AI points left behind</th><th>Human harm</th></tr></thead><tbody>${data.records.map(r=>`<tr><td>${r.round}</td><td>${percent(r.d)}</td><td>${action(r.action)}</td><td>${exact(r.human)}</td><td>${exact(r.ai)}</td><td>${exact(r.ai_regret)}</td><td>${exact(r.remaining_harm)}</td></tr>`).join('')}</tbody></table>`;
    simulationChart(data);
    el('sim-results').hidden=false; el('download-json').disabled=el('download-csv').disabled=false;
    el('sim-status').textContent='Complete · artificial baseline results only';
  } catch(error) {
    if (current!==simulationVersion) return;
    el('sim-status').textContent=`Simulation failed: ${error.message}`;
  } finally {
    if (current===simulationVersion) el('run').disabled=false;
  }
}

function simulationChart(data) {
  const values=data.records.flatMap(r=>[r.human.value,r.ai.value,0]);
  const lo=Math.min(...values),hi=Math.max(...values),pad=Math.max(.5,(hi-lo)*.1);
  const g=axes(1,lo-pad,hi+pad,'Defense (d)','Realized points · teal: you; pink: AI',260);
  let svg=g.markup;
  for (const row of data.records) for (const [key,color,offset] of [['human','#83dfd2',-3],['ai','#f0a8bb',3]])
    svg+=`<circle cx="${g.x(row.d.value)+offset}" cy="${g.y(row[key].value)}" r="5" fill="${color}"><title>${key==='human'?'Human':'AI'} payoff ${exact(row[key])}; defense ${percent(row.d)}; ${action(row.action)}</title></circle>`;
  el('sim-chart').innerHTML=svg+'</svg>';
}

function download(type) {
  if (!simulation) return;
  let text=JSON.stringify(simulation,null,2);
  if (type==='csv') {
    const headers=['synthetic','baseline','tie_action',...keys,'round','defense','action','human_payoff','ai_payoff','ai_regret','remaining_harm'];
    const rows=simulation.records.map(r=>['true',simulation.baseline,simulation.tie_action,...keys.map(k=>simulation.parameters[k].exact),r.round,r.d.exact,r.action,r.human.exact,r.ai.exact,r.ai_regret.exact,r.remaining_harm.exact]);
    text=[headers,...rows].map(row=>row.map(v=>`"${String(v).replaceAll('"','""')}"`).join(',')).join('\n')+'\n';
  }
  const url=URL.createObjectURL(new Blob([text],{type:type==='json'?'application/json':'text/csv;charset=utf-8'}));
  const link=document.createElement('a'); link.href=url; link.download=`oversight-toy-${simulation.baseline}.${type}`;
  document.body.appendChild(link); link.click(); link.remove(); setTimeout(()=>URL.revokeObjectURL(url),1000);
}

function activateTab(id,focus=false) {
  for (const name of ['explore','simulation']) {
    el(name).hidden=name!==id; el(`${name}-tab`).setAttribute('aria-selected',String(name===id));
    el(`${name}-tab`).tabIndex=name===id?0:-1;
  }
  if (focus) el(`${id}-tab`).focus();
}
for (const name of ['explore','simulation']) {
  el(`${name}-tab`).addEventListener('click',()=>activateTab(name));
  el(`${name}-tab`).addEventListener('keydown',e=>{
    if (['ArrowLeft','ArrowRight','Home','End'].includes(e.key)) {
      e.preventDefault(); activateTab(e.key==='Home'?'explore':e.key==='End'?'simulation':name==='explore'?'simulation':'explore',true);
    }
  });
}
keys.forEach(k=>el(k).addEventListener('input',schedule));
el('defense').addEventListener('input',schedule);
el('game').addEventListener('change',()=>{if(el('game').value==='resource'){location.href='resource-control.html';return;}if(el('game').value==='off-switch'){location.href='off-switch.html';return;}if(el('game').value==='science'){location.href='science.html';return;}if(el('game').value!=='oversight')location.href=`games.html?game=${encodeURIComponent(el('game').value)}`;});
el('reset').addEventListener('click',()=>{keys.forEach(k=>el(k).value=defaults[k]);el('defense').value=3;schedule();});
el('tie-example').addEventListener('click',()=>{keys.forEach(k=>el(k).value=defaults[k]);el('p').value=0;el('defense').value=5;schedule();});
document.addEventListener('click',e=>{const button=e.target.closest('[data-defense]');if(button){el('defense').value=Math.round(Number(button.dataset.defense)*10);schedule();}});
for (const name of ['baseline','scope','tie']) el(name).addEventListener('change',()=>{invalidateSimulation();describeBaseline();});
el('run').addEventListener('click',runSimulation);
for (const type of ['json','csv']) el(`download-${type}`).addEventListener('click',()=>download(type));
describeBaseline(); schedule();
