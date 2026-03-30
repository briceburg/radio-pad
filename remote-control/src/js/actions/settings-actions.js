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

export function createSettingsActions({
  prefs,
  auth,
  onPlayerSelected,
  onPresetSelected,
}) {
  let lastPlayerId = null;
  let lastPresetId = null;

  async function sync(failureReason = "accounts", options = {}) {
    try {
      const url = await prefs.get("registryUrl");
      if (!url) return;

      const accounts = await discoverAccounts(url, auth, options);
      await prefs.setOptions("accountId", accounts);

      const accountId = await prefs.get("accountId");
      if (!accountId) return;

      const [players, presets] = await Promise.all([
        discoverPlayers(accountId, prefs, auth, options),
        discoverPresets(accountId, prefs, auth, options),
      ]);

      await prefs.setOptions("playerId", players);
      await prefs.setOptions("presetId", presets);

      const playerId = await prefs.get("playerId");
      if (playerId && playerId !== lastPlayerId) {
        const player = await discoverPlayer(playerId, prefs, auth, options);
        if (player) {
          lastPlayerId = playerId;
          await onPlayerSelected(player);
        }
      }

      const presetId = await prefs.get("presetId");
      if (presetId && presetId !== lastPresetId) {
        lastPresetId = presetId;
        await onPresetSelected(presetId);
      }
    } catch (error) {
      if (error.name !== "AbortError") {
        toastRegistryFailure(failureReason, error, options);
      }
    } finally {
      preferencesStore.set({ definitions: prefs.getSnapshot() });
    }
  }

  return {
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
