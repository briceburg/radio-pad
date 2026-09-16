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
const RADIO_DIAL_RETRY_DELAYS_MS = [1000, 2000, 4000];

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

function waitForRetry(delay, signal) {
  if (signal.aborted) return Promise.resolve(false);
  return new Promise((resolve) => {
    const aborted = () => {
      clearTimeout(timeout);
      resolve(false);
    };
    const timeout = setTimeout(() => {
      signal.removeEventListener("abort", aborted);
      resolve(true);
    }, delay);
    signal.addEventListener("abort", aborted, { once: true });
  });
}

async function fetchRadioDial(url, load) {
  for (let attempt = 0; ; attempt += 1) {
    try {
      const response = await fetch(url, {
        cache: "no-cache",
        signal: load.controller.signal,
      });
      if (!response.ok) throw new Error(`Fetch failed (${response.status})`);
      return {
        radioDial: parseRadioDial(await response.json()),
        revision: response.headers?.get?.("etag"),
      };
    } catch (error) {
      if (error?.name === "AbortError") throw error;
      const retryBase = load.revision
        ? RADIO_DIAL_RETRY_DELAYS_MS[attempt]
        : undefined;
      const retryDelay =
        retryBase === undefined ? undefined : retryBase * (0.5 + Math.random());
      if (
        retryDelay === undefined ||
        !(await waitForRetry(retryDelay, load.controller.signal))
      ) {
        throw error;
      }
    }
  }
}

export function createControlActions({ localPlayback, control }) {
  const getTabStore = (tabName) =>
    tabName === "listen" ? listenStore : controlStore;
  const updateTab = (tabName, state) => patchStore(getTabStore(tabName), state);

  const radioDialLoads = { control: null, listen: null };
  const radioDialRevisions = { control: null, listen: null };

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

  async function loadRadioDial(url, tabName = "control", revision = null) {
    if (!url) {
      abortRadioDialLoad(tabName);
      radioDialRevisions[tabName] = null;
      updateTab(tabName, {
        radioDial: null,
        currentStation: null,
        requestedStation: null,
        failedStation: null,
        loading: false,
      });
      return null;
    }

    if (revision && radioDialRevisions[tabName] === revision) {
      return getTabStore(tabName).get().radioDial;
    }
    const activeLoad = radioDialLoads[tabName];
    if (
      activeLoad?.url === url &&
      (!revision || !activeLoad.revision || activeLoad.revision === revision)
    ) {
      activeLoad.revision ||= revision;
      return null;
    }

    abortRadioDialLoad(tabName);
    const controller = new AbortController();
    const load = { url, revision, controller };
    radioDialLoads[tabName] = load;
    updateTab(tabName, { loading: true });

    try {
      const result = await fetchRadioDial(url, load);

      if (radioDialLoads[tabName] !== load) return null;

      if (tabName === "control") {
        setStatusMap("resourceStatuses", RADIO_DIAL_OK_STATUS);
      }

      updateTab(tabName, { radioDial: result.radioDial, loading: false });
      radioDialRevisions[tabName] = result.revision || load.revision;
      radioDialLoads[tabName] = null;
      return result.radioDial;
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
  control.addEventListener("radiodialstate", (event) => {
    const player = controlStore.get().player;
    loadRadioDial(
      resolveReportedRadioDialUrl(player, event.detail.url),
      "control",
      event.detail.revision,
    );
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
      radioDialRevisions.control = null;
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
        const started = await localPlayback.play(station);
        if (!started) return toastWarning("Couldn’t start station playback.");
        return updateTab("listen", { currentStation: callSign });
      }
      control.startPlayback(callSign);
    },

    async stopStation(tabName) {
      if (tabName === "listen") {
        await localPlayback.stop();
        return updateTab("listen", { currentStation: null });
      }
      control.stopPlayback();
    },
  };
}
