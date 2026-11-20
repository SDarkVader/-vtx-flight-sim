import assert from 'node:assert/strict';
import {test} from 'node:test';
import {createFrameGate} from '../public/frame-pacing.js';

function framesInSecond(refreshHz, maxFps) {
  const allowsFrame = createFrameGate(maxFps);
  return Array.from({length: refreshHz}, (_, index) => index * 1000 / refreshHz).filter(allowsFrame).length;
}

test('desktop reaches 60 draws per second across common display rates', () => {
  for (const refreshHz of [60, 90, 120, 144, 240]) {
    assert.equal(framesInSecond(refreshHz, 60), 60);
  }
  assert.equal(framesInSecond(30, 60), 30);
});

test('fractional intervals hold the light view at 15 draws per second', () => {
  assert.equal(framesInSecond(60, 15), 15);
  assert.equal(framesInSecond(144, 15), 15);
});

test('a long stall draws one frame when the browser resumes', () => {
  const allowsFrame = createFrameGate(60);
  assert.equal(allowsFrame(0), true);
  assert.equal(allowsFrame(3000), true);
  assert.equal(allowsFrame(3000), false);
  assert.equal(allowsFrame(3000 + 1000 / 60), true);
});
