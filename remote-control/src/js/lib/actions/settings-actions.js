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
import { isAbortError } from "../utils/errors.js";
import { preferencesStore, settingsUiStore } from "../state-store/app-store.js";
import { toastDanger, toastRegistryFailure } from "../notifications.js";

function firstInvalidSummary(results, preferences) {
  const invalid = Object.values(results).find(
    (result) => result.status === "invalid",
  );
  if (!invalid) {
    return "⚠️ Failed saving settings.";
  }

  const label = preferences[invalid.key]?.label || invalid.key;
  return `⚠️ Failed saving settings. Invalid ${label}.`;
}

const PREFERENCE_FLOW = ["registryUrl", "accountId", "playerId", "presetId"];

function createPreferenceRequestFlow(preferenceFlow) {
  const controllers = new Map();

  return {
    start(key, options = {}) {
      const keyIndex = preferenceFlow.indexOf(key);
      const abortKeys =
        keyIndex === -1 ? [key] : preferenceFlow.slice(keyIndex);

      for (const abortKey of abortKeys) {
        controllers.get(abortKey)?.abort();
        controllers.delete(abortKey);
      }

      const controller = new AbortController();
      controllers.set(key, controller);

      return {
        ...options,
        preferenceKey: key,
        signal: controller.signal,
      };
    },

    isLatest({ preferenceKey, signal } = {}) {
      return (
        preferenceKey == null ||
        signal == null ||
        (!signal.aborted && controllers.get(preferenceKey)?.signal === signal)
      );
    },
  };
}

export function createSettingsActions({
  prefs,
  auth,
  onPlayerSelected,
  onPresetSelected,
}) {
  const requestFlow = createPreferenceRequestFlow(PREFERENCE_FLOW);

  function syncPreferences() {
    preferencesStore.set({
      definitions: prefs.getSnapshot(),
    });
  }

  function setSaveState(saveState) {
    settingsUiStore.set({ saveState });
  }

  async function applyOptions(entries, options) {
    const selections = [];
    for (const [key, values] of entries) {
      const { selection } = await prefs.setOptions(key, values);
      if (selection) {
        selections.push(selection);
      }
    }
    syncPreferences();
    for (const selection of selections) {
      if (selection.status === "applied") {
        await triggerPreferenceChange(selection.key, selection.value, options);
      }
    }
  }

  async function triggerPreferenceChange(key, value, options = {}) {
    return applyPreferenceChange(key, value, requestFlow.start(key, options));
  }

  async function runRegistryTask(reason, task, options = {}) {
    try {
      const result = await task();
      return requestFlow.isLatest(options) ? result : null;
    } catch (error) {
      if (isAbortError(error) || !requestFlow.isLatest(options)) {
        return null;
      }
      toastRegistryFailure(reason, error, options);
      return null;
    }
  }

  async function applyPreferenceChange(key, value, options = {}) {
    return {
      registryUrl: () =>
        refreshAccounts(value, options.failureReason || "accounts", options),
      accountId: () => refreshAccountChoices(value, options),
      playerId: () => refreshPlayer(value, options),
      presetId: () => onPresetSelected(value),
    }[key]?.();
  }

  async function refreshAccounts(registryUrl, failureReason, options = {}) {
    if (!registryUrl) {
      return null;
    }

    const accounts = await runRegistryTask(
      failureReason,
      () => discoverAccounts(registryUrl, auth, options),
      options,
    );
    if (!accounts) {
      return null;
    }

    await applyOptions([["accountId", accounts]], options);

    return accounts;
  }

  async function refreshAccountChoices(accountId, options = {}) {
    const choices = await runRegistryTask(
      "account_choices",
      () =>
        Promise.all([
          discoverPlayers(accountId, prefs, auth, options),
          discoverPresets(accountId, prefs, auth, options),
        ]),
      options,
    );
    if (!choices) {
      return null;
    }

    const [players, presets] = choices;
    await applyOptions(
      [
        ["playerId", players],
        ["presetId", presets],
      ],
      options,
    );

    return choices;
  }

  async function refreshPlayer(playerId, options = {}) {
    const player = await runRegistryTask(
      "player",
      () => discoverPlayer(playerId, prefs, auth, options),
      options,
    );
    if (!player) {
      return null;
    }

    await onPlayerSelected(player);
    return player;
  }

  return {
    async initialize() {
      await prefs.init();
      syncPreferences();

      const registryUrl = await prefs.get("registryUrl");
      if (registryUrl) {
        await triggerPreferenceChange("registryUrl", registryUrl);
      }

      for (const key of PREFERENCE_FLOW.slice(1)) {
        const value = await prefs.get(key);
        if (value) {
          await triggerPreferenceChange(key, value);
        }
      }
    },

    async save(settingsMap) {
      setSaveState("saving");
      const result = await prefs.setMany(settingsMap);

      if (result.status !== "ok") {
        setSaveState("error");
        toastDanger(firstInvalidSummary(result.results, prefs.getSnapshot()));
        return result;
      }

      syncPreferences();
      setSaveState("saved");

      for (const preferenceResult of Object.values(result.results)) {
        if (preferenceResult.status !== "applied") {
          continue;
        }

        void triggerPreferenceChange(
          preferenceResult.key,
          preferenceResult.value,
          {
            fromSettingsSave: true,
          },
        );
      }

      return result;
    },

    markDirty() {
      const { saveState } = settingsUiStore.get();
      if (saveState !== "saving") {
        setSaveState("idle");
      }
    },

    async refreshAccountsForCurrentRegistry(
      failureReason = "accounts",
      options = {},
    ) {
      const registryUrl = await prefs.get("registryUrl");
      if (!registryUrl) {
        return null;
      }
      return triggerPreferenceChange("registryUrl", registryUrl, {
        ...options,
        failureReason,
      });
    },
  };
}
