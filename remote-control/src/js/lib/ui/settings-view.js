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
  saving: {
    label: "Saving...",
    color: "medium",
    disabled: true,
    busy: "true",
  },
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
    this.saveButton = null;
    this.settingsList = null;
  }

  init() {
    this.saveButton = document.getElementById("settings-save-button");
    this.settingsList = document.getElementById("settings-list");

    for (const eventName of ["ionInput", "ionChange"]) {
      this.settingsList.addEventListener(eventName, () => {
        if (this.saveState !== "saving") {
          this.invokeAction("onSettingsEdited");
        }
      });
    }

    this.setSaveState("idle");
    this.saveButton.addEventListener("click", () => {
      this.invokeAction("onSaveSettings", this.getSettingsMap());
    });
  }

  getSettingsMap() {
    return Object.fromEntries(
      [...this.settingsList.querySelectorAll("ion-input, ion-select")]
        .map((input) => [input.id?.replace(/^pref-/, ""), input.value])
        .filter(([key]) => key),
    );
  }

  renderPreferences(preferences) {
    this.settingsList.innerHTML = "";
    const groups = {};

    for (const [groupKey, [label, icon]] of Object.entries(PREFERENCE_GROUPS)) {
      const group = document.createElement("ion-item-group");
      group.innerHTML = `<ion-item-divider color="tertiary"><ion-icon name="${icon}" slot="start"></ion-icon><ion-label>${label}</ion-label></ion-item-divider>`;
      this.settingsList.appendChild(group);
      groups[groupKey] = group;
    }

    for (const [key, pref] of Object.entries(preferences)) {
      const item = document.createElement("ion-item");
      const label = document.createElement("ion-label");
      label.setAttribute("position", "stacked");
      label.innerText = pref.label;

      let input;
      switch (pref.type) {
        case "text":
          input = document.createElement("ion-input");
          input.setAttribute("placeholder", pref.placeholder || "");
          break;
        case "select":
          input = document.createElement("ion-select");
          if (pref.options?.length) {
            this._populateSelectOptions(input, pref.options);
          }
          break;
      }

      input.id = `pref-${key}`;
      input.value = pref.value;
      item.appendChild(label);
      item.appendChild(input);
      groups[pref.group || "default"].appendChild(item);
    }
  }

  setSaveState(state = "idle") {
    if (!this.saveButton) {
      return;
    }

    const nextState = SETTINGS_SAVE_STATES[state] || SETTINGS_SAVE_STATES.idle;
    this.saveState = state;
    this.saveButton.innerText = nextState.label;
    this.saveButton.disabled = nextState.disabled;
    this.saveButton.setAttribute("aria-busy", nextState.busy);
    this.saveButton.dataset.saveState = state;
    if (nextState.color) {
      this.saveButton.color = nextState.color;
    } else {
      this.saveButton.removeAttribute("color");
    }
  }

  _populateSelectOptions(input, options) {
    input.innerHTML = "";
    for (const option of options) {
      const optionElement = document.createElement("ion-select-option");
      optionElement.value = option.value;
      optionElement.innerText = option.label;
      input.appendChild(optionElement);
    }
  }
}
