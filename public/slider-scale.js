export function addSliderScale(input, format = value => String(value)) {
  const min = Number(input.min), max = Number(input.max), step = Number(input.step);
  const doc = input.ownerDocument;
  const scale = doc.createElement('span');
  scale.className = 'slider-scale';
  scale.setAttribute('aria-hidden', 'true');
  const steps = Math.round((max - min) / step);
  const intervals = Math.min(4, steps);
  for (let i = 0; i <= intervals; i++) {
    const value = i === intervals ? max : Number((min + Math.round(i * steps / intervals) * step).toFixed(4));
    const tick = doc.createElement('span');
    tick.style.left = `${100 * (value - min) / (max - min)}%`;
    tick.textContent = format(value);
    scale.appendChild(tick);
  }
  input.after(scale);
}
