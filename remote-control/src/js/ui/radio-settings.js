/*
This file is part of the radio-pad project.
*/

import { LitElement, html } from "lit";
import { keyed } from "lit/directives/keyed.js";
import { StoreController } from "@nanostores/lit";
import { preferencesStore, settingsUiStore } from "../store.js";
import { PREFERENCE_GROUPS } from "../services/preferences.js";

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

export class RadioSettings extends LitElement {
  prefsController = new StoreController(this, preferencesStore);
  uiController = new StoreController(this, settingsUiStore);

  createRenderRoot() {
    return this;
  }

  _onChange() {
    if (this.uiController.value.saveState !== "saving") {
      this.dispatchEvent(
        new CustomEvent("settings-edited", { bubbles: true, composed: true }),
      );
    }
  }

  _onSave() {
    const settingsList = this.querySelector("#settings-list");
    const settingsMap = Object.fromEntries(
      [...settingsList.querySelectorAll("ion-input, ion-select")]
        .map((input) => [input.id?.replace(/^pref-/, ""), input.value])
        .filter(([key]) => key),
    );
    this.dispatchEvent(
      new CustomEvent("settings-save", {
        bubbles: true,
        composed: true,
        detail: settingsMap,
      }),
    );
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
      return keyed(
        options.length,
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
          const prefs = prefByGroup[groupKey];
          if (!prefs) return "";

          const visiblePrefs = prefs.filter((p) => {
            if (p.type !== "select") return true;
            if (!p.options || p.options.length === 0) return false;
            if (p.key === "accountId" && p.options.length <= 1) return false;
            return true;
          });

          if (visiblePrefs.length === 0) return "";

          const advancedPrefs = visiblePrefs.filter((p) => p.advanced);
          const regularPrefs = visiblePrefs.filter((p) => !p.advanced);

          if (regularPrefs.length === 0 && advancedPrefs.length === 0)
            return "";

          return html`
            <ion-item-group>
              ${groupKey === "radio-account"
                ? ""
                : html`
                    <ion-item-divider color="tertiary">
                      <ion-icon name="${icon}" slot="start"></ion-icon>
                      <ion-label>${label}</ion-label>
                    </ion-item-divider>
                  `}
              ${regularPrefs.map(
                (pref) => html`
                  <ion-item>
                    <ion-label position="stacked">${pref.label}</ion-label>
                    ${this.renderInput(pref, pref.value ?? "")}
                  </ion-item>
                `,
              )}
              ${advancedPrefs.length > 0
                ? html`
                    <ion-accordion-group>
                      <ion-accordion value="advanced">
                        <ion-item slot="header">
                          <ion-label>Advanced settings</ion-label>
                        </ion-item>
                        <div class="ion-padding" slot="content">
                          ${advancedPrefs.map(
                            (pref) => html`
                              <ion-item lines="none">
                                <ion-label position="stacked"
                                  >${pref.label}</ion-label
                                >
                                ${this.renderInput(pref, pref.value ?? "")}
                              </ion-item>
                            `,
                          )}
                        </div>
                      </ion-accordion>
                    </ion-accordion-group>
                  `
                : ""}
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

customElements.define("radio-settings", RadioSettings);
