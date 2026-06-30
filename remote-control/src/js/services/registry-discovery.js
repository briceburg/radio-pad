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

function resolveRegistryBaseUrl(registryUrl) {
  return new URL(registryUrl, window.location.origin).toString();
}

export function radioDialUrl(radioDialKey, registryUrl) {
  const parts = radioDialKey?.split("/") || [];
  if (parts.length !== 2 || parts.some((part) => !part)) {
    throw new Error("RadioDial must be in account_id/radio_dial_id format.");
  }
  const [accountId, radioDialId] = parts.map(encodeURIComponent);
  return new URL(
    `accounts/${accountId}/radio-dials/${radioDialId}`,
    resolveRegistryBaseUrl(registryUrl),
  ).toString();
}

function switchboardUrl(registryUrl, accountId, playerId) {
  const url = new URL(registryUrl, window.location.origin);
  const apiPath = url.pathname.replace(/\/$/, "");
  const basePath = apiPath.endsWith("/api") ? apiPath.slice(0, -4) : apiPath;
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = `${basePath}/switchboard/${encodeURIComponent(accountId)}/${encodeURIComponent(playerId)}`;
  url.search = "";
  url.hash = "";
  return url.toString();
}

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
  const registryBaseUrl = resolveRegistryBaseUrl(registryUrl);
  let url = new URL(startPath, registryBaseUrl).toString();
  const options = buildRequestOptions(auth, signal);

  while (url) {
    const resp = await fetch(url, options);
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

export async function discoverAuthEnabled(registryUrl, options = {}) {
  if (!registryUrl) return null;

  const url = new URL(
    "auth/status",
    resolveRegistryBaseUrl(registryUrl),
  ).toString();
  const response = await fetch(url, buildRequestOptions(null, options.signal));
  if (!response.ok) {
    throw new RegistryRequestError({ url, status: response.status });
  }

  const status = await response.json();
  if (typeof status?.enabled !== "boolean") {
    throw new Error("Invalid registry auth status response.");
  }
  return status.enabled;
}

export async function discoverPlayers(
  accountId,
  registryUrl,
  auth = null,
  options = {},
) {
  if (!(accountId && registryUrl)) return [];

  const items = await fetchAllPages(
    `accounts/${accountId}/players/`,
    registryUrl,
    auth,
    options.signal,
  );
  return items.map((i) => ({ value: i.id, label: i.name || i.id }));
}

export async function discoverRadioDials(
  accountId,
  registryUrl,
  auth = null,
  options = {},
) {
  if (!registryUrl) return [];
  const owners = [...new Set([accountId, "community"].filter(Boolean))];

  const discovered = await Promise.all(
    owners.map(async (owner) => {
      const items = await fetchAllPages(
        `accounts/${owner}/radio-dials/`,
        registryUrl,
        auth,
        options.signal,
      );
      return items
        .filter((item) => owner === accountId || item.discoverable)
        .map((item) => ({
          value: item.key,
          label: `${item.name || item.key} · ${owner}`,
        }));
    }),
  );
  return discovered.flat();
}

export async function discoverPlayer(
  accountId,
  playerId,
  registryUrl,
  auth = null,
  options = {},
) {
  if (!(accountId && playerId && registryUrl)) return null;

  const url = new URL(
    `accounts/${accountId}/players/${playerId}`,
    resolveRegistryBaseUrl(registryUrl),
  ).toString();
  const response = await fetch(url, buildRequestOptions(auth, options.signal));
  if (!response.ok) {
    throw new RegistryRequestError({ url, status: response.status });
  }
  const player = await response.json();
  return {
    ...player,
    configured_radio_dial_url: player.radio_dial
      ? radioDialUrl(player.radio_dial, registryUrl)
      : null,
    switchboard_url:
      player.switchboard_url ||
      switchboardUrl(registryUrl, accountId, playerId),
  };
}
