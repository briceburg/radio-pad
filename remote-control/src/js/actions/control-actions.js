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

import { authStore, controlStore, listenStore, patchStore } from "../store.js";
import { toastWarning } from "../notifications.js";

export function createControlActions({ control, listen }) {
  const getTabStore = (tabName) =>
    tabName === "listen" ? listenStore : controlStore;
  const updateTab = (tabName, state) => patchStore(getTabStore(tabName), state);

  const requestControllers = { control: null, listen: null };

  function abortStationLoad(tabName) {
    const controller = requestControllers[tabName];
    if (controller) {
      controller.abort();
      requestControllers[tabName] = null;
    }
  }

  function updatePlayerStatus(status) {
    const { scope, level, summary } = status.detail || {};
    if (!scope) return;

    const controlState = controlStore.get();
    const nextStatuses = { ...controlState.playerStatuses };
    if (level === "ok") {
      delete nextStatuses[scope];
    } else {
      nextStatuses[scope] = {
        level,
        summary: typeof summary === "string" ? summary : null,
      };
    }

    const playbackSummary = nextStatuses.playback?.summary;
    const statusText =
      playbackSummary ||
      (controlState.playerConnected === false
        ? "Player offline."
        : controlState.connectionState === "connected"
          ? `Connected to ${controlState.player.name}`
          : controlState.statusText);
    updateTab("control", {
      playerStatuses: nextStatuses,
      statusText,
    });
  }

  async function loadStations(url, tabName = "control") {
    if (!url) {
      abortStationLoad(tabName);
      updateTab(tabName, {
        stationsData: null,
        currentStation: null,
        loading: false,
      });
      return null;
    }

    abortStationLoad(tabName);
    const controller = new AbortController();
    requestControllers[tabName] = controller;
    updateTab(tabName, { loading: true });

    try {
      const response = await fetch(url, { signal: controller.signal });
      if (!response.ok) throw new Error(`Fetch failed (${response.status})`);

      const stationsData = await response.json();

      if (requestControllers[tabName] !== controller) return null;

      if (tabName === "listen") listen.setStations(stationsData);

      updateTab(tabName, { stationsData, loading: false });
      requestControllers[tabName] = null;
      return stationsData;
    } catch (error) {
      if (
        error?.name === "AbortError" ||
        requestControllers[tabName] !== controller
      ) {
        return null;
      }

      requestControllers[tabName] = null;
      updateTab(tabName, { loading: false });
      toastWarning("Failed loading stations.", error);
      return null;
    }
  }

  control.addEventListener("connect", () =>
    updateTab("control", {
      statusText: `Connected to ${controlStore.get().player.name}`,
      connectionState: "connected",
    }),
  );
  control.addEventListener("connecting", () =>
    updateTab("control", {
      statusText: "Connecting to switchboard...",
      connectionState: "connecting",
      playerConnected: null,
    }),
  );
  control.addEventListener("disconnect", () =>
    updateTab("control", {
      statusText: controlStore.get().player?.id
        ? "Switchboard unavailable. Reconnecting..."
        : "Disconnected.",
      connectionState: "disconnected",
      playerConnected: null,
    }),
  );
  control.addEventListener("error", (event) => toastWarning(event.detail));
  control.addEventListener("playbackstate", (event) =>
    updateTab("control", { currentStation: event.detail }),
  );
  control.addEventListener("stationcatalogurl", (event) =>
    loadStations(event.detail, "control"),
  );
  control.addEventListener("playerpresence", (event) => {
    const connected = event.detail?.connected === true;
    updateTab("control", {
      playerConnected: connected,
      statusText: connected
        ? `Connected to ${controlStore.get().player.name}`
        : "Player offline.",
    });
  });
  control.addEventListener("playerstatus", updatePlayerStatus);

  let lastAuthToken = authStore.get()?.registryBearerToken;
  authStore.subscribe((authState) => {
    const newToken = authState.registryBearerToken;
    if (newToken !== lastAuthToken) {
      lastAuthToken = newToken;
      // Only proactively reconnect if we have a new token.
      // If we signed out (lost token), we rely on settings sync to gracefully
      // drop the player if it's no longer accessible.
      if (newToken) {
        const player = controlStore.get().player;
        if (player?.switchboard_url) {
          control.connect(player.switchboard_url, newToken);
        }
      }
    }
  });

  return {
    async selectPlayer(player) {
      updateTab("control", {
        player,
        stationsData: null,
        currentStation: null,
        statusText: "",
        connectionState: player ? "connecting" : "idle",
        playerConnected: null,
        playerStatuses: {},
        loading: player ? true : false,
      });
      if (!player) {
        abortStationLoad("control");
        control.disconnect();
        return;
      }
      const token = authStore.get()?.registryBearerToken || null;
      await control.connect(player.switchboard_url, token);
      await loadStations(player.stations_url, "control");
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
      control.startPlayback(station);
    },

    async stopStation(tabName) {
      if (tabName === "listen") {
        await listen.stop();
        return updateTab("listen", { currentStation: null });
      }
      control.stopPlayback();
    },
  };
}
