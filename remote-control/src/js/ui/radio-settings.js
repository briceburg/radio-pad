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
import { keyed } from "lit/directives/keyed.js";
import { StoreController } from "@nanostores/lit";
import { RadioElement } from "./radio-element.js";
import { preferencesStore, settingsUiStore } from "../store.js";
import { PREFERENCE_GROUPS } from "../services/preferences.js";

// Ensure <radio-auth> is registered before this component renders it.
import "./radio-auth.js";

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

export class RadioSettings extends RadioElement {
  prefsController = new StoreController(this, preferencesStore);
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

  _isVisiblePref(pref) {
    if (pref.type !== "select") return true;
    if (!pref.options || pref.options.length === 0) return false;
    if (pref.key === "accountId" && pref.options.length <= 1) return false;
    return true;
  }

  renderInput(pref, value) {
    if (pref.type === "text") {
      // Use string interpolation (attribute) instead of Lit property binding (.value)
      // preventing the component from overriding user drafts when the save state triggers UI re-renders!
      return html`<ion-input
        id="pref-${pref.key}"
        placeholder="${pref.placeholder || ""}"
        value="${value}"
        @ionInput=${this._onChange}
        @ionChange=${this._onChange}
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
            @ionChange=${this._onChange}
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

  renderPrefs(prefs) {
    const regular = prefs.filter((p) => !p.advanced);
    const advanced = prefs.filter((p) => p.advanced);

    return html`
      ${regular.map(
        (pref) => html`
          <ion-item>
            <ion-label position="stacked">${pref.label}</ion-label>
            ${this.renderInput(pref, pref.value ?? "")}
          </ion-item>
        `,
      )}
      ${advanced.length > 0
        ? html`
            <ion-accordion-group>
              <ion-accordion value="advanced">
                <ion-item slot="header">
                  <ion-label>Advanced settings</ion-label>
                </ion-item>
                <div class="ion-padding" slot="content">
                  ${advanced.map(
                    (pref) => html`
                      <ion-item lines="none">
                        <ion-label position="stacked">${pref.label}</ion-label>
                        ${this.renderInput(pref, pref.value ?? "")}
                      </ion-item>
                    `,
                  )}
                </div>
              </ion-accordion>
            </ion-accordion-group>
          `
        : ""}
    `;
  }

  render() {
    const preferences = this.prefsController.value.definitions || {};
    const saveStateRaw = this.uiController.value.saveState;
    const saveState =
      SETTINGS_SAVE_STATES[saveStateRaw] || SETTINGS_SAVE_STATES.idle;

    const prefByGroup = Object.entries(preferences).reduce(
      (acc, [key, pref]) => {
        const g = pref.group || "default";
        acc[g] = acc[g] || [];
        acc[g].push({ ...pref, key });
        return acc;
      },
      {},
    );

    return html`
      <ion-list id="settings-list">
        ${Object.entries(PREFERENCE_GROUPS).map(([groupKey, [label, icon]]) => {
          const prefs = (prefByGroup[groupKey] || []).filter((p) =>
            this._isVisiblePref(p),
          );
          const isAccount = groupKey === "radio-account";

          // Hide non-account groups that have no visible preferences.
          // The account group always renders because it contains auth controls.
          if (!isAccount && prefs.length === 0) return "";

          return html`
            <ion-item-group>
              <ion-item-divider color="tertiary">
                <ion-icon name="${icon}" slot="start"></ion-icon>
                <ion-label>${label}</ion-label>
              </ion-item-divider>
              ${isAccount ? html`<radio-auth></radio-auth>` : ""}
              ${this.renderPrefs(prefs)}
            </ion-item-group>
          `;
        })}
      </ion-list>
      <ion-button
        exportparts="button"
        id="settings-save-button"
        expand="block"
        color=${saveState.color || "primary"}
        .disabled=${saveState.disabled}
        aria-busy=${saveState.busy}
        data-save-state=${saveStateRaw}
        @click=${this._onSave}
      >
        ${saveState.label}
      </ion-button>
    `;
  }
}

RadioSettings.register("radio-settings");
