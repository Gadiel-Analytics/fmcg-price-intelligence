const {test} = require('node:test');
const assert = require('node:assert/strict');
const {state} = require('../assets/freshness.js');
test('stale history stays overdue even if the page is rebuilt today', () => {
  const now = Date.parse('2026-10-27T15:00:00Z');
  assert.equal(state('2026-10-20', 2, now).stale, true);
  assert.equal(state('2026-10-26', 2, now).stale, false);
  assert.equal(state('2026-10-28', 2, now).stale, true);
  assert.equal(state('bad-date', 2, now).stale, true);
});
