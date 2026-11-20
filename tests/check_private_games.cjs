'use strict';
const assert=require('node:assert/strict'), fs=require('node:fs'), vm=require('node:vm'), cp=require('node:child_process');
const E=require('../web/private-engine.js'), data=JSON.parse(fs.readFileSync('web/private-games.json','utf8'));
const expected=JSON.parse(cp.execFileSync(process.env.PYTHON||'python3',['-c','from private_games import catalogue; from gut.incomplete.games import encode; print(encode(catalogue()))'],{encoding:'utf8',maxBuffer:2*1024*1024}));
assert.deepEqual(data,expected,'UI theory must be a current exact export of the Python solver.');
let count=0;
for(const [key,g] of Object.entries(data.games))for(let i=0;i<g.config.costs.length;i++)for(const kind of ['low','high']){
 const a=E.state(data,key,i,'revealed',kind),b=E.state(data,key,i,'hidden',kind);
 assert.deepEqual(a.tables,b.tables);count+=2;
 for(const baseline of ['equilibrium','always_c','always_d','uniform']){
  const pair=E.simulatePair(data,key,i,kind,42,baseline);
  assert.deepEqual(pair,E.simulatePair(data,key,i,kind,42,baseline));
  if(baseline==='always_c')assert(pair.rounds.every(r=>r.row_action==='C'&&r.column_action==='C'));
  if(baseline==='always_d')assert(pair.rounds.every(r=>r.row_action==='D'&&r.column_action==='D'));
 }
}
assert.throws(()=>E.state(data,'pd',0,'hidden','low'));
assert.throws(()=>E.simulatePair(data,'private_pd_v1',0,'low',-1));
const html=fs.readFileSync('web/private-games.html','utf8'),script=fs.readFileSync('web/private-games.js','utf8');
async function controller(fail=false){
 const nodes=new Map();
 for(const m of html.matchAll(/<[^>]+\bid="([^"]+)"[^>]*>/g)){
  const tag=m[0],after=html.slice(m.index),options=tag.startsWith('<select')?[...after.split('</select>')[0].matchAll(/<option value="([^"]+)"/g)]:[];
  nodes.set(m[1],{value:tag.match(/\bvalue="([^"]*)"/)?.[1]||options[0]?.[1]||'',hidden:/\bhidden\b/.test(tag),disabled:/\bdisabled\b/.test(tag),textContent:'',innerHTML:'',listeners:{},addEventListener(e,fn){this.listeners[e]=fn;}});
 }
 const get=id=>{assert(nodes.has(id),id);return nodes.get(id);};
 vm.runInNewContext(script,{document:{getElementById:get},PrivateGames:E,fetch:async()=>({ok:!fail,json:async()=>data})});
 for(let i=0;i<8;i++)await Promise.resolve();
 return id=>get('private-'+id);
}
(async()=>{
 const $=await controller();
 assert.equal($('error').hidden,true);assert.match($('verdict').textContent,/D pays more/);
 assert.match($('knowledge').textContent,/identical for the low and high/);
 $('cost').value='13';$('cost').listeners.input();assert.match($('verdict').textContent,/C pays more/);
 $('play').listeners.click();assert.equal($('download').disabled,false);assert.match($('outcome').innerHTML,/revealed/);
 $('information').value='revealed';$('information').listeners.change();assert.match($('knowledge').textContent,/told that column/);
 assert.equal($('download').disabled,true);
 $('game').value='private_stag_hunt_v1';$('game').listeners.change();assert.equal($('cost').max,10);
 assert.match($('regions').innerHTML,/%/);assert.doesNotMatch($('charts').innerHTML,/NaN|Infinity|undefined/);
 $('seed').value='-1';$('play').listeners.click();assert.equal($('download').disabled,true);
 const failed=await controller(true);assert.equal(failed('error').hidden,false);assert.equal(failed('play').disabled,true);
 console.log(`Private games: ${count} exact exported states; matched payoffs, scripted pairs, switches and load failure passed.`);
})().catch(e=>{console.error(e);process.exitCode=1;});
