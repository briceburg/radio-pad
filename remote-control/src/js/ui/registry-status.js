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

export function isRegistryPending(registryState) {
  return ["loading", "retrying"].includes(registryState.phase);
}

export function formatRegistryAttempt(retryAttempt = 0) {
  const attemptNumber = retryAttempt + 1;
  return attemptNumber >= 10 ? "10+" : String(attemptNumber);
}

export function getRegistryPendingTitle(registryState) {
  if (!isRegistryPending(registryState)) {
    return null;
  }

  return `Connecting to Registry (attempt ${formatRegistryAttempt(
    registryState.retryAttempt,
  )})`;
}

export function getRegistryPendingDetail() {
  return "Loading players and presets from the Registry...";
}
