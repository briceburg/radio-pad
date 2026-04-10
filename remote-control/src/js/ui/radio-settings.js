/*
This file is part of the radio-pad project.
https://github.com/briceburg/radio-pad

Copyright (c) 2025 Brice Burgess <https://github.com/briceburg>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.
You should have received a copy of the GNU General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.
*/

import { html } from "lit";
import { RadioElement } from "./radio-element.js";
import { keyed } from "lit/directives/keyed.js";
import { StoreController } from "@nanostores/lit";
import { preferencesStore, registryStore, settingsUiStore } from "../store.js";
import { PREFERENCE_GROUPS } from "../services/preferences.js";
import {
  getRegistryPendingDetail,
  getRegistryPendingTitle,
  isRegistryPending,
} from "./registry-status.js";

const ACCOUNT_GROUP_KEY = "radio-account";

const SETTINGS_SAVE_STATES = {
  idle: { label: "Save", color: null, disabled: false, busy: "false" },
  saving: { label: "Saving...", color: "medium", disabled: true, busy: "true" },
  saved: { label: "Saved", color: "success", disabled: false, busy: "false" },
  error: {
    label: "Retry Save",
    color: "danger",
    disabled: false,
    busy: "false",
  },
};

export function groupPreferencesByGroup(preferences = {}) {
  return Object.entries(preferences).reduce((groups, [key, pref]) => {
    const groupKey = pref.group || "default";
    groups[groupKey] = groups[groupKey] || [];
    groups[groupKey].push({ ...pref, key });
    return groups;
  }, {});
}

export function getVisiblePreferences(preferences = []) {
  return preferences.filter((pref) => {
    if (pref.type !== "select") return true;

    const optionCount = pref.options?.length || 0;
    if (optionCount === 0) return false;
    if (pref.key === "accountId" && optionCount <= 1) return false;
    return true;
  });
}

export function renderRegistryStatus(registryState) {
  if (!isRegistryPending(registryState)) {
    return "";
  }
  const title = getRegistryPendingTitle(registryState);

  return html`
    <ion-item lines="none" class="settings-status-item">
      <ion-icon
        slot="start"
        name="cloud-offline-outline"
        color="warning"
      ></ion-icon>
      <ion-label>
        <ion-text color="warning">
          <h3>${title}</h3>
        </ion-text>
        <p>${getRegistryPendingDetail()}</p>
      </ion-label>
      <ion-spinner slot="end" name="crescent"></ion-spinner>
    </ion-item>
  `;
}

export class RadioSettings extends RadioElement {
  prefsController = new StoreController(this, preferencesStore);
  registryController = new StoreController(this, registryStore);
  uiController = new StoreController(this, settingsUiStore);

  _onChange() {
    if (this.uiController.value.saveState !== "saving") {
      this._emit("settings-edited");
    }
  }

  _onSave() {
    const settingsList = this.querySelector("#settings-list");
    if (!settingsList) return;

    const settingsMap = Object.fromEntries(
      [...settingsList.querySelectorAll("ion-input, ion-select")]
        .map((input) => [input.id?.replace(/^pref-/, ""), input.value])
        .filter(([key]) => key),
    );
    this._emit("settings-save", settingsMap);
  }

  renderInput(pref, value) {
    if (pref.type === "text") {
      // Use string interpolation (attribute) instead of Lit property binding (.value)
      // preventing the component from overriding user drafts when the save state triggers UI re-renders!
      return html`<ion-input
        id="pref-${pref.key}"
        placeholder="${pref.placeholder || ""}"
        value="${value}"
        @ionInput=${() => this._onChange()}
        @ionChange=${() => this._onChange()}
      ></ion-input>`;
    }
    if (pref.type === "select") {
      const options = pref.options || [];
      // Use the 'keyed' directive to force Lit to completely destroy and re-create
      // the Ionic component when options change so it doesn't freeze the slot
      const optionsKey = options.map((o) => o.value).join(",");
      return keyed(
        optionsKey,
        html`
          <ion-select
            id="pref-${pref.key}"
            value="${value}"
            @ionChange=${() => this._onChange()}
          >
            ${options.map(
              (opt) =>
                html`<ion-select-option value="${opt.value}"
                  >${opt.label}</ion-select-option
                >`,
            )}
          </ion-select>
        `,
      );
    }
    return "";
  }

  renderGroupHeader(groupKey, label, icon) {
    return html`
      <ion-item-divider color="tertiary">
        <ion-icon name="${icon}" slot="start"></ion-icon>
        <ion-label>${label}</ion-label>
      </ion-item-divider>
    `;
  }

  renderPreferenceItems(preferences, { lines = "full" } = {}) {
    return preferences.map(
      (pref) => html`
        <ion-item lines=${lines}>
          <ion-label position="stacked" color="tertiary"
            >${pref.label}</ion-label
          >
          ${this.renderInput(pref, pref.value ?? "")}
        </ion-item>
      `,
    );
  }

  renderPreferenceGroup(groupKey, label, icon, preferences) {
    const visiblePrefs = getVisiblePreferences(preferences);

    if (visiblePrefs.length === 0 && groupKey !== ACCOUNT_GROUP_KEY) {
      return "";
    }

    return html`
      <ion-item-group>
        ${this.renderGroupHeader(groupKey, label, icon)}
        ${groupKey === ACCOUNT_GROUP_KEY ? html`<radio-auth></radio-auth>` : ""}
        ${this.renderPreferenceItems(visiblePrefs)}
      </ion-item-group>
    `;
  }

  render() {
    const preferences = this.prefsController.value.definitions || {};
    const registryState = this.registryController.value;
    const saveStateRaw = this.uiController.value.saveState;
    const saveState =
      SETTINGS_SAVE_STATES[saveStateRaw] || SETTINGS_SAVE_STATES.idle;

    const prefByGroup = groupPreferencesByGroup(preferences);

    return html`
      ${renderRegistryStatus(registryState)}
      <ion-list id="settings-list">
        ${Object.entries(PREFERENCE_GROUPS).map(([groupKey, [label, icon]]) =>
          this.renderPreferenceGroup(
            groupKey,
            label,
            icon,
            prefByGroup[groupKey] || [],
          ),
        )}
      </ion-list>
      <ion-button
        exportparts="button"
        id="settings-save-button"
        expand="block"
        color=${saveState.color || "primary"}
        .disabled=${saveState.disabled}
        aria-busy=${saveState.busy}
        data-save-state=${saveStateRaw}
        @click=${() => this._onSave()}
      >
        ${saveState.label}
      </ion-button>
    `;
  }
}

RadioSettings.register("radio-settings");
