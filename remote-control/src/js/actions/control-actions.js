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

import { Capacitor } from "@capacitor/core";
import { controlStore, listenStore, patchStore } from "../store.js";
import { toastWarning } from "../notifications.js";

function resolvePlayerSwitchboardUrl(url) {
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
    console.warn("Invalid VITE_SWITCHBOARD_URL override.", error);
    return url;
  }
}

export function createControlActions({ control, listen }) {
  const getTabStore = (tabName) =>
    tabName === "listen" ? listenStore : controlStore;
  const updateTab = (tabName, state) => patchStore(getTabStore(tabName), state);

  // Track out-of-order fetch responses by storing current URL
  const currentRequests = { control: null, listen: null };

  async function loadStations(url, tabName = "control") {
    if (!url) {
      updateTab(tabName, {
        stationsData: null,
        currentStation: null,
        loading: false,
      });
      return null;
    }

    updateTab(tabName, { loading: true });
    currentRequests[tabName] = url;

    try {
      const response = await fetch(url);
      if (!response.ok) throw new Error(`Fetch failed (${response.status})`);

      const stationsData = await response.json();

      // Prevent stale updates if another fetch started
      if (currentRequests[tabName] !== url) return null;

      if (tabName === "listen") listen.setStations(stationsData);

      updateTab(tabName, { stationsData, loading: false });
      return stationsData;
    } catch (error) {
      if (currentRequests[tabName] !== url) return null;

      updateTab(tabName, { loading: false });
      toastWarning("⚠️ Failed loading stations.", error);
      return null;
    }
  }

  control.onConnect = () =>
    updateTab("control", {
      statusText: `✅ Connected to ${controlStore.get().player.name}`,
    });
  control.onConnecting = () =>
    updateTab("control", { statusText: "🔄 Connecting..." });
  control.onDisconnect = () =>
    updateTab("control", { statusText: "🔌 Disconnected. Reconnecting..." });
  control.onError = (message) => toastWarning(`⚠️ ${message}`);
  control.onStationPlaying = (stationName) =>
    updateTab("control", { currentStation: stationName });
  control.onStationsUrl = (url) => loadStations(url, "control");

  return {
    async selectPlayer(player) {
      updateTab("control", { player, currentStation: null, loading: true });
      await control.connect(
        resolvePlayerSwitchboardUrl(player.switchboard_url),
      );
    },

    async selectPreset(presetId) {
      return loadStations(presetId, "listen");
    },

    async clickStation(tabName, station) {
      if (tabName === "listen") {
        const started = await listen.play(station);
        if (!started)
          return toastWarning("⚠️ Failed starting station playback.");
        return updateTab("listen", { currentStation: station });
      }
      control.sendStationRequest(station);
    },

    async stopStation(tabName) {
      if (tabName === "listen") {
        await listen.stop();
        return updateTab("listen", { currentStation: null });
      }
      control.sendStationRequest(null);
    },
  };
}
