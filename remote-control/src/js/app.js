const stationGrid = document.getElementById('station-grid');
const nowPlaying = document.getElementById('now-playing');
const stopButton = document.getElementById('stop-button');

const stationsUrl = 'https://raw.githubusercontent.com/briceburg/radio-pad/refs/heads/main/player/stations.json';
const switchboardUrl = import.meta.env.VITE_SWITCHBOARD_URL || 'ws://localhost:1980/';

let ws;
let reconnectTimer = null;
let reconnectDelay = 2000; // Start with 2 seconds

// Keep a map of station name to button for easy highlighting
const stationButtons = {};

async function loadStations() {
  try {
    const response = await fetch(stationsUrl);
    const stations = await response.json();

    let ionRow;
    stations.forEach((station, index) => {
      if (index % 3 === 0) {
        ionRow = document.createElement('ion-row');
        stationGrid.appendChild(ionRow);
      }

      const ionCol = document.createElement('ion-col');
      const ionButton = document.createElement('ion-button');
      ionButton.innerText = station.name;
      ionButton.expand = 'block';
      ionButton.addEventListener('click', () => {
        playStation(station.name, ionButton);
      });

      // Store button reference for highlighting
      stationButtons[station.name] = ionButton;

      ionCol.appendChild(ionButton);
      ionRow.appendChild(ionCol);
    });

    stopButton.addEventListener('click', (ev) => {
      stopStation();
    });
  } catch (error) {
    console.error('Error loading stations:', error);
  }
}

function connectWebSocket() {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    return;
  }

  console.log('Connecting to WebSocket:', switchboardUrl);
  ws = new WebSocket(switchboardUrl);

  // Add a 3-second timeout for the connection attempt
  const connectTimeout = setTimeout(() => {
    if (ws.readyState !== WebSocket.OPEN) {
      console.warn('WebSocket connection timed out after 3s, closing socket.');
      ws.close();
    }
  }, 3000);

  ws.onopen = () => {
    console.log('WebSocket connected');
    clearTimeout(connectTimeout);
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
    reconnectDelay = 2000; // Reset delay after successful connection
  };

  ws.onclose = () => {
    clearTimeout(connectTimeout);
    console.log('WebSocket closed, reconnecting in', reconnectDelay / 1000, 's...');
    scheduleReconnect();
  };

  ws.onerror = (err) => {
    clearTimeout(connectTimeout);
    console.error('WebSocket error:', err);
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
            btn.setAttribute('color', name === data ? 'success' : 'primary')
          );
          break;
        case "station_request":
        case "client_count":
          break;
        default:
          console.warn('Unknown WebSocket event:', event);
      }
    } catch (e) {
      console.error('Error parsing WebSocket message:', e);
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
    console.error('WebSocket not connected. Cannot send station request.');
  }
}

function playStation(stationName, button) {
  button.setAttribute('color', 'light');
  sendStationRequest(stationName);
}

function stopStation() {
  sendStationRequest(null);
}

loadStations();
connectWebSocket();
