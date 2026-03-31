/*
This file is part of the radio-pad project.
*/

import { LitElement, html } from "lit";
import { StoreController } from "@nanostores/lit";
import { controlStore, listenStore } from "../store.js";

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

export class RadioPlayerTab extends LitElement {
  static properties = {
    tabName: { type: String, attribute: "tab-name" },
  };

  constructor() {
    super();
    this.tabName = "control";
    this.controlController = new StoreController(this, controlStore);
    this.listenController = new StoreController(this, listenStore);
  }

  createRenderRoot() {
    return this;
  }

  get state() {
    return this.tabName === "listen"
      ? this.listenController.value
      : this.controlController.value;
  }

  _onSelectStation(stationName) {
    this.dispatchEvent(
      new CustomEvent("station-click", {
        bubbles: true,
        composed: true,
        detail: { tabName: this.tabName, stationName },
      }),
    );
  }

  _onStopStation() {
    this.dispatchEvent(
      new CustomEvent("station-stop", {
        bubbles: true,
        composed: true,
        detail: { tabName: this.tabName },
      }),
    );
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

  renderStationButtons(stations, currentStation) {
    return html`
      <ion-row>
        ${(stations || []).map((station) => {
          const isActive = station.name === currentStation;
          return html`
            <ion-col size="4">
              <ion-button
                expand="block"
                color=${isActive ? "success" : "primary"}
                @click=${() => this._onSelectStation(station.name)}
              >
                ${station.name}
              </ion-button>
            </ion-col>
          `;
        })}
      </ion-row>
    `;
  }

  render() {
    const s = this.state;

    let content;
    if (s.loading) {
      content = renderSkeleton();
    } else if (!s.stationsData) {
      content = this.renderEmptyState();
    } else {
      content = this.renderStationButtons(
        s.stationsData.stations,
        s.currentStation,
      );
    }

    return html`
      <ion-header>
        <ion-toolbar>
          <ion-title size="large">
            <span class="stations-name">${s.stationsData?.name || ""}</span>:
            <span class="now-playing">${s.currentStation || "..."}</span>
          </ion-title>
          <ion-buttons slot="end">
            <ion-button
              shape="round"
              size="small"
              color="danger"
              .disabled=${!s.currentStation}
              @click=${this._onStopStation}
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

customElements.define("radio-player-tab", RadioPlayerTab);
