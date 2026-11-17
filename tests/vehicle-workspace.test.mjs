import assert from 'node:assert/strict';
import {createVehicleWorkspace} from '../public/vehicle-workspace.js';

function element() {
  return {dataset: {}, children: [], listeners: {}, append(...items) {this.children.push(...items);}, prepend(item) {this.children.unshift(item);},
    addEventListener(name, fn) {this.listeners[name] = fn;}, setAttribute(key, value) {this[key] = value;}};
}
const host = element(), argon = element(), phantom = element(), boat = element();
host.append(argon, phantom);
const changes = [], actions = [];
const workspace = createVehicleWorkspace({host, harbourPanel: boat, document: {createElement: element},
  onAircraft: () => actions.push('aircraft'), onHarbour: () => actions.push('harbour'), onChange: value => changes.push(value)});
assert.equal(workspace.aircraftInput, true);
workspace.show('boat');
assert.equal(workspace.aircraftInput, false); assert.equal(host.dataset.vehicleControls, 'boat');
assert.equal(argon.inert, true); assert.equal(phantom.inert, true); assert.equal(boat.inert, false);
workspace.show('passenger'); assert.equal(boat.inert, true); assert.equal(workspace.aircraftInput, false);
workspace.show('aircraft'); assert.equal(argon.inert, false); assert.equal(phantom.inert, false); assert.equal(boat.inert, true);
assert.deepEqual(changes, ['boat', 'passenger', 'aircraft']);
for (const button of host.children[0].children) button.listeners.click();
assert.deepEqual(actions, ['aircraft', 'harbour']);
assert.throws(() => workspace.show('unknown'));
