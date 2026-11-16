import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import {runInNewContext} from 'node:vm';
import {test} from 'node:test';

test('opening the cockpit exposes controls without changing aircraft or environment', async () => {
  const source = await readFile(new URL('../public/startup-flight.js', import.meta.url), 'utf8');
  let selectionWrites = 0, environmentClicks = 0, requests = 0, panelsOpened = 0;
  const aircraft = {addEventListener() {}};
  Object.defineProperty(aircraft, 'value', {get: () => 'r6', set: () => {selectionWrites++;}});
  const elements = {
    'cockpit-workspace': {classList: {contains: () => false}},
    'airframe': aircraft,
    'start': {addEventListener() {}},
    'env-sandbox': {click() {environmentClicks++;}},
  };
  const document = {getElementById: id => elements[id],
    querySelector: () => ({click() {panelsOpened++;}})};
  runInNewContext(source, {document, fetch() {requests++; throw Error('unexpected request');}});
  assert.equal(panelsOpened, 2);
  assert.equal(selectionWrites, 0);
  assert.equal(environmentClicks, 0);
  assert.equal(requests, 0);
});
