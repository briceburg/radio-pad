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

function setText(node, text = "") {
  if (node) {
    node.innerText = text;
  }
}

export class PlayerTabsView {
  constructor(invokeAction) {
    this.invokeAction = invokeAction;
    this.tabs = {};
  }

  init(tabNames = ["control", "listen"]) {
    tabNames.forEach((tabName) => this._initPlayerTab(tabName));
  }

  setTabInfo(message, tabName = "control") {
    setText(this.tabs[tabName]?.radioInfo, message);
  }

  renderTabState(tabName, state) {
    if (tabName === "control") {
      this.setTabInfo(state.statusText || "", tabName);
    }

    if (state.loading || !state.stationsData) {
      this.showStationsLoading(tabName);
      return;
    }

    this.renderStations(state.stationsData, tabName);
    this.highlightCurrentStation(state.currentStation, tabName);
  }

  renderStations(stationsData, tabName = "control") {
    const tab = this.tabs[tabName];
    if (!tab) return;

    tab.stationButtons = {};
    tab.stationGrid.innerHTML = "";

    let ionRow;
    stationsData.stations.forEach((station, index) => {
      if (index % 3 === 0) {
        ionRow = document.createElement("ion-row");
        tab.stationGrid.appendChild(ionRow);
      }
      const ionCol = document.createElement("ion-col");
      const ionButton = document.createElement("ion-button");
      ionButton.innerText = station.name;
      ionButton.expand = "block";
      ionButton.addEventListener("click", () => {
        ionButton.setAttribute("color", "light");
        this.invokeAction("onClickStation", tabName, station.name);
      });
      tab.stationButtons[station.name] = ionButton;
      ionCol.appendChild(ionButton);
      ionRow.appendChild(ionCol);
    });

    setText(tab.stationsName, stationsData.name);
  }

  showStationsLoading(tabName = "control", { rows = 3, cols = 3 } = {}) {
    const tab = this.tabs[tabName];
    if (!tab) return;

    tab.stationButtons = {};
    tab.stationGrid.innerHTML = "";
    for (let rowIndex = 0; rowIndex < rows; rowIndex += 1) {
      const ionRow = document.createElement("ion-row");
      ionRow.className = "station-placeholder";
      for (let colIndex = 0; colIndex < cols; colIndex += 1) {
        const ionCol = document.createElement("ion-col");
        const skeleton = document.createElement("ion-skeleton-text");
        skeleton.setAttribute("animated", "");
        ionCol.appendChild(skeleton);
        ionRow.appendChild(ionCol);
      }
      tab.stationGrid.appendChild(ionRow);
    }

    this._setNowPlaying(tab, null);
  }

  highlightCurrentStation(currentStation, tabName = "control") {
    const tab = this.tabs[tabName];
    if (!tab) return;

    Object.entries(tab.stationButtons).forEach(([name, button]) => {
      button.setAttribute(
        "color",
        name === currentStation ? "success" : "primary",
      );
    });
    this._setNowPlaying(tab, currentStation);
  }

  _initPlayerTab(tabName) {
    const tabEl = document.querySelector(`ion-tab[tab="${tabName}"]`);
    const template = document.getElementById("tab-player");
    if (!template || !tabEl) return;

    const clone = template.content.cloneNode(true);
    tabEl.appendChild(clone);

    const tab = {
      stationsName: tabEl.querySelector(".stations-name"),
      nowPlaying: tabEl.querySelector(".now-playing"),
      stopButton: tabEl.querySelector(".stop-button"),
      radioInfo: tabEl.querySelector(".radio-info"),
      stationGrid: tabEl.querySelector(".station-grid"),
      stationButtons: {},
    };

    this.tabs[tabName] = tab;

    this.showStationsLoading(tabName);
    tab.stopButton?.addEventListener("click", () => {
      this.invokeAction("onStopStation", tabName);
    });
  }

  _setNowPlaying(tab, stationName = null) {
    if (!tab) {
      return;
    }

    setText(tab.nowPlaying, stationName || "...");
    if (tab.stopButton) {
      tab.stopButton.disabled = !stationName;
    }
  }
}
