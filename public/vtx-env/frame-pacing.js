export function createFrameGate(intervalMs) {
  if (!(intervalMs > 0)) return () => true;
  let nextFrame;
  // Display callbacks can land slightly before the nominal refresh boundary.
  const tolerance = Math.min(.35, intervalMs / 10);
  return now => {
    nextFrame ??= now;
    const elapsed = now + tolerance - nextFrame;
    if (elapsed < 0) return false;
    nextFrame += (Math.floor(elapsed / intervalMs) + 1) * intervalMs;
    return true;
  };
}
