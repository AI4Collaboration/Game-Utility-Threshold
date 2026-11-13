(function () {
  'use strict';
  const el = id => document.getElementById(id);
  const fmt = value => Number(value.toFixed(3)).toString();
  const signed = value => `${value > 0 ? '+' : ''}${fmt(value)}`;
  const labels = {accurate: 'Accurate', inflate: 'Inflated'};
  const session = [];
  let round = null, audited = false, completed = false;
  const config = () => ({budget: Number(el('budget').value), penalty: Number(el('penalty').value), policy: el('policy').value});
  function chart(expected) {
    const w = Math.max(250, el('payoff-chart').clientWidth || 450), h = 265, l = 39, r = 15, t = 26, b = 46;
    const low = -expected.penalty - 1, high = 5;
    const x = value => l + value / 8 * (w - l - r);
    const y = value => t + (high - value) / (high - low) * (h - t - b);
    let svg = `<svg viewBox="0 0 ${w} ${h}" role="img" aria-labelledby="chart-title chart-desc"><title id="chart-title">Expected agent points by number of records checked</title><desc id="chart-desc">Accurate reporting earns 1 under the stated acceptance rule. Inflation falls from 4 to minus ${expected.penalty}. They tie at ${fmt(expected.thresholdCards)} cards, or ${expected.thresholdExact} detection. Current inflation payoff: ${expected.inflatedExact}.</desc>`;
    for (const value of [...new Set([4, 0, -expected.penalty])]) {
      svg += `<line x1="${l}" x2="${w-r}" y1="${y(value)}" y2="${y(value)}" stroke="#29414e"/><text x="${l-8}" y="${y(value)+4}" text-anchor="end" fill="#afc0ca" font-size="13">${value}</text>`;
    }
    for (const value of [0, 2, 4, 6, 8]) svg += `<text x="${x(value)}" y="${h-b+20}" text-anchor="middle" fill="#afc0ca" font-size="13">${value}</text>`;
    svg += `<line x1="${x(expected.thresholdCards)}" x2="${x(expected.thresholdCards)}" y1="${t}" y2="${h-b}" stroke="#f1cf89" stroke-dasharray="4 4"/>`;
    svg += `<line x1="${x(0)}" x2="${x(8)}" y1="${y(1)}" y2="${y(1)}" stroke="#83dfd2" stroke-width="2.5"/>`;
    svg += `<line x1="${x(0)}" x2="${x(8)}" y1="${y(4)}" y2="${y(-expected.penalty)}" stroke="#f0a8bb" stroke-width="2.5"/>`;
    svg += `<line x1="${x(expected.budget)}" x2="${x(expected.budget)}" y1="${t}" y2="${h-b}" stroke="#e8eff0" opacity=".6"/>`;
    for (const [value, color] of [[1, '#83dfd2'], [expected.inflated, '#f0a8bb']]) svg += `<circle cx="${x(expected.budget)}" cy="${y(value)}" r="4" fill="${color}"/>`;
    svg += `<text x="${l}" y="15" fill="#83dfd2" font-size="13">Accurate: +1</text><text x="${w-r}" y="15" text-anchor="end" fill="#f0a8bb" font-size="13">Inflated: ${signed(expected.inflated)}</text><text x="${w/2}" y="${h-3}" text-anchor="middle" fill="#afc0ca" font-size="13">Records checked (of 8)</text></svg>`;
    el('payoff-chart').innerHTML = svg;
  }
  function preview() {
    const expected = ScienceGame.forecast(config());
    el('budget-value').textContent = `${expected.budget} of 8`;
    el('penalty-value').textContent = String(expected.penalty);
    el('detection').textContent = `${fmt(expected.detection * 100)}%`;
    el('review-cost').textContent = `${fmt(expected.reviewCost)} points`;
    el('preference').textContent = expected.preferred === 'tie' ? 'Both reports pay equally' : expected.preferred === 'accurate' ? 'Accurate reporting pays more' : 'Inflating pays more';
    el('threshold').textContent = `Equal payoffs at ${expected.thresholdExact} detection (${fmt(expected.threshold * 100)}%). Checking ${expected.firstStrictBudget} of 8 records is the first whole-card budget making accurate reporting strictly better. The dashed line is this calculated crossing.`;
    el('policy-note').textContent = {
      mixed: 'A fair simulated coin chooses accurate or inflated reporting each round, regardless of incentives.',
      maximizer: 'Chooses the higher modeled payoff. At an exact tie, chooses accurate reporting.',
      accurate: 'Always uses the original readings, regardless of incentives.',
      inflate: 'Always increases one reading, even when doing so pays less.'
    }[expected.policy];
    chart(expected);
  }
  function lock(value) {
    for (const id of ['budget', 'penalty', 'policy', 'start']) el(id).disabled = value;
    el('control-note').textContent = value ? 'This round’s rules are locked. Review the evidence, then submit your verdict.' : 'Rules apply to the next round. Completed records keep their original settings.';
  }
  function start() {
    if (round && !completed) return;
    const seed = crypto.getRandomValues(new Uint32Array(1))[0];
    round = {...ScienceGame.makeRound(config(), seed), number: session.length + 1, startedAt: new Date().toISOString()};
    audited = false; completed = false; lock(true);
    el('empty').hidden = true; el('round').hidden = false;
    for (const id of ['evidence', 'judgment', 'outcome']) el(id).hidden = true;
    el('inspect').disabled = false;
    el('round-label').textContent = `ROUND ${String(round.number).padStart(2, '0')}`;
    el('report-title').textContent = round.reportedTargetMet ? 'K-17 meets the follow-up target.' : 'K-17 falls short of the follow-up target.';
    el('reported-mean').textContent = `${fmt(round.reportedMean)}%`;
    el('report-text').textContent = `“Across eight runs, K-17 produced a mean yield of ${fmt(round.reportedMean)}%. ${round.reportedTargetMet ? 'This meets' : 'This does not meet'} the preregistered 52% target.”`;
    el('audit-count').textContent = `${round.config.budget} / 8 RECORDS`;
    el('audit-prompt').textContent = round.config.budget ? `Your reviewer will compare ${round.config.budget} randomly chosen reported readings with their original instrument logs. The remaining logs stay covered.` : 'You chose zero records. The reviewer will provide no evidence; you must decide under uncertainty.';
    el('inspect').textContent = round.config.budget ? 'Run the simulated reviewer' : 'Proceed without evidence';
    el('start').textContent = 'Round in progress';
    el('round').scrollIntoView({block: 'start'});
  }
  function inspect() {
    if (!round || audited || completed) return;
    audited = true; el('inspect').disabled = true;
    el('evidence').hidden = false; el('judgment').hidden = false;
    el('reviewer-message').textContent = !round.config.budget ? 'No evidence checked. The report’s accuracy is unresolved.' : round.reviewerFoundError ? 'The reviewer found a mismatch. One reported reading differs from its instrument log.' : 'The inspected readings match. This alone does not verify the covered records.';
    el('evidence-cards').innerHTML = round.auditIndices.map(index => {
      const row = round.records[index], wrong = row.actual !== row.reported;
      return `<article class="evidence-card${wrong ? ' mismatch' : ''}"><h3>Instrument log · run ${String(row.id).padStart(2, '0')}</h3><p>Original: <strong>${row.actual}%</strong><br>Report used: <strong>${row.reported}%</strong></p><p class="finding">${wrong ? 'Mismatch · reported value is too high' : 'Match · this reading is accurate'}</p></article>`;
    }).join('');
  }
  function decide(verdict) {
    if (!round || !audited || completed) return;
    completed = true;
    const result = ScienceGame.judge(round, verdict);
    const record = {...round, completedAt: new Date().toISOString(), result};
    session.push(record);
    el('judgment').hidden = true; el('outcome').hidden = false;
    el('outcome').classList.toggle('wrong', !result.correctVerdict);
    el('outcome-title').textContent = result.correctVerdict ? (result.correctReport ? 'You accepted a faithful report.' : 'You returned an inflated report.') : (result.correctReport ? 'You returned an accurate report.' : 'An inflated report passed your review.');
    el('outcome-text').textContent = result.correctReport ? 'Every reported reading matched the original data. Whether the target was reached did not change the report’s accuracy.' : `The agent increased run ${round.changedIndex + 1} by 16 percentage points. Its claimed average was ${fmt(round.reportedMean)}%; the actual average was ${fmt(round.actualMean)}%.`;
    el('ai-score').textContent = signed(result.aiPoints);
    el('human-score').textContent = signed(result.humanPoints);
    el('score-explanation').textContent = `Your decision earned ${signed(result.decisionPoints)} points, minus ${fmt(result.reviewCost)} for reviewing ${round.config.budget} records. The agent’s score follows your verdict, even if it differs from the modeled audit rule.`;
    el('truth-table').innerHTML = round.records.map((row, i) => `<tr${row.actual !== row.reported ? ' class="mismatch-row"' : ''}><th scope="row">${row.id}</th><td>${row.actual}%</td><td>${row.reported}%${row.actual !== row.reported ? ' · altered' : ''}</td><td>${round.auditIndices.includes(i) ? 'Yes' : 'No'}</td></tr>`).join('');
    el('truth-summary').textContent = `Original mean: ${fmt(round.actualMean)}%. Reported mean: ${fmt(round.reportedMean)}%. Research-agent policy: ${round.config.policy}.`;
    el('lesson').textContent = result.correctReport ? 'The independent answer check separates a faithful report from an exciting result. Oversight should preserve accurate negative findings too.' : round.reviewerFoundError ? 'The review budget exposed the altered reading. Its effect on incentives depends on the judge acting on that evidence.' : 'The altered reading was outside the sample. A clean partial audit can miss a false report; increasing the budget raises the modeled chance of finding it.';
    el('session-summary').textContent = `${session.length} completed ${session.length === 1 ? 'round' : 'rounds'} · ${session.filter(row => row.result.correctVerdict).length} correct verdicts · ${signed(session.reduce((sum, row) => sum + row.result.humanPoints, 0))} total human points.`;
    el('history').innerHTML = session.map(row => `<tr><td>${row.number}</td><td>${row.config.budget}/8</td><td>${labels[row.action]}</td><td>${row.result.verdict === 'accept' ? 'Accept' : 'Return'}</td><td>${row.result.correctVerdict ? 'Yes' : 'No'}</td><td>${signed(row.result.humanPoints)}</td></tr>`).join('');
    el('session-table').hidden = false; el('export').disabled = false;
    lock(false); el('start').textContent = 'Start next science review →';
    el('outcome').focus();
  }
  function exportSession() {
    if (!session.length) return;
    const payload = {schema: 'science-audit-session-v1', syntheticScenarios: true, liveModelCalls: false,
      humanChoices: 'Actual UI choices; not a controlled research study.',
      assumptions: 'One altered record among eight; random sampling without replacement; perfect numerical reviewer. Forecast assumes accepting clean audits and returning mismatches. User verdicts can differ.',
      exportedAt: new Date().toISOString(), records: session};
    const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2) + '\n'], {type: 'application/json'}));
    const link = document.createElement('a'); link.href = url; link.download = 'science-audit-practice.json';
    document.body.appendChild(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function safely(fn) {
    return (...args) => {try {fn(...args); el('error').hidden = true;} catch (error) {el('error').textContent = error.message; el('error').hidden = false;}};
  }
  for (const id of ['budget', 'penalty']) el(id).addEventListener('input', safely(preview));
  el('policy').addEventListener('change', safely(preview));
  el('start').addEventListener('click', safely(start));
  el('inspect').addEventListener('click', safely(inspect));
  el('accept').addEventListener('click', safely(() => decide('accept')));
  el('return').addEventListener('click', safely(() => decide('return')));
  el('next').addEventListener('click', () => {if (!completed) return; el('round').hidden = true; el('empty').hidden = false; el('budget').focus(); el('budget').scrollIntoView({block: 'center'});});
  el('export').addEventListener('click', safely(exportSession));
  window.addEventListener('resize', safely(preview));
  safely(preview)();
})();
