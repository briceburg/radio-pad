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
import { RadioPadStreamer } from "./lib/streaming.js";
import { RadioPadSwitchboard } from "./lib/switchboard.js";
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
    this.STREAMER = new RadioPadStreamer();
    this.SWITCHBOARD = new RadioPadSwitchboard();
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
          await this.PREFS.setOptions("playerId", players);
          await this.PREFS.setOptions("presetId", presets);
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
          this.STATE.set("stations_url_local", data.value);
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
        case "currentStation":
          if (this.STATE.get("localMode")) {
            this.STREAMER.play(data.value);
          }
          this.UI.highlightCurrentStation(data.value);
          break;
        case "localMode":
          if (data.value) {
            this.SWITCHBOARD.disconnect();
            this.UI.info("🎧 Playing Locally");
            this.STREAMER.play(this.STATE.get("currentStation"));
          } else {
            this.SWITCHBOARD.connect();
            this.STREAMER.stop();
          }
          break;
        case "player":
          await this.SWITCHBOARD.connect(data.value.switchboard_url);
          break;
        case "stations_url":
          await this.loadStations(data.value);
          break;
      }
    });

    // SWITCHBOARD EVENTS
    this.SWITCHBOARD.registerEvent("connect", (url) => {
      this.UI.info(`✅ Connected to ${this.STATE.get("player").name}`);
    });
    this.SWITCHBOARD.registerEvent("connecting", (url) => {
      this.UI.info(`🔄 Connecting...`);
    });
    this.SWITCHBOARD.registerEvent("disconnect", () => {
      this.UI.info("🔌 Disconnected. Reconnecting...");
    });
    this.SWITCHBOARD.registerEvent("error", (msg) => {
      this.UI.info(`⚠️ Error: ${msg}`);
    });
    this.SWITCHBOARD.registerEvent("station-playing", (stationName) => {
      this.STATE.set("currentStation", stationName);
    });
    this.SWITCHBOARD.registerEvent("stations-url", (url) => {
      this.STATE.set("stations_url", url);
    });

    // UI EVENTS
    this.UI.registerEvent("click-listen", async () => {
      this.STATE.set("localMode", !this.STATE.get("localMode"));
    });
    this.UI.registerEvent("click-station", (stationName) => {
      if (this.STATE.get("localMode")) {
        this.STATE.set("currentStation", stationName);
      } else {
        this.SWITCHBOARD.sendStationRequest(stationName);
      }
    });
    this.UI.registerEvent("click-stop", () => {
      if (this.STATE.get("localMode")) {
        this.STATE.set("currentStation", null);
      } else {
        this.SWITCHBOARD.sendStationRequest(null);
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

  async loadStations(stations_url) {
    this.UI.renderSkeletonStations();
    try {
      const response = await fetch(stations_url);
      const station_data = await response.json();
      this.STREAMER.setStations(station_data);
      this.UI.renderStations(station_data);
      this.UI.highlightCurrentStation(this.STATE.get("currentStation"));
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
