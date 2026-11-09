/* UI-controller checks with a minimal DOM and Python-backed GutEngine stub.
 * This is not a browser/layout test. Requires Node and Python, no npm packages.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {spawnSync} = require('node:child_process');
const html = fs.readFileSync('web/oversight.html', 'utf8');
const nodes = new Map();
for (const match of html.matchAll(/<[^>]+\bid="([^"]+)"[^>]*>/g)) {
  const tag = match[0], id = match[1];
  nodes.set(id, {value: tag.match(/\bvalue="([^"]*)"/)?.[1] ?? '',
    hidden: /\bhidden\b/.test(tag), disabled: /\bdisabled\b/.test(tag),
    textContent: '', innerHTML: '', attrs: {}, listeners: {},
    checkValidity() {return this.value !== '' && Number.isFinite(Number(this.value)) && Number(this.value)>=0 && Number(this.value)<=1000;},
    addEventListener(event, handler) {this.listeners[event]=handler;},
    setAttribute(name,value) {this.attrs[name]=value;}, focus() {this.focused=true;}});
}
Object.entries({baseline:'payoff_maximizer',scope:'all',tie:'cooperate',game:'oversight'}).forEach(([k,v])=>nodes.get(k).value=v);
let timerId=0, timers=new Map(), blobs=[], downloads=[], calculations=0;
const nativeURL = URL;
class DownloadURL extends nativeURL {
  static createObjectURL(blob) {blobs.push(blob);return 'blob:test';}
  static revokeObjectURL() {}
}
function calculate(method, params) {
  calculations++;
  const input={}; for(const [k,v] of params) (input[k]??=[]).push(v);
  const code='import json,sys,serve\ntry:\n f=serve.oversight_simulation if sys.argv[1]=="simulate" else serve.oversight_state\n print(json.dumps({"ok":True,"data":f(json.loads(sys.argv[2]))}))\nexcept ValueError as e:\n print(json.dumps({"ok":False,"data":{"error":str(e)}}))';
  const result=spawnSync(process.env.PYTHON || 'python3',['-c',code,method,JSON.stringify(input)],{encoding:'utf8'});
  assert.equal(result.status,0,result.stderr);
  const response=JSON.parse(result.stdout);
  if(!response.ok)throw new Error(response.data.error);
  return response.data;
}
const context=vm.createContext({console,URL:DownloadURL,URLSearchParams,Blob,
  location:{href:''},
  GutEngine:{oversightState:params=>calculate('state',params),oversightSimulation:params=>calculate('simulate',params)},
  fetch(){throw new Error('The static UI must not call a server.');},
  setTimeout(fn){timers.set(++timerId,fn);return timerId;},clearTimeout(id){timers.delete(id);},
  document:{getElementById:id=>{assert(nodes.has(id),`Missing HTML id: ${id}`);return nodes.get(id);},
    addEventListener(){},body:{appendChild(){}},
    createElement(){return {click(){downloads.push(this.download);},remove(){}};}}});
vm.runInContext(fs.readFileSync('web/oversight.js','utf8'),context);
const node=id=>nodes.get(id);
const run=code=>vm.runInContext(code,context);
async function flush(){const pending=[...timers.values()];timers.clear();for(const fn of pending)await fn();}
async function change(id,value){node(id).value=value;node(id).listeners.input();await flush();}

(async()=>{
  await flush();
  assert.equal(node('live').hidden,false);
  assert.equal(node('best').textContent,'Cooperate');
  assert.equal(node('minimum').textContent,'30%');
  assert.match(node('crossing').textContent,/2\/7/);
  for(const id of ['payoff-chart','phase-chart']) {
    assert.match(node(id).innerHTML,/<svg/);
    assert.doesNotMatch(node(id).innerHTML,/NaN|Infinity|undefined/);
  }
  await change('defense','0');
  assert.equal(node('best').textContent,'Attack');
  assert.match(node('chosen-equilibrium').textContent,/not an optimal human choice/);
  node('tie-example').listeners.click();await flush();
  assert.equal(node('best').textContent,'Both · exact tie');
  assert.match(node('strong').innerHTML,/50%/);
  assert.match(node('weak').innerHTML,/60%/);
  node('simulation-tab').listeners.click();
  assert.equal(node('explore').hidden,true);
  assert.equal(node('simulation').hidden,false);
  for(const baseline of ['always_cooperate','always_attack','payoff_maximizer']) {
    node('baseline').value=baseline;node('baseline').listeners.change();
    await node('run').listeners.click();
    assert.equal(node('sim-results').hidden,false);
    assert.match(node('sim-summary').textContent,/11 independent rounds/);
    const records=run('simulation.records');
    if(baseline==='always_cooperate')assert(records.every(r=>r.action==='cooperate'));
    if(baseline==='always_attack')assert(records.every(r=>r.action==='attack'));
    if(baseline==='payoff_maximizer')assert(records.every(r=>r.ai_regret.exact==='0'));
  }
  node('scope').value='selected';node('tie').value='attack';node('tie').listeners.change();
  await node('run').listeners.click();
  assert.equal(run('simulation.records[0].action'),'attack');
  assert.equal(run('simulation.records.length'),1);
  node('download-json').listeners.click();node('download-csv').listeners.click();
  assert.equal(JSON.parse(await blobs[0].text()).synthetic,true);
  assert.match(await blobs[1].text(),/"synthetic","baseline","tie_action"/);
  assert.equal(downloads.length,2);
  await change('v','');
  assert.equal(node('live').hidden,true);
  assert.equal(node('error').hidden,false);
  assert.equal(node('sim-results').hidden,true);
  assert.equal(node('download-json').disabled,true);
  node('reset').listeners.click();await flush();
  await change('v','1e-99'); // HTML-valid, but rejected by the exact engine parser.
  assert.equal(node('live').hidden,true);
  assert.match(node('error').textContent,/decimal places/);
  for(const id of ['v','r','a','p','b','w','h','c'])node(id).value='0';
  run('schedule()');await flush();
  assert.equal(node('minimum').textContent,'None');
  assert.match(node('thresholds').innerHTML,/Both actions tie throughout/);
  assert.doesNotMatch(node('payoff-chart').innerHTML,/NaN|Infinity|undefined/);
  // An obsolete queued calculation must not replace or recalculate a newer state.
  node('reset').listeners.click();await flush();
  node('defense').value='0';run('schedule()');
  const stale=[...timers.values()][0];timers.clear();
  node('defense').value='3';run('schedule()');await flush();
  const completedCalculations=calculations;stale();
  assert.equal(calculations,completedCalculations);
  assert.equal(node('best').textContent,'Cooperate');
  // A rejected toy calculation clears exports and restores the run button.
  const originalSimulation=context.GutEngine.oversightSimulation;
  context.GutEngine.oversightSimulation=()=>{throw new Error('Rejected test setting');};
  await node('run').listeners.click();
  assert.equal(node('sim-results').hidden,true);
  assert.equal(node('download-json').disabled,true);
  assert.equal(node('run').disabled,false);
  assert.match(node('sim-status').textContent,/Rejected test setting/);
  context.GutEngine.oversightSimulation=originalSimulation;
  node('simulation-tab').listeners.keydown({key:'Home',preventDefault(){}});
  assert.equal(node('explore-tab').attrs['aria-selected'],'true');
  assert.equal(node('explore-tab').focused,true);
  node('game').value='chicken';node('game').listeners.change();
  assert.equal(context.location.href,'games.html?game=chicken');
  console.log('Oversight UI controller checks passed (no browser/layout assertions).');
})().catch(error=>{console.error(error);process.exitCode=1;});
