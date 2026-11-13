/* A small synthetic science audit game. No model, network, or training calls.
 * Integer payoff comparisons keep ties exact. A seeded generator makes each
 * example replayable; the probability model assumes a uniform audit subset.
 */
(function (root) {
  'use strict';
  const RUNS = 8;
  const POLICIES = ['mixed', 'maximizer', 'accurate', 'inflate'];
  function integer(value, low, high, name) {
    if (!Number.isInteger(value) || value < low || value > high) throw new Error(`Invalid ${name}.`);
    return value;
  }
  function settings(input) {
    const budget = integer(input.budget, 0, RUNS, 'review budget');
    const penalty = integer(input.penalty, 0, 12, 'penalty');
    if (!POLICIES.includes(input.policy)) throw new Error('Unknown research-agent policy.');
    return {budget, penalty, policy: input.policy};
  }
  function fraction(n, d) {
    let a = Math.abs(n), b = d;
    while (b) { const rest = a % b; a = b; b = rest; }
    return d / a === 1 ? String(n / a) : `${n / a}/${d / a}`;
  }
  function forecast(input) {
    const config = settings(input), {budget, penalty} = config;
    // Eight times the inflation payoff: 4*(8-k) - penalty*k.
    const inflatedNumerator = 4 * RUNS - (4 + penalty) * budget;
    const marginNumerator = RUNS - inflatedNumerator;
    const strictBudgets = Array.from({length: RUNS + 1}, (_, k) => k)
      .filter(k => RUNS > 4 * RUNS - (4 + penalty) * k);
    return {...config, detection: budget / RUNS, detectionExact: fraction(budget, RUNS),
      accurate: 1, inflated: inflatedNumerator / RUNS,
      inflatedExact: fraction(inflatedNumerator, RUNS), margin: marginNumerator / RUNS,
      preferred: marginNumerator > 0 ? 'accurate' : marginNumerator < 0 ? 'inflate' : 'tie',
      threshold: 3 / (4 + penalty), thresholdExact: fraction(3, 4 + penalty),
      thresholdCards: 3 * RUNS / (4 + penalty), firstStrictBudget: strictBudgets[0],
      reviewCost: budget / 4};
  }
  function generator(seed) {
    let state = seed || 0x9e3779b9;
    function next() {
      state ^= state << 13; state ^= state >>> 17; state ^= state << 5;
      return state >>> 0;
    }
    return limit => {
      const ceiling = Math.floor(0x100000000 / limit) * limit;
      let value;
      do { value = next(); } while (value >= ceiling);
      return value % limit;
    };
  }
  function makeRound(input, seed) {
    const config = settings(input), expected = forecast(config);
    integer(seed, 0, 0xffffffff, 'seed');
    const random = generator(seed);
    const action = config.policy === 'mixed' ? (random(2) ? 'inflate' : 'accurate') :
      config.policy === 'maximizer' ? (expected.preferred === 'inflate' ? 'inflate' : 'accurate') : config.policy;
    const changedIndex = action === 'inflate' ? random(RUNS) : null;
    const records = Array.from({length: RUNS}, (_, index) => {
      const actual = 47 + random(8);
      return {id: index + 1, actual, reported: actual + (index === changedIndex ? 16 : 0)};
    });
    const order = Array.from({length: RUNS}, (_, i) => i);
    for (let i = order.length - 1; i > 0; i--) {
      const j = random(i + 1); [order[i], order[j]] = [order[j], order[i]];
    }
    const auditIndices = order.slice(0, config.budget);
    const actualMean = records.reduce((sum, row) => sum + row.actual, 0) / RUNS;
    const reportedMean = records.reduce((sum, row) => sum + row.reported, 0) / RUNS;
    return {schema: 'science-audit-round-v1', syntheticScenario: true, agentMode: 'simulated',
      seed, config, expected, action, changedIndex, records, auditIndices,
      actualMean, reportedMean, reportedTargetMet: reportedMean >= 52,
      reviewerFoundError: auditIndices.some(i => records[i].actual !== records[i].reported)};
  }
  function judge(round, verdict) {
    if (!['accept', 'return'].includes(verdict)) throw new Error('Choose accept or return.');
    const correctReport = round.action === 'accurate', accepted = verdict === 'accept';
    const aiPoints = correctReport ? (accepted ? 1 : 0) : (accepted ? 4 : -round.config.penalty);
    const decisionPoints = correctReport ? (accepted ? 3 : -2) : (accepted ? -6 : 2);
    return {verdict, correctReport, correctVerdict: correctReport === accepted,
      aiPoints, decisionPoints, reviewCost: round.config.budget / 4,
      humanPoints: decisionPoints - round.config.budget / 4};
  }
  const engine = Object.freeze({RUNS, POLICIES, forecast, makeRound, judge});
  root.ScienceGame = engine;
  if (typeof module !== 'undefined' && module.exports) module.exports = engine;
})(globalThis);
