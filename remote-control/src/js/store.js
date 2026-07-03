// SPDX-FileCopyrightText: 2025 Brice Burgess (github.com/briceburg)
// SPDX-License-Identifier: AGPL-3.0-or-later

import { atom } from "nanostores";

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
  player: null,
  radioDial: null,
  currentStation: null,
  requestedStation: null,
  failedStation: null,
  loading: false,
  connectionState: "idle",
  connectionMessage: null,
  playerConnected: null,
  playerStatuses: {},
  resourceStatuses: {},
});

export const listenStore = atom({
  radioDial: null,
  currentStation: null,
  loading: false,
});

export const toastStore = atom({
  id: 0,
  summary: null,
  error: null,
  format: "default",
  severity: "warning",
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

export function applyRetainedStatus(statuses = {}, status = {}) {
  const { scope, level, summary = null } = status;
  if (!(scope && level)) return statuses;

  const nextStatuses = { ...statuses };
  if (level === "ok") {
    delete nextStatuses[scope];
  } else {
    nextStatuses[scope] = {
      level,
      summary: typeof summary === "string" ? summary : null,
    };
  }
  return nextStatuses;
}

export function isDegradedStatus(status) {
  return ["warning", "error"].includes(status?.level);
}
