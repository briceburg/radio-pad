import { WebSocketManager, StationManager, EVENTS } from '../../../shared/radio-utils.js';

const stationGrid = document.getElementById('station-grid');
const nowPlaying = document.getElementById('now-playing');

// Initialize managers
const stationManager = new StationManager();
let wsManager;

// WebSocket message handler
function handleWebSocketMessage(event, data) {
  switch (event) {
    case EVENTS.STATION_PLAYING:
      nowPlaying.innerText = data || "...";
      stationManager.updateStationHighlight(data);
      break;
    case EVENTS.STATION_REQUEST:
    case EVENTS.CLIENT_COUNT:
      break;
    default:
      console.warn('Unknown WebSocket event:', event);
  }
}

// Station click handler
function playStation(stationName, button) {
  stationManager.setStationLoading(stationName);
  
  if (wsManager && wsManager.isConnected) {
    wsManager.send(EVENTS.STATION_REQUEST, stationName);
  } else {
    console.error('WebSocket not connected. Cannot send station request.');
  }
}

// Initialize the application
async function initializeApp() {
  try {
    // Load stations and create grid
    await stationManager.loadStations();
    stationManager.createStationGrid(stationGrid, playStation);
    
    // Initialize WebSocket connection
    wsManager = new WebSocketManager(
      import.meta.env.VITE_SWITCHBOARD_URL || 'ws://localhost:1980/',
      handleWebSocketMessage
    );
    wsManager.connect();
    
  } catch (error) {
    console.error('Error initializing app:', error);
  }
}

// Start the application
initializeApp();
