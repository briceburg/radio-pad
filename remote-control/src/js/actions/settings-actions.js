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
  discoverAuthEnabled,
  discoverPlayer,
  discoverPlayers,
  discoverRadioDials,
  radioDialUrl,
} from "../services/registry-discovery.js";
import { preferencesStore, settingsUiStore } from "../store.js";
import { toastDanger, toastRegistryFailure } from "../notifications.js";

const REGISTRY_OK_STATUS = { level: "ok" };
const REGISTRY_UNAVAILABLE_STATUS = {
  level: "warning",
  summary: "Registry unavailable. Using last known selections.",
};

function resolveSelection(value, options) {
  const available =
    !value || options === null || options.some((item) => item.value === value);
  return available ? value : null;
}

export function createSettingsActions({
  prefs,
  auth,
  onPlayerSelected,
  onRadioDialSelected,
  onRegistryStatus = () => {},
}) {
  let lastPlayerSelection = null;
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
        const registryUrl = await prefs.get("registryUrl");
        if (!registryUrl) return;

        const [accountsResult, authEnabledResult] = await Promise.allSettled([
          discoverAccounts(registryUrl, auth, options),
          discoverAuthEnabled(registryUrl, options),
        ]);
        // null means discovery failed; [] means the registry was reachable and returned no items.
        const accounts =
          accountsResult.status === "fulfilled" ? accountsResult.value : null;
        const authEnabled =
          authEnabledResult.status === "fulfilled"
            ? authEnabledResult.value
            : null;

        if (accountsResult.status === "rejected") {
          noteRegistryFailure(
            "Failed to discover accounts",
            accountsResult.reason,
          );
        }
        if (authEnabledResult.status === "rejected") {
          noteRegistryFailure(
            "Failed to discover registry auth status",
            authEnabledResult.reason,
          );
        }
        if (accounts !== null) {
          await prefs.setOptions("accountId", accounts);
        }

        const accountId = (await prefs.get("accountId")) || null;
        const playerAccessKnown = authEnabled !== null;
        const playerDiscovery = !playerAccessKnown
          ? Promise.resolve(null)
          : authEnabled && !auth.signedIn
            ? Promise.resolve([])
            : discoverPlayers(accountId, registryUrl, auth, options);

        // Discover APIs natively handle null accountId safely
        const results = await Promise.allSettled([
          playerDiscovery,
          discoverRadioDials(accountId, registryUrl, auth, options),
        ]);
        const players =
          results[0].status === "fulfilled" ? results[0].value : null;
        const radioDials =
          results[1].status === "fulfilled" ? results[1].value : null;

        if (results[0].status === "rejected") {
          noteRegistryFailure("Failed to discover players", results[0].reason);
        }
        if (results[1].status === "rejected") {
          noteRegistryFailure(
            "Failed to discover RadioDials",
            results[1].reason,
          );
        }

        if (players !== null) await prefs.setOptions("playerId", players);
        if (radioDials !== null)
          await prefs.setOptions("radioDial", radioDials);

        const playerId = (await prefs.get("playerId")) || null;
        // Validate against available options, clearing inaccessible selections after sign-out.
        const resolvedPlayerId = resolveSelection(playerId, players);
        const playerSelection = resolvedPlayerId
          ? `${registryUrl} ${accountId}/${resolvedPlayerId}`
          : null;

        if (playerAccessKnown && resolvedPlayerId) {
          if (playerSelection !== lastPlayerSelection || !hasSyncedOnce) {
            let player = null;
            try {
              player = await discoverPlayer(
                accountId,
                resolvedPlayerId,
                registryUrl,
                auth,
                options,
              );
            } catch (err) {
              noteRegistryFailure("Failed to discover selected player", err);
            }

            if (player) {
              await onPlayerSelected(player);
              lastPlayerSelection = playerSelection;
            } else if (!registryFailure) {
              await onPlayerSelected(null);
              lastPlayerSelection = null;
            }
          }
        } else if (
          playerAccessKnown &&
          (lastPlayerSelection !== null || !hasSyncedOnce)
        ) {
          await onPlayerSelected(null);
          lastPlayerSelection = null;
        }

        const radioDialKey = (await prefs.get("radioDial")) || null;
        const resolvedRadioDialKey = resolveSelection(radioDialKey, radioDials);
        const selectedRadioDialUrl = resolvedRadioDialKey
          ? radioDialUrl(resolvedRadioDialKey, registryUrl)
          : null;
        await onRadioDialSelected(selectedRadioDialUrl);
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
          await onRadioDialSelected(null);
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

    sync,

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

    refreshAccountsForCurrentRegistry(
      failureReason = "accounts",
      options = {},
    ) {
      return sync(failureReason, options);
    },
  };
}
