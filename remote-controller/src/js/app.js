const stationGrid = document.getElementById('station-grid');
const nowPlaying = document.getElementById('now-playing');

const stationsUrl = 'https://raw.githubusercontent.com/briceburg/radio-pad/refs/heads/main/player/stations.json';
const switchboardUrl = 'wss://radioswitchboard.loca.lt';

let ws;
let wsConnectTimeout;

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

  // Set a 5s timeout for connection
  wsConnectTimeout = setTimeout(() => {
    if (ws.readyState !== WebSocket.OPEN) {
      console.error('WebSocket connection timeout. Closing socket.');
      ws.close();
    }
  }, 5000);

  ws.onopen = () => {
    clearTimeout(wsConnectTimeout);
    console.log('WebSocket connected');
  };
  ws.onerror = (err) => {
    clearTimeout(wsConnectTimeout);
    console.error('WebSocket error:', err);
  };
  ws.onclose = () => {
    clearTimeout(wsConnectTimeout);
    console.log('WebSocket closed, reconnecting in 2s...');
    setTimeout(connectWebSocket, 2000);
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
connectWebSocket();

function playStation(stationName, button) {
  button.setAttribute('color', 'light');

  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ event: "station_request", data: stationName }));
  } else {
    console.error('WebSocket not connected. Cannot send station request.');
  }
}

loadStations();
