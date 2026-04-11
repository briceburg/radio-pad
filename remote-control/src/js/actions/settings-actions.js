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
  discoverAccounts,
  discoverPlayer,
  discoverPlayers,
  discoverPresets,
} from "../services/registry-discovery.js";
import {
  patchStore,
  preferencesStore,
  registryStore,
  settingsUiStore,
} from "../store.js";
import {
  dismissRegistryUnavailableToast,
  toastDanger,
  toastRegistryUnavailable,
} from "../notifications.js";
import {
  advanceRetryState,
  createRetryState,
  resetRetryState,
} from "../utils/retry.js";

export function createSettingsActions({
  prefs,
  auth,
  onPlayerSelected,
  onPresetSelected,
}) {
  const setRegistryPhase = (phase, errorText = "", extra = {}) => {
    patchStore(registryStore, { phase, errorText, ...extra });
  };
  const retryState = createRetryState();

  let lastPlayerId = null;
  let lastPresetId = null;
  let hasSyncedOnce = false;
  let retryTimer = null;

  const clearRetryTimer = () => {
    if (retryTimer) {
      clearTimeout(retryTimer);
      retryTimer = null;
    }
  };

  const scheduleRetry = (failureReason, options) => {
    clearRetryTimer();
    const { attempt, delayMs } = advanceRetryState(retryState);
    setRegistryPhase("retrying", "Registry unavailable", {
      retryAttempt: attempt,
      retryDelayMs: delayMs,
    });
    retryTimer = setTimeout(() => {
      retryTimer = null;
      void sync(failureReason, options);
    }, delayMs);
  };

  let syncPromise = null;
  async function sync(failureReason = "accounts", options = {}) {
    if (syncPromise) return syncPromise;
    clearRetryTimer();
    const previousPhase = registryStore.get().phase;
    syncPromise = (async () => {
      try {
        const url = await prefs.get("registryUrl");
        if (!url) {
          resetRetryState(retryState);
          await dismissRegistryUnavailableToast();
          setRegistryPhase("idle", "", { retryAttempt: 0, retryDelayMs: 0 });
          return;
        }

        setRegistryPhase("loading", "", {
          retryAttempt: retryState.attempt,
          retryDelayMs: 0,
        });

        const accounts = await discoverAccounts(url, auth, options);
        await prefs.setOptions("accountId", accounts);

        const accountId = (await prefs.get("accountId")) || null;

        const [players, presets] = await Promise.all([
          discoverPlayers(accountId, prefs, auth, options),
          discoverPresets(accountId, prefs, auth, options),
        ]);

        await prefs.setOptions("playerId", players);
        await prefs.setOptions("presetId", presets);

        const playerId = (await prefs.get("playerId")) || null;
        // Validate against available options, clear if no longer available (e.g. signed out)
        const isPlayerValid =
          !playerId ||
          players === null ||
          players.some((p) => p.value === playerId);
        const resolvedPlayerId = isPlayerValid ? playerId : null;

        if (resolvedPlayerId) {
          if (resolvedPlayerId !== lastPlayerId || !hasSyncedOnce) {
            const player = await discoverPlayer(
              resolvedPlayerId,
              prefs,
              auth,
              options,
            );
            await onPlayerSelected(player || null);
            lastPlayerId = player ? resolvedPlayerId : null;
          } else if (previousPhase !== "ready") {
            const player = await discoverPlayer(
              resolvedPlayerId,
              prefs,
              auth,
              options,
            );
            await onPlayerSelected(player || null, { reconnectOnly: true });
          }
        } else if (lastPlayerId !== null || !hasSyncedOnce) {
          await onPlayerSelected(null);
          lastPlayerId = null;
        }

        const presetId = (await prefs.get("presetId")) || null;
        if (presetId !== lastPresetId || !hasSyncedOnce) {
          await onPresetSelected(presetId || null);
          lastPresetId = presetId;
        }
        clearRetryTimer();
        resetRetryState(retryState);
        setRegistryPhase("ready", "", { retryAttempt: 0, retryDelayMs: 0 });
        await dismissRegistryUnavailableToast();
        hasSyncedOnce = true;
      } catch (error) {
        if (error.name !== "AbortError") {
          if (retryState.attempt === 0) {
            toastRegistryUnavailable(error);
          }
          scheduleRetry(failureReason, options);
        }
      } finally {
        if (!hasSyncedOnce && registryStore.get().phase === "idle") {
          await onPlayerSelected(null);
          await onPresetSelected(null);
          hasSyncedOnce = true;
        }
        preferencesStore.set({ definitions: prefs.getSnapshot() });
        syncPromise = null;
      }
    })();
    return syncPromise;
  }

  return {
    async initialize() {
      setRegistryPhase("loading", "", { retryAttempt: 0, retryDelayMs: 0 });
      await prefs.init();
      preferencesStore.set({ definitions: prefs.getSnapshot() });

      const isOauthCallback = await auth.init();
      await sync();
      return isOauthCallback;
    },

    sync: () => sync(),

    async save(settingsMap) {
      settingsUiStore.set({ saveState: "saving" });
      const { status, results } = await prefs.setMany(settingsMap);

      if (status !== "ok") {
        settingsUiStore.set({ saveState: "error" });
        const invalid = Object.values(results).find(
          (r) => r.status === "invalid",
        );
        const label = prefs.getSnapshot()[invalid.key]?.label || invalid.key;
        toastDanger(`Failed saving settings. Invalid ${label}.`);
        return { status, results };
      }

      await sync("accounts", { fromSettingsSave: true });
      settingsUiStore.set({ saveState: "saved" });

      return { status, results };
    },

    markDirty() {
      if (settingsUiStore.get().saveState !== "saving") {
        settingsUiStore.set({ saveState: "idle" });
      }
    },

    async refreshAccountsForCurrentRegistry(
      failureReason = "accounts",
      options = {},
    ) {
      await sync(failureReason, options);
    },
  };
}
