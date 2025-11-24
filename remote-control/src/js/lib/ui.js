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

import { EventEmitter } from "./interfaces.js";
import { RegistryRequestError } from "./error-utils.js";

export class RadioPadUI extends EventEmitter {
  constructor() {
    super();
    this.tabs = {}; // map of tab name to { element, refs, stationButtons }
    this._toast = null;
  }

  init() {
    this._settingsSaveButton = document.getElementById("settings-save-button");
    this._toast = document.getElementById("global-toast");

    // Initialize tabs
    ["control", "listen"].forEach((tabName) => this._initPlayerTab(tabName));

    this._settingsSaveButton.addEventListener("click", async () => {
      const settingsMap = {};
      document
        .querySelectorAll("#settings-list ion-input, #settings-list ion-select")
        .forEach((input) => {
          const key = input.id?.replace(/^pref-/, "");
          if (key) settingsMap[key] = input.value;
        });
      this.emitEvent("settings-save", settingsMap);
    });
  }

  _initPlayerTab(tabName) {
    const tabEl = document.querySelector(`ion-tab[tab="${tabName}"]`);
    const template = document.getElementById("tab-player");
    if (!template || !tabEl) return;

    const clone = template.content.cloneNode(true);
    tabEl.appendChild(clone);

    const refs = {
      stationsName: tabEl.querySelector(".stations-name"),
      nowPlaying: tabEl.querySelector(".now-playing"),
      stopButton: tabEl.querySelector(".stop-button"),
      radioInfo: tabEl.querySelector(".radio-info"),
      stationGrid: tabEl.querySelector(".station-grid"),
    };

    this.tabs[tabName] = {
      element: tabEl,
      refs,
      stationButtons: {},
      setInfo: (msg) => {
        if (refs.radioInfo) refs.radioInfo.innerText = msg;
      },
      setNowPlaying: (stationName = null) => {
        if (refs.nowPlaying) refs.nowPlaying.innerText = stationName || "...";
        if (refs.stopButton) refs.stopButton.disabled = !stationName;
      },
    };

    this.showStationsLoading(tabName);

    refs.stopButton.addEventListener("click", () => {
      this.emitEvent("click-stop", { tab: tabName });
    });
  }

  getTab(tabName) {
    return this.tabs[tabName] || null;
  }

  setTabInfo(message, tabName = "control") {
    this.getTab(tabName)?.setInfo?.(message);
  }

  async showError({
    summary,
    error = null,
    tab = "control",
    toastColor = "warning",
  }) {
    const detailText = this._formatError(error);
    const message = detailText ? `${summary} ${detailText}`.trim() : summary;
    this.setTabInfo(message, tab);
    await this.toast(message, { color: toastColor });
  }

  async showRegistryError(summary, error, options = {}) {
    const registryDetail = RegistryRequestError.format(error);
    await this.showError({
      summary,
      error: { message: registryDetail },
      ...options,
    });
  }

  async toast(message, { color = "tertiary", duration = 3000 } = {}) {
    if (!this._toast) return;
    this._toast.message = message;
    this._toast.duration = duration;
    this._toast.color = color;
    await this._toast.present();
  }

  async toastWarning(message) {
    await this.toast(message, { color: "warning" });
  }

  async toastSuccess(message) {
    await this.toast(message, { color: "success" });
  }

  renderPreferences(preferences) {
    const settingsList = document.getElementById("settings-list");
    settingsList.innerHTML = "";
    const groups = {
      default: {
        label: "Primary Settings",
        icon: "settings",
        color: "tertiary",
      },
      "radio-control": {
        label: "Control Settings",
        icon: "radio",
        color: "tertiary",
      },
      "radio-listen": {
        label: "Listen Settings",
        icon: "headset",
        color: "tertiary",
      },
    };

    for (const [groupKey, { label, icon, color }] of Object.entries(groups)) {
      const group = document.createElement("ion-item-group");
      group.innerHTML = `<ion-item-divider color="${color}"><ion-icon name="${icon}" slot="start"></ion-icon><ion-label>${label}</ion-label></ion-item-divider>`;
      settingsList.appendChild(group);
      groups[groupKey].element = group;
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
          if (pref.options && pref.options.length > 0) {
            this._populateSelectOptions(input, pref.options);
          }
          break;
      }
      input.id = `pref-${key}`;
      input.value = pref.value;
      item.appendChild(label);
      item.appendChild(input);
      groups[pref.group || "default"].element.appendChild(item);
    }
  }

  renderStations(station_data, tabName = "control") {
    const tab = this.tabs[tabName];
    if (!tab) return;

    tab.stationButtons = {};
    tab.refs.stationGrid.innerHTML = "";

    let ionRow;
    station_data.stations.forEach((station, index) => {
      if (index % 3 === 0) {
        ionRow = document.createElement("ion-row");
        tab.refs.stationGrid.appendChild(ionRow);
      }
      const ionCol = document.createElement("ion-col");
      const ionButton = document.createElement("ion-button");
      ionButton.innerText = station.name;
      ionButton.expand = "block";
      ionButton.addEventListener("click", () => {
        ionButton.setAttribute("color", "light");
        this.emitEvent("click-station", {
          station: station.name,
          tab: tabName,
        });
      });
      tab.stationButtons[station.name] = ionButton;
      ionCol.appendChild(ionButton);
      ionRow.appendChild(ionCol);
    });

    tab.refs.stationsName.innerText = station_data.name;
  }

  showStationsLoading(tabName = "control", options = {}) {
    const { rows = 3, cols = 3 } = options;
    const tab = this.tabs[tabName];
    if (!tab) return;

    tab.stationButtons = {};
    tab.refs.stationGrid.innerHTML = "";
    for (let i = 0; i < rows; i++) {
      const ionRow = document.createElement("ion-row");
      ionRow.className = "station-placeholder";
      for (let j = 0; j < cols; j++) {
        const ionCol = document.createElement("ion-col");
        const skeleton = document.createElement("ion-skeleton-text");
        skeleton.setAttribute("animated", "");
        ionCol.appendChild(skeleton);
        ionRow.appendChild(ionCol);
      }
      tab.refs.stationGrid.appendChild(ionRow);
    }

    tab.setNowPlaying?.(null);
  }

  highlightCurrentStation(currentStation, tabName = "control") {
    const tab = this.tabs[tabName];
    if (!tab) return;

    Object.entries(tab.stationButtons).forEach(([name, btn]) => {
      btn.setAttribute(
        "color",
        name === currentStation ? "success" : "primary",
      );
    });
    tab.setNowPlaying?.(currentStation);
  }

  updatePreference(key, value, options = null) {
    console.log("updatePreference: ", key, value, options);
    const input = document.getElementById(`pref-${key}`);
    if (input) {
      if (options !== null) {
        this._populateSelectOptions(input, options);
      }
      input.value = value;
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

  _formatError(error) {
    if (error && typeof error.message === "string" && error.message.trim()) {
      return error.message.trim();
    }
    return "";
  }
}
