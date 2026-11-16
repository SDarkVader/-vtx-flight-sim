// Commands are patches: unrelated values must remain held by the plant.
export function createPatchQueue() {
  let queued = {}, epoch = 0;
  return {
    add(patch) { Object.assign(queued, structuredClone(patch)); },
    take() { const ticket = {patch: queued, epoch}; queued = {}; return ticket; },
    retry(ticket) { if (ticket.epoch === epoch) queued = {...ticket.patch, ...queued}; },
    discard(fields) { for (const field of fields) delete queued[field]; },
    clear() { queued = {}; epoch++; },
    get dirty() { return Object.keys(queued).length > 0; },
  };
}

export function editArrayCommand(current, observed, index, value, count) {
  const source = Array.isArray(current) ? current : Array.isArray(observed) ? observed : Array(count).fill(0);
  const next = [...source];
  next[index] = value;
  return next;
}
