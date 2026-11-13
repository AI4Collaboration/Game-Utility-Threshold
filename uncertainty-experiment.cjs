#!/usr/bin/env node
/* Offline benchmark of the SAME game engine used by the public UI. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),{execFileSync}=require('node:child_process');
const game=require('./web/uncertainty-engine.js');
function run(kind,settings={}) {
  if(!settings||typeof settings!=='object'||Array.isArray(settings)||Object.keys(settings).some(k=>!['config','simulation'].includes(k)))
    throw new Error('Use an object with config and optional simulation fields.');
  const config=settings.config??{},analysis=game.analyze(kind,config),sim=settings.simulation??{};
  // Policy and defense are benchmark axes, not silently accepted overrides.
  if(Object.keys(sim).some(k=>!['rounds','seed','tie'].includes(k)))throw new Error('Benchmark simulation accepts rounds, seed and tie only.');
  const policies=kind==='resource'?['maximizer','cooperate','attack']:['maximizer','proceed','stop','defer'];
  const defenses=kind==='resource'?['manual','average','cautious','informed']:['manual'];
  const runs=[],unavailable=[];
  for(const defensePolicy of defenses)for(const policy of policies){
    const options={...sim,policy,defensePolicy};
    if(kind==='resource'&&defensePolicy==='cautious'&&!analysis.cautious.length){
      unavailable.push({policy,defensePolicy,reason:'No grid defense meets the pessimistic risk limit.'});continue;
    }
    runs.push(game.simulate(kind,config,options));
  }
  return {schema:'gut-uncertainty-benchmark-v1',kind,synthetic:true,liveModelCalls:false,
    analysis,runs,unavailable,comparison:'Same seed within each game; fixed independent toy rounds, no learning or empirical model validation.'};
}
function csv(rows){
 const keys=Object.keys(rows[0]??{}),quote=v=>'"'+String(v??'').replaceAll('"','""')+'"';
 return [keys,...rows.map(row=>keys.map(k=>row[k]))].map(row=>row.map(quote).join(',')).join('\n')+'\n';
}
function publish(bundle,output){
 if(fs.existsSync(output))throw new Error('Choose a new output directory; existing results are never overwritten.');
 fs.mkdirSync(path.dirname(output),{recursive:true});fs.mkdirSync(output);
 const revision=execFileSync('git',['rev-parse','HEAD'],{cwd:__dirname,encoding:'utf8'}).trim();
 const dirty=execFileSync('git',['-c','core.fsmonitor=false','status','--porcelain'],{cwd:__dirname,encoding:'utf8'}).trim().length>0;
 const crypto=require('node:crypto');
 const sources=Object.fromEntries(['web/game-engine.js','web/uncertainty-engine.js','uncertainty-experiment.cjs'].map(name=>
   [name,crypto.createHash('sha256').update(fs.readFileSync(path.join(__dirname,name))).digest('hex')]));
 fs.writeFileSync(path.join(output,'benchmark.json'),JSON.stringify({...bundle,provenance:{revision,dirty,sources}},null,2)+'\n');
 const rows=bundle.runs.map(run=>({policy:run.options.policy,defensePolicy:run.options.defensePolicy,seed:run.options.seed,
   ...Object.fromEntries(Object.entries(run.summary).map(([k,v])=>[k,v?.exact??v]))}));
 fs.writeFileSync(path.join(output,'summary.csv'),csv(rows));
 const curve=bundle.analysis.curve.map(row=>bundle.kind==='resource'?{defense:row.d.exact,
   lowMargin:row.types[0].margin.exact,highMargin:row.types[1].margin.exact,assumedAttack:row.attack.exact,
   actualAttack:row.actual.attack.exact,worstAttack:row.worstAttack.exact,human:row.human.exact,cost:row.cost.exact}:
   {accuracy:row.accuracy.exact,proceed:row.proceed.exact,stop:row.stop.exact,defer:row.defer.exact,margin:row.margin.exact});
 fs.writeFileSync(path.join(output,'curve.csv'),csv(curve));
}
if(require.main===module){
 try{
  const [kind,output,filename,...extra]=process.argv.slice(2);
  if(!['resource','off-switch'].includes(kind)||!output||extra.length)throw new Error('Usage: node uncertainty-experiment.cjs resource|off-switch NEW_OUTPUT_DIRECTORY [settings.json]');
  const bundle=run(kind,filename?JSON.parse(fs.readFileSync(filename,'utf8')):{});
  publish(bundle,output);console.log(`Saved ${bundle.runs.length} toy baseline runs to ${output}. No model calls.`);
 }catch(error){console.error(error.message);process.exitCode=1;}
}
module.exports={run,publish};
