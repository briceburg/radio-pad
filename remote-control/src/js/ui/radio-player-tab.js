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
import { StoreController } from "@nanostores/lit";
import { controlStore, listenStore, registryStore } from "../store.js";
import { isRegistryPending } from "./registry-status.js";

export function getRegistryStatusText(registryState) {
  if (isRegistryPending(registryState)) {
    return "Connecting to Registry";
  }
  if (registryState.phase === "error") {
    return registryState.errorText;
  }
  return null;
}

export function shouldRenderSkeleton(tabName, state, registryState) {
  return (
    state.loading ||
    (tabName === "control" && state.player?.id && !state.stationsData) ||
    (!state.stationsData &&
      (isRegistryPending(registryState) || registryState.phase === "error"))
  );
}

export function getStationVisualState(tabName, state, registryState) {
  if (
    shouldRenderSkeleton(tabName, state, registryState) &&
    (state.loading || isRegistryPending(registryState))
  ) {
    return "loading";
  }

  if (
    tabName === "control" &&
    state.stationsData &&
    (registryState.phase === "error" ||
      isRegistryPending(registryState) ||
      ["connecting", "disconnected"].includes(state.connectionState))
  ) {
    return "warning";
  }

  return "ready";
}

export function getStationButtonColor(visualState, isActive) {
  if (isActive) {
    return "success";
  }
  if (visualState === "warning") {
    return "warning";
  }
  return "primary";
}

export function getTitlePrefix(tabName, state) {
  if (state.stationsData?.name) {
    return state.stationsData.name;
  }
  if (tabName === "control") {
    return state.player?.name || "Control";
  }
  return state.titleName || "Listen";
}

export function getTitleSuffix(tabName, state, registryState) {
  if (state.currentStation) {
    return state.currentStation;
  }

  const registryStatus = getRegistryStatusText(registryState);
  if (tabName === "control") {
    if (state.loading && state.player?.id) {
      return "Connecting to player";
    }
    if (!state.stationsData && registryStatus) {
      return registryStatus;
    }
    if (state.connectionState === "connecting" && state.stationsData) {
      return "Connecting to switchboard";
    }
    if (state.connectionState === "disconnected" && state.stationsData) {
      return "Switchboard unavailable";
    }
    return state.player?.id ? "Ready" : "Choose a player";
  }

  if (state.loading) {
    return "Loading preset";
  }
  if (!state.stationsData && registryStatus) {
    return registryStatus;
  }
  return state.titleName ? "Ready" : "Choose a preset";
}

function renderSkeleton(visualState) {
  const rows = [1, 2, 3];
  const rowClass =
    visualState === "loading"
      ? "station-placeholder station-placeholder-warning"
      : "station-placeholder";

  return html`
    ${rows.map(
      () => html`
        <ion-row class=${rowClass}>
          ${Array.from({ length: 3 }).map(
            () => html`
              <ion-col size="4">
                <ion-skeleton-text animated></ion-skeleton-text>
              </ion-col>
            `,
          )}
        </ion-row>
      `,
    )}
  `;
}

export class RadioPlayerTab extends RadioElement {
  static properties = {
    tabName: { type: String, attribute: "tab-name" },
  };

  constructor() {
    super();
    this.tabName = "control";
    this.controlController = new StoreController(this, controlStore);
    this.listenController = new StoreController(this, listenStore);
    this.registryController = new StoreController(this, registryStore);
  }

  get state() {
    return this.tabName === "listen"
      ? this.listenController.value
      : this.controlController.value;
  }

  get registryState() {
    return this.registryController.value;
  }

  _onSelectStation(stationName) {
    this._emit("station-click", { tabName: this.tabName, stationName });
  }

  _onStopStation() {
    this._emit("station-stop", { tabName: this.tabName });
  }

  renderEmptyState() {
    const noun = this.tabName === "listen" ? "preset" : "player";
    return html`
      <div class="ion-text-center ion-padding ion-margin-top">
        <ion-icon
          class="icon-hero"
          color="medium"
          name="radio-outline"
        ></ion-icon>
        <ion-text color="medium">
          <h2>No ${noun} selected</h2>
        </ion-text>
        <p>
          Please select a ${noun} from the
          <ion-icon name="settings-outline"></ion-icon>
          <strong>Settings</strong> tab to begin.
        </p>
        ${this.tabName === "control"
          ? html`<ion-text color="medium">
              <p class="ion-margin-top text-sm">
                Note: You may need to sign in to access private players.
              </p>
            </ion-text>`
          : ""}
      </div>
    `;
  }

  renderStationButtons(stations, currentStation, visualState) {
    const rows = [];
    const stationsList = stations || [];
    for (let i = 0; i < stationsList.length; i += 3) {
      rows.push(stationsList.slice(i, i + 3));
    }

    return html`
      ${rows.map(
        (row) => html`
          <ion-row>
            ${row.map((station) => {
              const isActive = station.name === currentStation;
              return html`
                <ion-col size="4">
                  <ion-button
                    expand="block"
                    color=${getStationButtonColor(visualState, isActive)}
                    @click=${() => this._onSelectStation(station.name)}
                  >
                    ${station.name}
                  </ion-button>
                </ion-col>
              `;
            })}
          </ion-row>
        `,
      )}
    `;
  }

  render() {
    const s = this.state;
    const registryState = this.registryState;
    const visualState = getStationVisualState(this.tabName, s, registryState);
    const titlePrefix = getTitlePrefix(this.tabName, s);
    const titleSuffix = getTitleSuffix(this.tabName, s, registryState);

    let content;
    if (s.stationsData) {
      content = this.renderStationButtons(
        s.stationsData.stations,
        s.currentStation,
        visualState,
      );
    } else if (shouldRenderSkeleton(this.tabName, s, registryState)) {
      content = renderSkeleton(visualState);
    } else if (!s.stationsData) {
      content = this.renderEmptyState();
    }

    return html`
      <ion-header>
        <ion-toolbar>
          <ion-title size="large">
            <span class="stations-name">${titlePrefix}</span>:
            <span class="now-playing">${titleSuffix}</span>
          </ion-title>
          <ion-buttons slot="end">
            <ion-button
              shape="round"
              size="small"
              color="danger"
              .disabled=${!s.currentStation}
              @click=${() => this._onStopStation()}
              aria-label="Stop playback"
            >
              <ion-icon slot="icon-only" name="stop"></ion-icon>
            </ion-button>
          </ion-buttons>
        </ion-toolbar>
      </ion-header>
      <ion-content class="ion-padding">
        <div class="radio-info ion-text-center">${s.statusText || ""}</div>
        <ion-grid class="station-grid">${content}</ion-grid>
      </ion-content>
    `;
  }
}

RadioPlayerTab.register("radio-player-tab");
