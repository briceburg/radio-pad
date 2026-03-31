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

import { html, render } from "lit-html";

function renderEmptyState(tabName) {
  const noun = tabName === "listen" ? "preset" : "player";
  return html`
    <div class="ion-text-center ion-padding" style="margin-top: 2rem;">
      <ion-icon
        name="radio-outline"
        style="font-size: 64px; color: var(--ion-color-medium);"
      ></ion-icon>
      <h2 style="color: var(--ion-color-medium);">No ${noun} selected</h2>
      <p>
        Please select a ${noun} from the
        <ion-icon name="settings-outline"></ion-icon>
        <strong>Settings</strong> tab to begin.
      </p>
      ${tabName === "control"
        ? html`<p
            style="color: var(--ion-color-medium); font-size: 0.9em; margin-top: 1rem;"
          >
            Note: You may need to sign in to access private players.
          </p>`
        : ""}
    </div>
  `;
}

function renderSkeleton() {
  return html`
    <ion-row class="station-placeholder">
      ${Array.from({ length: 9 }).map(
        () => html`
          <ion-col size="4">
            <ion-skeleton-text animated></ion-skeleton-text>
          </ion-col>
        `,
      )}
    </ion-row>
  `;
}

function renderStationButtons(stations, currentStation, onSelect) {
  return html`
    <ion-row>
      ${stations.map((station) => {
        const isActive = station.name === currentStation;
        return html`
          <ion-col size="4">
            <ion-button
              expand="block"
              color=${isActive ? "success" : "primary"}
              @click=${() => onSelect(station.name)}
            >
              ${station.name}
            </ion-button>
          </ion-col>
        `;
      })}
    </ion-row>
  `;
}

export class PlayerTabsView {
  constructor(invokeAction) {
    this.invokeAction = invokeAction;
    this.tabState = {
      control: { loading: true },
      listen: { loading: true },
    };
  }

  init(tabNames = ["control", "listen"]) {
    tabNames.forEach((tabName) => this._renderTab(tabName));
  }

  _renderTab(tabName) {
    const state = this.tabState[tabName];
    const tabEl = document.querySelector(`ion-tab[tab="${tabName}"]`);
    if (!tabEl) return;

    let content;
    if (state.loading) {
      content = renderSkeleton();
    } else if (!state.stationsData) {
      content = renderEmptyState(tabName);
    } else {
      content = renderStationButtons(
        state.stationsData.stations || [],
        state.currentStation,
        (stationName) =>
          this.invokeAction("onClickStation", tabName, stationName),
      );
    }

    const template = html`
      <ion-header>
        <ion-toolbar>
          <ion-title size="large">
            <span class="stations-name">${state.stationsData?.name || ""}</span
            >:
            <span class="now-playing">${state.currentStation || "..."}</span>
          </ion-title>
          <ion-buttons slot="end">
            <ion-button
              shape="round"
              size="small"
              color="danger"
              .disabled=${!state.currentStation}
              @click=${() => this.invokeAction("onStopStation", tabName)}
              aria-label="Stop playback"
            >
              <ion-icon slot="icon-only" name="stop"></ion-icon>
            </ion-button>
          </ion-buttons>
        </ion-toolbar>
      </ion-header>
      <ion-content class="ion-padding">
        <div class="radio-info ion-text-center">${state.statusText || ""}</div>
        <ion-grid class="station-grid">${content}</ion-grid>
      </ion-content>
    `;

    render(template, tabEl);
  }

  setTabInfo(message, tabName = "control") {
    if (!this.tabState[tabName]) return;
    this.tabState[tabName].statusText = message;
    this._renderTab(tabName);
  }

  renderTabState(tabName, state) {
    this.tabState[tabName] = { ...this.tabState[tabName], ...state };
    this._renderTab(tabName);
  }
}
