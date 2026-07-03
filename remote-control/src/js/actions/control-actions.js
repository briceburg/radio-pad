// SPDX-FileCopyrightText: 2025 Brice Burgess (github.com/briceburg)
// SPDX-License-Identifier: AGPL-3.0-or-later

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

export function createControlActions({ localPlayback, control }) {
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

  const stationCommands = {
    control: {
      async start(callSign) {
        control.startPlayback(callSign);
      },
      async stop() {
        control.stopPlayback();
      },
    },
    listen: {
      async start(callSign) {
        const station = listenStore
          .get()
          .radioDial?.stations?.find(
            (candidate) => candidate.call_sign === callSign,
          );
        const started = await localPlayback.play(station);
        if (!started) return toastWarning("Couldn’t start station playback.");
        updateTab("listen", { currentStation: callSign });
      },
      async stop() {
        await localPlayback.stop();
        updateTab("listen", { currentStation: null });
      },
    },
  };

  async function loadRadioDial(url, tabName = "control") {
    if (!url) {
      abortRadioDialLoad(tabName);
      updateTab(tabName, {
        radioDial: null,
        currentStation: null,
        requestedStation: null,
        failedStation: null,
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
      connectionMessage: null,
    }),
  );
  control.addEventListener("connecting", () =>
    updateTab("control", {
      connectionState: "connecting",
      connectionMessage: null,
      playerConnected: null,
      currentStation: null,
      requestedStation: null,
      failedStation: null,
    }),
  );
  control.addEventListener("disconnect", () =>
    updateTab("control", {
      connectionState: "disconnected",
      connectionMessage: null,
      playerConnected: null,
      currentStation: null,
      requestedStation: null,
      failedStation: null,
    }),
  );
  control.addEventListener("accessdenied", (event) => {
    updateTab("control", {
      connectionState: "unauthorized",
      connectionMessage: event.detail,
      playerConnected: null,
      currentStation: null,
      requestedStation: null,
      failedStation: null,
    });
    toastWarning(event.detail);
  });
  control.addEventListener("error", (event) => toastWarning(event.detail));
  control.addEventListener("playbackstate", (event) =>
    updateTab("control", {
      currentStation: event.detail.callSign,
      requestedStation: event.detail.requestedCallSign,
      failedStation: event.detail.failedCallSign,
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
      const signedOut = Boolean(lastAuthToken && !newToken);
      lastAuthToken = newToken;
      if (newToken) {
        const player = controlStore.get().player;
        if (player?.switchboard_url) {
          control.connect(player.switchboard_url, newToken);
        }
      } else if (signedOut) {
        control.disconnect();
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
        failedStation: null,
        connectionState: player ? "connecting" : "idle",
        connectionMessage: null,
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
      await (stationCommands[tabName] || stationCommands.control).start(
        callSign,
      );
    },

    async stopStation(tabName) {
      await (stationCommands[tabName] || stationCommands.control).stop();
    },
  };
}
