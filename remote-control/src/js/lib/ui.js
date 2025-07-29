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

export class RadioPadUI extends EventEmitter {
  constructor() {
    super();
    this.stationButtons = {}; // map of station name to button element
  }

  init() {
    this._radioInfo = document.getElementById("radio-info");
    this._nowPlaying = document.getElementById("now-playing");
    this._stationGrid = document.getElementById("station-grid");
    this._stopButton = document.getElementById("stop-button");
    this._settingsSaveButton = document.getElementById("settings-save-button");

    this._stopButton.addEventListener("click", () => {
      this.emitEvent("click-stop", null);
    });
  }

  info(msg) {
    this._radioInfo.innerText = msg;
  }

  renderPreferences(prefs) {
    const settingsList = document.getElementById("settings-list");
    settingsList.innerHTML = "";

    for (const [key, pref] of Object.entries(prefs.preferences)) {
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
            for (const option of pref.options) {
              const optionElement = document.createElement("ion-select-option");
              optionElement.value = option.value;
              optionElement.innerText = option.label;
              input.appendChild(optionElement);
            }
          }
          break;
      }
      input.id = `pref-${key}`;
      input.value = pref.value;
      item.appendChild(label);
      item.appendChild(input);
      settingsList.appendChild(item);
    }

    // allow multiple calls to renderPreferences without adding multiple save listeners
    if (!this._settingsSaveButton._listenerAdded) {
      this._settingsSaveButton.addEventListener("click", async () => {
        for (const [key, pref] of Object.entries(prefs.preferences)) {
          const input = document.getElementById(`pref-${key}`);
          if (input) {
            await prefs.set(key, input.value);
          }
        }
      });
      this._settingsSaveButton._listenerAdded = true;
    }
  }

  renderStations(stations, currentStation) {
    this.stationButtons = {};
    this._stationGrid.innerHTML = "";

    let ionRow;
    stations.forEach((station, index) => {
      if (index % 3 === 0) {
        ionRow = document.createElement("ion-row");
        this._stationGrid.appendChild(ionRow);
      }
      const ionCol = document.createElement("ion-col");
      const ionButton = document.createElement("ion-button");
      ionButton.innerText = station.name;
      ionButton.expand = "block";
      ionButton.addEventListener("click", () => {
        ionButton.setAttribute("color", "light");
        this.emitEvent("click-station", station.name);
      });
      this.stationButtons[station.name] = ionButton;
      ionCol.appendChild(ionButton);
      ionRow.appendChild(ionCol);
    });

    this.highlightCurrentStation(currentStation);
  }

  renderSkeletonStations(rows = 3, cols = 3) {
    this._stationGrid.innerHTML = "";
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
      this._stationGrid.appendChild(ionRow);
    }
  }

  highlightCurrentStation(currentStation) {
    Object.entries(this.stationButtons).forEach(([name, btn]) => {
      btn.setAttribute(
        "color",
        name === currentStation ? "success" : "primary"
      );
    });
    this._stopButton.disabled = !currentStation;
    this._nowPlaying.innerText = currentStation || "...";
  }
}
