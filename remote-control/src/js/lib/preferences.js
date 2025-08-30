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
        validate: (value) => {
          try {
            new URL(value);
            return true;
          } catch {
            return false;
          }
        },
      },
      accountId: {
        type: "select",
        label: "Account",
        options: [],
      },
      playerId: {
        type: "select",
        label: "Player",
        options: [],
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
        this.set(key, defaultValue);
      } else {
        this.set(key, value);
      }
    }
  }

  async get(key) {
    const result = await Preferences.get({ key });
    return result.value;
  }

  async set(key, value) {
    const pref = this.preferences[key];
    if (value !== pref.value) {
      if (pref.validate && !pref.validate(value)) {
        console.warn(`Invalid value for preference ${key}: ${value}`);
      } else {
        pref.value = value;
        await Preferences.set({ key, value });
        await this.emitEvent("on-change", { key, value });
      }
    }
  }

  async setOptions(key, options) {
    if (
      !Array.isArray(options) ||
      options.some(
        (opt) =>
          !opt ||
          typeof opt !== "object" ||
          Object.keys(opt).sort().join() !== "label,value"
      )
    ) {
      throw new Error("options must be an array of objects with 'label' and 'value' fields.");
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
