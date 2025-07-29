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
      playerId: {
        type: "select",
        label: "Player",
        default: import.meta.env.VITE_PLAYER_ID || "briceburg",
      },
    }
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
      if (value !== null) {
        pref.value = value;
      } else {
        pref.value = pref.default || "";
      }
    }
  }

  async get(key) {
    const result = await Preferences.get({ key });
    if (result.value !== this.preferences[key]?.value) {
      await this.emitEvent("on-change", { key, value: result.value });
    }
    return result.value;
  }

  async set(key, value) {
    if (value !== this.preferences[key]?.value) {
      this.preferences[key] = value;
      await Preferences.set({ key, value });
      await this.emitEvent("on-change", { key, value });
    }
  }
}
