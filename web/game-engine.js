/* Browser counterpart of gut/game.py, gut/canonical.py, gut/oversight.py and
 * serve.py's JSON adapters. Decisions use reduced BigInt fractions throughout;
 * Number conversions are only for displayed values and plot coordinates.
 * tests/check_browser_engine.cjs compares these outputs with Python directly.
 */
(function (root) {
  'use strict';

  function gcd(a, b) {
    a = a < 0n ? -a : a; b = b < 0n ? -b : b;
    while (b) { const rest = a % b; a = b; b = rest; }
    return a;
  }
  class Fraction {
    constructor(n, d = 1n) {
      n = BigInt(n); d = BigInt(d);
      if (!d) throw new Error('Division by zero.');
      if (d < 0n) { n = -n; d = -d; }
      const common = gcd(n, d);
      this.n = n / common; this.d = d / common;
    }
    add(b) { return new Fraction(this.n*b.d + b.n*this.d, this.d*b.d); }
    sub(b) { return new Fraction(this.n*b.d - b.n*this.d, this.d*b.d); }
    mul(b) { return new Fraction(this.n*b.n, this.d*b.d); }
    div(b) { return new Fraction(this.n*b.d, this.d*b.n); }
    neg() { return new Fraction(-this.n, this.d); }
    cmp(b) { const value = this.n*b.d - b.n*this.d; return value > 0n ? 1 : value < 0n ? -1 : 0; }
    toString() { return this.d === 1n ? String(this.n) : `${this.n}/${this.d}`; }
    value() { return Number(this.n) / Number(this.d); }
  }
  const F = (n, d = 1) => new Fraction(n, d);
  const ZERO = F(0), ONE = F(1);
  const max = (...items) => items.reduce((a, b) => a.cmp(b) >= 0 ? a : b);
  const min = (...items) => items.reduce((a, b) => a.cmp(b) <= 0 ? a : b);
  const uniqueSorted = items => [...new Map(items.map(v => [v.toString(), v])).values()].sort((a, b) => a.cmp(b));
  const record = value => ({exact: value.toString(), value: value.value()});
  function serialize(value, exact = true) {
    if (value instanceof Fraction) return exact ? record(value) : value.value();
    if (Array.isArray(value)) return value.map(item => serialize(item, exact));
    if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, serialize(item, exact)]));
    return value;
  }

  function queryValues(query, expected, message) {
    const result = Object.create(null);
    // Repeated URL keys remain an error instead of silently selecting a value.
    const entries = query instanceof URLSearchParams ? query.entries() : Object.entries(query || {});
    for (const [key, raw] of entries) {
      if (Object.hasOwn(result, key) || !expected.includes(key)) throw new Error(message);
      if (Array.isArray(raw)) {
        if (raw.length !== 1) throw new Error(message);
        result[key] = String(raw[0]);
      } else result[key] = String(raw);
    }
    if (Object.keys(result).length !== expected.length) throw new Error(message);
    return result;
  }
  function number(text, low, high) {
    if (text.length > 32) throw new Error('Use a short decimal number.');
    const cleaned = text.trim().replaceAll('_', '');
    const parts = /^([+-]?)(?:(\d+)(?:\.(\d*))?|\.(\d+))(?:[eE]([+-]?\d+))?$/.exec(cleaned);
    if (!parts) throw new Error('Enter a finite decimal number.');
    const fraction = parts[3] || parts[4] || '';
    const exponent = Number(parts[5] || 0) - fraction.length;
    if (!Number.isSafeInteger(exponent) || exponent < -12 || exponent > 12) throw new Error('Use at most 12 decimal places.');
    let numerator = BigInt((parts[2] || '0') + fraction);
    if (parts[1] === '-') numerator = -numerator;
    const value = exponent >= 0 ? F(numerator * 10n**BigInt(exponent)) : F(numerator, 10n**BigInt(-exponent));
    if (value.cmp(low) < 0 || value.cmp(high) > 0) throw new Error(`Value must be between ${low.value()} and ${high.value()}.`);
    return value;
  }

  const REGIONS = {
    defection_dominant: ['Defection pays against either action', "This is the strict Prisoner's Dilemma region."],
    cooperation_dominant: ['Cooperation pays against either action', 'Both conditional thresholds have been crossed.'],
    chicken: ['Chicken: opposite actions pay', 'Cooperate against D; defect against C.'],
    stag_hunt: ['Stag Hunt: matching actions pay', 'Cooperate against C; defect against D.'],
    boundary: ['At a threshold', 'At least one comparison is an exact tie. Both actions are optimal in that comparison.'],
  };
  const symmetric = (t, s) => [[[ONE, ONE], [s, t]], [[t, s], [ZERO, ZERO]]];
  const penalized = (matrix, cost) => matrix.map((row, i) => row.map((cell, j) => [cell[0].sub(cost.mul(F(i))), cell[1].sub(cost.mul(F(j)))]));
  function analyze(query) {
    const input = queryValues(query, ['s', 't', 'z'], 'Supply exactly one s, t and z.');
    const s = number(input.s, F(-10), F(-1, 1000)), t = number(input.t, F(1001, 1000), F(10)), z = number(input.z, ZERO, F(20));
    const thresholds = [t.sub(ONE), s.neg()];
    const margins = cost => [ONE.sub(t).add(cost), s.add(cost)];
    const maximum = max(F(3, 2), max(...thresholds).mul(F(13, 10)), z.mul(F(11, 10)));
    const coordinates = uniqueSorted([...Array.from({length: 61}, (_, i) => maximum.mul(F(i, 60))), ...thresholds, z]);
    const series = [['against_c', 'Against C'], ['against_d', 'Against D']].map(([key, label], i) => ({key, label, points: coordinates.map(x => ({x: x.value(), y: margins(x)[i].value()}))}));
    const values = series.flatMap(line => line.points.map(p => p.y)), pad = Math.max((Math.max(...values)-Math.min(...values))*.12, .1);
    const signs = margins(z).map(m => m.cmp(ZERO));
    const region = signs.includes(0) ? 'boundary' : signs[0] < 0 ? (signs[1] < 0 ? 'defection_dominant' : 'chicken') : (signs[1] < 0 ? 'stag_hunt' : 'cooperation_dominant');
    const [label, description] = REGIONS[region];
    return {
      inputs: {s: s.value(), t: t.value(), z: z.value()},
      matrices: serialize({baseline: symmetric(t, s), adjusted: penalized(symmetric(t, s), z)}, false),
      margins: Object.fromEntries(['against_c', 'against_d'].map((key, i) => [key, {...record(margins(z)[i]), response: signs[i] > 0 ? 'cooperate' : signs[i] < 0 ? 'defect' : 'tie'}])),
      thresholds: {against_c: record(thresholds[0]), against_d: record(thresholds[1])},
      region: {label, description},
      plot: {x_min: 0, x_max: maximum.value(), y_min: Math.min(...values)-pad, y_max: Math.max(...values)+pad, series},
    };
  }

  const EXAMPLES = {
    pd: {name: "Prisoner's Dilemma", actions: ['C', 'D'], baseline: symmetric(F(2), F(-1, 2)), description: 'At baseline, D pays more against either action. The cost can change that.'},
    stag_hunt: {name: 'Stag Hunt', actions: ['C', 'D'], baseline: symmetric(F(1, 2), F(-1, 2)), description: 'At baseline, matching pays: C against C, D against D. Both prefer mutual C to mutual D.'},
    chicken: {name: 'Chicken', actions: ['C', 'D'], baseline: symmetric(F(3, 2), F(1, 2)), description: 'At baseline, opposite actions pay: D against C, C against D. Mutual D is worst.'},
    battle_of_sexes: {name: 'Battle of the Sexes', actions: ['X', 'Y'], baseline: [[[F(2), ONE], [ZERO, ZERO]], [[ZERO, ZERO], [ONE, F(2)]]], description: 'Both want to match, but the row player prefers XX and the column player prefers YY. The shared cost of Y favors X; neither action is called defection.'},
  };
  function canonicalState(query) {
    const input = queryValues(query, ['game', 'z'], 'Supply exactly one game and z.');
    if (!Object.hasOwn(EXAMPLES, input.game)) throw new Error(`unknown game: ${input.game}`);
    const game = EXAMPLES[input.game], z = number(input.z, ZERO, F(20));
    const adjusted = penalized(game.baseline, z);
    const margins = (matrix, role) => role === 'row' ? [0, 1].map(j => matrix[0][j][0].sub(matrix[1][j][0])) : [0, 1].map(j => matrix[j][0][1].sub(matrix[j][1][1]));
    const comparisons = [], thresholds = [];
    for (const role of ['row', 'column']) {
      const current = margins(adjusted, role), roots = margins(game.baseline, role).map(v => v.neg());
      roots.forEach((threshold, i) => {
        thresholds.push(threshold);
        comparisons.push({role, against: game.actions[i], margin: current[i].toString(), value: current[i].value(), threshold: threshold.toString(), tie_at: threshold.value(), best: current[i].cmp(ZERO) > 0 ? game.actions[0] : current[i].cmp(ZERO) < 0 ? game.actions[1] : 'tie'});
      });
    }
    const maximum = max(F(3, 2), z.mul(F(11, 10)), ...thresholds.map(t => t.mul(F(6, 5))));
    const lines = comparisons.map(row => ({role: row.role, against: row.against, start: -row.tie_at, end: maximum.value()-row.tie_at}));
    const values = lines.flatMap(line => [line.start, line.end]);
    const rowMargins = margins(adjusted, 'row'), columnMargins = margins(adjusted, 'column'), stable = [];
    for (let i = 0; i < 2; i++) for (let j = 0; j < 2; j++) {
      if (rowMargins[j].mul(F(1-2*i)).cmp(ZERO) >= 0 && columnMargins[i].mul(F(1-2*j)).cmp(ZERO) >= 0) stable.push(game.actions[i]+game.actions[j]);
    }
    const exactMatrix = matrix => matrix.map(row => row.map(cell => cell.map(v => v.toString())));
    return {name: game.name, actions: [...game.actions], description: game.description, z: z.value(),
      baseline: serialize(game.baseline, false), adjusted: serialize(adjusted, false), comparisons,
      baseline_exact: exactMatrix(game.baseline), adjusted_exact: exactMatrix(adjusted), stable_outcomes: stable,
      plot: {xmax: maximum.value(), ymin: Math.min(...values)-.2, ymax: Math.max(...values)+.2, lines}};
  }

  const ACTIONS = ['cooperate', 'attack'];
  const DEFENSES = Array.from({length: 11}, (_, i) => F(i, 10));
  const PARAMETERS = ['v', 'r', 'a', 'p', 'b', 'w', 'h', 'c'];
  function oversightInputs(query, simulation = false) {
    const keys = [...PARAMETERS, 'd', ...(simulation ? ['baseline', 'tie', 'scope'] : [])];
    const input = queryValues(query, keys, 'Supply exactly one value for each oversight input.');
    const parameters = Object.fromEntries(PARAMETERS.map(key => [key, number(input[key], ZERO, F(1000))]));
    const d = number(input.d, ZERO, ONE);
    if (!DEFENSES.some(value => value.cmp(d) === 0)) throw new Error('Choose defense 0, 0.1, …, 1 (eleven available levels).');
    return {input, game: new Oversight(parameters), d};
  }
  class Oversight {
    constructor(parameters) { this.parameters = parameters; Object.assign(this, parameters); }
    payoff(d, action) {
      if (action === 'cooperate') return [this.w.sub(this.c.mul(d)), this.b];
      return [this.h.mul(ONE.sub(d)).neg().sub(this.c.mul(d)), this.v.mul(this.r).mul(ONE.sub(d)).sub(this.a).sub(this.p.mul(d))];
    }
    margin(d) { return this.b.sub(this.payoff(d, 'attack')[1]); }
    best(d) { const sign = this.margin(d).cmp(ZERO); return sign > 0 ? ['cooperate'] : sign < 0 ? ['attack'] : [...ACTIONS]; }
    thresholds(d) {
      const vr = this.v.mul(this.r), residual = vr.mul(ONE.sub(d));
      const specifications = {
        d: [this.b.add(this.a).sub(vr), vr.add(this.p), ONE],
        v: [this.b.add(this.a).add(this.p.mul(d)), this.r.mul(ONE.sub(d)).neg(), null],
        a: [this.b.add(this.p.mul(d)).sub(residual), ONE, null],
        p: [this.b.add(this.a).sub(residual), d, null],
      };
      return Object.fromEntries(Object.entries(specifications).map(([key, [intercept, slope, upper]]) => {
        const sign = slope.cmp(ZERO), root = sign ? intercept.neg().div(slope) : null;
        return [key, {root, intercept, slope,
          in_domain: root !== null && root.cmp(ZERO) >= 0 && (upper === null || root.cmp(upper) <= 0),
          cooperate_when: sign > 0 ? 'above' : sign < 0 ? 'below' : intercept.cmp(ZERO) > 0 ? 'always' : intercept.cmp(ZERO) < 0 ? 'never' : 'always_tied'}];
      }));
    }
    equilibria() {
      const best = DEFENSES.map(d => this.best(d));
      const payoffs = DEFENSES.map(d => Object.fromEntries(ACTIONS.map(action => [action, this.payoff(d, action)])));
      const outcome = (i, action) => ({d: DEFENSES[i], action, human: payoffs[i][action][0], ai: payoffs[i][action][1]});
      const enumerate = credible => {
        const results = [];
        DEFENSES.forEach((d, i) => best[i].forEach(action => {
          const human = payoffs[i][action][0];
          const allowed = DEFENSES.map((other, j) => j === i ? [action] : (credible ? best[j] : ACTIONS).filter(a => payoffs[j][a][0].cmp(human) <= 0));
          if (allowed.every(a => a.length)) results.push({...outcome(i, action), responses: allowed,
            witness: allowed.map(a => a[0]), strategy_count: allowed.reduce((count, a) => count*a.length, 1)});
        }));
        return results;
      };
      const commitment = optimistic => {
        const candidates = [];
        DEFENSES.forEach((d, i) => {
          const score = (optimistic ? max : min)(...best[i].map(a => payoffs[i][a][0]));
          best[i].filter(a => payoffs[i][a][0].cmp(score) === 0).forEach(a => candidates.push(outcome(i, a)));
        });
        const optimum = max(...candidates.map(row => row.human));
        return candidates.filter(row => row.human.cmp(optimum) === 0);
      };
      return {defenses: DEFENSES, nash: enumerate(false), subgame_perfect: enumerate(true),
        stackelberg_favorable: commitment(true), stackelberg_unfavorable: commitment(false)};
    }
  }
  function oversightState(query) {
    const {game, d} = oversightInputs(query), thresholds = game.thresholds(d);
    const points = uniqueSorted([...DEFENSES, ...(thresholds.d.in_domain ? [thresholds.d.root] : [])]);
    const curve = points.map(x => ({d: x, human_c: game.payoff(x, 'cooperate')[0], human_a: game.payoff(x, 'attack')[0],
      ai_c: game.b, ai_a: game.payoff(x, 'attack')[1], margin: game.margin(x), best: game.best(x)}));
    const vmax = max(F(10), game.v.mul(F(6, 5))), pmax = max(F(10), game.p.mul(F(6, 5))), cells = [];
    for (let j = 0; j < 21; j++) for (let i = 0; i < 21; i++) {
      const v = vmax.mul(F(i, 20)), p = pmax.mul(F(j, 20));
      const alternative = new Oversight({...game.parameters, v, p});
      cells.push({i, j, v, p, margin: alternative.margin(d), best: alternative.best(d)});
    }
    return serialize({parameters: game.parameters, d,
      selected: {cooperate: game.payoff(d, 'cooperate'), attack: game.payoff(d, 'attack'), margin: game.margin(d), best: game.best(d)},
      thresholds, first_strict_defense: DEFENSES.find(x => game.margin(x).cmp(ZERO) > 0) || null,
      first_weak_defense: DEFENSES.find(x => game.margin(x).cmp(ZERO) >= 0) || null,
      equilibria: game.equilibria(), curve, map: {vmax, pmax, cells}});
  }
  function oversightSimulation(query) {
    const {input, game, d} = oversightInputs(query, true);
    if (!['selected', 'all'].includes(input.scope)) throw new Error('Choose selected or all defense levels.');
    if (!['always_cooperate', 'always_attack', 'payoff_maximizer'].includes(input.baseline)) throw new Error('Unknown baseline.');
    if (!ACTIONS.includes(input.tie)) throw new Error('Choose cooperate or attack for exact ties.');
    const records = (input.scope === 'selected' ? [d] : DEFENSES).map((defense, i) => {
      const best = game.best(defense), action = input.baseline === 'always_cooperate' ? 'cooperate' : input.baseline === 'always_attack' ? 'attack' : best.length === 1 ? best[0] : input.tie;
      const [human, ai] = game.payoff(defense, action);
      return {round: i+1, d: defense, action, human, ai, best_responses: best, is_best_response: best.includes(action),
        ai_regret: max(...ACTIONS.map(a => game.payoff(defense, a)[1])).sub(ai),
        remaining_harm: action === 'attack' ? game.h.mul(ONE.sub(defense)) : ZERO};
    });
    return serialize({schema: 'oversight-toy-v1', synthetic: true,
      description: 'Independent deterministic toy rounds; no learning, randomness or LLM calls.',
      parameters: game.parameters, selected_defense: d, scope: input.scope, baseline: input.baseline, tie_action: input.tie, records,
      summary: {rounds: records.length, cooperate_count: records.filter(row => row.action === 'cooperate').length,
        mean_human: records.reduce((sum, row) => sum.add(row.human), ZERO).div(F(records.length)),
        mean_ai: records.reduce((sum, row) => sum.add(row.ai), ZERO).div(F(records.length))}});
  }

  const engine = Object.freeze({analyze, canonicalState, oversightState, oversightSimulation});
  root.GutEngine = engine;
  if (typeof module !== 'undefined' && module.exports) module.exports = engine;
})(globalThis);
