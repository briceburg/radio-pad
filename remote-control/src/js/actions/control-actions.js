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
  applyRetainedStatus,
  authStore,
  controlStore,
  listenStore,
  patchStore,
} from "../store.js";
import { toastWarning } from "../notifications.js";

const STATION_CATALOG_OK_STATUS = {
  scope: "station_catalog",
  level: "ok",
};
const STATION_CATALOG_UNAVAILABLE_STATUS = {
  scope: "station_catalog",
  level: "warning",
  summary: "Station catalog unavailable.",
};

export function createControlActions({ control, listen }) {
  const getTabStore = (tabName) =>
    tabName === "listen" ? listenStore : controlStore;
  const updateTab = (tabName, state) => patchStore(getTabStore(tabName), state);

  const stationCatalogLoads = { control: null, listen: null };

  function abortStationCatalogLoad(tabName) {
    const load = stationCatalogLoads[tabName];
    if (load) {
      load.controller.abort();
      stationCatalogLoads[tabName] = null;
    }
  }

  function setStatusMap(statusMap, status) {
    if (!(status?.scope && status?.level)) return;
    const controlState = controlStore.get();
    updateTab("control", {
      [statusMap]: applyRetainedStatus(controlState[statusMap], status),
    });
  }

  async function loadStationCatalog(url, tabName = "control") {
    if (!url) {
      abortStationCatalogLoad(tabName);
      updateTab(tabName, {
        stationCatalog: null,
        currentStation: null,
        loading: false,
      });
      return null;
    }

    if (stationCatalogLoads[tabName]?.url === url) return null;

    abortStationCatalogLoad(tabName);
    const controller = new AbortController();
    const load = { url, controller };
    stationCatalogLoads[tabName] = load;
    updateTab(tabName, { loading: true });

    try {
      const response = await fetch(url, { signal: controller.signal });
      if (!response.ok) throw new Error(`Fetch failed (${response.status})`);

      const stationCatalog = await response.json();

      if (stationCatalogLoads[tabName] !== load) return null;

      if (tabName === "listen") listen.setStationCatalog(stationCatalog);

      if (tabName === "control") {
        setStatusMap("resourceStatuses", STATION_CATALOG_OK_STATUS);
      }

      updateTab(tabName, { stationCatalog, loading: false });
      stationCatalogLoads[tabName] = null;
      return stationCatalog;
    } catch (error) {
      if (
        error?.name === "AbortError" ||
        stationCatalogLoads[tabName] !== load
      ) {
        return null;
      }

      stationCatalogLoads[tabName] = null;
      updateTab(tabName, { loading: false });
      if (tabName === "control") {
        setStatusMap("resourceStatuses", STATION_CATALOG_UNAVAILABLE_STATUS);
      }
      toastWarning("Failed loading station catalog.", error);
      return null;
    }
  }

  control.addEventListener("connect", () =>
    updateTab("control", {
      connectionState: "connected",
    }),
  );
  control.addEventListener("connecting", () =>
    updateTab("control", {
      connectionState: "connecting",
      playerConnected: null,
    }),
  );
  control.addEventListener("disconnect", () =>
    updateTab("control", {
      connectionState: "disconnected",
      playerConnected: null,
    }),
  );
  control.addEventListener("error", (event) => toastWarning(event.detail));
  control.addEventListener("playbackstate", (event) =>
    updateTab("control", { currentStation: event.detail }),
  );
  control.addEventListener("stationcatalogurl", (event) =>
    loadStationCatalog(event.detail, "control"),
  );
  control.addEventListener("playerpresence", (event) => {
    const connected = event.detail?.connected === true;
    updateTab("control", {
      playerConnected: connected,
    });
  });
  control.addEventListener("playerstatus", (event) =>
    setStatusMap("playerStatuses", event.detail),
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
    setRegistryStatus(status = {}) {
      setStatusMap("resourceStatuses", {
        ...status,
        scope: "registry",
      });
    },

    async selectPlayer(player) {
      updateTab("control", {
        player,
        stationCatalog: null,
        currentStation: null,
        connectionState: player ? "connecting" : "idle",
        playerConnected: null,
        playerStatuses: {},
        resourceStatuses: {},
        loading: player ? true : false,
      });
      if (!player) {
        abortStationCatalogLoad("control");
        control.disconnect();
        return;
      }
      const token = authStore.get()?.registryBearerToken || null;
      await control.connect(player.switchboard_url, token);
      await loadStationCatalog(player.stations_url, "control");
    },

    async selectPreset(presetId) {
      return loadStationCatalog(presetId, "listen");
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
