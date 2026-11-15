import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import {test} from 'node:test';

const source = await readFile(new URL('../public/aircraft-selection.js', import.meta.url));
const {knownAircraft, flownEvidence} = await import('data:text/javascript;base64,' + source.toString('base64'));

test('unknown aircraft cannot become the selected mission by default', () => {
  const select = {options: [{value: '', disabled: true}, {value: 'r6', disabled: false}]};
  const view = variant => ({observation: {configuration: {airframe_variant: variant}}});
  assert.equal(knownAircraft(select, view('r6')), true);
  assert.equal(knownAircraft(select, view('phantom-unlisted')), false);
  assert.equal(knownAircraft(select, view('')), false);
  assert.equal(knownAircraft(select, {}), false);
  assert.equal(knownAircraft(select, {...view('r6'), inspection_selection_known:false}), false);
});

test('flown selection reports its recorded environments and limitations', () => {
  const view = {rendering_truth: {provenance: {flight_revision: {
    evidence: [{environment: 'airport', summary: 'Takeoff; later collision', run_id: 'run-1'}],
    limitations: 'Nose mechanism is not shown.',
  }}}};
  assert.match(flownEvidence(view), /airport: Takeoff; later collision \(run-1\)/);
  assert.match(flownEvidence(view), /Nose mechanism is not shown/);
  assert.equal(flownEvidence({}), '');
});
