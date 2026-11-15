export function knownAircraft(select, view) {
  const variant = view?.observation?.configuration?.airframe_variant;
  return view?.inspection_selection_known !== false && typeof variant === 'string' && variant !== '' &&
    Array.from(select.options).some(option => !option.disabled && option.value === variant);
}

export function flownEvidence(view) {
  const revision = view?.rendering_truth?.provenance?.flight_revision;
  if (!revision) return '';
  const records = (revision.evidence || []).map(item =>
    `${item.environment}: ${item.summary} (${item.run_id})`).join(' · ');
  return [records, revision.limitations, 'Details: Engineering and Flight records.'].filter(Boolean).join(' ');
}
