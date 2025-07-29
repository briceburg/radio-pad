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

export async function discoverPlayer(registryUrl, playerId) {
  const url = `${registryUrl}/v1/players/${playerId}`;
  console.log("Discovering player from registry:", url);
  try {
    const response = await fetch(url);
    return await response.json();
  } catch (error) {
    // TODO: use toast / ui  notification error?
    console.error("Error discovering player info from registry:", error);
  }
}

export async function discoverPlayers(registryUrl) {
  let players = [];
  let page = 1;
  try {
    do {
      const url = `${registryUrl}/v1/players?page=${page}&per_page=50`;
      const response = await fetch(url);
      const data = await response.json();
      if (Array.isArray(data.items)) {
        players = players.concat(data.items);
      }
      page = data.page < data.total_pages ? data.page + 1 : -1;
    } while (page !== -1);
  } catch (e) {
    // TODO: use toast / ui  notification error?
    console.error("Failed to fetch players from registry:", e);
  }
  return players.map((p) => ({ value: p.id, label: p.name || p.id }));
}
