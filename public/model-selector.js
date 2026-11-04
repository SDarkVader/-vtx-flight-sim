const dialog = document.getElementById('model-selector-dialog');
const choices = document.getElementById('model-choice');
const confirm = document.getElementById('model-choice-confirm');
const airframe = document.getElementById('airframe');
const status = document.getElementById('model-choice-status');
let selectedVariant = airframe.value;

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

document.getElementById('models').addEventListener('click', () => openSelector(true));
document.getElementById('model-choice-cancel').addEventListener('click', () => dialog.close());
confirm.addEventListener('click', () => {
  if (confirm.disabled || airframe.disabled) return;
  airframe.value = selectedVariant;
  airframe.dispatchEvent(new Event('change', { bubbles: true }));
  const title = airframe.selectedOptions[0].textContent.split(' · ')[0];
  document.getElementById('start').firstChild.textContent = `New ${title} mission `;
  dialog.close();
  document.querySelector('.mission-panel').scrollIntoView({ behavior: 'smooth', block: 'start' });
});
openSelector(false);
