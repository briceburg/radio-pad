import { html, render } from "lit-html";

export class PlayerTabsView {
  constructor(invokeAction) {
    this.invokeAction = invokeAction;
    this.tabState = {
      control: { loading: true },
      listen: { loading: true },
    };
  }

  init(tabNames = ["control", "listen"]) {
    // We just set up initial renders
    tabNames.forEach((tabName) => this._renderTab(tabName));
  }

  _renderTab(tabName) {
    const state = this.tabState[tabName];
    const tabEl = document.querySelector(`ion-tab[tab="${tabName}"]`);
    if (!tabEl) return;

    // Helper functions for inner templates
    const renderStations = () => {
      if (state.loading || !state.stationsData) {
        // Skeleton loader
        return html`${Array.from({ length: 3 }).map(
          () =>
            html`<ion-row class="station-placeholder">
              ${Array.from({ length: 3 }).map(
                () =>
                  html`<ion-col
                    ><ion-skeleton-text animated></ion-skeleton-text
                  ></ion-col>`,
              )}
            </ion-row>`,
        )}`;
      }

      // Station buttons
      const rows = [];
      const stations = state.stationsData.stations || [];
      for (let i = 0; i < stations.length; i += 3) {
        rows.push(stations.slice(i, i + 3));
      }

      return html`${rows.map(
        (row) =>
          html`<ion-row>
            ${row.map((station) => {
              const isActive = station.name === state.currentStation;
              return html`<ion-col>
                <ion-button
                  expand="block"
                  color=${isActive ? "success" : "primary"}
                  @click=${() =>
                    this.invokeAction("onClickStation", tabName, station.name)}
                >
                  ${station.name}
                </ion-button>
              </ion-col>`;
            })}
          </ion-row>`,
      )}`;
    };

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
        <ion-grid class="station-grid"> ${renderStations()} </ion-grid>
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
