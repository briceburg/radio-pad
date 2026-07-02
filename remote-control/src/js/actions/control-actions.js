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

const RADIO_DIAL_OK_STATUS = {
  scope: "radio_dial",
  level: "ok",
};
const RADIO_DIAL_UNAVAILABLE_STATUS = {
  scope: "radio_dial",
  level: "warning",
  summary: "RadioDial unavailable.",
};

function isPlayableStation(station) {
  return [station?.call_sign, station?.stream_url].every(
    (value) => typeof value === "string" && value.length > 0,
  );
}

function parseRadioDial(value) {
  const stations = value?.stations;
  const callSigns = Array.isArray(stations)
    ? stations.map((station) => station.call_sign)
    : [];
  if (
    typeof value?.name !== "string" ||
    !Array.isArray(stations) ||
    !stations.every(isPlayableStation) ||
    new Set(callSigns).size !== callSigns.length
  ) {
    throw new Error("Invalid RadioDial response");
  }
  return value;
}

function radioDialResourcePath(url) {
  try {
    const segments = new URL(url, window.location.origin).pathname
      .split("/")
      .filter(Boolean);
    const resource = segments.slice(-4);
    return resource[0] === "accounts" && resource[2] === "radio-dials"
      ? resource.join("/")
      : null;
  } catch {
    return null;
  }
}

function resolveReportedRadioDialUrl(player, reportedUrl) {
  const configuredUrl = player?.configured_radio_dial_url;
  const reportedResource = radioDialResourcePath(reportedUrl);
  return configuredUrl &&
    reportedResource &&
    reportedResource === radioDialResourcePath(configuredUrl)
    ? configuredUrl
    : reportedUrl;
}

export function createControlActions({ control, listen }) {
  const getTabStore = (tabName) =>
    tabName === "listen" ? listenStore : controlStore;
  const updateTab = (tabName, state) => patchStore(getTabStore(tabName), state);

  const radioDialLoads = { control: null, listen: null };

  function abortRadioDialLoad(tabName) {
    const load = radioDialLoads[tabName];
    if (load) {
      load.controller.abort();
      radioDialLoads[tabName] = null;
    }
  }

  function setStatusMap(statusMap, status) {
    if (!(status?.scope && status?.level)) return;
    const controlState = controlStore.get();
    updateTab("control", {
      [statusMap]: applyRetainedStatus(controlState[statusMap], status),
    });
  }

  async function loadRadioDial(url, tabName = "control") {
    if (!url) {
      abortRadioDialLoad(tabName);
      updateTab(tabName, {
        radioDial: null,
        currentStation: null,
        requestedStation: null,
        loading: false,
      });
      return null;
    }

    if (radioDialLoads[tabName]?.url === url) return null;

    abortRadioDialLoad(tabName);
    const controller = new AbortController();
    const load = { url, controller };
    radioDialLoads[tabName] = load;
    updateTab(tabName, { loading: true });

    try {
      const response = await fetch(url, { signal: controller.signal });
      if (!response.ok) throw new Error(`Fetch failed (${response.status})`);

      const radioDial = parseRadioDial(await response.json());

      if (radioDialLoads[tabName] !== load) return null;

      if (tabName === "control") {
        setStatusMap("resourceStatuses", RADIO_DIAL_OK_STATUS);
      }

      updateTab(tabName, { radioDial, loading: false });
      radioDialLoads[tabName] = null;
      return radioDial;
    } catch (error) {
      if (error?.name === "AbortError" || radioDialLoads[tabName] !== load) {
        return null;
      }

      radioDialLoads[tabName] = null;
      updateTab(tabName, { loading: false });
      if (tabName === "control") {
        setStatusMap("resourceStatuses", RADIO_DIAL_UNAVAILABLE_STATUS);
      }
      toastWarning("Couldn’t load RadioDial.", error);
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
      currentStation: null,
      requestedStation: null,
    }),
  );
  control.addEventListener("disconnect", () =>
    updateTab("control", {
      connectionState: "disconnected",
      playerConnected: null,
      currentStation: null,
      requestedStation: null,
    }),
  );
  control.addEventListener("error", (event) => toastWarning(event.detail));
  control.addEventListener("playbackstate", (event) =>
    updateTab("control", {
      currentStation: event.detail.callSign,
      requestedStation: event.detail.requestedCallSign,
    }),
  );
  control.addEventListener("radiodialurl", (event) => {
    const player = controlStore.get().player;
    loadRadioDial(resolveReportedRadioDialUrl(player, event.detail), "control");
  });
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
        radioDial: null,
        currentStation: null,
        requestedStation: null,
        connectionState: player ? "connecting" : "idle",
        playerConnected: null,
        playerStatuses: {},
        resourceStatuses: {},
        loading: player ? true : false,
      });
      if (!player) {
        abortRadioDialLoad("control");
        control.disconnect();
        return;
      }
      const token = authStore.get()?.registryBearerToken || null;
      control.connect(player.switchboard_url, token);
      await loadRadioDial(player.configured_radio_dial_url, "control");
    },

    selectRadioDial(url) {
      return loadRadioDial(url, "listen");
    },

    async clickStation(tabName, callSign) {
      if (tabName === "listen") {
        const station = listenStore
          .get()
          .radioDial?.stations?.find(
            (candidate) => candidate.call_sign === callSign,
          );
        const started = await listen.play(station);
        if (!started) return toastWarning("Couldn’t start station playback.");
        return updateTab("listen", { currentStation: callSign });
      }
      control.startPlayback(callSign);
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
