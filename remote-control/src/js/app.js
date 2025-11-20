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
SafeArea.enable({ config: {} });

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
    this.stations = new Map();

    // PREFERENCE CHANGES
    this.PREFS.registerEvent("on-change", async (data) => {
      switch (data.key) {
        case "registryUrl": {
          const accounts = await discoverAccounts(data.value);
          await this.PREFS.setOptions("accountId", accounts);
          break;
        }
        case "accountId": {
          const players = await discoverPlayers(data.value, this.PREFS);
          const presets = await discoverPresets(data.value, this.PREFS);
          this.STATE.set("available_players", players);
          this.STATE.set("available_presets", presets);
          break;
        }
        case "playerId": {
          const player = await discoverPlayer(data.value, this.PREFS);
          if (player) {
            this.STATE.set("player", player);
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
          await this.CONTROL.connect(data.value.switchboard_url);
          break;
        case "stations_url":
          await this.loadStations(data.value, "control");
          break;
        case "controlStation":
          this.UI.highlightCurrentStation(data.value, "control");
          break;
        case "listenStation":
          this.UI.highlightCurrentStation(data.value, "listen");
          break;
      }
    });

    // REMOTE CONTROL EVENTS
    this.CONTROL.registerEvent("connect", (url) => {
      this.UI.info(
        `✅ Connected to ${this.STATE.get("player").name}`,
        "control",
      );
    });
    this.CONTROL.registerEvent("connecting", (url) => {
      this.UI.info(`🔄 Connecting...`, "control");
    });
    this.CONTROL.registerEvent("disconnect", () => {
      this.UI.info("🔌 Disconnected. Reconnecting...", "control");
    });
    this.CONTROL.registerEvent("error", (msg) => {
      this.UI.info(`⚠️ Error: ${msg}`, "control");
    });
    this.CONTROL.registerEvent("station-playing", (stationName) => {
      this.STATE.set("controlStation", stationName);
    });
    this.CONTROL.registerEvent("stations-url", (url) => {
      this.STATE.set("stations_url", url);
    });

    // UI EVENTS
    this.UI.registerEvent("click-station", (data) => {
      if (data.tab === "listen") {
        this.LISTEN.play(data.station);
        this.STATE.set("listenStation", data.station);
      } else {
        this.CONTROL.sendStationRequest(data.station);
      }
    });
    this.UI.registerEvent("click-stop", (data) => {
      if (data.tab === "listen") {
        this.LISTEN.stop();
        this.STATE.set("listenStation", null);
      } else {
        this.CONTROL.sendStationRequest(null);
      }
    });
    this.UI.registerEvent("settings-save", (settingsMap) => {
      for (const [key, value] of Object.entries(settingsMap)) {
        this.PREFS.set(key, value);
      }
    });
  }

  async start() {
    await this.PREFS.init();
    this.UI.init();
    this.UI.renderPreferences(this.PREFS.preferences);
  }

  async loadStations(stations_url, tabName = "control") {
    this.UI.renderSkeletonStations(3, 3, tabName);
    try {
      const response = await fetch(stations_url);
      const station_data = await response.json();
      if (tabName === "listen") {
        this.LISTEN.setStations(station_data);
      }
      this.UI.renderStations(station_data, tabName);
      const currentStation =
        tabName === "listen"
          ? this.STATE.get("listenStation")
          : this.STATE.get("controlStation");
      this.UI.highlightCurrentStation(currentStation, tabName);
    } catch (error) {
      // TODO: use toast / ui notification error?
      console.error("Error loading stations:", error);
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const app = new RadioPad();
  app.start();
});
