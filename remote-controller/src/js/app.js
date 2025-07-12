const stationGrid = document.getElementById('station-grid');
const nowPlaying = document.getElementById('now-playing');

const stationsUrl = 'https://raw.githubusercontent.com/briceburg/radio-pad/refs/heads/main/player/stations.json';
const switchboardUrl = import.meta.env.VITE_SWITCHBOARD_URL || 'wss://radioswitchboard.loca.lt';

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
  } catch (error) {
    console.error('Error loading stations:', error);
  }
}

function highlightStationButton(stationName) {
  // Remove highlight from all buttons
  Object.values(stationButtons).forEach(btn => btn.removeAttribute('color'));
  // Highlight the button for the given station
  if (stationButtons[stationName]) {
    stationButtons[stationName].setAttribute('color', 'success');
  }
}

function connectWebSocket() {
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

  ws.onerror = (err) => {
    clearTimeout(connectTimeout);
    console.error('WebSocket error:', err);
    scheduleReconnect();
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

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      if (msg.event === "station_playing") {
        nowPlaying.innerText = msg.data || "...";
        highlightStationButton(msg.data);
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

function playStation(stationName, button) {
  button.setAttribute('color', 'light');

  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ event: "station_request", data: stationName }));
  } else {
    console.error('WebSocket not connected. Cannot send station request.');
  }
}

loadStations();
connectWebSocket();
