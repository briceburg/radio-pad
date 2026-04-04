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

import { Preferences } from "@capacitor/preferences";

export const PREFERENCE_GROUPS = {
  "radio-account": ["Account", "person"],
  "radio-control": ["Control", "radio"],
  "radio-listen": ["Listen", "headset"],
  "radio-advanced": ["Advanced", "construct"],
};

function isPresent(value) {
  return value !== null && value !== undefined;
}

function isEmptyValue(value) {
  return value === null || value === undefined;
}

function identity(value) {
  return value;
}

function withTrailingSlash(value) {
  return value.endsWith("/") ? value : `${value}/`;
}

function normalizeRegistryUrl(value) {
  const trimmed = typeof value === "string" ? value.trim() : "";
  if (!trimmed) return null;
  if (trimmed.startsWith("/")) {
    return withTrailingSlash(trimmed);
  }

  const candidate = /^https?:\/\//i.test(trimmed)
    ? trimmed
    : `https://${trimmed}`;
  try {
    const parsed = new URL(candidate);
    parsed.pathname = withTrailingSlash(parsed.pathname);
    return parsed.toString();
  } catch {
    return candidate;
  }
}

function clonePreference(pref) {
  return {
    ...pref,
    options: [...(pref.options || [])],
  };
}

function prepareResult(key, status, value, reason) {
  return reason ? { key, status, value, reason } : { key, status, value };
}

function validateOptions(options) {
  return (
    Array.isArray(options) &&
    options.every(
      (option) =>
        option &&
        typeof option === "object" &&
        "label" in option &&
        "value" in option,
    )
  );
}

const DEFAULT_PREFERENCES = {
  accountId: {
    type: "select",
    label: "Account",
    options: [],
    group: "radio-account",
  },
  registryUrl: {
    type: "text",
    label: "Registry URL",
    placeholder: "Enter registry URL",
    group: "radio-advanced",
    default:
      import.meta.env.VITE_REGISTRY_URL || "https://registry.radiopad.dev",
    normalize: normalizeRegistryUrl,
    validate: (value) => {
      if (typeof value === "string" && value.startsWith("/")) {
        return true;
      }
      try {
        return /^https?:$/.test(new URL(value).protocol);
      } catch {
        return false;
      }
    },
  },
  playerId: {
    type: "select",
    label: "Player",
    options: [],
    group: "radio-control",
  },
  presetId: {
    type: "select",
    label: "Station Preset",
    options: [],
    group: "radio-listen",
  },
};

export class RadioPadPreferences {
  constructor(prefs = DEFAULT_PREFERENCES) {
    this.preferences = Object.fromEntries(
      Object.entries(prefs).map(([key, pref]) => [key, clonePreference(pref)]),
    );
  }

  async init() {
    for (const [key, pref] of Object.entries(this.preferences)) {
      const storedValue = await this.readStoredValue(key);
      if (isPresent(storedValue)) {
        pref.value = storedValue;
        continue;
      }

      if (isPresent(pref.default)) {
        await this.set(key, pref.default);
      }
    }
  }

  async readStoredValue(key) {
    const result = await Preferences.get({ key });
    return result.value;
  }

  async get(key) {
    const pref = this.preferences[key];
    if (pref && pref.value !== undefined) {
      return pref.value;
    }

    const value = await this.readStoredValue(key);
    if (pref) {
      pref.value = value;
    }
    return value;
  }

  getSnapshot() {
    return Object.fromEntries(
      Object.entries(this.preferences).map(([key, pref]) => [
        key,
        clonePreference(pref),
      ]),
    );
  }

  prepare(key, value) {
    const pref = this.preferences[key];
    if (!pref) {
      return prepareResult(key, "invalid", value, "unknown_preference");
    }

    const normalize = pref.normalize || identity;
    let nextValue;
    try {
      nextValue = normalize(value);
    } catch (error) {
      console.warn(`Normalization failed for preference ${key}`, error);
      return prepareResult(key, "invalid", value, "normalize_error");
    }

    if (
      pref.type === "select" &&
      (isEmptyValue(nextValue) || nextValue === "")
    ) {
      return prepareResult(key, "unchanged", pref.value ?? null);
    }

    if (isEmptyValue(nextValue)) {
      return prepareResult(key, "invalid", value, "empty_value");
    }

    if (pref.validate && !pref.validate(nextValue)) {
      console.warn(`Invalid value for preference ${key}: ${nextValue}`);
      return prepareResult(key, "invalid", nextValue, "validation_failed");
    }

    if (nextValue === pref.value) {
      return prepareResult(key, "unchanged", nextValue);
    }

    return prepareResult(key, "applied", nextValue);
  }

  async applyPreparedResult(result) {
    if (result.status !== "applied") {
      return result;
    }

    const pref = this.preferences[result.key];
    pref.value = result.value;
    await Preferences.set({ key: result.key, value: result.value });
    return result;
  }

  async set(key, value) {
    const result = this.prepare(key, value);
    await this.applyPreparedResult(result);
    return result;
  }

  async setMany(settingsMap) {
    const results = Object.fromEntries(
      Object.entries(settingsMap).map(([key, value]) => [
        key,
        this.prepare(key, value),
      ]),
    );

    const resultList = Object.values(results);
    if (resultList.some((result) => result.status === "invalid")) {
      return {
        status: "invalid",
        results,
      };
    }

    for (const result of resultList) {
      await this.applyPreparedResult(result);
    }

    return {
      status: "ok",
      results,
    };
  }

  async setOptions(key, options) {
    if (!validateOptions(options)) {
      throw new Error(
        "options must be an array of objects with 'label' and 'value' fields.",
      );
    }

    const pref = this.preferences[key];
    pref.options = options;

    let selection = null;
    if (options.length > 0) {
      const current = await this.get(key);
      if (!options.some((opt) => opt.value === current)) {
        selection = await this.set(key, options[0].value);
      }
    }

    return {
      selection,
      value: await this.get(key),
    };
  }
}
