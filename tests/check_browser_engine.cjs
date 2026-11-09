/* Compare the actual dependency-free browser engine against Python's reference
 * adapters, including exact ties, degenerate equilibria and invalid inputs.
 * Run: node tests/check_browser_engine.cjs (optionally set PYTHON).
 */
'use strict';
const assert = require('node:assert/strict');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const engine = require('../web/game-engine.js');

const python = spawnSync(process.env.PYTHON || 'python3', [path.join(__dirname, 'browser_engine_fixtures.py')], {
  encoding: 'utf8', maxBuffer: 64*1024*1024,
});
assert.equal(python.status, 0, python.stderr || String(python.error));
const cases = JSON.parse(python.stdout);
function compare(actual, expected, where) {
  if (typeof expected === 'number') {
    assert.equal(typeof actual, 'number', where);
    assert.ok(Number.isFinite(actual), where);
    // Fractions and decision labels are compared exactly below. Numeric plot
    // coordinates can differ by the final IEEE-754 rounding operation.
    const tolerance = 2e-13*Math.max(1, Math.abs(expected));
    assert.ok(Math.abs(actual-expected) <= tolerance, `${where}: ${actual} != ${expected}`);
  } else if (Array.isArray(expected)) {
    assert.ok(Array.isArray(actual), where);
    assert.equal(actual.length, expected.length, `${where}.length`);
    expected.forEach((item, i) => compare(actual[i], item, `${where}[${i}]`));
  } else if (expected !== null && typeof expected === 'object') {
    assert.ok(actual && typeof actual === 'object', where);
    assert.deepEqual(Object.keys(actual).sort(), Object.keys(expected).sort(), `${where}.keys`);
    for (const key of Object.keys(expected)) compare(actual[key], expected[key], `${where}.${key}`);
  } else assert.equal(actual, expected, where);
}
let valid = 0, invalid = 0;
for (const test of cases) {
  const query = new URLSearchParams(test.query);
  if (test.invalid) {
    assert.throws(() => engine[test.method](query), undefined, test.name);
    invalid++;
  } else {
    compare(engine[test.method](query), test.expected, test.name);
    // Public object input follows the same path, including parse_qs arrays.
    compare(engine[test.method](Object.fromEntries(test.query)), test.expected, `${test.name}/object`);
    compare(engine[test.method](Object.fromEntries(test.query.map(([k, v]) => [k, [v]]))), test.expected, `${test.name}/arrays`);
    valid++;
  }
}
assert.throws(() => engine.canonicalState({game: ['pd', 'chicken'], z: ['0']}));
assert.equal(globalThis.GutEngine, engine);
console.log(`Browser engine parity passed: ${valid} valid reference cases (three input forms), ${invalid} invalid cases; exact fractions, decisions, equilibria and exports match Python.`);
