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

function showToast(summary, options = {}) {
  updateStore(toastStore, (toast) => ({
    id: toast.id + 1,
    summary,
    error: options.error || null,
    format: options.format || "default",
    severity: options.severity || "warning",
    persistent: options.persistent ?? true,
    dismissible: options.dismissible ?? true,
  }));
}

export function toastDanger(summary, error = null) {
  showToast(summary, {
    error,
    persistent: true,
    severity: "danger",
  });
}

export function toastWarning(summary, error = null) {
  showToast(summary, {
    error,
    persistent: true,
    severity: "warning",
  });
}

function registrySummary(summary, { fromSettingsSave = false } = {}) {
  return fromSettingsSave ? `Saved settings. ${summary}` : summary;
}

const REGISTRY_FAILURE_MESSAGES = {
  accounts: "Failed refreshing accounts.",
  auth_accounts: "Failed refreshing accounts after auth change.",
  account_choices: "Failed refreshing account players/presets.",
  player: "Failed refreshing player info.",
};

function registryFailureMessage(reason = "accounts") {
  return (
    REGISTRY_FAILURE_MESSAGES[reason] || REGISTRY_FAILURE_MESSAGES.accounts
  );
}

export function toastRegistryFailure(reason, error, options = {}) {
  showToast(registrySummary(registryFailureMessage(reason), options), {
    error,
    format: "registry",
    persistent: true,
    severity: "warning",
  });
}

export function toastRegistryUnavailable(error = null) {
  showToast("Registry unavailable.", {
    error,
    format: "registry-status",
    persistent: true,
    severity: "warning",
  });
}

export async function dismissRegistryUnavailableToast() {
  if (toastStore.get().format !== "registry-status") {
    return;
  }

  const toast = document.querySelector("#global-toast");
  if (toast) {
    await toast.dismiss();
  }
}

export function toastSuccess(summary) {
  showToast(summary, {
    persistent: false,
    severity: "success",
  });
}

import { formatErrorMessage, RegistryRequestError } from "./utils/errors.js";

async function presentToast(notification) {
  const toast = document.querySelector("#global-toast");
  if (!toast || !notification?.summary) return;

  const TOAST_SEVERITY = {
    danger: { color: "danger", duration: 0, position: "top" },
    warning: { color: "warning", duration: 0, position: "top" },
    success: { color: "success", duration: 3000, position: "bottom" },
  };

  const config =
    TOAST_SEVERITY[notification.severity] || TOAST_SEVERITY.warning;
  const detailText =
    notification.format === "registry"
      ? RegistryRequestError.format(notification.error)
      : formatErrorMessage(notification.error);
  const message = detailText
    ? `${notification.summary} ${detailText}`.trim()
    : notification.summary;
  const icon =
    notification.format === "registry-status"
      ? "cloud-offline-outline"
      : notification.severity === "success"
        ? "checkmark-circle-outline"
        : notification.severity === "danger"
          ? "alert-circle-outline"
          : "warning-outline";

  toast.message = message;
  toast.icon = icon;
  toast.duration = notification.persistent ? 0 : config.duration;
  toast.color = config.color;
  toast.buttons =
    notification.persistent && notification.dismissible !== false
      ? [{ text: "Dismiss", role: "cancel" }]
      : [];
  toast.position = config.position;
  await toast.present();
}

export function initNotifications() {
  let lastToastId = 0;
  toastStore.subscribe((notification) => {
    if (notification.id !== lastToastId) {
      lastToastId = notification.id;
      void presentToast(notification).catch(console.error);
    }
  });
}
