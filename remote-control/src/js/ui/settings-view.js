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

import { PREFERENCE_GROUPS } from "../services/preferences.js";
import { html, render } from "lit-html";
import { unsafeHTML } from "lit-html/directives/unsafe-html.js";

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

export class SettingsView {
  constructor(invokeAction, { rootSelector = 'ion-tab[tab="settings"]' } = {}) {
    this.invokeAction = invokeAction;
    this.rootSelector = rootSelector;
    this.saveState = "idle";
  }

  init() {
    this.root =
      typeof this.rootSelector === "string"
        ? document.querySelector(this.rootSelector)
        : this.rootSelector;
    this.saveButton = this.root.querySelector("#settings-save-button");
    this.settingsList = this.root.querySelector("#settings-list");

    ["ionInput", "ionChange"].forEach((event) => {
      this.settingsList.addEventListener(event, () => {
        if (this.saveState !== "saving") this.invokeAction("onSettingsEdited");
      });
    });

    this.setSaveState("idle");
    this.saveButton.addEventListener("click", () =>
      this.invokeAction("onSaveSettings", this.getSettingsMap()),
    );
  }

  getSettingsMap() {
    return Object.fromEntries(
      [...this.settingsList.querySelectorAll("ion-input, ion-select")]
        .map((input) => [input.id?.replace(/^pref-/, ""), input.value])
        .filter(([key]) => key),
    );
  }

  renderPreferences(preferences) {
    // Group preferences
    const prefByGroup = Object.entries(preferences).reduce(
      (acc, [key, pref]) => {
        const g = pref.group || "default";
        acc[g] = acc[g] || [];
        acc[g].push({ ...pref, key });
        return acc;
      },
      {},
    );

    const renderInput = (pref, value) => {
      if (pref.type === "text") {
        // Ionic Web Components are sometimes finicky when Lit binds boolean/string properties aggressively
        // We use string interpolation here so the component mounts exactly as expected.
        return html`<ion-input
          id="pref-${pref.key}"
          placeholder="${pref.placeholder || ""}"
          value="${value}"
        ></ion-input>`;
      }
      if (pref.type === "select") {
        return html`
          <ion-select id="pref-${pref.key}" value="${value}">
            ${(pref.options || []).map(
              (opt) =>
                html`<ion-select-option value="${opt.value}"
                  >${opt.label}</ion-select-option
                >`,
            )}
          </ion-select>
        `;
      }
      return "";
    };

    const template = html`
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

        if (regularPrefs.length === 0 && advancedPrefs.length === 0) return "";

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
                  ${renderInput(pref, pref.value ?? "")}
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
                              ${renderInput(pref, pref.value ?? "")}
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
    `;

    render(template, this.settingsList);
  }

  setSaveState(state = "idle") {
    if (!this.saveButton) return;

    const nextState = SETTINGS_SAVE_STATES[state] || SETTINGS_SAVE_STATES.idle;
    this.saveState = state;

    Object.assign(this.saveButton, {
      textContent: nextState.label,
      disabled: nextState.disabled,
    });
    this.saveButton.setAttribute("aria-busy", nextState.busy);
    this.saveButton.dataset.saveState = state;

    if (nextState.color) this.saveButton.color = nextState.color;
    else this.saveButton.removeAttribute("color");
  }
}
