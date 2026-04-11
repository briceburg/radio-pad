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

import {
  authStore,
  controlStore,
  listenStore,
  patchStore,
  preferencesStore,
} from "../store.js";
import { toastWarning } from "../notifications.js";

export function createControlActions({ control, listen }) {
  const getTabStore = (tabName) =>
    tabName === "listen" ? listenStore : controlStore;
  const updateTab = (tabName, state) => patchStore(getTabStore(tabName), state);
  const getOptionLabel = (key, value) => {
    const options = preferencesStore.get().definitions?.[key]?.options || [];
    return (
      options.find((option) => option.value === value)?.label || value || null
    );
  };
  const requestControllers = { control: null, listen: null };

  const abortStationLoad = (tabName) => {
    requestControllers[tabName]?.abort();
    requestControllers[tabName] = null;
  };

  async function loadStations(url, tabName = "control", titleName = null) {
    if (!url) {
      abortStationLoad(tabName);
      updateTab(tabName, {
        stationsData: null,
        currentStation: null,
        loading: false,
        ...(tabName === "listen" ? { titleName } : {}),
      });
      return null;
    }

    updateTab(tabName, {
      loading: true,
      ...(tabName === "listen" ? { titleName } : {}),
    });
    abortStationLoad(tabName);
    const controller = new AbortController();
    requestControllers[tabName] = controller;

    try {
      const response = await fetch(url, { signal: controller.signal });
      if (!response.ok) throw new Error(`Fetch failed (${response.status})`);

      const stationsData = await response.json();
      if (requestControllers[tabName] !== controller) return null;

      if (tabName === "listen") listen.setStations(stationsData);

      updateTab(tabName, {
        stationsData,
        loading: false,
        ...(tabName === "control"
          ? { connectionState: "connected" }
          : { titleName: stationsData?.name || titleName }),
      });
      requestControllers[tabName] = null;
      return stationsData;
    } catch (error) {
      if (
        error.name === "AbortError" ||
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
    }),
  );
  control.addEventListener("disconnect", () =>
    updateTab("control", {
      statusText: controlStore.get().player?.id
        ? "Switchboard unavailable. Reconnecting..."
        : "Disconnected.",
      connectionState: "disconnected",
    }),
  );
  control.addEventListener("error", (event) => toastWarning(event.detail));
  control.addEventListener("stationplaying", (event) =>
    updateTab("control", { currentStation: event.detail }),
  );
  control.addEventListener("stationsurl", (event) =>
    loadStations(event.detail, "control"),
  );

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
    async selectPlayer(player, options = {}) {
      const { reconnectOnly = false } = options;
      if (reconnectOnly) {
        updateTab("control", { connectionState: "connecting" });
      } else {
        abortStationLoad("control");
        updateTab("control", {
          player,
          stationsData: null,
          currentStation: null,
          statusText: "",
          loading: player ? true : false,
          connectionState: player ? "connecting" : "idle",
        });
      }
      if (!player?.switchboard_url) {
        control.disconnect();
        return;
      }
      const token = authStore.get()?.registryBearerToken || null;
      await control.connect(player.switchboard_url, token);
      if (!reconnectOnly) {
        await loadStations(player.stations_url, "control");
      }
    },

    async selectPreset(presetId) {
      const label = getOptionLabel("preset", presetId);
      return loadStations(presetId, "listen", label);
    },

    async clickStation(tabName, station) {
      if (tabName === "listen") {
        const started = await listen.play(station);
        if (!started) return toastWarning("Failed starting station playback.");
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
