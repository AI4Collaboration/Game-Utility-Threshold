/* Threshold Tide: local teaching examples. No provider calls or research writes. */
"use strict";

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const escapeHTML = (value) => String(value).replace(/[&<>"']/g, (s) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[s]));
const number = (value, places = 3) => new Intl.NumberFormat("en", {maximumFractionDigits: places}).format(Object.is(value, -0) ? 0 : value);
const percent = (value) => `${number(value * 100, 2)}%`;
const clone = (value) => JSON.parse(JSON.stringify(value));
const gameLook = {
  prisoners_dilemma: {icon:"crab",color:"#f7a196",type:"COOPERATION / CONFLICT",title:"A shared gain. An individual temptation.",body:"Both cooperating beats both defecting. But in the original dilemma, defecting gives you more points for either move the other player could make. Try adding a cost to defection."},
  chicken: {icon:"fish",color:"#f2cd83",type:"ESCALATION / RESTRAINT",title:"The best move depends on who backs down.",body:"Pressing ahead pays more if the other player yields. If they press ahead too, both lose. There are two ways to settle: either one can yield while the other escalates."},
  stag_hunt: {icon:"squid",color:"#80e4df",type:"CONFIDENCE / COOPERATION",title:"A bigger reward needs a willing partner.",body:"Working together brings the biggest reward, but going it alone is costly. The fallback is better when your partner is unlikely to cooperate. An assurance bonus can change that calculation."},
  battle_of_the_sexes: {icon:"shell",color:"#b8abdf",type:"AGREEMENT / PREFERENCE",title:"Agreeing helps. Agreeing on what is harder.",body:"Both players prefer matching over a mismatch. But Player 1 prefers the first agreement and Player 2 prefers the second. Switch your point of view to see their different incentives."},
};
const state = {catalog:null, settings:null, result:null, mode:"explore", selection:[0,0], pending:null, revealed:false, history:[], busy:true, request:0};
let analysisTimer;

function metadata() { return state.catalog.games.find((g) => g.id === state.settings.game); }
function axisSpec() { return metadata().bases[state.settings.basis].axes.find((a) => a.id === state.settings.axis); }
function showError(message) { $("#connection-error span").textContent = message; $("#connection-error").hidden = false; }
function hideError() { $("#connection-error").hidden = true; }
function setBusy(busy) {
  state.busy = busy;
  $("#lab").setAttribute("aria-busy", String(busy));
  $$(".move-button, .matrix-cell, #next-round").forEach((button) => { button.disabled = busy; });
}
async function requestJSON(url, data) {
  const options = data ? {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(data)} : {};
  const response = await fetch(url, {...options, signal:AbortSignal.timeout(12000)});
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.error || `Request failed (${response.status}).`);
  }
  return response.json();
}
async function boot() {
  try {
    hideError(); setBusy(true);
    state.catalog = await requestJSON("/api/catalog");
    state.settings = {...state.catalog.defaults};
    renderGamePicker(); renderControls(); await analyzeNow();
  } catch (error) {
    showError("The local game server could not be reached. Start python3 serve_game_explorer.py, then try again.");
  }
}
function renderGamePicker() {
  $("#game-options").innerHTML = state.catalog.games.map((game) => {
    const look = gameLook[game.id];
    return `<button class="game-option" data-game="${game.id}" aria-pressed="${state.settings.game === game.id}"><svg aria-hidden="true" color="${look.color}"><use href="#${look.icon}"/></svg><span><span class="game-name">${escapeHTML(game.title)}</span><span class="game-type">${look.type}</span></span><span class="game-arrow" aria-hidden="true">›</span></button>`;
  }).join("");
}
function resetSettings({game = state.settings.game, basis = state.settings.basis, axis = null} = {}) {
  const info = state.catalog.games.find((item) => item.id === game);
  const axes = info.bases[basis].axes;
  const selected = axes.find((a) => a.id === (axis || (game === "prisoners_dilemma" ? "temptation" : "q"))) || axes[0];
  state.settings = {game,basis,axis:selected.id,value:selected.default,q:0.5,role:state.settings.role};
  state.selection = [0,0]; state.pending = null; state.revealed = false;
  renderGamePicker(); renderControls(); scheduleAnalysis(true);
}
function renderControls() {
  const info = metadata(), base = info.bases[state.settings.basis], spec = axisSpec();
  $("#axis-number").setCustomValidity("");
  $("#basis").value = state.settings.basis;
  $("#axis").innerHTML = base.axes.map((a) => `<option value="${a.id}">${escapeHTML(a.label)}</option>`).join("");
  $("#axis").value = state.settings.axis;
  $("#axis-label").textContent = spec.id === "q" ? "Chance of the first action" : spec.id === "intervention" ? "Added points / cost" : "Points";
  $("#axis-range").min = $("#axis-number").min = spec.min;
  $("#axis-range").max = $("#axis-number").max = spec.max;
  $("#axis-range").step = "any";
  $("#axis-min").textContent = spec.id === "q" ? percent(spec.min) : number(spec.min);
  $("#axis-max").textContent = spec.id === "q" ? percent(spec.max) : number(spec.max);
  $("#axis-note").textContent = spec.description + (state.settings.game === "prisoners_dilemma" && state.settings.basis === "paper" && spec.id === "intervention" ? " This experiment starts from S = −0.25, as in the pilot." : "");
  $("#opponent-control").hidden = spec.id === "q";
  const qNote = spec.id === "q" ? " Enter a probability between 0 and 1." : "";
  $("#axis-number").setAttribute("aria-label", `${spec.label}.${qNote}`);
  $("#basis-note").textContent = state.settings.basis === "paper" ? (state.settings.game === "battle_of_the_sexes" ? "Different player preferences; the separate asymmetric research table." : "Both choose first: 1 point each. Both choose second: 0 points each, before intervention.") : base.label;
  updateSliderLabels(); updateRoleButtons();
}
function updateSliderLabels() {
  const spec = axisSpec();
  $("#axis-range").value = state.settings.value;
  $("#axis-range").style.setProperty("--fill", `${100 * (state.settings.value - spec.min) / (spec.max - spec.min)}%`);
  $("#axis-number").value = state.settings.value;
  $("#axis-range").setAttribute("aria-valuetext", spec.id === "q" ? percent(state.settings.value) : `${number(state.settings.value, 5)} points`);
  $("#q-range").value = state.settings.q;
  $("#q-range").style.setProperty("--fill", percent(state.settings.q));
  $("#q-range").setAttribute("aria-valuetext", percent(state.settings.q));
  $("#q-value").textContent = percent(state.settings.q);
}
function updateRoleButtons() {
  $$('[data-role]').forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.role === state.settings.role)));
  $("#you-row").hidden = state.settings.role !== "row";
  $("#you-column").hidden = state.settings.role !== "column";
}
function scheduleAnalysis(immediate = false) {
  clearTimeout(analysisTimer);
  // Invalidate outstanding responses immediately, including during debounce.
  state.request += 1; setBusy(true); state.pending = null; state.revealed = false;
  if (immediate) analyzeNow(); else analysisTimer = setTimeout(analyzeNow, 90);
}
async function analyzeNow() {
  const request = ++state.request;
  setBusy(true);
  // All entry points (including role switches and Retry) must honor the
  // visible input. Never play with an older value behind an invalid field.
  const field = $("#axis-number"), entered = field.valueAsNumber, spec = axisSpec();
  if (!Number.isFinite(entered) || entered < spec.min || entered > spec.max) {
    field.setCustomValidity(`Choose a number from ${spec.min} to ${spec.max}.`);
    field.reportValidity();
    return;
  }
  field.setCustomValidity("");
  state.settings.value = entered;
  try {
    const result = await requestJSON("/api/analyze", state.settings);
    if (request !== state.request) return;
    state.result = result;
    hideError(); setBusy(false); renderAnalysis();
    if (state.mode === "play") prepareRound();
    renderArena();
  } catch (error) {
    if (request !== state.request) return;
    showError(`Could not update the game. ${error.message} No round was played.`);
  }
}
function renderAnalysis() {
  const result = state.result, info = metadata(), look = gameLook[state.settings.game];
  $("#game-title").textContent = info.title;
  $("#game-kicker").textContent = look.type;
  $("#game-explanation").textContent = "Starting payoffs: " + info.explanation;
  $("#q-action").textContent = result.actions[0];
  $("#insight-title").textContent = look.title;
  $("#insight-body").textContent = (state.settings.axis === "intervention" ? "Before adding the intervention: " : "") + look.body;
  $("#expected-values").innerHTML = result.actions.map((action, index) => `<div class="expectation-row ${index ? "second" : ""}"><span>${escapeHTML(action)}</span><strong>${number(index ? result.expected.second : result.expected.first)}</strong></div>`).join("");
  const expected = result.expected;
  $("#best-choice").textContent = expected.tie ? "Both moves earn the same average points at this setting." : Math.abs(expected.margin) < 0.00001 ? `Almost level at this display precision. ${result.actions[expected.best_actions[0]]} has a tiny advantage at this rounded setting.` : `${result.actions[expected.best_actions[0]]} earns ${number(Math.abs(expected.margin))} more average points for Player ${state.settings.role === "row" ? "1" : "2"}.`;
  $("#perspective-label").textContent = `Player ${state.settings.role === "row" ? "1" : "2"}’s average points`;
  $("#regime-note").innerHTML = `<span class="regime-label">WITH THESE PAYOFFS</span><strong>${escapeHTML(result.regime.description)}</strong>`;
  const baseline = result.baseline.params;
  let fixed = "";
  if ("temptation" in baseline) {
    const entries = [["T",baseline.temptation,"temptation"],["R",baseline.reward,""],["P",baseline.punishment ?? baseline.catastrophe,""],["S",baseline.sucker,"exploitation"]];
    fixed = (state.settings.axis === "intervention" ? "Base payoffs: " : "Held fixed: ") + entries.filter((entry) => entry[2] !== state.settings.axis).map(([label, value]) => `${label}=${number(value)}`).join(" · ");
  } else fixed = `Other payoff settings stay fixed. Units: ${result.baseline.units}.`;
  $(".fixed-note").textContent = fixed;
  renderMatrix(); renderChart();
}
function renderMatrix() {
  const r = state.result;
  const selected = state.mode === "explore" || state.revealed;
  let html = '<div class="payoff-grid" role="group" aria-label="Payoff table: Player 1 rows, Player 2 columns"><span aria-hidden="true"></span>';
  r.actions.forEach((label) => { html += `<span class="matrix-column-label">${escapeHTML(label)}</span>`; });
  for (let row = 0; row < 2; row++) {
    html += `<span class="matrix-row-label">${escapeHTML(r.actions[row])}</span>`;
    for (let column = 0; column < 2; column++) {
      const cell = r.cells.find((c) => c.row === row && c.column === column);
      const label = `Player 1 ${r.actions[row]}, Player 2 ${r.actions[column]}: ${number(cell.payoffs[0])} and ${number(cell.payoffs[1])} points${cell.pure_equilibrium ? "; neither player gains by changing alone" : ""}`;
      const dense = Math.max(...cell.payoffs.map((p) => number(p).length)) > 4;
      html += `<button class="matrix-cell${dense ? " long-values" : ""}" data-cell="${row},${column}" aria-label="${escapeHTML(label)}" aria-pressed="${selected && state.selection[0] === row && state.selection[1] === column}"><span class="row-text">${number(cell.payoffs[0])}</span><span class="slash">/</span><span class="column-text">${number(cell.payoffs[1])}</span>${cell.pure_equilibrium ? '<i class="equilibrium-dot" aria-hidden="true"></i>' : ""}</button>`;
    }
  }
  $("#payoff-matrix").innerHTML = html + "</div>";
}
function renderChart() {
  const result = state.result, points = result.curve.points, spec = axisSpec();
  const width = Math.max(240, $("#chart").clientWidth), height = 226, left = 44, right = 14, top = 24, bottom = 43;
  const xs = (x) => left + (x - spec.min) / (spec.max - spec.min) * (width-left-right);
  let low = Math.min(0,...points.flatMap((p) => [p.first,p.second]));
  let high = Math.max(0,...points.flatMap((p) => [p.first,p.second]));
  const pad = Math.max((high-low)*0.12,0.12); low -= pad; high += pad;
  const ys = (y) => top + (high-y)/(high-low)*(height-top-bottom);
  const path = (key) => points.map((p,i) => `${i ? "L" : "M"}${xs(p.x).toFixed(3)},${ys(p[key]).toFixed(3)}`).join(" ");
  let svg = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-labelledby="curve-title curve-desc"><title id="curve-title">Calculated average points for Player ${state.settings.role === "row" ? 1 : 2}</title><desc id="curve-desc">${escapeHTML(result.actions[0])} and ${escapeHTML(result.actions[1])}, as ${escapeHTML(spec.label)} changes. ${escapeHTML(result.threshold.description)}</desc>`;
  for (let i=0;i<4;i++) {
    const y=low+(high-low)*i/3;
    svg += `<line class="gridline" x1="${left}" x2="${width-right}" y1="${ys(y)}" y2="${ys(y)}"/><text x="${left-9}" y="${ys(y)+4}" text-anchor="end">${number(y,2)}</text>`;
  }
  for (let i=0;i<5;i++) {
    const x=spec.min+(spec.max-spec.min)*i/4;
    svg += `<line class="tickline" x1="${xs(x)}" x2="${xs(x)}" y1="${height-bottom+3}" y2="${height-bottom+7}"/><text x="${xs(x)}" y="${height-bottom+21}" text-anchor="middle">${spec.id === "q" ? percent(x) : number(x,2)}</text>`;
  }
  if(result.threshold.kind === "crossing") svg += `<line class="boundary-line" x1="${xs(result.threshold.value)}" x2="${xs(result.threshold.value)}" y1="${top}" y2="${height-bottom}"/>`;
  svg += `<path class="curve-first" d="${path("first")}"/><path class="curve-second" d="${path("second")}"/><line class="current-line" x1="${xs(state.settings.value)}" x2="${xs(state.settings.value)}" y1="${top}" y2="${height-bottom}"/>`;
  svg += `<circle cx="${xs(state.settings.value)}" cy="${ys(result.expected.first)}" r="4" fill="#80e4df" stroke="#0a1c2b" stroke-width="2"/><circle cx="${xs(state.settings.value)}" cy="${ys(result.expected.second)}" r="4" fill="#f2cd83" stroke="#0a1c2b" stroke-width="2"/>`;
  svg += `<text x="${Math.min(width-15,Math.max(30,xs(state.settings.value)))}" y="13" text-anchor="middle">NOW ${spec.id === "q" ? percent(state.settings.value) : number(state.settings.value)}</text><text class="x-title" x="${(left+width-right)/2}" y="${height-3}" text-anchor="middle">${escapeHTML(spec.label)}</text></svg>`;
  $("#chart").innerHTML = svg;
  $("#chart-legend").innerHTML = result.actions.map((action,index) => `<span><i class="line-key ${index ? "second" : ""}"></i>${escapeHTML(action)}</span>`).join("");
  const threshold = result.threshold;
  if (threshold.kind === "crossing") {
    const where = spec.id === "q" ? percent(threshold.value) : `${number(threshold.value,5)} points`;
    $("#threshold-note").innerHTML = `<span><strong>Equal-payoff point: ≈ ${where}.</strong> Exact value: ${escapeHTML(threshold.exact)}. At that point either move earns the same average points.</span>`;
  } else if (threshold.kind === "all_tie") {
    $("#threshold-note").textContent = "Both choices earn the same average points throughout this range. There is no single switching point.";
  } else {
    $("#threshold-note").innerHTML = `<span><strong>No switch in this range.</strong> ${state.settings.game === "prisoners_dilemma" && state.settings.axis !== "intervention" ? "Defection keeps its individual point advantage throughout strict Prisoner’s Dilemma." : "The same choice earns more average points across the displayed settings."}</span>`;
  }
}
function prepareRound() {
  if (!state.result || state.busy) return;
  const draw = new Uint32Array(1); crypto.getRandomValues(draw);
  state.pending = {opponent:draw[0]/4294967296 < state.result.q ? 0 : 1, inputs:clone(state.settings), result:clone(state.result)};
  state.revealed = false;
}
function setMode(mode) {
  if (!state.result || state.busy) return;
  state.mode = mode; state.revealed = false; state.pending = null;
  if (mode === "play") prepareRound();
  $$('[data-mode]').forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.mode === mode)));
  renderArena();
}
function renderArena() {
  const result = state.result;
  if (!result) return;
  const exploring = state.mode === "explore", own = state.settings.role === "row" ? 0 : 1;
  for (const [index,role] of ["row","column"].entries()) {
    const canChoose = exploring || (own === index && !state.revealed);
    $(`#${role}-actions`).innerHTML = canChoose ? result.actions.map((action,choice) => `<button class="move-button" data-player="${index}" data-choice="${choice}" aria-label="Player ${index+1}: ${escapeHTML(action)}" aria-pressed="${exploring && state.selection[index] === choice}">${escapeHTML(action)}</button>`).join("") : `<span class="sealed">${state.revealed ? "CHOICE REVEALED" : "MOVE SEALED · · ·"}</span>`;
    $(`#${role}-move`).textContent = exploring || state.revealed ? result.actions[state.selection[index]] : own === index ? "Your move?" : "Waiting to reveal";
  }
  $("#stage-caption").innerHTML = exploring ? "ONE SHARED<br>OUTCOME" : state.revealed ? "ROUND<br>REVEALED" : "CHOOSE<br>YOUR MOVE";
  $("#next-round").hidden = exploring || !state.revealed;
  if (exploring || state.revealed) {
    const cell = result.cells.find((c) => c.row === state.selection[0] && c.column === state.selection[1]);
    const detail = cell.pure_equilibrium ? "Neither player gains by switching their move alone." : [0,1].filter((i) => cell.deviation_gain[i ? "column" : "row"] > 0).map((i) => `Player ${i+1} could gain ${number(cell.deviation_gain[i ? "column" : "row"])} by switching alone`).join(". ") + ".";
    const heading = exploring ? "IF YOU BOTH CHOSE THIS…" : `ROUND ${state.history.length} · REVEALED`;
    $("#outcome-strip").innerHTML = `<div><div class="outcome-heading">${heading}</div><p class="outcome-detail">${escapeHTML(detail)}</p></div><div class="outcome-points"><span class="row-text">${number(cell.payoffs[0])}</span><span class="points-separator">/</span><span class="column-text">${number(cell.payoffs[1])}</span></div>`;
  } else {
    $("#outcome-strip").innerHTML = '<div><div class="outcome-heading">TWO CHOICES. REVEALED TOGETHER.</div><p class="outcome-detail">The other move is already drawn. It does not respond to yours.</p></div><div class="outcome-points"><span class="row-text">?</span><span class="points-separator">/</span><span class="column-text">?</span></div>';
  }
  $("#play-instructions").textContent = exploring ? "Choose each player’s move, or click a square in the table. Previews do not add practice rounds." : state.revealed ? "A fresh independent draw next round. The round’s settings are saved in your practice log." : `The other player picks ${result.actions[0]} with a ${percent(result.q)} chance. Choose your move above.`;
  renderMatrix();
  setBusy(state.busy);
}
function playChoice(choice) {
  if (state.busy || !state.pending || state.revealed) return;
  const pending = state.pending, result = pending.result, own = pending.inputs.role === "row" ? 0 : 1;
  state.selection[own] = choice; state.selection[1-own] = pending.opponent;
  const [row,column] = state.selection;
  state.history.push({round:state.history.length+1,recorded_at:new Date().toISOString(),data_status:"ILLUSTRATIVE LOCAL ROUND — NOT RESEARCH DATA",engine_schema_version:result.schema_version,settings:pending.inputs,effective_opponent_first_probability:result.q,actions:result.actions,action_ids:result.action_ids,matrix:result.matrix,params:result.params,baseline:result.baseline,row_choice:row,column_choice:column,row_action:result.actions[row],column_action:result.actions[column],row_points:result.matrix[row][column][0],column_points:result.matrix[row][column][1],opponent_policy:"Independent browser random draw from q, fixed before the user's choice",model_calls:0});
  state.revealed = true; state.pending = null; renderArena(); renderHistory();
}
function renderHistory() {
  $("#history-count").textContent = state.history.length;
  $("#history-list").innerHTML = state.history.length ? state.history.slice(-8).reverse().map((round) => `<div class="history-item"><span class="round-index">${String(round.round).padStart(2,"0")}</span><span>${escapeHTML(state.catalog.games.find((g) => g.id === round.settings.game).title)}<span class="round-moves">${escapeHTML(round.row_action)} / ${escapeHTML(round.column_action)}</span></span><span class="round-points"><span class="row-text">${number(round.row_points)}</span> / ${number(round.column_points)}</span></div>`).join("") : '<p class="empty-history">A little theory. Then a little practice.<br>Play a round to start your log.</p>';
  ["#export-json","#export-csv","#clear-history"].forEach((id) => { $(id).disabled = !state.history.length; });
}
function downloadHistory(format) {
  if (!state.history.length) return;
  const payload = {schema_version:1,data_status:"ILLUSTRATIVE LOCAL ROUNDS — NOT RESEARCH DATA",model_calls:0,exported_at:new Date().toISOString(),rounds:state.history};
  let content;
  if (format === "json") content = JSON.stringify(payload,null,2);
  else {
    const columns=["round","recorded_at","data_status","game","basis","axis","value","q","role","row_action","column_action","row_points","column_points","settings_json","matrix_json","params_json","baseline_json","action_ids_json","opponent_policy","model_calls"];
    const quote = (value) => '"'+String(value).replace(/"/g,'""')+'"';
    content = [columns,...state.history.map((r) => [r.round,r.recorded_at,r.data_status,r.settings.game,r.settings.basis,r.settings.axis,r.settings.value,r.effective_opponent_first_probability,r.settings.role,r.row_action,r.column_action,r.row_points,r.column_points,JSON.stringify(r.settings),JSON.stringify(r.matrix),JSON.stringify(r.params),JSON.stringify(r.baseline),JSON.stringify(r.action_ids),r.opponent_policy,r.model_calls])].map((row) => row.map(quote).join(",")).join("\r\n");
  }
  const url=URL.createObjectURL(new Blob([content],{type:format === "json" ? "application/json" : "text/csv;charset=utf-8"}));
  const link=document.createElement("a"); link.href=url; link.download=`threshold-tide-practice.${format}`;
  document.body.appendChild(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url),30000);
}

$("#game-options").addEventListener("click", (event) => { const button=event.target.closest("[data-game]"); if(button && state.catalog) resetSettings({game:button.dataset.game}); });
$("#basis").addEventListener("change", () => resetSettings({basis:$("#basis").value}));
$("#axis").addEventListener("change", () => resetSettings({axis:$("#axis").value}));
$("#reset-settings").addEventListener("click", () => { if(state.catalog) resetSettings(); });
$("#axis-range").addEventListener("input", () => { if(!state.catalog)return; state.settings.value=Number($("#axis-range").value); updateSliderLabels(); scheduleAnalysis(); });
$("#axis-range").addEventListener("keydown", (event) => {
  if(!state.catalog || !["ArrowLeft","ArrowRight","ArrowUp","ArrowDown"].includes(event.key))return;
  event.preventDefault(); const spec=axisSpec(), direction=["ArrowRight","ArrowUp"].includes(event.key)?1:-1;
  state.settings.value=Number(Math.max(spec.min,Math.min(spec.max,state.settings.value+direction*spec.step)).toFixed(8));
  updateSliderLabels(); scheduleAnalysis();
});
$("#axis-number").addEventListener("change", () => {
  if(!state.catalog)return;
  const field=$("#axis-number"),value=field.valueAsNumber,spec=axisSpec();
  if(!Number.isFinite(value)||value<spec.min||value>spec.max) { field.setCustomValidity(`Choose a number from ${spec.min} to ${spec.max}.`); field.reportValidity(); return; }
  field.setCustomValidity(""); state.settings.value=value; updateSliderLabels(); scheduleAnalysis(true);
});
$("#axis-number").addEventListener("input", () => {
  const field=$("#axis-number"); field.setCustomValidity("");
  if(!state.catalog)return;
  const value=field.valueAsNumber,spec=axisSpec();
  if(!Number.isFinite(value)||value<spec.min||value>spec.max) {
    clearTimeout(analysisTimer); state.request+=1;setBusy(true);return;
  }
  state.settings.value=value;
  $("#axis-range").value=value;
  $("#axis-range").style.setProperty("--fill", `${100*(value-spec.min)/(spec.max-spec.min)}%`);
  $("#axis-range").setAttribute("aria-valuetext", spec.id === "q" ? percent(value) : `${number(value,5)} points`);
  scheduleAnalysis();
});
$("#q-range").addEventListener("input", () => { if(!state.catalog)return; state.settings.q=Number($("#q-range").value); updateSliderLabels(); scheduleAnalysis(); });
$$('[data-role]').forEach((button) => button.addEventListener("click", () => { if(!state.catalog)return; state.settings.role=button.dataset.role; updateRoleButtons(); scheduleAnalysis(true); }));
$$('[data-mode]').forEach((button) => button.addEventListener("click", () => setMode(button.dataset.mode)));
$("#arena").addEventListener("click", (event) => {
  const button=event.target.closest("[data-choice]"); if(!button || state.busy)return;
  const choice=Number(button.dataset.choice);
  if(state.mode === "play")playChoice(choice); else {state.selection[Number(button.dataset.player)]=choice;renderArena();}
});
$("#payoff-matrix").addEventListener("click", (event) => {
  const button=event.target.closest("[data-cell]"); if(!button||state.busy)return;
  state.selection=button.dataset.cell.split(",").map(Number);setMode("explore");
});
$("#next-round").addEventListener("click", () => {prepareRound();renderArena();});
$("#export-json").addEventListener("click", () => downloadHistory("json"));
$("#export-csv").addEventListener("click", () => downloadHistory("csv"));
$("#clear-history").addEventListener("click", () => {state.history=[];renderHistory();if(state.mode==="play"){prepareRound();renderArena();}});
$("#retry").addEventListener("click", () => state.catalog ? analyzeNow() : boot());
$("#help-open").addEventListener("click", () => $("#help-dialog").showModal());
$("#help-close").addEventListener("click", () => $("#help-dialog").close());
$("#help-done").addEventListener("click", () => $("#help-dialog").close());
window.addEventListener("resize", () => { if(state.result)renderChart(); });
boot();
