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
import {
  advanceRetryState,
  createRetryState,
  resetRetryState,
} from "../utils/retry.js";

const CONTROL_CONNECT_TIMEOUT_MS = 4000;
const CONTROL_RETRY_OPTIONS = {
  initialDelayMs: 500,
  factor: 1.5,
  jitterMs: 500,
  maxDelayMs: 8000,
};

function resolveSwitchboardPath(basePath, targetPath) {
  const normalizedBasePath = basePath.replace(/\/$/, "");
  return normalizedBasePath && !targetPath.startsWith(normalizedBasePath)
    ? `${normalizedBasePath}${targetPath}`
    : targetPath;
}

function resolvePlayerSwitchboardUrl(url) {
  const override = import.meta.env.VITE_SWITCHBOARD_URL?.trim();
  if (!(override && url) || Capacitor.isNativePlatform()) {
    return url;
  }

  try {
    const target = new URL(url);
    const local = new URL(
      override,
      window.location.origin.replace(/^http/, "ws"),
    );
    local.pathname = resolveSwitchboardPath(local.pathname, target.pathname);
    local.search = target.search;
    local.hash = target.hash;
    return local.toString();
  } catch (error) {
    console.warn("Invalid VITE_SWITCHBOARD_URL override.", error);
    return url;
  }
}

function resolvePlayerStationsUrl(url) {
  if (!(url && !Capacitor.isNativePlatform())) {
    return url;
  }

  try {
    const target = new URL(url);
    const local = new URL(window.location.origin);
    const apiPath = local.pathname.replace(/\/$/, "");

    local.pathname = target.pathname.replace(/^\/api/, apiPath || "/api");
    local.search = target.search;
    local.hash = target.hash;
    return local.toString();
  } catch (error) {
    console.warn("Invalid stations URL received from player.", error);
    return url;
  }
}

export class RadioControl extends EventTarget {
  constructor() {
    super();
    this.ws = null;
    this.reconnectTimer = null;
    this.retryState = createRetryState(CONTROL_RETRY_OPTIONS);
    this._lastUrl = null;
    this._lastToken = null;
  }

  async connect(url = null, token = null) {
    const nextUrl = url ? resolvePlayerSwitchboardUrl(url) : this._lastUrl;
    const nextToken = token !== undefined ? token : this._lastToken;
    this.disconnect();
    this._lastUrl = nextUrl;
    this._lastToken = nextToken;
    this._connectWebSocket(this._lastUrl, this._lastToken);
  }

  disconnect() {
    this._lastUrl = null;
    this._lastToken = null;
    const hadSocket = Boolean(this.ws);
    if (this.connectTimer) {
      clearTimeout(this.connectTimer);
      this.connectTimer = null;
    }
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.onopen = null;
      this.ws.onclose = null;
      this.ws.onerror = null;
      this.ws.onmessage = null;
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

  _connectWebSocket(url, token) {
    if (!url) return;

    if (
      this.ws &&
      (this.ws.readyState === WebSocket.OPEN ||
        this.ws.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    this.dispatchEvent(new CustomEvent("connecting", { detail: url }));

    let wsUrl = url;
    if (token) {
      try {
        const u = new URL(wsUrl);
        u.searchParams.set("token", token);
        wsUrl = u.toString();
      } catch {}
    }
    const ws = new WebSocket(wsUrl);
    this.ws = ws;

    this.connectTimer = setTimeout(() => {
      if (ws.readyState !== WebSocket.OPEN) {
        ws.close();
      }
    }, CONTROL_CONNECT_TIMEOUT_MS);

    ws.onopen = () => {
      clearTimeout(this.connectTimer);
      resetRetryState(this.retryState);
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer);
      }
      this.dispatchEvent(new CustomEvent("connect", { detail: url }));
    };

    ws.onclose = () => {
      clearTimeout(this.connectTimer);
      this.dispatchEvent(new Event("disconnect"));
      this._scheduleReconnect();
    };

    ws.onerror = () => {
      clearTimeout(this.connectTimer);
      this.dispatchEvent(
        new CustomEvent("error", { detail: "WebSocket error." }),
      );
    };

    ws.onmessage = (msg) => {
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
              new CustomEvent("stationsurl", {
                detail: resolvePlayerStationsUrl(data),
              }),
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
    // Only schedule a reconnect if we still have an active URL and haven't explicitly disconnected
    if (!this._lastUrl) return;

    const { delayMs } = advanceRetryState(this.retryState);

    this.reconnectTimer = setTimeout(() => {
      if (this._lastUrl) {
        this._connectWebSocket(this._lastUrl, this._lastToken);
      }
    }, delayMs);
  }
}
