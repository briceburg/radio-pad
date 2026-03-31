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

function buildRequestOptions(auth, signal) {
  const token = auth?.getRegistryBearerToken?.();
  const headers = token ? { Authorization: `Bearer ${token}` } : undefined;

  return {
    ...(headers ? { headers } : {}),
    ...(signal ? { signal } : {}),
  };
}

async function fetchAllPages(
  startPath,
  registryUrl,
  auth = null,
  signal = null,
) {
  const items = [];
  let url = new URL(startPath, registryUrl).toString();
  const options = buildRequestOptions(auth, signal);

  while (url) {
    const resp = await fetch(url, options);
    if (!resp.ok) {
      throw new RegistryRequestError({ url, status: resp.status });
    }
    const data = await resp.json();
    if (Array.isArray(data.items)) items.push(...data.items);

    const next = data && data.links ? data.links.next : null;
    url = next ? new URL(next, registryUrl).toString() : null;
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
    "/v1/accounts/",
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
      `/v1/accounts/${accountId}/players/`,
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

  const presets = [];
  const paths = [
    ...(accountId ? [`/v1/accounts/${accountId}/presets/`] : []),
    `/v1/presets/`,
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
          value: `${registryUrl}${path}${i.id}`,
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
    const url = `${registryUrl}/v1/accounts/${accountId}/players/${playerId}`;
    const response = await fetch(
      url,
      buildRequestOptions(auth, options.signal),
    );
    if (!response.ok) {
      throw new RegistryRequestError({ url, status: response.status });
    }
    return await response.json();
  });
}
