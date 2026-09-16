import {test} from 'node:test';
import assert from 'node:assert/strict';
import {screenDpr, performanceBounds} from './renderQuality.js';

test('high-density phones start sharp and have a bounded GPU pixel budget', () => {
  assert.equal(screenDpr(2), 2);
  assert.equal(screenDpr(3), 2.5);
  assert.equal(screenDpr(4), 2.5);
});

test('performance reductions retain a sharp floor and can recover', () => {
  const declining = [1, .75, .5, .25, 0].map(quality => screenDpr(3, quality));
  assert.deepEqual(declining, [2.5, 2.25, 2, 1.75, 1.5]);
  assert.equal(screenDpr(3, -1), 1.5);
  assert.equal(screenDpr(3, 2), 2.5);
  assert.equal(screenDpr(3, 1), declining[0]);
});

test('standard and fractional-density displays are never forced to supersample', () => {
  for (const native of [.8, 1, 1.25, 1.5]) {
    assert.equal(screenDpr(native, 0), native);
    assert.equal(screenDpr(native, 1), native);
  }
  for (const invalid of [undefined, NaN, Infinity, 0, -1]) {
    assert.equal(screenDpr(invalid), 1);
  }
});

test('a 60 fps scene can recover on both 60 Hz and 120 Hz displays', () => {
  for (const refreshRate of [60, 90, 120]) {
    const [lower, upper] = performanceBounds(refreshRate);
    assert.ok(40 < lower);
    assert.ok(60 >= upper);
    assert.ok(lower < 50 && 50 < upper);
  }
});
