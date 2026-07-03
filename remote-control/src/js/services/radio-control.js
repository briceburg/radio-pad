// SPDX-FileCopyrightText: 2025 Brice Burgess (github.com/briceburg)
// SPDX-License-Identifier: AGPL-3.0-or-later

import { Capacitor } from "@capacitor/core";

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

export class RadioControl extends EventTarget {
  constructor() {
    super();
    this.ws = null;
    this.authTimer = null;
    this.reconnectTimer = null;
    this.reconnectDelay = 1000;
    this._lastUrl = null;
    this._lastToken = null;
    this.authenticated = false;
  }

  connect(url = null, token = null) {
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
    this.authenticated = false;
    const hadSocket = Boolean(this.ws);
    if (this.authTimer) {
      clearTimeout(this.authTimer);
      this.authTimer = null;
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

  sendCommand(event, data = null) {
    if (
      this.authenticated &&
      this.ws &&
      this.ws.readyState === WebSocket.OPEN
    ) {
      this.ws.send(JSON.stringify({ event, data }));
      return;
    }

    this.dispatchEvent(
      new CustomEvent("error", {
        detail: `WebSocket not connected. Cannot send ${event} command.`,
      }),
    );
  }

  startPlayback(callSign) {
    this.sendCommand("playback_start", { call_sign: callSign });
  }

  stopPlayback() {
    this.sendCommand("playback_stop");
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

    const ws = new WebSocket(url);
    this.ws = ws;
    this.authenticated = false;

    this.authTimer = setTimeout(() => {
      if (!this.authenticated) {
        ws.close();
      }
    }, 10000);

    ws.onopen = () => {
      ws.send(JSON.stringify({ event: "authenticate", data: { token } }));
    };

    ws.onclose = (event) => {
      clearTimeout(this.authTimer);
      this.authTimer = null;
      this.ws = null;
      this.authenticated = false;
      if (event.code === 1008) {
        this._lastUrl = null;
        this._lastToken = null;
        const detail =
          event.reason === "Access denied"
            ? "You don’t have access to this player."
            : "Session expired—sign in again.";
        this.dispatchEvent(new CustomEvent("accessdenied", { detail }));
        return;
      }
      this.dispatchEvent(new Event("disconnect"));
      this._scheduleReconnect();
    };

    ws.onerror = () => {
      this.dispatchEvent(
        new CustomEvent("error", { detail: "WebSocket connection error." }),
      );
    };

    ws.onmessage = (msg) => {
      try {
        const { event, data } = JSON.parse(msg.data);
        switch (event) {
          case "authenticated":
            clearTimeout(this.authTimer);
            this.authTimer = null;
            this.authenticated = true;
            this.reconnectDelay = 1000;
            if (this.reconnectTimer) {
              clearTimeout(this.reconnectTimer);
              this.reconnectTimer = null;
            }
            this.dispatchEvent(new CustomEvent("connect", { detail: url }));
            break;
          case "playback_state": {
            const state = data && typeof data === "object" ? data : {};
            this.dispatchEvent(
              new CustomEvent("playbackstate", {
                detail: {
                  callSign: state.call_sign || null,
                  requestedCallSign: state.requested_call_sign || null,
                  failedCallSign: state.failed_call_sign || null,
                },
              }),
            );
            break;
          }
          case "radio_dial_url":
            if (typeof data === "string" && data) {
              this.dispatchEvent(
                new CustomEvent("radiodialurl", { detail: data }),
              );
            }
            break;
          case "player_presence":
            if (data && typeof data === "object") {
              this.dispatchEvent(
                new CustomEvent("playerpresence", { detail: data }),
              );
            }
            break;
          case "player_status":
            if (data && typeof data === "object") {
              this.dispatchEvent(
                new CustomEvent("playerstatus", { detail: data }),
              );
            }
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
    if (!this._lastUrl) return;

    this.reconnectTimer = setTimeout(() => {
      if (this._lastUrl) {
        this._connectWebSocket(this._lastUrl, this._lastToken);
        const jitter = Math.random() * 1000;
        this.reconnectDelay = Math.min(
          this.reconnectDelay * 1.5 + jitter,
          30000,
        );
      }
    }, this.reconnectDelay);
  }
}
