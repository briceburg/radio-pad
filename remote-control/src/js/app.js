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

import "@ionic/core/css/ionic.bundle.css";
import { defineCustomElements } from "@ionic/core/loader/index.js";
import { Capacitor } from "@capacitor/core";
import { addIcons } from "ionicons";
import * as appIcons from "./lib/icons.js";
import { RadioPadPreferences } from "./lib/preferences.js";
import { RadioPadState } from "./lib/state.js";
import { RadioListen } from "./lib/radio-listen.js";
import { RadioControl } from "./lib/radio-control.js";
import { RadioPadAuth } from "./lib/auth.js";
import { RadioPadUI } from "./lib/ui.js";
import {
  discoverAccounts,
  discoverPlayer,
  discoverPlayers,
  discoverPresets,
} from "./lib/discovery.js";

addIcons(appIcons);
defineCustomElements(window);

function resolveSwitchboardUrl(url) {
  const override = import.meta.env.VITE_SWITCHBOARD_URL?.trim();
  if (!(override && url) || Capacitor.isNativePlatform()) {
    return url;
  }

  try {
    const target = new URL(url);
    const local = new URL(override);
    local.pathname = `${local.pathname.replace(/\/$/, "")}${target.pathname}`;
    local.search = target.search;
    local.hash = target.hash;
    return local.toString();
  } catch (error) {
    console.warn("Invalid VITE_SWITCHBOARD_URL override; using player URL.", {
      override,
      url,
      error,
    });
    return url;
  }
}

class RadioPad {
  constructor() {
    this.STATE = new RadioPadState();
    this.PREFS = new RadioPadPreferences();
    this.LISTEN = new RadioListen();
    this.CONTROL = new RadioControl();
    this.AUTH = new RadioPadAuth();
    this.UI = new RadioPadUI();
    this.copyTokenAvailable = !Capacitor.isNativePlatform();
    this.isSavingSettings = false;
    this.stationRequests = new Map();
    this.PREFS.registerEvent("on-change", ({ key, value }) => {
      void this.onPreferenceChange(key, value, {
        fromSettingsSave: this.isSavingSettings,
      });
      this.UI.updatePreference(key, value);
    });
    this.PREFS.registerEvent("options-changed", async ({ key, options }) => {
      this.UI.updatePreference(key, await this.PREFS.get(key), options);
    });
    this.STATE.registerEvent("on-change", async ({ key, value }) => {
      await this.onStateChange(key, value);
    });
    this.bindControlEvents();
    this.UI.registerEvent("click-station", ({ tab, station }) => {
      if (tab === "listen") {
        this.LISTEN.play(station);
        this.STATE.set("listen_station", station);
        return;
      }
      this.CONTROL.sendStationRequest(station);
    });
    this.UI.registerEvent("click-stop", ({ tab }) => {
      if (tab === "listen") {
        this.LISTEN.stop();
        this.STATE.set("listen_station", null);
        return;
      }
      this.CONTROL.sendStationRequest(null);
    });
    this.UI.registerEvent("settings-save", (settingsMap) =>
      this.saveSettings(settingsMap),
    );
    this.registerUiAction("auth-sign-in", "⚠️ Failed starting sign-in.", () =>
      this.AUTH.signIn(),
    );
    this.registerUiAction(
      "auth-sign-out",
      "⚠️ Failed signing out.",
      async () => {
        await this.AUTH.signOut();
        await this.UI.toastSuccess("Signed out.");
      },
    );
    this.registerUiAction(
      "auth-copy-token",
      "⚠️ Failed copying API test token.",
      async () => {
        const token = this.AUTH.getRegistryBearerToken();
        if (!token) {
          await this.UI.toastWarning("No API test token is available.");
          return;
        }
        await navigator.clipboard.writeText(token);
        await this.UI.toastSuccess("Copied API test token.");
      },
    );
    this.AUTH.registerEvent("state-changed", async (state) => {
      this.UI.updateAuthState(state);
      await this.refreshAccounts(
        await this.PREFS.get("registryUrl"),
        "⚠️ Failed refreshing accounts after auth change.",
      );
    });
    this.AUTH.registerEvent("error", ({ summary, error }) =>
      this.UI.showDangerError(summary, error),
    );
  }

  registerUiAction(event, summary, action) {
    this.UI.registerEvent(event, async () => {
      try {
        await action();
      } catch (error) {
        await this.UI.showDangerError(summary, error);
      }
    });
  }

  bindControlEvents() {
    this.CONTROL.registerEvent("connect", () => {
      this.UI.setTabInfo(`✅ Connected to ${this.STATE.get("player").name}`);
    });
    for (const [event, message] of Object.entries({
      connecting: "🔄 Connecting...",
      disconnect: "🔌 Disconnected. Reconnecting...",
    })) {
      this.CONTROL.registerEvent(event, () => {
        this.UI.setTabInfo(message);
      });
    }
    this.CONTROL.registerEvent("error", (message) => {
      this.UI.showError({ summary: `⚠️ ${message}` });
    });
    this.CONTROL.registerEvent("station-playing", (value) => {
      this.STATE.set("current_station", value);
    });
    this.CONTROL.registerEvent("stations-url", (value) => {
      this.STATE.set("stations_url", value);
    });
  }

  async onPreferenceChange(key, value, options = {}) {
    return {
      registryUrl: () =>
        this.refreshAccounts(value, "⚠️ Failed refreshing accounts.", options),
      accountId: () => this.refreshAccountChoices(value, options),
      playerId: () => this.refreshPlayer(value, options),
      presetId: () => this.loadStations(value, "listen"),
    }[key]?.();
  }

  async onStateChange(key, value) {
    return {
      available_players: () => this.PREFS.setOptions("playerId", value),
      available_presets: () => this.PREFS.setOptions("presetId", value),
      player: async () => {
        this.STATE.set("current_station", null);
        this.UI.showStationsLoading("control");
        await this.CONTROL.connect(
          resolveSwitchboardUrl(value.switchboard_url),
        );
      },
      stations_url: () => this.loadStations(value, "control"),
      current_station: () => this.UI.highlightCurrentStation(value, "control"),
      listen_station: () => this.UI.highlightCurrentStation(value, "listen"),
    }[key]?.();
  }

  async refreshAccountChoices(accountId, options = {}) {
    const choices = await this.withRegistryError(
      "⚠️ Failed refreshing account players/presets.",
      () =>
        Promise.all([
          discoverPlayers(accountId, this.PREFS, this.AUTH),
          discoverPresets(accountId, this.PREFS, this.AUTH),
        ]),
      options,
    );
    if (!choices) return;
    const [players, presets] = choices;
    this.STATE.set("available_players", players);
    this.STATE.set("available_presets", presets);
  }

  async refreshPlayer(playerId, options = {}) {
    const player = await this.withRegistryError(
      "⚠️ Failed refreshing player info.",
      () => discoverPlayer(playerId, this.PREFS, this.AUTH),
      options,
    );
    if (player) this.STATE.set("player", player);
  }

  async saveSettings(settingsMap) {
    this.isSavingSettings = true;
    try {
      for (const [key, value] of Object.entries(settingsMap)) {
        await this.PREFS.set(key, value);
      }
    } catch (error) {
      this.UI.setSettingsSaveState("error");
      await this.UI.showDangerError("⚠️ Failed saving settings.", error);
      return;
    } finally {
      this.isSavingSettings = false;
    }

    this.UI.setSettingsSaveState("saved");
  }

  async withRegistryError(summary, task, { fromSettingsSave = false } = {}) {
    try {
      return await task();
    } catch (error) {
      await this.UI.showRegistryError(
        fromSettingsSave
          ? `Saved settings. ${summary.replace(/^⚠️\s*/, "").trim()}`
          : summary,
        error,
      );
      return null;
    }
  }

  async start() {
    this.UI.init();
    this.UI.setCopyTokenAvailable(this.copyTokenAvailable);
    await this.AUTH.init();
    await this.PREFS.init();
    this.UI.renderPreferences(this.PREFS.preferences);
    this.UI.updateAuthState(this.AUTH.getState());
  }

  async refreshAccounts(registryUrl, failureSummary, options = {}) {
    if (!registryUrl) {
      return;
    }

    const accounts = await this.withRegistryError(
      failureSummary,
      () => discoverAccounts(registryUrl, this.AUTH),
      options,
    );
    if (accounts) await this.PREFS.setOptions("accountId", accounts);
  }

  async loadStations(stations_url, tabName = "control") {
    this.UI.showStationsLoading(tabName);
    const nextRequestId = (this.stationRequests.get(tabName) || 0) + 1;
    this.stationRequests.set(tabName, nextRequestId);
    try {
      const response = await fetch(stations_url);
      const station_data = await response.json();
      if (nextRequestId !== this.stationRequests.get(tabName)) {
        return;
      }
      if (tabName === "listen") {
        this.LISTEN.setStations(station_data);
      }
      this.UI.renderStations(station_data, tabName);
      const currentStation =
        tabName === "listen"
          ? this.STATE.get("listen_station")
          : this.STATE.get("current_station");
      this.UI.highlightCurrentStation(currentStation, tabName);
    } catch (error) {
      if (nextRequestId !== this.stationRequests.get(tabName)) {
        return;
      }
      console.error("Error loading stations:", error);
      await this.UI.showError({
        summary: "⚠️ Failed loading stations.",
        error,
      });
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const app = new RadioPad();
  app.start();
});
