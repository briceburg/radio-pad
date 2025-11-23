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
import { EventEmitter } from "./interfaces.js";

export class RadioPadPreferences extends EventEmitter {
  constructor(
    prefs = {
      registryUrl: {
        type: "text",
        label: "Registry URL",
        placeholder: "Enter registry URL",
        default:
          import.meta.env.VITE_REGISTRY_URL || "https://registry.radiopad.dev",
        normalize: (value) => {
          const trimmed = typeof value === "string" ? value.trim() : "";
          if (!trimmed) return trimmed;
          return /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
        },
        validate: (value) => {
          try {
            new URL(value);
            return true;
          } catch {
            return false;
          }
        },
        group: "default",
      },
      accountId: {
        type: "select",
        label: "Account",
        options: [],
        group: "default",
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
    },
  ) {
    super();
    this.preferences = prefs;
    this.registerEvent("on-change", (data) => {
      console.log(`Preference changed: ${data.key} = ${data.value}`);
    });
  }

  async init() {
    for (const [key, pref] of Object.entries(this.preferences)) {
      const value = await this.get(key);
      const defaultValue = this.preferences[key]?.default || null;
      if (value === null && defaultValue !== null) {
        await this.set(key, defaultValue);
      } else {
        await this.set(key, value);
      }
    }
  }

  async get(key) {
    const result = await Preferences.get({ key });
    return result.value;
  }

  async set(key, value) {
    const pref = this.preferences[key];
    if (!pref) {
      console.warn(`Unknown preference: ${key}`);
      return null;
    }

    const currentValue = pref.value ?? null;
    if (pref.value !== undefined && value === pref.value) {
      return currentValue;
    }

    const normalize = pref.normalize || ((v) => v);
    let nextValue;
    try {
      nextValue = normalize(value);
    } catch (error) {
      console.warn(`Normalization failed for preference ${key}`, error);
      return currentValue;
    }

    if (nextValue !== value) {
      console.info(`Normalized preference ${key}: '${value}' -> '${nextValue}'`);
    }

    if (pref.validate && !pref.validate(nextValue)) {
      console.warn(`Invalid value for preference ${key}: ${nextValue}`);
      return currentValue;
    }

    if (nextValue === pref.value) {
      return pref.value ?? null;
    }

    pref.value = nextValue;
    await Preferences.set({ key, value: nextValue });
    await this.emitEvent("on-change", { key, value: nextValue });
    return nextValue;
  }

  async setOptions(key, options) {
    if (
      !Array.isArray(options) ||
      options.some(
        (opt) =>
          !opt ||
          typeof opt !== "object" ||
          !("label" in opt) ||
          !("value" in opt) ||
          Object.keys(opt).length !== 2,
      )
    ) {
      throw new Error(
        "options must be an array of objects with 'label' and 'value' fields.",
      );
    }

    const prevOptions = JSON.stringify(this.preferences[key].options || []);
    const newOptions = JSON.stringify(options);

    this.preferences[key].options = options;
    if (options.length > 0) {
      const current = await this.get(key);
      if (!options.some((opt) => opt.value === current)) {
        // If current value is not in the updated list of options, set it to the first option
        await this.set(key, options[0].value);
      }
    }

    if (prevOptions !== newOptions) {
      await this.emitEvent("options-changed", { key, options });
    }
  }
}
