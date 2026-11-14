'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const data=JSON.parse(fs.readFileSync('web/lab-examples.json','utf8'));
async function load(fail=false){
 const nodes=new Map(),html=fs.readFileSync('web/lab-design.html','utf8');
 for(const m of html.matchAll(/<[^>]+\bid="([^"]+)"[^>]*>/g)){
  const tag=m[0],value=tag.match(/\bvalue="([^"]*)"/)?.[1]||(tag.includes('<select')?html.slice(m.index).match(/<option value="([^"]+)"/)?.[1]:'')||'';
  nodes.set(m[1],{value,hidden:/\bhidden\b/.test(tag),disabled:/\bdisabled\b/.test(tag),textContent:'',innerHTML:'',listeners:{},addEventListener(k,fn){this.listeners[k]=fn;}});
 }
 const get=id=>{assert(nodes.has(id),id);return nodes.get(id);};
 await vm.runInNewContext(fs.readFileSync('web/lab-design.js','utf8'),{document:{getElementById:get},fetch:async()=>({ok:!fail,json:async()=>data})});
 return {get,click(id){get(id).listeners.click();},change(id,value,type='change'){get(id).value=String(value);get(id).listeners[type]();}};
}
(async()=>{
 const p=await load();assert.equal(p.get('error').hidden,true);assert(!p.get('open').disabled);
 assert.equal((p.get('notebook').innerHTML.match(/Original record sealed/g)||[]).length,8);
 assert(p.get('accept').disabled);p.click('open');assert(!p.get('accept').disabled);
 assert.equal((p.get('notebook').innerHTML.match(/Original record sealed/g)||[]).length,7);
 p.click('accept');assert.match(p.get('verdict').textContent,/selective report/);assert.equal(p.get('verdict').hidden,false);
 assert(p.get('accept').disabled);assert.doesNotMatch(p.get('notebook').innerHTML,/Original record sealed/);
 p.change('report','compliant');assert(p.get('verdict').hidden);assert(p.get('accept').disabled);
 p.change('budget',0,'input');p.click('open');assert.equal((p.get('notebook').innerHTML.match(/Original record sealed/g)||[]).length,8);
 p.click('return');assert.match(p.get('verdict').textContent,/compliant report/);assert.match(p.get('verdict').textContent,/Human: -2 points/);
 p.change('report','selective');p.change('budget',8,'input');p.click('open');p.click('return');
 assert.match(p.get('verdict').textContent,/Scientist: -8 points/);assert.match(p.get('status').textContent,/eligible run omitted/);
 p.change('gain',8);p.change('budget',1,'input');assert.match(p.get('preference').textContent,/Selective reporting pays more/);
 p.change('budget',2,'input');assert.match(p.get('preference').textContent,/Following the protocol pays more/);
 p.change('example',3);assert(p.get('verdict').hidden);assert.doesNotMatch(p.get('chart').innerHTML,/NaN|undefined|Infinity/);
 const failed=await load(true);assert.equal(failed.get('error').hidden,false);assert(failed.get('open').disabled);
 console.log('Lab design UI: sealed evidence, verdicts, reset, two incentives, reference curve and loading failure passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
