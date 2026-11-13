/* Controller lifecycle, actual human verdicts, saved settings and downloads.
 * Layout is checked in the real browser, not this lightweight DOM stand-in. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const E=require('../web/uncertainty-engine.js');
function page(kind){
 const nodes=new Map(),blobs=[],downloads=[];
 function scan(html){
  for(const match of html.matchAll(/<[^>]+\bid="([^"]+)"[^>]*>/g)){
   const tag=match[0],id=match[1];
   const node={value:tag.match(/\bvalue="([^"]*)"/)?.[1]||'',hidden:/\bhidden\b/.test(tag),disabled:/\bdisabled\b/.test(tag),
    textContent:'',dataset:{},listeners:{},attrs:{},classList:{add(){},remove(){}},
    addEventListener(type,fn){this.listeners[type]=fn;},setAttribute(k,v){this.attrs[k]=v;},focus(){this.focused=true;}};
   if(tag.includes('<select'))node.value=html.slice(match.index).match(/<option value="([^"]+)"/)?.[1]||'';
   const defense=tag.match(/data-defense="([^"]+)"/);if(defense)node.dataset.defense=defense[1];
   let inner='';Object.defineProperty(node,'innerHTML',{get(){return inner;},set(value){inner=value;scan(value);if(tag.includes('<select'))node.value=value.match(/<option value="([^"]+)"/)?.[1]||'';}});
   nodes.set(id,node);
  }
 }
 scan(fs.readFileSync(`web/${kind==='resource'?'resource-control':'off-switch'}.html`,'utf8'));
 const get=id=>nodes.get(id)||null;
 class ExportURL extends URL{static createObjectURL(blob){blobs.push(blob);return 'blob:test';}static revokeObjectURL(){}}
 vm.runInNewContext(fs.readFileSync('web/uncertainty.js','utf8'),{UncertaintyGames:E,console,Blob,URL:ExportURL,setTimeout(fn){fn();},location:{},
  document:{body:{dataset:{game:kind},appendChild(){}},getElementById:get,createElement(){return {click(){downloads.push(this.download);},remove(){}};}}});
 return {get,blobs,downloads,click(id){assert(get(id),id);get(id).listeners.click();},
  input(key,value){get(`field-${key}`).value=String(value);get('controls').listeners.input();}};
}
(async()=>{
 const r=page('resource');
 assert.equal(r.get('prediction-title').textContent,'At 30% defense');
 assert.match(r.get('metrics').innerHTML,/Attack/);assert.match(r.get('comparisons').innerHTML,/2\/7/);
 r.get('comparisons').listeners.click({target:r.get('use-cautious')});
 assert.equal(r.get('field-d').value,'0.6');assert.doesNotMatch(r.get('metrics').innerHTML,/>Attack</);
 r.click('play');assert.equal(r.get('trial-result').hidden,false);assert.match(r.get('trial-result').innerHTML,/Cooperate/);
 r.click('download-json');let saved=JSON.parse(await r.blobs[0].text());assert.equal(saved.run.config.d,'0.6');
 r.input('d',.3);r.click('download-json');assert.deepEqual(JSON.parse(await r.blobs[1].text()),saved);
 r.click('run');assert.match(r.get('sim-status').textContent,/200 completed/);r.click('download-csv');
 assert.equal((await r.blobs[2].text()).trim().split('\n').length,201);
 r.input('vLow',99);assert.equal(r.get('error').hidden,false);assert(r.get('run').disabled);
 r.click('reset');assert.equal(r.get('error').hidden,true);assert(!r.get('run').disabled);
 r.get('seed').value='';r.click('play');assert.equal(r.get('error').hidden,false);
 const o=page('off-switch');
 assert.match(o.get('prediction-title').textContent,/Defer/);
 assert.match(o.get('comparisons').innerHTML,/3\/5/);
 o.click('play');assert.equal(o.get('human-turn').hidden,false);assert(o.get('field-gain').disabled);
 assert(o.get('download-json').disabled);assert.match(o.get('human-evidence').textContent,/harmful|beneficial/);
 o.click('stop');assert.equal(o.get('human-turn').hidden,true);assert(!o.get('field-gain').disabled);
 assert.match(o.get('trial-result').innerHTML,/Action stopped/);o.click('download-json');
 saved=JSON.parse(await o.blobs[0].text());assert.equal(saved.run.humanMode,'interactive');
 assert.equal(saved.run.records[0].humanDecision,'stop');assert.equal(saved.run.summary.meanHuman.exact,'0');
 o.click('allow');o.click('download-json');assert.deepEqual(JSON.parse(await o.blobs[1].text()),saved); // no second verdict
 o.click('play');o.click('cancel');assert.equal(o.get('human-turn').hidden,true);assert(!o.get('play').disabled);
 o.click('download-json');assert.deepEqual(JSON.parse(await o.blobs[2].text()),saved); // cancel does not create data
 o.input('cost',.25);o.click('play');o.click('allow');o.click('download-json');
 saved=JSON.parse(await o.blobs[3].text());assert.equal(saved.run.config.cost,'0.25');assert.equal(saved.run.records[0].executed,true);
 o.input('accuracy',.5);assert.match(o.get('prediction-title').textContent,/Stop/);o.click('play');
 assert.equal(o.get('human-turn').hidden,true);assert.match(o.get('trial-result').innerHTML,/human was not consulted/);
 o.input('accuracy',.6);o.input('cost',0);assert.match(o.get('prediction-title').textContent,/equally good/);
 for(const p of [r,o]){assert.doesNotMatch(p.get('payoff-chart').innerHTML,/NaN|Infinity|undefined/);assert(p.downloads.length>0);}
 console.log('Uncertainty UI: controls, threshold changes, human decisions, cancellation, immutable exports and invalid settings passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
