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
import { isAbortError } from "../utils/errors.js";
import {
  controlStore,
  listenStore,
  patchStore,
} from "../state-store/app-store.js";
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
    console.warn("Invalid VITE_SWITCHBOARD_URL override; using player URL.", {
      override,
      url,
      error,
    });
    return url;
  }
}

export function createControlActions({ control, listen }) {
  const stationControllers = new Map();
  const getTabStore = (tabName) =>
    tabName === "listen" ? listenStore : controlStore;
  const patchTabStore = (tabName, patch) =>
    patchStore(getTabStore(tabName), patch);
  const resetTabStations = (tabName) => {
    stationControllers.get(tabName)?.abort();
    stationControllers.delete(tabName);
    patchTabStore(tabName, {
      stationsData: null,
      currentStation: null,
      loading: false,
    });
  };

  function startStationRequest(tabName) {
    stationControllers.get(tabName)?.abort();
    const controller = new AbortController();
    stationControllers.set(tabName, controller);
    return controller.signal;
  }

  function isCurrentStationRequest(tabName, signal) {
    return (
      !signal.aborted && stationControllers.get(tabName)?.signal === signal
    );
  }

  async function loadStations(stationsUrl, tabName = "control") {
    if (!stationsUrl) {
      resetTabStations(tabName);
      return null;
    }

    patchTabStore(tabName, { loading: true });
    const signal = startStationRequest(tabName);

    try {
      const response = await fetch(stationsUrl, { signal });
      if (!response.ok) {
        throw new Error(`Station list request failed (${response.status}).`);
      }
      const stationsData = await response.json();
      if (!isCurrentStationRequest(tabName, signal)) {
        return null;
      }

      if (tabName === "listen") {
        listen.setStations(stationsData);
      }

      patchTabStore(tabName, {
        stationsData,
        loading: false,
      });
      return stationsData;
    } catch (error) {
      if (isAbortError(error) || !isCurrentStationRequest(tabName, signal)) {
        return null;
      }
      patchTabStore(tabName, { loading: false });
      toastWarning("⚠️ Failed loading stations.", error);
      return null;
    }
  }

  control.onConnect = () => {
    patchStore(controlStore, {
      statusText: `✅ Connected to ${controlStore.get().player.name}`,
    });
  };
  control.onConnecting = () => {
    patchStore(controlStore, { statusText: "🔄 Connecting..." });
  };
  control.onDisconnect = () => {
    patchStore(controlStore, {
      statusText: "🔌 Disconnected. Reconnecting...",
    });
  };
  control.onError = (message) => {
    toastWarning(`⚠️ ${message}`);
  };
  control.onStationPlaying = (stationName) => {
    patchStore(controlStore, { currentStation: stationName });
  };
  control.onStationsUrl = (stationsUrl) => {
    void loadStations(stationsUrl, "control");
  };

  return {
    async selectPlayer(player) {
      patchStore(controlStore, {
        player,
        currentStation: null,
        loading: true,
      });
      await control.connect(
        resolvePlayerSwitchboardUrl(player.switchboard_url),
      );
    },

    async selectPreset(presetId) {
      if (!presetId) {
        resetTabStations("listen");
        return null;
      }

      return loadStations(presetId, "listen");
    },

    async clickStation(tabName, station) {
      if (tabName === "listen") {
        const started = await listen.play(station);
        if (!started) {
          toastWarning("⚠️ Failed starting station playback.");
          return;
        }
        patchStore(listenStore, { currentStation: station });
        return;
      }

      control.sendStationRequest(station);
    },

    async stopStation(tabName) {
      if (tabName === "listen") {
        await listen.stop();
        patchStore(listenStore, { currentStation: null });
        return;
      }

      control.sendStationRequest(null);
    },
  };
}
