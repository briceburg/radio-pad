import { Preferences } from '@capacitor/preferences';

export const preferencesConfig = [
  {
    key: 'registryUrl',
    label: 'Registry URL',
    placeholder: 'Enter registry URL',
    type: 'text',
  },
  {
    key: 'playerId',
    label: 'Player',
    type: 'select', // custom type for ion-select
    options: [],    // will be populated dynamically
  },
  // Add more preferences here as needed
];

export class PreferencesManager {
  constructor(config, listId, saveButtonId, onChange) {
    this.config = config;
    this.listId = listId;
    this.saveButtonId = saveButtonId;
    this.inputs = {};
    this.onChange = onChange; // callback for preference changes
  }

  async render() {
    const settingsList = document.getElementById(this.listId);
    settingsList.innerHTML = '';

    for (const pref of this.config) {
      const item = document.createElement('ion-item');
      const label = document.createElement('ion-label');
      label.setAttribute('position', 'stacked');
      label.innerText = pref.label;

      let input;
      if (pref.type === 'select') {
        input = document.createElement('ion-select');
        input.setAttribute('id', `settings-${pref.key}`);
        // Populate options dynamically if any
        if (pref.options && pref.options.length > 0) {
          for (const option of pref.options) {
            const optionElement = document.createElement('ion-select-option');
            optionElement.value = option.value;
            optionElement.innerText = option.label;
            input.appendChild(optionElement);
          }
        }
      } else {
        input = document.createElement('ion-input');
        input.setAttribute('id', `settings-${pref.key}`);
        input.setAttribute('placeholder', pref.placeholder);
        input.setAttribute('type', pref.type);
      }

      // Load saved value
      const result = await Preferences.get({ key: pref.key });
      if (result.value) {
        input.value = result.value;
      }

      item.appendChild(label);
      item.appendChild(input);
      settingsList.appendChild(item);

      this.inputs[pref.key] = input;
    }

    this._setupSaveListener();
  }

  _setupSaveListener() {
    const saveButton = document.getElementById(this.saveButtonId);
    const newSaveButton = saveButton.cloneNode(true);
    saveButton.parentNode.replaceChild(newSaveButton, saveButton);

    newSaveButton.addEventListener('click', async () => {
      await this.saveAll();
    });
  }

  async saveAll() {
    for (const pref of this.config) {
      const input = this.inputs[pref.key];
      if (input && input.value) {
        // URL validation for registryUrl
        if (pref.key === 'registryUrl' && !this._isValidUrl(input.value)) {
          alert('Please enter a valid Registry URL (must start with http:// or https://)');
          continue;
        }
        await Preferences.set({ key: pref.key, value: input.value });
        console.log(`Saved ${pref.key}: ${input.value}`);
        if (this.onChange) {
          this.onChange(pref.key, input.value);
        }
      }
    }
  }

  _isValidUrl(url) {
    try {
      const parsed = new URL(url);
      return parsed.protocol === 'http:' || parsed.protocol === 'https:';
    } catch (e) {
      return false;
    }
  }

  async get(key) {
    const result = await Preferences.get({ key });
    return result.value;
  }

  getInputValue(key) {
    return this.inputs[key]?.value;
  }
}
