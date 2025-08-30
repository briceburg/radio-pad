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
      },
      accountId: {
        type: "select",
        label: "Account",
        default: import.meta.env.VITE_ACCOUNT_ID || "briceburg",
      },
      playerId: {
        type: "select",
        label: "Player",
        default: import.meta.env.VITE_PLAYER_ID || "living-room",
      },
    },
  ) {
    super();
    this.preferences = prefs;
    this.registerEvent("on-change", (data) => {
      console.log(`Preference changed: ${data.key} = ${data.value}`);
    });
  }

  async setOptions(key, options) {
    if (
      !Array.isArray(options) ||
      options.some(
        (opt) =>
          typeof opt !== "object" ||
          opt === null ||
          !("value" in opt) ||
          !("label" in opt) ||
          Object.keys(opt).length !== 2,
      )
    ) {
      console.error(options);
      throw new Error(
        "Each option must be an object with only 'value' and 'label' fields.",
      );
    }

    this.preferences[key].options = options;
    const current = await this.get(key, false);

    if (!options || options.length === 0) {
      // If no options are available, unset the preference
      await this.set(key, "");
    } else if (!current || !options.some((opt) => opt.value === current)) {
      // If current value is not set, or not in the list of options, set it to the first option
      let firstOption = options[0];
      await this.set(key, firstOption.value);
    }
  }

  async init() {
    for (const [key, pref] of Object.entries(this.preferences)) {
      const value = await this.get(key);
      if (value !== null) {
        pref.value = value;
      } else {
        pref.value = pref.default || "";
      }
    }
  }

  async get(key, onChange = true) {
    const result = await Preferences.get({ key });
    if (onChange && result.value !== this.preferences[key]?.value) {
      await this.emitEvent("on-change", { key, value: result.value });
    }
    return result.value;
  }

  async set(key, value) {
    if (value !== this.preferences[key]?.value) {
      this.preferences[key].value = value;
      await Preferences.set({ key, value });
      await this.emitEvent("on-change", { key, value });
    }
  }
}
