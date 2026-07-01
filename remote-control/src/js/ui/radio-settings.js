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
import { preferencesStore, settingsUiStore } from "../store.js";
import { PREFERENCE_GROUPS } from "../services/preferences.js";

const ACCOUNT_GROUP_KEY = "radio-account";
const ADVANCED_GROUP_KEY = "radio-advanced";
const ACCOUNT_DEPENDENT_KEYS = new Set(["playerId", "radioDial"]);
const EMPTY_OPTION_MESSAGES = {
  playerId: "No players are available for this account.",
  radioDial: "No RadioDials are available for this account.",
};

const SETTINGS_SAVE_STATES = {
  idle: { label: "Save", color: null, disabled: false, busy: "false" },
  saving: { label: "Saving…", color: "medium", disabled: true, busy: "true" },
  saved: { label: "Saved", color: "success", disabled: false, busy: "false" },
  error: {
    label: "Retry save",
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

function hasOwn(object, key) {
  return Object.prototype.hasOwnProperty.call(object, key);
}

export function preferenceValues(preferences, draftValues = {}) {
  return Object.fromEntries(
    Object.entries(preferences).map(([key, pref]) => [
      key,
      hasOwn(draftValues, key) ? draftValues[key] : (pref.value ?? ""),
    ]),
  );
}

function hasPreferenceChanges(preferences, values) {
  return Object.entries(values).some(
    ([key, value]) => value !== (preferences[key]?.value ?? ""),
  );
}

export class RadioSettings extends RadioElement {
  prefsController = new StoreController(this, preferencesStore);
  uiController = new StoreController(this, settingsUiStore);
  draftValues = {};
  previousSaveState = undefined;
  advancedExpanded = false;

  willUpdate() {
    const saveState = this.uiController.value.saveState;
    if (saveState === "saved" && this.previousSaveState !== "saved") {
      this.draftValues = {};
    }
    this.previousSaveState = saveState;
  }

  _onChange(pref, event) {
    this.draftValues = {
      ...this.draftValues,
      [pref.key]: event.detail?.value ?? event.target?.value ?? "",
    };
    this.requestUpdate();

    if (this.uiController.value.saveState !== "saving") {
      this._emit("settings-edited");
    }
  }

  _onSave() {
    const preferences = this.prefsController.value.definitions || {};
    const values = preferenceValues(preferences, this.draftValues);
    if (!hasPreferenceChanges(preferences, values)) return;

    this._emit("settings-save", values);
  }

  _toggleAdvanced() {
    this.advancedExpanded = !this.advancedExpanded;
    this.requestUpdate();
  }

  _onAdvancedKeydown(event) {
    if (!["Enter", " "].includes(event.key)) return;
    event.preventDefault();
    this._toggleAdvanced();
  }

  renderInput(pref, value) {
    if (pref.type === "text") {
      return html`<ion-input
        id="pref-${pref.key}"
        placeholder="${pref.placeholder || ""}"
        .value=${value}
        .disabled=${this.uiController.value.saveState === "saving"}
        @ionInput=${(event) => this._onChange(pref, event)}
        @ionChange=${(event) => this._onChange(pref, event)}
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
            .value=${value}
            .disabled=${this.uiController.value.saveState === "saving"}
            @ionChange=${(event) => this._onChange(pref, event)}
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
    const advanced = groupKey === ADVANCED_GROUP_KEY;
    return html`
      <ion-item-divider
        id=${advanced ? "advanced-toggle" : null}
        class=${advanced ? "settings-group-toggle" : null}
        color="tertiary"
        role=${advanced ? "button" : null}
        tabindex=${advanced ? "0" : null}
        aria-controls=${advanced ? `settings-group-${groupKey}` : null}
        aria-expanded=${advanced ? String(this.advancedExpanded) : null}
        aria-label=${advanced
          ? `${this.advancedExpanded ? "Hide" : "Show"} Advanced settings`
          : null}
        @click=${advanced ? () => this._toggleAdvanced() : null}
        @keydown=${advanced ? (event) => this._onAdvancedKeydown(event) : null}
      >
        <ion-icon name="${icon}" slot="start"></ion-icon>
        <ion-label>${label}</ion-label>
        ${advanced
          ? html`
              <span slot="end">${this.advancedExpanded ? "Hide" : "Show"}</span>
              <ion-icon
                slot="end"
                name=${this.advancedExpanded
                  ? "chevron-down"
                  : "chevron-forward"}
              ></ion-icon>
            `
          : ""}
      </ion-item-divider>
    `;
  }

  renderPreferenceItems(preferences, values) {
    return preferences.map(
      (pref) => html`
        <ion-item lines="full">
          <ion-label position="stacked" color="tertiary"
            >${pref.label}</ion-label
          >
          ${this.renderInput(pref, values[pref.key])}
        </ion-item>
      `,
    );
  }

  renderPreferenceGroup(
    groupKey,
    label,
    icon,
    preferences,
    values,
    accountChangePending,
  ) {
    const visiblePrefs = getVisiblePreferences(preferences).filter(
      (pref) => !accountChangePending || !ACCOUNT_DEPENDENT_KEYS.has(pref.key),
    );
    const emptyPreference =
      !accountChangePending && values.accountId
        ? preferences.find(
            (pref) =>
              EMPTY_OPTION_MESSAGES[pref.key] &&
              (pref.options?.length || 0) === 0,
          )
        : null;

    if (
      visiblePrefs.length === 0 &&
      groupKey !== ACCOUNT_GROUP_KEY &&
      !emptyPreference
    ) {
      return "";
    }

    const groupCollapsed =
      groupKey === ADVANCED_GROUP_KEY && !this.advancedExpanded;
    const content = html`
      ${this.renderPreferenceItems(visiblePrefs, values)}
      ${emptyPreference
        ? html`
            <ion-item
              id="empty-${emptyPreference.key}"
              lines="none"
              color="light"
            >
              <ion-label color="medium">
                ${EMPTY_OPTION_MESSAGES[emptyPreference.key]}
              </ion-label>
            </ion-item>
          `
        : ""}
    `;

    return html`
      <ion-item-group>
        ${this.renderGroupHeader(groupKey, label, icon)}
        ${groupKey === ACCOUNT_GROUP_KEY ? html`<radio-auth></radio-auth>` : ""}
        ${groupKey === ADVANCED_GROUP_KEY
          ? html`<div id="settings-group-${groupKey}" ?hidden=${groupCollapsed}>
              ${content}
            </div>`
          : content}
        ${groupKey === ACCOUNT_GROUP_KEY && accountChangePending
          ? html`
              <ion-item id="account-save-required" lines="none" color="light">
                <ion-icon name="information-circle" slot="start"></ion-icon>
                <ion-label class="ion-text-wrap">
                  <h3>Save this account change</h3>
                  <p>
                    Player and RadioDial options will refresh after saving. Your
                    current player stays active until then.
                  </p>
                </ion-label>
              </ion-item>
            `
          : ""}
      </ion-item-group>
    `;
  }

  render() {
    const preferences = this.prefsController.value.definitions || {};
    const saveStateRaw = this.uiController.value.saveState;
    const saveState =
      SETTINGS_SAVE_STATES[saveStateRaw] || SETTINGS_SAVE_STATES.idle;
    const values = preferenceValues(preferences, this.draftValues);
    const hasChanges = hasPreferenceChanges(preferences, values);
    const accountChangePending =
      values.accountId !== (preferences.accountId?.value ?? "");

    const prefByGroup = groupPreferencesByGroup(preferences);

    return html`
      <ion-list id="settings-list">
        ${Object.entries(PREFERENCE_GROUPS).map(([groupKey, [label, icon]]) =>
          this.renderPreferenceGroup(
            groupKey,
            label,
            icon,
            prefByGroup[groupKey] || [],
            values,
            accountChangePending,
          ),
        )}
      </ion-list>
      <ion-button
        exportparts="button"
        id="settings-save-button"
        expand="block"
        color=${saveState.color || "primary"}
        .disabled=${saveState.disabled || !hasChanges}
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
