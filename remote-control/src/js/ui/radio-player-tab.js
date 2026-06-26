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
import { controlStore, listenStore } from "../store.js";

export function isControlDegraded(state) {
  if (state.connectionState === "disconnected") return true;
  if (state.playerConnected === false) return true;

  const degradedStatuses = ["stations", "switchboard"];
  return degradedStatuses.some((scope) =>
    ["warning", "error"].includes(state.playerStatuses?.[scope]?.level),
  );
}

export function getStationVisualState(tabName, state) {
  if (tabName === "control" && isControlDegraded(state)) return "warning";
  if (state.loading) return "loading";
  return "normal";
}

export function getStationButtonColor(visualState, isActive) {
  if (isActive) return "success";
  return visualState === "warning" ? "warning" : "primary";
}

function renderSkeleton(visualState = "loading") {
  const rows = [1, 2, 3];
  const cssClass =
    visualState === "warning"
      ? "station-placeholder station-placeholder-warning"
      : "station-placeholder";

  return html`
    ${rows.map(
      () => html`
        <ion-row class=${cssClass}>
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
  }

  get state() {
    return this.tabName === "listen"
      ? this.listenController.value
      : this.controlController.value;
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
              const color = getStationButtonColor(visualState, isActive);
              return html`
                <ion-col size="4">
                  <ion-button
                    expand="block"
                    color=${color}
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
    const visualState = getStationVisualState(this.tabName, s);
    const shouldRenderSkeleton =
      s.loading ||
      (visualState === "warning" &&
        !s.stationsData &&
        this.tabName === "control" &&
        s.player?.id);

    let content;
    if (shouldRenderSkeleton) {
      content = renderSkeleton(visualState);
    } else if (!s.stationsData) {
      content = this.renderEmptyState();
    } else {
      content = this.renderStationButtons(
        s.stationsData.stations,
        s.currentStation,
        visualState,
      );
    }

    const titleName =
      this.tabName === "control"
        ? s.player?.name || s.stationsData?.name || ""
        : s.stationsData?.name || "";
    const nowPlaying =
      s.currentStation ||
      (s.loading
        ? "Loading..."
        : s.playerConnected === false
          ? "Offline"
          : "...");

    return html`
      <ion-header>
        <ion-toolbar>
          <ion-title size="large">
            <span class="stations-name">${titleName}</span>:
            <span class="now-playing">${nowPlaying}</span>
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
