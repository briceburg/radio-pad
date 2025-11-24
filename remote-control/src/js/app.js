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

import { SafeArea } from "@capacitor-community/safe-area";
import { Capacitor } from "@capacitor/core";

// Only enable SafeArea on native platforms
if (Capacitor.isNativePlatform()) {
  SafeArea.enable({ config: {} });
}

import { RadioPadPreferences } from "./lib/preferences.js";
import { RadioPadState } from "./lib/state.js";
import { RadioListen } from "./lib/radio-listen.js";
import { RadioControl } from "./lib/radio-control.js";
import { RadioPadUI } from "./lib/ui.js";
import {
  discoverAccounts,
  discoverPlayer,
  discoverPlayers,
  discoverPresets,
} from "./lib/discovery.js";

class RadioPad {
  constructor() {
    this.STATE = new RadioPadState();
    this.PREFS = new RadioPadPreferences();
    this.LISTEN = new RadioListen();
    this.CONTROL = new RadioControl();
    this.UI = new RadioPadUI();
    // PREFERENCE CHANGES
    this.PREFS.registerEvent("on-change", async (data) => {
      switch (data.key) {
        case "registryUrl": {
          try {
            const accounts = await discoverAccounts(data.value);
            await this.PREFS.setOptions("accountId", accounts);
          } catch (error) {
            await this.UI.showRegistryError(
              "⚠️ Failed refreshing accounts.",
              error,
            );
          }
          break;
        }
        case "accountId": {
          try {
            const [players, presets] = await Promise.all([
              discoverPlayers(data.value, this.PREFS),
              discoverPresets(data.value, this.PREFS),
            ]);
            this.STATE.set("available_players", players);
            this.STATE.set("available_presets", presets);
          } catch (error) {
            await this.UI.showRegistryError(
              "⚠️ Failed refreshing account players/presets.",
              error,
            );
          }
          break;
        }
        case "playerId": {
          try {
            const player = await discoverPlayer(data.value, this.PREFS);
            if (player) {
              this.STATE.set("player", player);
            }
          } catch (error) {
            await this.UI.showRegistryError(
              "⚠️ Failed refreshing player info.",
              error,
            );
          }
          break;
        }
        case "presetId": {
          await this.loadStations(data.value, "listen");
          break;
        }
      }
      this.UI.updatePreference(data.key, data.value);
    });
    this.PREFS.registerEvent("options-changed", async (data) => {
      this.UI.updatePreference(
        data.key,
        await this.PREFS.get(data.key),
        data.options,
      );
    });

    // STATE CHANGES
    this.STATE.registerEvent("on-change", async (data) => {
      switch (data.key) {
        case "available_players":
          await this.PREFS.setOptions("playerId", data.value);
          break;
        case "available_presets":
          await this.PREFS.setOptions("presetId", data.value);
          break;
        case "player":
          this.STATE.set("current_station", null);
          this.UI.showStationsLoading("control");
          await this.CONTROL.connect(data.value.switchboard_url);
          break;
        case "stations_url":
          await this.loadStations(data.value, "control");
          break;
        case "current_station":
          this.UI.highlightCurrentStation(data.value, "control");
          break;
        case "listen_station":
          this.UI.highlightCurrentStation(data.value, "listen");
          break;
      }
    });

    // REMOTE CONTROL EVENTS
    this.CONTROL.registerEvent("connect", (url) => {
      this.UI.setTabInfo(`✅ Connected to ${this.STATE.get("player").name}`);
    });
    this.CONTROL.registerEvent("connecting", (url) => {
      this.UI.setTabInfo(`🔄 Connecting...`);
    });
    this.CONTROL.registerEvent("disconnect", () => {
      this.UI.setTabInfo("🔌 Disconnected. Reconnecting...");
    });
    this.CONTROL.registerEvent("error", (msg) => {
      this.UI.setTabInfo(`⚠️ Error: ${msg}`);
    });
    this.CONTROL.registerEvent("station-playing", (stationName) => {
      this.STATE.set("current_station", stationName);
    });
    this.CONTROL.registerEvent("stations-url", (url) => {
      this.STATE.set("stations_url", url);
    });

    // UI EVENTS
    this.UI.registerEvent("click-station", (data) => {
      if (data.tab === "listen") {
        this.LISTEN.play(data.station);
        this.STATE.set("listen_station", data.station);
      } else {
        this.CONTROL.sendStationRequest(data.station);
      }
    });
    this.UI.registerEvent("click-stop", (data) => {
      if (data.tab === "listen") {
        this.LISTEN.stop();
        this.STATE.set("listen_station", null);
      } else {
        this.CONTROL.sendStationRequest(null);
      }
    });
    this.UI.registerEvent("settings-save", async (settingsMap) => {
      // Apply sequentially so downstream events fire in a predictable order.
      for (const [key, value] of Object.entries(settingsMap)) {
        await this.PREFS.set(key, value);
      }
    });
  }

  async start() {
    this.UI.init();
    await this.PREFS.init();
    this.UI.renderPreferences(this.PREFS.preferences);
  }

  async loadStations(stations_url, tabName = "control") {
    this.UI.showStationsLoading(tabName);
    try {
      const response = await fetch(stations_url);
      const station_data = await response.json();
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
      console.error("Error loading stations:", error);
      await this.UI.showError({
        summary: "⚠️ Failed loading stations.",
        error,
        tab: tabName,
      });
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const app = new RadioPad();
  app.start();
});
