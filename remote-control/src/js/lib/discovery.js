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

import { RegistryRequestError } from "./error-utils.js";

async function buildRequestOptions(auth) {
  const token = auth?.getRegistryBearerToken?.();
  if (!token) {
    return {};
  }

  return {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  };
}

async function fetchAllPages(startPath, registryUrl, auth = null) {
  const items = [];
  let url = new URL(startPath, registryUrl).toString();
  const options = await buildRequestOptions(auth);

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

export async function discoverAccounts(registryUrl, auth = null) {
  if (!registryUrl) return [];
  try {
    const items = await fetchAllPages("/v1/accounts/", registryUrl, auth);
    return items.map((i) => ({ value: i.id, label: i.name || i.id }));
  } catch (error) {
    console.error("Failed to fetch accounts from registry:", error);
    throw error;
  }
}

export async function discoverPlayers(accountId, prefs, auth = null) {
  if (!accountId) return [];

  const registryUrl = await prefs.get("registryUrl");
  if (!registryUrl) return [];

  try {
    const path = `/v1/accounts/${accountId}/players/`;
    const items = await fetchAllPages(path, registryUrl, auth);
    return items.map((i) => ({ value: i.id, label: i.name || i.id }));
  } catch (error) {
    console.error("Failed to fetch players from registry:", error);
    throw error;
  }
}

export async function discoverPresets(accountId, prefs, auth = null) {
  const registryUrl = await prefs.get("registryUrl");
  if (!registryUrl) return [];

  const presets = [];
  const paths = [
    ...(accountId ? [`/v1/accounts/${accountId}/presets/`] : []),
    `/v1/presets/`,
  ];

  try {
    for (const path of paths) {
      const items = await fetchAllPages(path, registryUrl, auth);
      presets.push(
        ...items.map((i) => ({
          value: `${registryUrl}${path}${i.id}`,
          label: i.name || i.id,
        })),
      );
    }
  } catch (error) {
    console.error("Failed to fetch presets from registry:", error);
    throw error;
  }

  return presets;
}

export async function discoverPlayer(playerId, prefs, auth = null) {
  if (!playerId) return null;

  const [accountId, registryUrl] = await Promise.all([
    prefs.get("accountId"),
    prefs.get("registryUrl"),
  ]);

  if (!(registryUrl && accountId)) return null;

  const url = `${registryUrl}/v1/accounts/${accountId}/players/${playerId}`;
  try {
    const response = await fetch(url, await buildRequestOptions(auth));
    if (!response.ok) {
      throw new RegistryRequestError({ url, status: response.status });
    }
    return await response.json();
  } catch (error) {
    console.error("Error discovering player info from registry:", error);
    throw error;
  }
}
