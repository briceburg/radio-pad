/**
 * Shared utilities for radio-pad remote controller
 */

// Configuration constants
export const CONFIG = {
  STATIONS_URL: 'https://raw.githubusercontent.com/briceburg/radio-pad/refs/heads/main/player/stations.json',
  SWITCHBOARD_URL: import.meta.env.VITE_SWITCHBOARD_URL || 'ws://localhost:1980/',
  RECONNECT_DELAY_START: 2000,
  RECONNECT_DELAY_MAX: 30000,
  CONNECTION_TIMEOUT: 3000
};

// Event types
export const EVENTS = {
  STATION_PLAYING: 'station_playing',
  STATION_REQUEST: 'station_request',
  CLIENT_COUNT: 'client_count'
};

/**
 * Message protocol utilities
 */
export class MessageProtocol {
  static createMessage(event, data = null) {
    return JSON.stringify({ event, data });
  }

  static parseMessage(message) {
    try {
      const { event, data } = JSON.parse(message);
      return { event, data };
    } catch (e) {
      console.error('Error parsing message:', e);
      return { event: null, data: null };
    }
  }
}

/**
 * WebSocket connection manager with automatic reconnection
 */
export class WebSocketManager {
  constructor(url, messageHandler) {
    this.url = url;
    this.messageHandler = messageHandler;
    this.ws = null;
    this.reconnectTimer = null;
    this.reconnectDelay = CONFIG.RECONNECT_DELAY_START;
    this.isConnected = false;
  }

  connect() {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    console.log('Connecting to WebSocket:', this.url);
    this.ws = new WebSocket(this.url);

    // Connection timeout
    const connectTimeout = setTimeout(() => {
      if (this.ws.readyState !== WebSocket.OPEN) {
        console.warn('WebSocket connection timed out, closing socket');
        this.ws.close();
      }
    }, CONFIG.CONNECTION_TIMEOUT);

    this.ws.onopen = () => {
      console.log('WebSocket connected');
      clearTimeout(connectTimeout);
      this.clearReconnectTimer();
      this.reconnectDelay = CONFIG.RECONNECT_DELAY_START;
      this.isConnected = true;
    };

    this.ws.onclose = () => {
      clearTimeout(connectTimeout);
      this.isConnected = false;
      console.log('WebSocket closed, reconnecting in', this.reconnectDelay / 1000, 's...');
      this.scheduleReconnect();
    };

    this.ws.onerror = (err) => {
      clearTimeout(connectTimeout);
      console.error('WebSocket error:', err);
    };

    this.ws.onmessage = (msg) => {
      const { event, data } = MessageProtocol.parseMessage(msg.data);
      if (event && this.messageHandler) {
        this.messageHandler(event, data);
      }
    };
  }

  send(event, data = null) {
    if (this.isConnected && this.ws) {
      const message = MessageProtocol.createMessage(event, data);
      this.ws.send(message);
      return true;
    } else {
      console.error('WebSocket not connected. Cannot send message.');
      return false;
    }
  }

  scheduleReconnect() {
    this.clearReconnectTimer();
    this.reconnectTimer = setTimeout(() => {
      this.connect();
      // Exponential backoff
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, CONFIG.RECONNECT_DELAY_MAX);
    }, this.reconnectDelay);
  }

  clearReconnectTimer() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  close() {
    this.clearReconnectTimer();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.isConnected = false;
  }
}

/**
 * Station manager for loading and managing stations
 */
export class StationManager {
  constructor() {
    this.stations = [];
    this.stationButtons = {};
  }

  async loadStations() {
    try {
      const response = await fetch(CONFIG.STATIONS_URL);
      this.stations = await response.json();
      return this.stations;
    } catch (error) {
      console.error('Error loading stations:', error);
      return [];
    }
  }

  createStationGrid(container, onStationClick) {
    container.innerHTML = ''; // Clear existing content
    this.stationButtons = {};

    let ionRow;
    this.stations.forEach((station, index) => {
      if (index % 3 === 0) {
        ionRow = document.createElement('ion-row');
        container.appendChild(ionRow);
      }

      const ionCol = document.createElement('ion-col');
      const ionButton = document.createElement('ion-button');
      ionButton.innerText = station.name;
      ionButton.expand = 'block';
      ionButton.addEventListener('click', () => {
        onStationClick(station.name, ionButton);
      });

      // Store button reference for highlighting
      this.stationButtons[station.name] = ionButton;

      ionCol.appendChild(ionButton);
      ionRow.appendChild(ionCol);
    });
  }

  updateStationHighlight(currentStation) {
    Object.entries(this.stationButtons).forEach(([name, btn]) => {
      btn.setAttribute('color', name === currentStation ? 'success' : 'primary');
    });
  }

  setStationLoading(stationName) {
    const button = this.stationButtons[stationName];
    if (button) {
      button.setAttribute('color', 'light');
    }
  }
}