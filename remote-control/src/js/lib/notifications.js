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

import { toastStore, updateStore } from "./state-store/app-store.js";

function showToast(summary, options = {}) {
  updateStore(toastStore, (toast) => ({
    id: toast.id + 1,
    summary,
    error: options.error || null,
    format: options.format || "default",
    severity: options.severity || "warning",
    persistent: options.persistent ?? true,
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
  return fromSettingsSave
    ? `Saved settings. ${summary.replace(/^⚠️\s*/, "").trim()}`
    : summary;
}

const REGISTRY_FAILURE_MESSAGES = {
  accounts: "⚠️ Failed refreshing accounts.",
  auth_accounts: "⚠️ Failed refreshing accounts after auth change.",
  account_choices: "⚠️ Failed refreshing account players/presets.",
  player: "⚠️ Failed refreshing player info.",
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

export function toastSuccess(summary) {
  showToast(summary, {
    persistent: false,
    severity: "success",
  });
}
