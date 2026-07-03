// SPDX-FileCopyrightText: 2025 Brice Burgess (github.com/briceburg)
// SPDX-License-Identifier: AGPL-3.0-or-later

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
  async function sync(
    failureReason = "accounts",
    { invalidDependentSelection, fromSettingsSave = false } = {},
  ) {
    if (syncPromise) return syncPromise;
    syncPromise = (async () => {
      let registryFailure = null;
      const noteRegistryFailure = (message, error) => {
        console.warn(message, error);
        if (!registryFailure) registryFailure = error;
      };

      try {
        const registryUrl = await prefs.get("registryUrl");
        if (!registryUrl) return;

        const [accountsResult, authEnabledResult] = await Promise.allSettled([
          discoverAccounts(registryUrl, auth),
          discoverAuthEnabled(registryUrl),
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
            : discoverPlayers(accountId, registryUrl, auth);

        // Discover APIs natively handle null accountId safely
        const results = await Promise.allSettled([
          playerDiscovery,
          discoverRadioDials(accountId, registryUrl, auth),
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

        const dependentOptionPolicy = {
          invalidSelection:
            invalidDependentSelection || (hasSyncedOnce ? "preserve" : "first"),
        };
        if (players !== null)
          await prefs.setOptions("playerId", players, dependentOptionPolicy);
        if (radioDials !== null)
          await prefs.setOptions(
            "radioDial",
            radioDials,
            dependentOptionPolicy,
          );

        const playerId = (await prefs.get("playerId")) || null;
        // Resolve against available options, deactivating inaccessible selections after sign-out.
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
          toastRegistryFailure(failureReason, registryFailure, {
            fromSettingsSave,
          });
        } else {
          onRegistryStatus(REGISTRY_OK_STATUS);
        }
      } catch (error) {
        onRegistryStatus(REGISTRY_UNAVAILABLE_STATUS);
        toastRegistryFailure(failureReason, error, { fromSettingsSave });
        if (!registryFailure) registryFailure = error;
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

  async function syncAfterCurrent(failureReason, options) {
    if (syncPromise) await syncPromise;
    return sync(failureReason, options);
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
      let result;
      try {
        result = await prefs.setMany(settingsMap);
      } catch (error) {
        settingsUiStore.set({ saveState: "error" });
        toastDanger("Couldn’t save settings.", error);
        return { status: "error", error };
      }
      const { status, results } = result;

      if (status !== "ok") {
        settingsUiStore.set({ saveState: "error" });
        const invalid = Object.values(results).find(
          (r) => r.status === "invalid",
        );
        const label = prefs.getSnapshot()[invalid.key]?.label || invalid.key;
        toastDanger(`Couldn’t save settings: ${label} is invalid.`);
        return { status, results };
      }

      await syncAfterCurrent("accounts", {
        fromSettingsSave: true,
        invalidDependentSelection:
          results.accountId?.status === "applied" ? "clear" : undefined,
      });
      settingsUiStore.set({ saveState: "saved" });

      return { status, results };
    },

    markDirty() {
      if (settingsUiStore.get().saveState !== "saving") {
        settingsUiStore.set({ saveState: "idle" });
      }
    },

    refreshAccountsForCurrentRegistry: syncAfterCurrent,
  };
}
