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

import { Capacitor } from "@capacitor/core";

function resolvePlayerSwitchboardUrl(url) {
  const override = import.meta.env.VITE_SWITCHBOARD_URL?.trim();
  if (!(override && url) || Capacitor.isNativePlatform()) {
    return url;
  }

  try {
    const target = new URL(url);
    const local = new URL(override);
    local.pathname = `${local.pathname.replace(/\/$/, "")}${target.pathname}`;
    local.search = target.search;
    local.hash = target.hash;
    return local.toString();
  } catch (error) {
    console.warn("Invalid VITE_SWITCHBOARD_URL override.", error);
    return url;
  }
}

export class RadioControl extends EventTarget {
  constructor() {
    super();
    this.ws = null;
    this.reconnectTimer = null;
    this.reconnectDelay = 1000;
    this._lastUrl = null;
  }

  async connect(url = null) {
    if (url) {
      this._lastUrl = resolvePlayerSwitchboardUrl(url);
    }
    this.disconnect();
    this._connectWebSocket(this._lastUrl);
  }

  disconnect() {
    const hadSocket = Boolean(this.ws);
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.onclose = null;
      this.ws.close();
      this.ws = null;
    }
    if (hadSocket) {
      this.dispatchEvent(new Event("disconnect"));
    }
  }

  sendStationRequest(stationName) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(
        JSON.stringify({ event: "station_request", data: stationName }),
      );
      return;
    }

    this.dispatchEvent(
      new CustomEvent("error", {
        detail: "WebSocket not connected. Cannot send station request.",
      }),
    );
  }

  _connectWebSocket(url) {
    if (
      this.ws &&
      (this.ws.readyState === WebSocket.OPEN ||
        this.ws.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    this.dispatchEvent(new CustomEvent("connecting", { detail: url }));
    this.ws = new WebSocket(url);

    const connectTimeout = setTimeout(() => {
      if (this.ws.readyState !== WebSocket.OPEN) {
        this.ws.close();
      }
    }, 3000);

    this.ws.onopen = () => {
      clearTimeout(connectTimeout);
      this.reconnectDelay = 1000;
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer);
      }
      this.dispatchEvent(new CustomEvent("connect", { detail: url }));
    };

    this.ws.onclose = () => {
      clearTimeout(connectTimeout);
      this.dispatchEvent(new Event("disconnect"));
      this._scheduleReconnect();
    };

    this.ws.onerror = () => {
      clearTimeout(connectTimeout);
      this.dispatchEvent(
        new CustomEvent("error", { detail: "WebSocket error." }),
      );
    };

    this.ws.onmessage = (msg) => {
      try {
        const { event, data } = JSON.parse(msg.data);
        switch (event) {
          case "station_playing":
            this.dispatchEvent(
              new CustomEvent("stationplaying", { detail: data }),
            );
            break;
          case "stations_url":
            this.dispatchEvent(
              new CustomEvent("stationsurl", { detail: data }),
            );
            break;
        }
      } catch {
        this.dispatchEvent(
          new CustomEvent("error", {
            detail: "Error parsing WebSocket message.",
          }),
        );
      }
    };
  }

  _scheduleReconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
    }
    this.reconnectTimer = setTimeout(() => {
      if (this._lastUrl) {
        this._connectWebSocket(this._lastUrl);
        this.reconnectDelay = Math.min(this.reconnectDelay * 2, 30000);
      }
    }, this.reconnectDelay);
  }
}
