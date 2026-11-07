const dialog = document.getElementById('model-selector-dialog');
const choices = document.getElementById('model-choice');
const confirm = document.getElementById('model-choice-confirm');
const airframe = document.getElementById('airframe');
const status = document.getElementById('model-choice-status');
let selectedVariant = airframe.value;
let loadedVariant = airframe.value;

// Build clickable choices from the mission form's authoritative model list.
function renderChoices() {
  choices.replaceChildren();
  for (const option of airframe.options) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'model-choice-card';
    button.textContent = option.textContent;
    button.setAttribute('aria-pressed', String(option.value === selectedVariant));
    button.addEventListener('click', () => {
      selectedVariant = option.value;
      for (const card of choices.children) {
        card.setAttribute('aria-pressed', String(card === button));
      }
    });
    choices.append(button);
  }
}

async function openSelector(showWhenActive = true) {
  try {
    const response = await fetch('/api/view', { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const view = await response.json();
    if (view.active) {
      if (!showWhenActive) return;
      status.textContent = `Run ${view.run_id} is active. End and retain it before selecting another vehicle.`;
      confirm.disabled = true;
      choices.hidden = true;
    } else {
      status.textContent = '';
      confirm.disabled = false;
      choices.hidden = false;
      const actual = view.observation?.configuration?.airframe_variant;
      if (actual && [...airframe.options].some(option => option.value === actual)) {
        airframe.value = actual;
        loadedVariant = actual;
        const title = airframe.selectedOptions[0].textContent.split(' Â· ')[0];
        document.getElementById('start').firstChild.textContent = `New ${title} mission `;
      }
      selectedVariant = airframe.value;
      renderChoices();
    }
    if (!dialog.open) dialog.showModal();
  } catch (error) {
    status.textContent = `Model status unavailable: ${error.message}`;
    confirm.disabled = true;
    if (showWhenActive && !dialog.open) dialog.showModal();
  }
}

document.getElementById('models').addEventListener('click', () => { document.getElementById('airframe').focus(); document.getElementById('airframe').scrollIntoView({block:'center',behavior:'smooth'}); });
document.getElementById('model-choice-cancel').addEventListener('click', () => dialog.close());
async function applyPreview(variant) {
  const response = await fetch('/api/model-preview', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ airframe_variant: variant, start_configuration: document.getElementById('phantom-start').value, departure: document.getElementById('dep').value.split(',').map(Number) }),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || `HTTP ${response.status}`);
  airframe.value = variant;
  loadedVariant = variant;
  const title = airframe.selectedOptions[0].textContent.split(' Â· ')[0];
  document.getElementById('start').firstChild.textContent = `New ${title} mission `;
  return result;
}

confirm.addEventListener('click', async () => {
  if (confirm.disabled || airframe.disabled) return;
  confirm.disabled = true;
  status.textContent = 'Loading vehicle and controlsâ€¦';
  try {
    await applyPreview(selectedVariant);
    dialog.close();
    document.querySelector('.mission-panel').scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (error) {
    status.textContent = error.message;
  } finally {
    confirm.disabled = false;
  }
});
airframe.addEventListener('change', async () => {
  const variant = airframe.value;
  try {
    await applyPreview(variant);
  } catch (error) {
    airframe.value = loadedVariant;
    status.textContent = error.message;
    status.textContent = error.message;
  }
});
// The existing LOWER FRAME selector is the sole vehicle selector.


// Keep idle inspection in the selected physical starting configuration.
document.getElementById('phantom-start').addEventListener('change', async () => {
  if (!airframe.value.startsWith('phantom') || airframe.disabled) return;
  const selector = document.getElementById('phantom-start');
  selector.disabled = true;
  try { await applyPreview(airframe.value); }
  catch (error) { status.textContent = error.message; }
  finally { selector.disabled = false; }
});

document.addEventListener('vtx-preview-start', async () => {
  if (airframe.disabled) return;
  try { await applyPreview(airframe.value); }
  catch (error) { document.getElementById('validation').textContent = error.message; }
});
