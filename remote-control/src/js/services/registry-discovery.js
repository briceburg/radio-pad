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

import { RegistryRequestError } from "../utils/errors.js";

const REGISTRY_REQUEST_TIMEOUT_MS = 10000;

function resolveRegistryBaseUrl(registryUrl) {
  return new URL(registryUrl, window.location.origin).toString();
}

function inferPlayerStationsUrl(registryUrl, accountId) {
  return new URL(
    `presets/${accountId}`,
    resolveRegistryBaseUrl(registryUrl),
  ).toString();
}

function inferPlayerSwitchboardUrl(registryUrl, accountId, playerId) {
  const baseUrl = new URL(resolveRegistryBaseUrl(registryUrl));
  const scheme = baseUrl.protocol === "https:" ? "wss:" : "ws:";
  const apiPath = baseUrl.pathname.replace(/\/$/, "");
  const switchboardPath = apiPath.endsWith("/api")
    ? `${apiPath.slice(0, -4)}/switchboard/${accountId}/${playerId}`
    : `${apiPath}/switchboard/${accountId}/${playerId}`;

  return new URL(
    `${scheme}//${baseUrl.host}${switchboardPath}`,
    window.location.origin,
  ).toString();
}

function buildRequestOptions(auth, signal) {
  const token = auth?.getRegistryBearerToken?.();
  const headers = token ? { Authorization: `Bearer ${token}` } : undefined;

  return {
    ...(headers ? { headers } : {}),
    ...(signal ? { signal } : {}),
  };
}

async function fetchWithTimeout(url, options) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => {
    controller.abort(new Error("Request timed out."));
  }, REGISTRY_REQUEST_TIMEOUT_MS);
  const relayAbort = () => controller.abort(options.signal?.reason);

  if (options.signal) {
    if (options.signal.aborted) {
      controller.abort(options.signal.reason);
    } else {
      options.signal.addEventListener("abort", relayAbort, { once: true });
    }
  }

  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } catch (error) {
    if (
      controller.signal.aborted &&
      controller.signal.reason instanceof Error &&
      controller.signal.reason.message === "Request timed out."
    ) {
      throw controller.signal.reason;
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
    options.signal?.removeEventListener("abort", relayAbort);
  }
}

async function fetchAllPages(
  startPath,
  registryUrl,
  auth = null,
  signal = null,
) {
  const items = [];
  const registryBaseUrl = resolveRegistryBaseUrl(registryUrl);
  let url = new URL(startPath, registryBaseUrl).toString();
  const options = buildRequestOptions(auth, signal);

  while (url) {
    const resp = await fetchWithTimeout(url, options);
    if (!resp.ok) {
      throw new RegistryRequestError({ url, status: resp.status });
    }
    const data = await resp.json();
    if (Array.isArray(data.items)) items.push(...data.items);

    const next = data && data.links ? data.links.next : null;
    url = next ? new URL(next, registryBaseUrl).toString() : null;
  }

  return items;
}

const withAuthFallback = async (fallback, promiseCallback) => {
  try {
    return await promiseCallback();
  } catch (error) {
    if (
      error instanceof RegistryRequestError &&
      (error.status === 401 || error.status === 403)
    ) {
      return fallback;
    }
    throw error;
  }
};

export async function discoverAccounts(registryUrl, auth = null, options = {}) {
  if (!registryUrl) return [];
  const items = await fetchAllPages(
    "accounts/",
    registryUrl,
    auth,
    options.signal,
  );
  return items.map((i) => ({ value: i.id, label: i.name || i.id }));
}

export async function discoverPlayers(
  accountId,
  prefs,
  auth = null,
  options = {},
) {
  if (!accountId) return [];
  if (auth && !auth.signedIn) return [];

  const registryUrl = await prefs.get("registryUrl");
  if (!registryUrl) return [];

  return withAuthFallback([], async () => {
    const items = await fetchAllPages(
      `accounts/${accountId}/players/`,
      registryUrl,
      auth,
      options.signal,
    );
    return items.map((i) => ({ value: i.id, label: i.name || i.id }));
  });
}

export async function discoverPresets(
  accountId,
  prefs,
  auth = null,
  options = {},
) {
  const registryUrl = await prefs.get("registryUrl");
  if (!registryUrl) return [];
  const registryBaseUrl = resolveRegistryBaseUrl(registryUrl);

  const presets = [];
  const paths = [
    ...(accountId ? [`accounts/${accountId}/presets/`] : []),
    `presets/`,
  ];

  await withAuthFallback([], async () => {
    for (const path of paths) {
      const items = await fetchAllPages(
        path,
        registryUrl,
        auth,
        options.signal,
      );
      presets.push(
        ...items.map((i) => ({
          value: new URL(`${path}${i.id}`, registryBaseUrl).toString(),
          label: i.name || i.id,
        })),
      );
    }
  });

  return presets;
}

export async function discoverPlayer(
  playerId,
  prefs,
  auth = null,
  options = {},
) {
  if (!playerId) return null;
  if (auth && !auth.signedIn) return null;

  const [accountId, registryUrl] = await Promise.all([
    prefs.get("accountId"),
    prefs.get("registryUrl"),
  ]);

  if (!(registryUrl && accountId)) return null;

  return withAuthFallback(null, async () => {
    const url = new URL(
      `accounts/${accountId}/players/${playerId}`,
      resolveRegistryBaseUrl(registryUrl),
    ).toString();
    const response = await fetchWithTimeout(
      url,
      buildRequestOptions(auth, options.signal),
    );
    if (!response.ok) {
      throw new RegistryRequestError({ url, status: response.status });
    }
    const player = await response.json();
    return {
      ...player,
      stations_url:
        player.stations_url || inferPlayerStationsUrl(registryUrl, accountId),
      switchboard_url:
        player.switchboard_url ||
        inferPlayerSwitchboardUrl(registryUrl, accountId, playerId),
    };
  });
}
