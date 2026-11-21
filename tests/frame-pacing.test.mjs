import assert from 'node:assert/strict';
import test from 'node:test';
import {createFrameGate} from '../public/vtx-env/frame-pacing.js';

test('phase-aligned caps reach 60 Hz on faster and equal refresh displays', () => {
  for (const refresh of [60, 120, 144, 164]) {
    const due = createFrameGate(1000 / 60);
    let count = 0;
    for (let i = 0; i < refresh * 10; i++) {
      if (due(i * 1000 / refresh + (i % 2 ? -.15 : 0))) count++;
    }
    assert.equal(count, 600, `refresh ${refresh}`);
  }
});

test('the gate skips missed frames and draws one fresh frame after a long pause', () => {
  const due = createFrameGate(1000 / 60);
  assert.equal(due(0), true);
  assert.equal(due(1), false);
  assert.equal(due(3010), true);
  assert.equal(due(3011), false);
  assert.equal(due(3020), true);
  assert.equal(createFrameGate(0)(1), true);
});
