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
import { controlStore, isDegradedStatus, listenStore } from "../store.js";

const PLAYER_DEGRADED_SCOPES = ["radio_dial", "switchboard"];
const RESOURCE_DEGRADED_SCOPES = ["registry", "radio_dial"];
const STATUS_SUMMARY_ORDER = [
  ["playerStatuses", "playback"],
  ["playerStatuses", "radio_dial"],
  ["resourceStatuses", "radio_dial"],
  ["resourceStatuses", "registry"],
  ["playerStatuses", "switchboard"],
];

function hasDegradedStatus(statuses = {}, scopes = []) {
  return scopes.some((scope) => isDegradedStatus(statuses[scope]));
}

function retainedStatusSummary(state) {
  for (const [statusMap, scope] of STATUS_SUMMARY_ORDER) {
    const status = state[statusMap]?.[scope];
    if (
      isDegradedStatus(status) &&
      typeof status.summary === "string" &&
      status.summary
    ) {
      return status.summary;
    }
  }
  return null;
}

export function isControlDegraded(state) {
  if (state.connectionState === "disconnected") return true;
  if (state.playerConnected === false) return true;

  return (
    hasDegradedStatus(state.playerStatuses, PLAYER_DEGRADED_SCOPES) ||
    hasDegradedStatus(state.resourceStatuses, RESOURCE_DEGRADED_SCOPES)
  );
}

export function getControlStatusText(state) {
  if (state.playerConnected === false) return "Player offline.";
  if (state.connectionState === "disconnected") {
    return state.player?.id
      ? "Switchboard unavailable. Reconnecting..."
      : "Disconnected.";
  }

  const summary = retainedStatusSummary(state);
  if (summary) return summary;

  if (state.connectionState === "connecting") {
    return "Connecting to switchboard...";
  }
  if (state.connectionState === "connected" && state.player?.name) {
    return `Connected to ${state.player.name}`;
  }
  return "";
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

  _onSelectStation(callSign) {
    this._emit("station-click", { tabName: this.tabName, callSign });
  }

  _onStopStation() {
    this._emit("station-stop", { tabName: this.tabName });
  }

  renderEmptyState() {
    const noun = this.tabName === "listen" ? "RadioDial" : "player";
    return html`
      <div class="ion-text-center ion-padding ion-margin-top">
        <ion-icon
          aria-hidden="true"
          class="icon-hero"
          color="medium"
          name="radio-outline"
        ></ion-icon>
        <ion-text color="medium">
          <h2>No ${noun} selected</h2>
        </ion-text>
        <p>Choose a ${noun} in <strong>Settings</strong> to begin.</p>
        ${this.tabName === "control"
          ? html`<ion-text color="medium">
              <p class="ion-margin-top text-sm">
                You may need to sign in to access private players.
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
              const isActive = station.call_sign === currentStation;
              const color = getStationButtonColor(visualState, isActive);
              return html`
                <ion-col size="4">
                  <ion-button
                    expand="block"
                    color=${color}
                    aria-pressed=${String(isActive)}
                    @click=${() => this._onSelectStation(station.call_sign)}
                  >
                    ${station.call_sign}
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
    const statusText =
      this.tabName === "control" ? getControlStatusText(s) : "";
    const shouldRenderSkeleton =
      s.loading ||
      (visualState === "warning" &&
        !s.radioDial &&
        this.tabName === "control" &&
        s.player?.id);

    let content;
    if (shouldRenderSkeleton) {
      content = renderSkeleton(visualState);
    } else if (!s.radioDial) {
      content = this.renderEmptyState();
    } else {
      content = this.renderStationButtons(
        s.radioDial.stations,
        s.currentStation,
        visualState,
      );
    }

    const titleName =
      this.tabName === "control"
        ? s.player?.name || s.radioDial?.name || ""
        : s.radioDial?.name || "";
    const nowPlaying =
      s.currentStation ||
      (s.loading
        ? "Loading..."
        : s.playerConnected === false
          ? "Offline"
          : "...");
    const pageTitle = this.tabName === "control" ? "Control" : "Listen";
    const title = titleName ? `${titleName}: ${nowPlaying}` : pageTitle;

    return html`
      <ion-header>
        <ion-toolbar>
          <ion-title size="large" role="heading" aria-level="1">
            ${title}
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
              <ion-icon
                aria-hidden="true"
                slot="icon-only"
                name="stop"
              ></ion-icon>
            </ion-button>
          </ion-buttons>
        </ion-toolbar>
      </ion-header>
      <ion-content class="ion-padding">
        <div class="ion-text-center" role="status" aria-live="polite">
          ${statusText}
        </div>
        <ion-grid>${content}</ion-grid>
      </ion-content>
    `;
  }
}

RadioPlayerTab.register("radio-player-tab");
