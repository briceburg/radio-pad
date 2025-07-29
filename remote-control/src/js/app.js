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

import { RadioPadPreferences } from "./lib/preferences.js";
import { RadioPadState } from "./lib/state.js";
import { RadioPadSwitchboard } from "./lib/switchboard.js";
import { RadioPadUI } from "./lib/ui.js";
import { discoverPlayer, discoverPlayers } from "./lib/discovery.js";

class RadioPad {
  constructor() {
    this.STATE = new RadioPadState();
    this.PREFS = new RadioPadPreferences();
    this.SWITCHBOARD = new RadioPadSwitchboard();
    this.UI = new RadioPadUI();

    // PREFERENCE CHANGES
    this.PREFS.registerEvent("on-change", async (data) => {
      console.log(`data: ${data.key} = ${data.value}`);
      switch (data.key) {
        case "registryUrl":
          this.PREFS.preferences.playerId.options = await discoverPlayers(
            data.value
          );
          break;
        case "playerId":
          const registryUrl = await this.PREFS.get("registryUrl");
          this.STATE.set(
            "player",
            await discoverPlayer(registryUrl, data.value)
          );
          break;
      }
    });

    // STATE CHANGES
    this.STATE.registerEvent("on-change", async (data) => {
      switch (data.key) {
        case "currentStation":
          this.UI.highlightCurrentStation(data.value);
          break;
        case "player":
          await this.SWITCHBOARD.connect(data.value.switchboardUrl);
          break;
        case "stationsUrl":
          await this.loadStations(data.value);
          break;
      }
    });

    // SWITCHBOARD EVENTS
    this.SWITCHBOARD.registerEvent("connect", (url) => {
      this.UI.info(`✅ Connected`);
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
      this.STATE.set("stationsUrl", url);
    });

    // UI EVENTS
    this.UI.registerEvent("click-station", (stationName) => {
      this.SWITCHBOARD.sendStationRequest(stationName);
    });
    this.UI.registerEvent("click-stop", () => {
      this.SWITCHBOARD.sendStationRequest(null);
    });
  }

  async start() {
    this.UI.init();
    await this.PREFS.init();
    this.UI.renderPreferences(this.PREFS);
  }

  async loadStations(url) {
    this.UI.renderSkeletonStations();
    try {
      const response = await fetch(url);
      const stations = await response.json();
      this.UI.renderStations(stations, this.STATE.get("currentStation"));
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
