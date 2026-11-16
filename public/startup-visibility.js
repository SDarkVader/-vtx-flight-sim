// Only reveal a newly rendered frame when its physical position is known.
export function startupFrameReady({worldReady, offline, physicalPosition, transition, view}) {
  if (!worldReady) return false;
  if (offline && !transition) return true;
  if (!physicalPosition) return false;
  return !transition || !!(view?.active && view.run_id && view.run_id !== transition.previousRunId);
}
