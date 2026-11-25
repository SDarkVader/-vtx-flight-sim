import assert from 'node:assert/strict';
import {detents,isAudio,stepTrack,titleOf,turnBetween} from '../public/vtx-env/cockpit-radio.js';

assert.equal(stepTrack(0,-1,15),14);
assert.equal(stepTrack(14,1,15),0);
assert.equal(stepTrack(3,-20,15),13);
assert.equal(stepTrack(-1,1,0),-1);
assert.equal(titleOf('Where_Iron_Ends.mp3'),'Where Iron Ends');
assert.ok(isAudio({name:'a.MP3'}));
assert.ok(!isAudio({name:'lyrics.md'}));
assert.equal(detents(29),0);
assert.equal(detents(-65),-2);
assert.equal(turnBetween(170,-170),20);
assert.equal(turnBetween(-170,170),-20);
