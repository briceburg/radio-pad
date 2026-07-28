// SPDX-FileCopyrightText: 2025 Brice Burgess (github.com/briceburg)
// SPDX-License-Identifier: AGPL-3.0-or-later

import { html } from "lit";
import { RadioElement } from "./radio-element.js";
import { StoreController } from "@nanostores/lit";
import { controlStore, isDegradedStatus, listenStore } from "../store.js";

const PLAYER_DEGRADED_SCOPES = ["radio_dial", "switchboard"];
const RESOURCE_DEGRADED_SCOPES = ["registry", "radio_dial"];
const PLAYBACK_STATUS_SUMMARY_ORDER = [["playerStatuses", "playback"]];
const LOADING_STATUS_SUMMARY_ORDER = [
  ["playerStatuses", "radio_dial"],
  ["resourceStatuses", "radio_dial"],
  ["resourceStatuses", "registry"],
  ["playerStatuses", "switchboard"],
];

function hasDegradedStatus(statuses = {}, scopes = []) {
  return scopes.some((scope) => isDegradedStatus(statuses[scope]));
}

function retainedStatusSummary(state, order) {
  for (const [statusMap, scope] of order) {
    const status = state[statusMap]?.[scope];
    if (typeof status?.summary === "string" && status.summary) {
      return status.summary;
    }
  }
  return null;
}

export function isControlDegraded(state) {
  if (["disconnected", "unauthorized"].includes(state.connectionState))
    return true;
  if (state.playerConnected === false) return true;

  return (
    hasDegradedStatus(state.playerStatuses, PLAYER_DEGRADED_SCOPES) ||
    hasDegradedStatus(state.resourceStatuses, RESOURCE_DEGRADED_SCOPES)
  );
}

export function getControlTitle(state) {
  if (state.connectionState === "unauthorized") {
    return state.connectionMessage || "Sign-in required.";
  }
  if (state.connectionState === "disconnected") {
    return state.player?.id ? "Reconnecting..." : "Disconnected";
  }
  if (state.connectionState === "connecting") return "Connecting...";
  if (state.playerConnected === false) return "Waiting for Player";
  if (state.requestedStation) return `Starting ${state.requestedStation}`;
  if (state.failedStation) return `Failed ${state.failedStation}`;

  const playbackSummary = retainedStatusSummary(
    state,
    PLAYBACK_STATUS_SUMMARY_ORDER,
  );
  if (playbackSummary) return playbackSummary;
  if (state.currentStation) return state.currentStation;

  if (!state.radioDial) {
    const loadingSummary = retainedStatusSummary(
      state,
      LOADING_STATUS_SUMMARY_ORDER,
    );
    if (loadingSummary) return loadingSummary;
    if (state.player || state.loading) return "Loading RadioDial";
  }

  return state.player?.name || state.radioDial?.name || "Control";
}

export function getStationVisualState(tabName, state) {
  if (tabName === "control" && isControlDegraded(state)) return "warning";
  if (state.loading) return "loading";
  return "normal";
}

function renderSkeleton(visualState) {
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
        ${
          this.tabName === "control"
            ? html`<ion-text color="medium">
                <p class="ion-margin-top text-sm">
                  You may need to sign in to access private players.
                </p>
              </ion-text>`
            : ""
        }
      </div>
    `;
  }

  renderStationButtons(
    stations,
    currentStation,
    requestedStation,
    failedStation,
    visualState,
  ) {
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
              const isPending = station.call_sign === requestedStation;
              const isFailed = station.call_sign === failedStation;
              const color = isActive
                ? "success"
                : isPending
                  ? "warning"
                  : isFailed
                    ? "danger"
                    : visualState === "warning"
                      ? "warning"
                      : "primary";
              return html`
                <ion-col size="4">
                  <ion-button
                    expand="block"
                    color=${color}
                    fill=${isPending ? "outline" : "solid"}
                    aria-pressed=${String(isActive)}
                    aria-busy=${String(isPending)}
                    aria-invalid=${String(isFailed)}
                    aria-label=${
                      isPending
                        ? `${station.call_sign}, starting playback`
                        : isFailed
                          ? `${station.call_sign}, playback failed`
                          : station.call_sign
                    }
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
        s.requestedStation,
        s.failedStation,
        visualState,
      );
    }

    const listenTitle = s.radioDial?.name
      ? [
          s.radioDial.name,
          s.currentStation || (s.loading ? "Loading..." : null),
        ]
          .filter(Boolean)
          .join(": ")
      : "Listen";
    const title = this.tabName === "control" ? getControlTitle(s) : listenTitle;

    return html`
      <ion-header>
        <ion-toolbar>
          <ion-title
            role="heading"
            aria-level="1"
            aria-live="polite"
            aria-atomic="true"
          >
            ${title}
          </ion-title>
          <ion-buttons slot="end">
            <ion-button
              shape="round"
              size="small"
              color="danger"
              .disabled=${!(s.currentStation || s.requestedStation)}
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
        <ion-grid>${content}</ion-grid>
      </ion-content>
    `;
  }
}

RadioPlayerTab.register("radio-player-tab");
