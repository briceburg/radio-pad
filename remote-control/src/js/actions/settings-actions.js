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
import { preferencesStore, settingsUiStore } from "../store.js";
import { toastDanger, toastRegistryFailure } from "../notifications.js";

const REGISTRY_OK_STATUS = { level: "ok" };
const REGISTRY_UNAVAILABLE_STATUS = {
  level: "warning",
  summary: "Registry unavailable. Using last known selections.",
};

export function createSettingsActions({
  prefs,
  auth,
  onPlayerSelected,
  onPresetSelected,
  onRegistryStatus = () => {},
}) {
  let lastPlayerId = null;
  let lastPresetId = null;
  let hasSyncedOnce = false;

  let syncPromise = null;
  async function sync(failureReason = "accounts", options = {}) {
    if (syncPromise) return syncPromise;
    syncPromise = (async () => {
      let registryFailure = null;
      const noteRegistryFailure = (message, error) => {
        if (error?.name === "AbortError") throw error;
        console.warn(message, error);
        if (!registryFailure) registryFailure = error;
      };

      try {
        const url = await prefs.get("registryUrl");
        if (!url) return;

        // null means discovery failed; [] means the registry was reachable and returned no items.
        let accounts = null;
        try {
          accounts = await discoverAccounts(url, auth, options);
        } catch (err) {
          noteRegistryFailure("Failed to discover accounts", err);
        }
        if (accounts !== null) {
          await prefs.setOptions("accountId", accounts);
        }

        const accountId = (await prefs.get("accountId")) || null;

        // Discover APIs natively handle null accountId safely
        const results = await Promise.allSettled([
          discoverPlayers(accountId, prefs, auth, options),
          discoverPresets(accountId, prefs, auth, options),
        ]);
        const players =
          results[0].status === "fulfilled" ? results[0].value : null;
        const presets =
          results[1].status === "fulfilled" ? results[1].value : null;

        if (results[0].status === "rejected") {
          noteRegistryFailure("Failed to discover players", results[0].reason);
        }
        if (results[1].status === "rejected") {
          noteRegistryFailure("Failed to discover presets", results[1].reason);
        }

        if (players !== null) await prefs.setOptions("playerId", players);
        if (presets !== null) await prefs.setOptions("presetId", presets);

        const playerId = (await prefs.get("playerId")) || null;
        // Validate against available options, clear if no longer available (e.g. signed out)
        const isPlayerValid =
          !playerId ||
          players === null ||
          players.some((p) => p.value === playerId);
        const resolvedPlayerId = isPlayerValid ? playerId : null;

        if (resolvedPlayerId) {
          if (resolvedPlayerId !== lastPlayerId || !hasSyncedOnce) {
            let player = null;
            try {
              player = await discoverPlayer(
                resolvedPlayerId,
                prefs,
                auth,
                options,
              );
            } catch (err) {
              noteRegistryFailure("Failed to discover selected player", err);
            }

            if (player) {
              await onPlayerSelected(player);
              lastPlayerId = resolvedPlayerId;
            } else if (!registryFailure) {
              await onPlayerSelected(null);
              lastPlayerId = null;
            }
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
        hasSyncedOnce = true;

        if (registryFailure) {
          onRegistryStatus(REGISTRY_UNAVAILABLE_STATUS);
          toastRegistryFailure(failureReason, registryFailure, options);
        } else {
          onRegistryStatus(REGISTRY_OK_STATUS);
        }
      } catch (error) {
        if (error.name !== "AbortError") {
          onRegistryStatus(REGISTRY_UNAVAILABLE_STATUS);
          toastRegistryFailure(failureReason, error, options);
          if (!registryFailure) registryFailure = error;
        }
      } finally {
        if (!hasSyncedOnce && !registryFailure) {
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
      await prefs.init();
      preferencesStore.set({ definitions: prefs.getSnapshot() });

      const isOauthCallback = await auth.init();
      if (!auth.signedIn) {
        await sync();
      }
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
        toastDanger(`⚠️ Failed saving settings. Invalid ${label}.`);
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
