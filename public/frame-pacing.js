// Use the browser's display clock. Keep fractional frame intervals so small
// timing differences do not cost an entire refresh.
export function createFrameGate(maxFps) {
  const intervalMs = 1000 / maxFps;
  let deadlineMs = -Infinity;
  return (timestampMs) => {
    if (timestampMs + 0.25 < deadlineMs) return false;
    deadlineMs += intervalMs;
    if (deadlineMs <= timestampMs) deadlineMs = timestampMs + intervalMs;
    return true;
  };
}
