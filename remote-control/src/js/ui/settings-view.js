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
  constructor(invokeAction) {
    this.invokeAction = invokeAction;
    this.saveState = "idle";
  }

  init() {
    this.saveButton = document.getElementById("settings-save-button");
    this.settingsList = document.getElementById("settings-list");

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

    this.settingsList.innerHTML = Object.entries(PREFERENCE_GROUPS)
      .map(([groupKey, [label, icon]]) => {
        if (!prefByGroup[groupKey]) return "";

        const itemsHtml = prefByGroup[groupKey]
          .map((pref) => {
            const value = pref.value ?? "";
            let inputHtml = "";

            if (pref.type === "text") {
              inputHtml = `<ion-input id="pref-${pref.key}" placeholder="${pref.placeholder || ""}" value="${value}"></ion-input>`;
            } else if (pref.type === "select") {
              const optionsHtml = (pref.options || [])
                .map(
                  (opt) =>
                    `<ion-select-option value="${opt.value}">${opt.label}</ion-select-option>`,
                )
                .join("");
              inputHtml = `<ion-select id="pref-${pref.key}" value="${value}">${optionsHtml}</ion-select>`;
            }

            return `
          <ion-item>
            <ion-label position="stacked">${pref.label}</ion-label>
            ${inputHtml}
          </ion-item>
        `;
          })
          .join("");

        return `
        <ion-item-group>
          <ion-item-divider color="tertiary">
            <ion-icon name="${icon}" slot="start"></ion-icon>
            <ion-label>${label}</ion-label>
          </ion-item-divider>
          ${itemsHtml}
        </ion-item-group>
      `;
      })
      .join("");
  }

  setSaveState(state = "idle") {
    if (!this.saveButton) return;

    const nextState = SETTINGS_SAVE_STATES[state] || SETTINGS_SAVE_STATES.idle;
    this.saveState = state;

    Object.assign(this.saveButton, {
      innerText: nextState.label,
      disabled: nextState.disabled,
    });
    this.saveButton.setAttribute("aria-busy", nextState.busy);
    this.saveButton.dataset.saveState = state;

    if (nextState.color) this.saveButton.color = nextState.color;
    else this.saveButton.removeAttribute("color");
  }
}
