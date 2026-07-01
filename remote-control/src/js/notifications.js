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

import { toastStore, updateStore } from "./store.js";
import { formatErrorMessage, RegistryRequestError } from "./utils/errors.js";

const TOAST_SEVERITY = {
  danger: {
    header: "Error",
    duration: 10000,
    position: "top",
  },
  warning: {
    header: "Warning",
    duration: 8000,
    position: "top",
  },
  success: {
    header: "Success",
    duration: 3000,
    position: "bottom",
  },
};

function showToast(
  summary,
  { error = null, format = "default", severity = "warning" } = {},
) {
  updateStore(toastStore, (toast) => ({
    id: toast.id + 1,
    summary,
    error,
    format,
    severity,
  }));
}

export function toastDanger(summary, error = null) {
  showToast(summary, {
    error,
    severity: "danger",
  });
}

export function toastWarning(summary, error = null) {
  showToast(summary, {
    error,
    severity: "warning",
  });
}

const REGISTRY_FAILURE_ACTIONS = {
  accounts: "refresh accounts",
  auth_accounts: "refresh accounts after signing in or out",
  account_choices: "refresh all players and RadioDials",
  player: "refresh player details",
};

export function toastRegistryFailure(
  reason,
  error,
  { fromSettingsSave = false } = {},
) {
  const action =
    REGISTRY_FAILURE_ACTIONS[reason] || REGISTRY_FAILURE_ACTIONS.accounts;
  const prefix = fromSettingsSave ? "Settings saved, but couldn’t" : "Couldn’t";
  showToast(`${prefix} ${action}.`, {
    error,
    format: "registry",
    severity: "warning",
  });
}

export function toastSuccess(summary) {
  showToast(summary, { severity: "success" });
}

async function presentToast(notification) {
  const toast = document.querySelector("#global-toast");
  if (!toast || !notification?.summary) return;

  const severity = TOAST_SEVERITY[notification.severity]
    ? notification.severity
    : "warning";
  const config = TOAST_SEVERITY[severity];
  const detailText =
    notification.format === "registry"
      ? RegistryRequestError.format(notification.error)
      : formatErrorMessage(notification.error);
  const message = detailText
    ? `${notification.summary} ${detailText}`.trim()
    : notification.summary;

  await toast.dismiss();
  toast.header = config.header;
  toast.message = message;
  toast.duration = config.duration;
  toast.color = severity;
  toast.buttons =
    severity === "success" ? [] : [{ text: "Dismiss", role: "cancel" }];
  toast.position = config.position;
  toast.positionAnchor =
    config.position === "bottom" ? "main-tab-bar" : undefined;
  toast.swipeGesture = "vertical";
  await toast.present();
}

export function initNotifications() {
  let lastToastId = toastStore.get().id;
  let presentation = Promise.resolve();
  return toastStore.subscribe((notification) => {
    if (notification.id !== lastToastId) {
      lastToastId = notification.id;
      presentation = presentation
        .then(() => presentToast(notification))
        .catch(console.error);
    }
  });
}
