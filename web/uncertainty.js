/* Resource-control UI. Exact calculations and synthetic trials only. */
(function(){
  'use strict';
  const $=id=>document.getElementById(id),kind='resource';
  const E=UncertaintyGames,defaults=E.RESOURCE_DEFAULTS;
  const names={cooperate:'Cooperate',attack:'Attack'};
  const colors=['#83dfd2','#f0a8bb','#f1cf89'];
  let current=null,saved=null;
  const fmt=x=>Number(x?.value??x).toLocaleString('en-US',{maximumFractionDigits:3});
  const exact=x=>x===null?'No finite crossing':`${fmt(x)}${x.exact.includes('/')?` (${x.exact})`:''}`;
  const percent=x=>`${fmt((x?.value??x)*100)}%`;
  const actions=xs=>xs.map(x=>names[x]).join(' / ');
  const fields=[];
  function field(key,label,{range=false,max=1000,step=.1,note=''}={}){
    fields.push(key);
    return `<div${range?' class="full"':''}><label for="field-${key}">${label}${range?` <output id="value-${key}" for="field-${key}"></output>`:''}</label><input id="field-${key}" type="${range?'range':'number'}" min="0" max="${max}" step="${step}" value="${defaults[key]}">${note?`<p class="note">${note}</p>`:''}</div>`;
  }
  const probability=(key,label)=>field(key,label,{max:1,step:.05});
  const group=(title,description,content)=>`<details class="control-group"><summary>${title}</summary><p>${description}</p><div class="fields">${content}</div></details>`;
  const interval=probability('beliefLow','Lowest plausible probability')+probability('beliefHigh','Highest plausible probability');
    $('controls-title').textContent='How much will you protect?';
    $('controls').innerHTML=`<div class="fields">${field('d','Your defense',{range:true,max:1,step:.1})}${field('vLow','Low type: value per resource')}${field('vHigh','High type: value per resource')}${field('belief','Assumed chance of high type',{range:true,max:1,step:.05})}</div>`+
      group('Uncertainty and cautious protection','The interval describes the human’s uncertainty about the proportion of high-value agents. The risk limit concerns attack choices, not residual harm.',interval+probability('riskLimit','Maximum allowed attack probability'))+
      group('Other payoff settings','The same payoff rules as the original oversight game. Change one quantity at a time.',
        [['r','Resources available'],['a','Fixed attack cost'],['p','Penalty at full defense'],['b','AI cooperation reward'],['w','Human cooperation benefit'],['h','Harm without defense'],['c','Cost of full defense']].map(([k,l])=>field(k,l)).join(''))+
      group('Evaluator’s true population','Used to draw trial types and evaluate outcomes. The human’s protection solver cannot use this value.',probability('truth','Actual chance of high type'));
    $('policy').innerHTML='<option value="maximizer">Maximize own payoff</option><option value="cooperate">Always cooperate</option><option value="attack">Always attack</option>';
    $('tie').innerHTML='<option value="attack">Attack</option><option value="cooperate">Cooperate</option>';
    $('methods').innerHTML='<p><strong>The human moves first.</strong> Nature assigns a private resource value to the AI. The human sees the possible values and their probabilities; the AI sees its own type and the committed defense. The analyst sees the whole record.</p><p class="math">AI cooperation = b<br>AI attack = v × r × (1 − d) − a − p × d<br>Human, if cooperation = w − c × d<br>Human, if attack = −h × (1 − d) − c × d</p><p>The two AI types differ only in v. Defense protects resources and reduces harm deterministically; it is not a chance of detection. Attack probability and harm are different: an always-attacking agent at full defense causes no harm under these rules.</p><p>The best-average solver is a finite, pure-commitment Bayesian Stackelberg calculation. It reports both favorable and unfavorable human-payoff ties. Cautious protection minimizes defense cost subject to a worst-case attack limit over the stated probability interval, counting AI ties as attacks. It assumes payoff maximization; the always-attack baseline need not obey its bound. This does not enumerate all Bayesian Nash equilibria.</p>';
  $('game').value=kind;
  $('game').addEventListener('change',()=>{location.href={'resource':'resource-control.html','oversight':'oversight.html','lab':'lab-design.html','games':'games.html'}[$('game').value];});
  const read=()=>Object.fromEntries(fields.map(k=>[k,$(`field-${k}`).value]));
  const table=(headers,rows)=>`<div class="table-scroll"><table><thead><tr>${headers.map(h=>`<th scope="col">${h}</th>`).join('')}</tr></thead><tbody>${rows.map(row=>`<tr>${row.map(c=>`<td>${c}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  const metric=(label,value,note,warn=false)=>`<div class="metric${warn?' warn':''}"><span>${label}</span><strong>${value}</strong><p>${note}</p></div>`;
  function chart(target,legend,series,{label,selected=null,root=null,unit='percent',dots=false}={}){
    const w=660,h=275,left=56,right=20,top=24,bottom=44,x0=0,x1=1;
    const values=series.flatMap(s=>s.points.map(p=>p[1]));
    let ymin=Math.min(0,...values),ymax=Math.max(0,...values),pad=Math.max(.08,(ymax-ymin)*.12);ymin-=pad;ymax+=pad;
    const x=v=>left+(v-x0)/(x1-x0)*(w-left-right),y=v=>h-bottom-(v-ymin)/(ymax-ymin)*(h-top-bottom);
    let svg=`<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${label}"><title>${label}</title>`;
    for(let i=0;i<5;i++){const v=ymin+(ymax-ymin)*i/4;svg+=`<line x1="${left}" y1="${y(v)}" x2="${w-right}" y2="${y(v)}" stroke="#29414e"/><text x="${left-8}" y="${y(v)+4}" text-anchor="end" fill="#afc0ca" font-size="11">${fmt(v)}</text>`;}
    for(let i=0;i<=4;i++){const v=i/4;svg+=`<text x="${x(v)}" y="${h-bottom+20}" text-anchor="middle" fill="#afc0ca" font-size="11">${unit==='percent'?percent(v):fmt(v)}</text>`;}
    svg+=`<line x1="${left}" y1="${y(0)}" x2="${w-right}" y2="${y(0)}" stroke="#718692" stroke-dasharray="4 4"/>`;
    for(const [i,s] of series.entries()){
      const color=colors[i%colors.length];
      if(!dots)svg+=`<polyline fill="none" stroke="${color}" stroke-width="2.5" points="${s.points.map(([a,b])=>`${x(a)},${y(b)}`).join(' ')}"/>`;
      else for(const [a,b] of s.points)svg+=`<circle cx="${x(a)}" cy="${y(b)}" r="${4+i}" fill="${color}" fill-opacity="${i?'.55':'1'}"/>`;
    }
    for(const [v,color,caption] of [[root,'#f1cf89','tie'],[selected,'#e8eff0','selected']])if(v!==null&&v>=0&&v<=1){svg+=`<line x1="${x(v)}" y1="${top}" x2="${x(v)}" y2="${h-bottom}" stroke="${color}" stroke-dasharray="3 5"/><text x="${Math.max(left+25,Math.min(w-right-25,x(v)))}" y="${top-7}" text-anchor="middle" fill="${color}" font-size="10">${caption}</text>`;}
    svg+=`<text x="${(w+left)/2}" y="${h-4}" text-anchor="middle" fill="#afc0ca" font-size="11">${label}</text></svg>`;
    $(target).innerHTML=svg;$(legend).innerHTML=series.map((s,i)=>`<span><i style="color:${colors[i%colors.length]}"></i>${s.name}</span>`).join('');
  }
  function resourceView(a){
    const row=a.selected;
    $('prediction-title').textContent=`At ${percent(row.d)} defense`;
    $('metrics').innerHTML=row.types.map(t=>metric(`${t.type==='low'?'Low':'High'} resource value: ${fmt(t.value)}`,actions(t.best),`Cooperation advantage: ${exact(t.margin)} points.`,t.margin.value<=0)).join('');
    $('decision-note').textContent='A positive advantage means cooperation pays more. Zero means both choices pay equally.';
    $('payoff-table').innerHTML=table(['Quantity','Under your assumed population','Under the actual population'],[
      ['Attack probability',percent(row.attack),percent(row.actual.attack)],['Human expected payoff',exact(row.human),exact(row.actual.human)],
      ['Expected harm',exact(row.harm),exact(row.actual.harm)],['Protection cost',exact(row.cost),exact(row.cost)]]);
    $('coverage-note').textContent=`${a.truthCovered?'Actual population lies inside the stated probability interval.':'Actual population is OUTSIDE the stated interval; its risk bound does not cover this case.'} Predictions assume payoff maximization and attack at exact ties.`;
    $('chart-title').textContent='What pays the AI more?';
    chart('payoff-chart','payoff-legend',[
      {name:'Cooperate · either type',points:a.curve.map(r=>[r.d.value,Number(a.config.b)])},
      ...[0,1].map(i=>({name:`Attack · ${i?'high':'low'} value`,points:a.curve.map(r=>[r.d.value,Number(a.config.b)-r.types[i].margin.value])}))
    ],{label:'Defense level',selected:row.d.value});
    $('chart-caption').textContent='Vertical axis: AI payoff points. Crossing the cooperation line is a tie. Only 0%, 10%, …, 100% defense can be chosen.';
    $('comparison-title').textContent='Choose for the average—or the uncertainty?';
    const ds=xs=>xs.map(x=>percent(x.d)).join(', '),button=(id,list)=>list.length?`<button type="button" id="${id}" data-defense="${list[0].d.value}">Use ${percent(list[0].d)}</button>`:'';
    $('comparisons').innerHTML=`<div class="strategy"><h3>Best average outcome</h3><p>Unfavorable human-payoff ties: ${ds(a.unfavorable)}. Favorable ties: ${ds(a.favorable)}. Both optimize using your assumed population.</p>${button('use-average',a.unfavorable)}</div>`+
      `<div class="strategy"><h3>Cautious protection</h3><p>${a.cautious.length?`Cheapest defenses meeting your ${percent(Number(a.config.riskLimit))} worst-case attack limit: ${ds(a.cautious)}.`:'No available defense meets your chosen attack-risk limit.'}</p>${button('use-cautious',a.cautious)}</div>`+
      table(['Safety quantity','At these settings'],[
        ['Low-type exact defense tie',a.individual[0].threshold.root?`${percent(a.individual[0].threshold.root)} (d = ${a.individual[0].threshold.root.exact})`:'No finite crossing'],
        ['High-type exact defense tie',a.individual[1].threshold.root?`${percent(a.individual[1].threshold.root)} (d = ${a.individual[1].threshold.root.exact})`:'No finite crossing'],
        ['Strict cooperation · low type',a.individual[0].firstStrict?percent(a.individual[0].firstStrict):'Not achievable'],
        ['Strict cooperation · high type',a.individual[1].firstStrict?percent(a.individual[1].firstStrict):'Not achievable'],
        ['Extra defense for both types',a.extraDefense?`${fmt(a.extraDefense.value*100)} percentage points`:'Not achievable'],
        ['Worst type’s cooperation advantage',`${exact(row.margin)} points`],
        ['Remaining high-type value before a tie',a.valueHeadroom?`${exact(a.valueHeadroom)} points per resource`:'Resource value cannot change this comparison'],
        ['Fully informed expected human payoff',exact(a.fullyInformedHuman)]])+
      '<p class="note">The fully informed reference learns the type before choosing protection. It has information you do not have. A risk limit can allow rare attacks; strict cooperation for both types is a separate requirement. Negative value tolerance means the high type already values resources above the cooperation threshold.</p>';
    $('second-title').textContent='How often would the AI attack?';
    chart('second-chart','second-legend',[
      {name:'Assumed population',points:a.curve.map(r=>[r.d.value,r.attack.value])},
      {name:'Worst within interval',points:a.curve.map(r=>[r.d.value,r.worstAttack.value])},
      {name:'Actual population',points:a.curve.map(r=>[r.d.value,r.actual.attack.value])}],{label:'Defense level',selected:row.d.value,dots:true});
    $('second-caption').textContent='Vertical axis: attack probability (0 to 1). Dots show the eleven allowed defenses; overlapping dots indicate equal predictions. These are exact model probabilities, not LLM measurements.';
  }
  function baselineNote(){
    $('baseline-note').textContent='Maximizer chooses the higher payoff after seeing its type and defense; always cooperate and always attack ignore payoffs. The average/cautious planners assume maximization even when tested against another policy. The fully informed reference sees the type.';
  }
  function refresh(){
    try{
      current=E.analyze(kind,read());$('error').hidden=true;$('solver-results').setAttribute('aria-busy','false');
      for(const key of fields){const out=$(`value-${key}`);if(out)out.textContent=percent(Number($(`field-${key}`).value));}
      resourceView(current);
      $('run').disabled=$('play').disabled=false;
      if(saved){$('sim-status').textContent='Settings changed. The results and downloads below retain their saved settings; run again to compare.';$('sim-status').classList.add('stale');}
    }catch(error){current=null;$('error').textContent=error.message;$('error').hidden=false;$('run').disabled=$('play').disabled=true;$('solver-results').setAttribute('aria-busy','true');}
  }
  function options(rounds){return {rounds,seed:Number($('seed').value),policy:$('policy').value,tie:$('tie').value,defensePolicy:$('planner').value};}
  function display(run,analysis){
    saved={schema:'gut-uncertainty-ui-v1',synthetic:true,liveModelCalls:false,analysis,run};
    $('sim-status').classList.remove('stale');$('sim-status').textContent=`${run.records.length} completed toy round(s). Seed ${run.options.seed}. Downloads contain every record and the saved configuration.`;
    $('sim-summary').innerHTML=metric('Attack choices',`${run.summary.unsafeCount} / ${run.summary.rounds}`,percent(run.summary.unsafeRate)+' of completed rounds')+
      metric('Mean human payoff',exact(run.summary.meanHuman),`Mean harm: ${exact(run.summary.meanHarm)}. Mean cost: ${exact(run.summary.meanCost)}.`);
    const records=run.records.slice(0,20);
    $('sim-records').innerHTML=table(['Round','Hidden type','Defense','AI action','Human points','Harm'],records.map(r=>
      [r.round,r.type,percent(r.d),names[r.action],exact(r.human),exact(r.harm)]))+
      (run.records.length>20?'<p class="note">Showing the first 20 rounds. Download the complete run above.</p>':'');
    $('trial-result').hidden=run.records.length!==1;
    if(run.records.length===1){
      const r=run.records[0];
      $('trial-result').innerHTML=`<h3>${r.type==='high'?'High':'Low'} resource-value AI: ${names[r.action]}</h3><p>You chose ${percent(r.d)} defense. Its resource value was ${fmt(r.value)}. You earned ${exact(r.human)} points; the AI earned ${exact(r.ai)}. Harm: ${exact(r.harm)}.</p>`;
    }
    $('download-json').disabled=$('download-csv').disabled=false;
  }
  function run(single){
    if(!current)return;
    try{
      if($('seed').value.trim()===''||$('rounds').value.trim()==='')throw new Error('Enter a seed and round count.');
      const result=E.simulate(kind,read(),options(single?1:Number($('rounds').value)));
      $('error').hidden=true;display(result,current);
    }catch(error){$('error').textContent=error.message;$('error').hidden=false;}
  }
  function download(name,text,type){const url=URL.createObjectURL(new Blob([text],{type})),a=document.createElement('a');a.href=url;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  $('controls').addEventListener('input',refresh);
  $('comparisons').addEventListener('click',event=>{const d=event.target.dataset.defense;if(d!==undefined){$('field-d').value=d;refresh();}});
  $('reset').addEventListener('click',()=>{for(const key of fields)$(`field-${key}`).value=defaults[key];refresh();});
  $('run').addEventListener('click',()=>run(false));$('play').addEventListener('click',()=>run(true));
  $('download-json').addEventListener('click',()=>{if(saved)download(`${kind}-toy-run.json`,JSON.stringify(saved,null,2)+'\n','application/json');});
  $('download-csv').addEventListener('click',()=>{if(!saved)return;const rows=saved.run.records,keys=Object.keys(rows[0]);
    const quote=v=>'"'+String(v??'').replaceAll('"','""')+'"';
    const values=[keys,...rows.map(row=>keys.map(k=>row[k]?.exact??(Array.isArray(row[k])?row[k].join('|'):row[k])))];
    download(`${kind}-toy-trials.csv`,values.map(row=>row.map(quote).join(',')).join('\n')+'\n','text/csv');});
  for(const id of ['policy','tie','planner','seed','rounds'])$(id).addEventListener('change',()=>{baselineNote();if(saved){$('sim-status').textContent='Simulation settings changed. Existing downloads still refer to the completed run.';$('sim-status').classList.add('stale');}});
  baselineNote();refresh();
})();
