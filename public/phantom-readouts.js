// Keep missing telemetry visibly distinct from a valid zero.
export function renderReadout(item, value, {unit='', digits=2, title='Actual position'} = {}) {
  const valid = value != null && value !== '' && Number.isFinite(Number(value));
  if (item.tagName === 'METER') {
    item.hidden = !valid;
    if (valid) item.value = Number(value);
  } else {
    item.title = valid ? title : 'Unavailable';
    item.textContent = valid ? Number(value).toFixed(digits) + unit : '—';
  }
}
