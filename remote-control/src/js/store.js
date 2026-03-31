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

import { atom } from "nanostores";

const EMPTY_PLAYER = {
  id: null,
  name: null,
  stations_url: null,
  switchboard_url: null,
};

export const authStore = atom({
  enabled: false,
  reason: "not_configured",
  signedIn: false,
  name: null,
  email: null,
  subject: null,
  registryBearerToken: null,
});

export const preferencesStore = atom({
  definitions: {},
});

export const settingsUiStore = atom({
  saveState: "idle",
});

export const controlStore = atom({
  player: EMPTY_PLAYER,
  stationsData: null,
  currentStation: null,
  loading: true,
  statusText: "",
});

export const listenStore = atom({
  stationsData: null,
  currentStation: null,
  loading: false,
});

export const toastStore = atom({
  id: 0,
  summary: null,
  error: null,
  format: "default",
  severity: "warning",
  persistent: true,
});

export function updateStore(store, updater) {
  store.set(updater(store.get()));
}

export function patchStore(store, patch) {
  updateStore(store, (state) => ({
    ...state,
    ...patch,
  }));
}

if (import.meta.env.DEV) {
  import("@nanostores/logger").then(({ logger }) => {
    logger({
      authStore,
      preferencesStore,
      settingsUiStore,
      controlStore,
      listenStore,
      toastStore,
    });
  });
}
