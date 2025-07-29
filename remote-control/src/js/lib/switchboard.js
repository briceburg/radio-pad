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

import { EventEmitter } from "./interfaces.js";

export class RadioPadSwitchboard extends EventEmitter {
  constructor() {
    super();
    this.ws = null;
    this.reconnectTimer = null;
    this.reconnectDelay = 1000; // Initial reconnect delay
    this._lastUrl = null;
  }

  async connect(url) {
    this._lastUrl = url;
    this.disconnect(); // Ensure any existing connection is closed
    this._connectWebSocket(url);
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
  }

  sendStationRequest(stationName) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(
        JSON.stringify({ event: "station_request", data: stationName })
      );
    } else {
      this.emitEvent(
        "error",
        "WebSocket not connected. Cannot send station request."
      );
    }
  }

  _connectWebSocket(url) {
    if (
      this.ws &&
      (this.ws.readyState === WebSocket.OPEN ||
        this.ws.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    this.emitEvent("connecting", url);
    this.ws = new WebSocket(url);

    const connectTimeout = setTimeout(() => {
      if (this.ws.readyState !== WebSocket.OPEN) {
        this.ws.close();
      }
    }, 3000);

    this.ws.onopen = () => {
      clearTimeout(connectTimeout);
      this.reconnectDelay = 1000;
      if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
      this.emitEvent("connect", url);
    };

    this.ws.onclose = () => {
      clearTimeout(connectTimeout);
      this.emitEvent("disconnect");
      this._scheduleReconnect();
    };

    this.ws.onerror = (err) => {
      clearTimeout(connectTimeout);
      this.emitEvent("error", "WebSocket error.");
    };

    this.ws.onmessage = (msg) => {
      try {
        const { event, data } = JSON.parse(msg.data);
        switch (event) {
          case "station_playing":
            this.emitEvent("station-playing", data);
            break;
          case "stations_url":
            this.emitEvent("stations-url", data);
            break;
        }
      } catch (e) {
        this.emitEvent("error", "Error parsing WebSocket message.");
      }
    };
  }

  _scheduleReconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = setTimeout(() => {
      if (this._lastUrl) {
        this._connectWebSocket(this._lastUrl);
        this.reconnectDelay = Math.min(this.reconnectDelay * 2, 30000);
      }
    }, this.reconnectDelay);
  }
}
