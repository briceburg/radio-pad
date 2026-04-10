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

const DEFAULT_RETRY_OPTIONS = {
  initialDelayMs: 1000,
  factor: 1.5,
  jitterMs: 1000,
  maxDelayMs: 30000,
};

export function createRetryState(options = {}) {
  const config = {
    ...DEFAULT_RETRY_OPTIONS,
    ...options,
  };

  return {
    ...config,
    attempt: 0,
    nextDelayMs: config.initialDelayMs,
  };
}

export function resetRetryState(retryState) {
  retryState.attempt = 0;
  retryState.nextDelayMs = retryState.initialDelayMs;
}

export function advanceRetryState(retryState) {
  const delayMs = retryState.nextDelayMs;
  const jitter = retryState.jitterMs ? Math.random() * retryState.jitterMs : 0;

  retryState.attempt += 1;
  retryState.nextDelayMs = Math.min(
    retryState.nextDelayMs * retryState.factor + jitter,
    retryState.maxDelayMs,
  );

  return {
    attempt: retryState.attempt,
    delayMs,
  };
}
