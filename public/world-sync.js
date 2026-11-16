// A world response is usable only for the environment in the latest view.
export function worldMatches(world, expected) {
  return !!world && !!expected && typeof expected.key === 'string' &&
    world.environment === expected.key && world.id === expected.id && world.version === expected.version &&
    Number.isSafeInteger(expected.seed) && world.seed === expected.seed &&
    typeof expected.displayed_world_sha256 === 'string' && /^[0-9a-f]{64}$/.test(expected.displayed_world_sha256) &&
    world.displayed_world_sha256 === expected.displayed_world_sha256;
}

export function createWorldSynchronizer({getExpected, getRendered, fetchWorld, applyWorld, setUnavailable, now = () => Date.now(), retryMs = 1000}) {
  let pending = false, retryAfter = 0;
  return {
    reconcile() {
      const expected = getExpected();
      if (worldMatches(getRendered(), expected)) { setUnavailable(false); return; }
      setUnavailable(true);
      if (!expected?.key || pending || now() < retryAfter) return;
      pending = true;
      Promise.resolve().then(fetchWorld).then(world => {
        // A response can arrive after a second environment change.
        if (!worldMatches(world, getExpected())) return;
        applyWorld(world);
        setUnavailable(!worldMatches(getRendered(), getExpected()));
        retryAfter = 0;
      }).catch(() => { retryAfter = now() + retryMs; }).finally(() => { pending = false; });
    },
  };
}
