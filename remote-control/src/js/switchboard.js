export class SwitchboardClient {
  constructor(registryUrl, playerId, callbacks) {
    this.registryUrl = registryUrl;
    this.playerId = playerId;
    this.callbacks = callbacks || {}; // e.g., onConnect, onDisconnect, onStationPlaying

    this.ws = null;
    this.switchboardUrl = null;
    this.reconnectTimer = null;
    this.reconnectDelay = 1000; // Initial reconnect delay
  }

  async connect() {
    if (!this.playerId) {
      this.callbacks.onError?.('Player ID is not set.');
      return;
    }

    await this._discover();

    if (!this.switchboardUrl) {
      this.callbacks.onError?.('Could not discover switchboard URL.');
      return;
    }

    this._connectWebSocket();
  }

  disconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.onclose = null; // Prevent reconnect logic from firing on manual close
      this.ws.close();
      this.ws = null;
    }
    console.log('Switchboard client disconnected.');
  }

  sendStationRequest(stationName) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ event: 'station_request', data: stationName }));
    } else {
      console.error('WebSocket not connected. Cannot send station request.');
    }
  }

  async _discover() {
    const url = `${this.registryUrl}/v1/players/${this.playerId}`;
    console.log(`Discovering switchboard from ${url}...`);
    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`Failed to fetch player info: ${response.statusText}`);
      }
      const data = await response.json();
      this.switchboardUrl = data.switchboardUrl;
    } catch (error) {
      console.error('Error discovering player info from registry:', error);
      this.switchboardUrl = null;
      this.callbacks.onError?.(error.message);
    }
  }

  _connectWebSocket() {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    console.log('Connecting to WebSocket:', this.switchboardUrl);
    this.callbacks.onConnecting?.(this.switchboardUrl);
    this.ws = new WebSocket(this.switchboardUrl);

    const connectTimeout = setTimeout(() => {
      if (this.ws.readyState !== WebSocket.OPEN) {
        this.ws.close();
      }
    }, 3000);

    this.ws.onopen = () => {
      clearTimeout(connectTimeout);
      this.reconnectDelay = 1000;
      if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
      this.callbacks.onConnect?.(this.switchboardUrl);
    };

    this.ws.onclose = () => {
      clearTimeout(connectTimeout);
      this.callbacks.onDisconnect?.();
      this._scheduleReconnect();
    };

    this.ws.onerror = (err) => {
      clearTimeout(connectTimeout);
      this.callbacks.onError?.('WebSocket error.');
    };

    this.ws.onmessage = (msg) => {
      try {
        const { event, data } = JSON.parse(msg.data);
        switch (event) {
          case 'station_playing':
            this.callbacks.onStationPlaying?.(data);
            break;
          case 'stations_url':
            this.callbacks.onStationsUrl?.(data);
            break;
          default:
            break;
        }
      } catch (e) {
        console.error('Error parsing WebSocket message:', e);
      }
    };
  }

  _scheduleReconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = setTimeout(() => {
      this._connectWebSocket();
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, 30000);
    }, this.reconnectDelay);
  }
}