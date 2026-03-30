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
  if (node) node.innerText = text;
}

export class PlayerTabsView {
  constructor(invokeAction, { templateSelector = '#tab-player' } = {}) {
    this.invokeAction = invokeAction;
    this.templateSelector = templateSelector;
    this.tabs = {};
  }

  init(tabNames = ["control", "listen"]) {
    tabNames.forEach((tabName) => this._initPlayerTab(tabName));
  }

  setTabInfo(message, tabName = "control") {
    setText(this.tabs[tabName]?.radioInfo, message);
  }

  renderTabState(tabName, state) {
    if (tabName === "control") this.setTabInfo(state.statusText || "", tabName);

    if (state.loading || !state.stationsData) {
      return this.showStationsLoading(tabName);
    }

    this.renderStations(state.stationsData, tabName);
    this.highlightCurrentStation(state.currentStation, tabName);
  }

  renderStations(stationsData, tabName = "control") {
    const tab = this.tabs[tabName];
    if (!tab) return;

    let html = "";
    stationsData.stations.forEach((station, index) => {
      if (index % 3 === 0) html += `<ion-row>`;
      html += `
        <ion-col>
          <ion-button expand="block" data-station="${station.name}">
            ${station.name}
          </ion-button>
        </ion-col>
      `;
      if (index % 3 === 2 || index === stationsData.stations.length - 1) {
        html += `</ion-row>`;
      }
    });

    tab.stationGrid.innerHTML = html;

    // Store button references for fast highlighting
    tab.stationButtons = Object.fromEntries(
      [...tab.stationGrid.querySelectorAll("ion-button")].map((btn) => [
        btn.dataset.station,
        btn,
      ]),
    );

    setText(tab.stationsName, stationsData.name);
  }

  showStationsLoading(tabName = "control", { rows = 3, cols = 3 } = {}) {
    const tab = this.tabs[tabName];
    if (!tab) return;

    tab.stationButtons = {};
    tab.stationGrid.innerHTML = Array.from({ length: rows })
      .map(
        () => `
        <ion-row class="station-placeholder">
          ${Array.from({ length: cols })
            .map(
              () => `
            <ion-col><ion-skeleton-text animated></ion-skeleton-text></ion-col>
          `,
            )
            .join("")}
        </ion-row>
      `,
      )
      .join("");

    this._setNowPlaying(tab, null);
  }

  highlightCurrentStation(currentStation, tabName = "control") {
    const tab = this.tabs[tabName];
    if (!tab) return;

    for (const [name, button] of Object.entries(tab.stationButtons)) {
      button.setAttribute(
        "color",
        name === currentStation ? "success" : "primary",
      );
    }
    this._setNowPlaying(tab, currentStation);
  }

  _initPlayerTab(tabName) {
    const tabEl = document.querySelector(`ion-tab[tab="${tabName}"]`);
    const template = typeof this.templateSelector === 'string' ? document.querySelector(this.templateSelector) : this.templateSelector;
    if (!template || !tabEl) return;

    tabEl.appendChild(template.content.cloneNode(true));

    const tab = {
      stationsName: tabEl.querySelector(".stations-name"),
      nowPlaying: tabEl.querySelector(".now-playing"),
      stopButton: tabEl.querySelector(".stop-button"),
      radioInfo: tabEl.querySelector(".radio-info"),
      stationGrid: tabEl.querySelector(".station-grid"),
      stationButtons: {},
    };

    // Event delegation on the parent grid instead of attaching to every single button
    tab.stationGrid.addEventListener("click", (e) => {
      const button = e.target.closest("ion-button");
      if (!button || !button.dataset.station) return;
      button.setAttribute("color", "light");
      this.invokeAction("onClickStation", tabName, button.dataset.station);
    });

    tab.stopButton?.addEventListener("click", () =>
      this.invokeAction("onStopStation", tabName),
    );

    this.tabs[tabName] = tab;
    this.showStationsLoading(tabName);
  }

  _setNowPlaying(tab, stationName = null) {
    if (!tab) return;
    setText(tab.nowPlaying, stationName || "...");
    if (tab.stopButton) tab.stopButton.disabled = !stationName;
  }
}
