// Replay never substitutes the current aircraft for a recorded one.
export function replayFrameAsset(frame, context) {
  const v = context?.visual, p = frame?.provenance;
  if (!v || v.status !== 'server-asset-matches-record' || !p) return null;
  return (frame.variant === undefined || frame.variant === v.variant) && p.airframe_variant === v.variant &&
    p.model_xml_sha256 === v.model_xml_sha256 && (p.config_sha256 ?? null) === v.config_sha256 &&
    p.render_asset === v.render_asset ? v.render_asset : null;
}

// Recorded physical fuel is explicitly in kg. Sensor clearance, speed and
// vertical speed are not present in every physics snapshot: never use live values.
export function replayCockpitReadings(frame) {
  const fuel = frame?.fuel_kg;
  return {altitude:'—', verticalSpeed:'—', speed:'—',
    fuel:Array.isArray(fuel) && fuel.length && fuel.every(Number.isFinite)
      ? fuel.reduce((a, b) => a + b, 0).toFixed(1) : '—'};
}
