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

const stationGrid = document.getElementById("station-grid");
const nowPlaying = document.getElementById("now-playing");
const stopButton = document.getElementById("stop-button");

let playerId = import.meta.env.VITE_PLAYER_ID || "briceburg";
let registryUrl =
  import.meta.env.VITE_REGISTRY_URL || "https://registry.radiopad.dev";
let stationsUrl = import.meta.env.VITE_STATIONS_URL || null;
let switchboardUrl = import.meta.env.VITE_SWITCHBOARD_URL || null;

let ws;
let reconnectTimer = null;
let reconnectDelay = 2000; // Start with 2 seconds

// Keep a map of station name to button for easy highlighting
let stationButtons = {};

function resetStations() {
  stationButtons = {};
  stationGrid.innerHTML = "";
  for (let i = 0; i < 3; i++) {
    const ionRow = document.createElement("ion-row");
    ionRow.className = "station-placeholder";
    for (let j = 0; j < 3; j++) {
      const ionCol = document.createElement("ion-col");
      const skeleton = document.createElement("ion-skeleton-text");
      skeleton.setAttribute("animated", "");
      ionCol.appendChild(skeleton);
      ionRow.appendChild(ionCol);
    }
    stationGrid.appendChild(ionRow);
  }
}

async function loadStations() {
  resetStations();
  try {
    const response = await fetch(stationsUrl);
    const stations = await response.json();
    stationGrid.innerHTML = "";

    let ionRow;
    stations.forEach((station, index) => {
      if (index % 3 === 0) {
        ionRow = document.createElement("ion-row");
        stationGrid.appendChild(ionRow);
      }

      const ionCol = document.createElement("ion-col");
      const ionButton = document.createElement("ion-button");
      ionButton.innerText = station.name;
      ionButton.expand = "block";
      ionButton.addEventListener("click", () => {
        playStation(station.name, ionButton);
      });

      // Store button reference for highlighting
      stationButtons[station.name] = ionButton;

      ionCol.appendChild(ionButton);
      ionRow.appendChild(ionCol);
    });

    stopButton.addEventListener("click", (ev) => {
      stopStation();
    });
  } catch (error) {
    console.error("Error loading stations:", error);
  }
}

function connectWebSocket() {
  if (
    ws &&
    (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)
  ) {
    return;
  }

  console.log("Connecting to WebSocket:", switchboardUrl);
  ws = new WebSocket(switchboardUrl);

  // Add a 3-second timeout for the connection attempt
  const connectTimeout = setTimeout(() => {
    if (ws.readyState !== WebSocket.OPEN) {
      console.warn("WebSocket connection timed out after 3s, closing socket.");
      ws.close();
    }
  }, 3000);

  ws.onopen = () => {
    console.log("WebSocket connected");
    clearTimeout(connectTimeout);
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
    reconnectDelay = 2000; // Reset delay after successful connection
  };

  ws.onclose = () => {
    clearTimeout(connectTimeout);
    console.log(
      "WebSocket closed, reconnecting in",
      reconnectDelay / 1000,
      "s...",
    );
    scheduleReconnect();
  };

  ws.onerror = (err) => {
    clearTimeout(connectTimeout);
    console.error("WebSocket error:", err);
  };

  ws.onmessage = (msg) => {
    try {
      const { event, data } = JSON.parse(msg.data);
      switch (event) {
        case "station_playing":
          nowPlaying.innerText = data || "...";
          // Enable/disable stop button based on whether a station is playing
          stopButton.disabled = !data;
          Object.entries(stationButtons).forEach(([name, btn]) =>
            btn.setAttribute("color", name === data ? "success" : "primary"),
          );
          break;
        case "stations_url":
          stationsUrl = data;
          loadStations();
          break;
        case "station_request":
        case "client_count":
          break;
        default:
          console.warn("Unknown WebSocket event:", event);
      }
    } catch (e) {
      console.error("Error parsing WebSocket message:", e);
    }
  };
}

function scheduleReconnect() {
  if (reconnectTimer) clearTimeout(reconnectTimer);
  reconnectTimer = setTimeout(() => {
    connectWebSocket();
    // Exponential backoff, max 30s
    reconnectDelay = Math.min(reconnectDelay * 2, 30000);
  }, reconnectDelay);
}

function sendStationRequest(stationName) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ event: "station_request", data: stationName }));
  } else {
    console.error("WebSocket not connected. Cannot send station request.");
  }
}

function playStation(stationName, button) {
  button.setAttribute("color", "light");
  sendStationRequest(stationName);
}

function stopStation() {
  sendStationRequest(null);
}

// Initialize the app
async function initialize() {
  async function discover() {
    const url = `${registryUrl}/v1/players/${playerId}`;
    console.log(`Discovering switchboard from ${url}...`);
    try {
      const response = await fetch(url);
      const data = await response.json();
      switchboardUrl = switchboardUrl || data.switchboardUrl;
    } catch (error) {
      console.error("Error discovering player info from registry:", error);
    }
  }

  resetStations();

  if (!switchboardUrl) {
    await discover();

    if (!switchboardUrl) {
      console.error("Missing switchboardUrl. Cannot initialize app.");
      return;
    }
  }

  connectWebSocket();
}

initialize();
