// SPDX-FileCopyrightText: 2025 Brice Burgess (github.com/briceburg)
// SPDX-License-Identifier: AGPL-3.0-or-later

import { GoogleSignIn } from "@capawesome/capacitor-google-sign-in";
import { Capacitor } from "@capacitor/core";
import { Preferences } from "@capacitor/preferences";

const REFRESH_EARLY_MS = 60_000;
const REFRESH_RETRY_MS = 30_000;
const LEGACY_AUTH_STORAGE_KEY = "radio-pad.google-sign-in.user";

function sessionUrl(registryUrl, suffix = "") {
  const registryBase = new URL(registryUrl, window.location.origin);
  return new URL(`auth/session${suffix}`, registryBase).toString();
}

export class RadioPadAuth extends EventTarget {
  constructor() {
    super();
    this.isWeb = Capacitor.getPlatform() === "web";
    this.registryUrl = null;
    this.user = null;
    this.refreshTimer = null;
    this.initialized = false;
    this.initError = null;

    const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID?.trim() || null;
    this.config = clientId
      ? {
          clientId,
          redirectUrl:
            import.meta.env.VITE_GOOGLE_REDIRECT_URL?.trim() ||
            `${window.location.origin}${window.location.pathname}`,
        }
      : null;
  }

  get enabled() {
    return (
      Boolean(this.config?.clientId) && this.initialized && !this.initError
    );
  }

  get signedIn() {
    return Boolean(this.user);
  }

  _getReason() {
    if (!this.config?.clientId) return "not_configured";
    if (this.initError) return "init_failed";
    return null;
  }

  _setRegistryUrl(registryUrl) {
    this.registryUrl = registryUrl
      ? new URL(registryUrl, window.location.origin).toString()
      : null;
  }

  _clearUser() {
    this.user = null;
    if (this.refreshTimer) {
      clearTimeout(this.refreshTimer);
      this.refreshTimer = null;
    }
  }

  _applySession(session) {
    const identity = session?.identity;
    if (
      typeof session?.access_token !== "string" ||
      typeof session?.expires_at !== "number" ||
      typeof identity?.subject !== "string"
    ) {
      throw new Error("Invalid registry session response.");
    }
    this.user = {
      accessToken: session.access_token,
      expiresAt: session.expires_at,
      subject: identity.subject,
      email: identity.email || null,
      name: identity.name || identity.email || identity.subject,
    };
    this._scheduleRefresh();
  }

  async _requestSession(suffix, { method = "POST", token = null } = {}) {
    if (!this.registryUrl) throw new Error("Registry URL is not configured.");
    const headers = {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(suffix === "/refresh" ? { "RadioPad-Session": "refresh" } : {}),
    };
    const response = await fetch(sessionUrl(this.registryUrl, suffix), {
      method,
      credentials: "include",
      ...(Object.keys(headers).length ? { headers } : {}),
    });
    if (response.status === 401) return null;
    if (!response.ok) {
      throw new Error(`Registry session request failed (${response.status}).`);
    }
    return response.status === 204 ? null : response.json();
  }

  async _createSession(idToken) {
    const session = await this._requestSession("", { token: idToken });
    if (!session) throw new Error("Google sign-in was not accepted.");
    this._applySession(session);
  }

  async _refreshSession() {
    const session = await this._requestSession("/refresh");
    if (!session) {
      this._clearUser();
      return false;
    }
    this._applySession(session);
    return true;
  }

  _scheduleRefresh(delay = null) {
    if (this.refreshTimer) clearTimeout(this.refreshTimer);
    const expiresIn = this.user ? this.user.expiresAt * 1000 - Date.now() : 0;
    this.refreshTimer = setTimeout(
      () => void this._refreshActiveSession(),
      delay ?? Math.max(expiresIn - REFRESH_EARLY_MS, 0),
    );
  }

  async _refreshActiveSession() {
    try {
      if (!(await this._refreshSession())) {
        this._emitError("Session expired—sign in again.");
      }
      this._emitState();
    } catch (error) {
      if (this.user && this.user.expiresAt * 1000 > Date.now()) {
        this._scheduleRefresh(REFRESH_RETRY_MS);
      } else {
        this._clearUser();
        this._emitError("Session expired—sign in again.", error);
        this._emitState();
      }
    }
  }

  _emitError(summary, error = null) {
    this.dispatchEvent(
      new CustomEvent("error", { detail: { summary, error } }),
    );
  }

  async init(registryUrl, currentUrl = window.location.href) {
    this._setRegistryUrl(registryUrl);
    await Preferences.remove({ key: LEGACY_AUTH_STORAGE_KEY }).catch((error) =>
      console.warn("Couldn’t remove legacy sign-in data.", error),
    );
    if (!this.config?.clientId) {
      this._emitState();
      return false;
    }

    try {
      await GoogleSignIn.initialize({
        clientId: this.config.clientId,
        redirectUrl: this.isWeb ? this.config.redirectUrl : undefined,
      });
      this.initialized = true;
    } catch (error) {
      this.initError = error;
      this._emitError("Sign-in unavailable.", error);
      this._emitState();
      return false;
    }

    const isOauthCallback =
      this.isWeb &&
      currentUrl.includes("state=") &&
      (currentUrl.includes("id_token=") || currentUrl.includes("error="));

    try {
      if (isOauthCallback) {
        const profile = await GoogleSignIn.handleRedirectCallback();
        await this._createSession(profile.idToken);
      } else {
        await this._refreshSession();
      }
    } catch (error) {
      this._clearUser();
      this._emitError(
        isOauthCallback ? "Sign-in failed." : "Couldn’t restore sign-in.",
        error,
      );
    }

    this._emitState();
    return isOauthCallback;
  }

  async useRegistry(registryUrl) {
    const resolved = new URL(registryUrl, window.location.origin).toString();
    if (resolved === this.registryUrl) return;
    this._clearUser();
    this.registryUrl = resolved;
    try {
      if (this.enabled) await this._refreshSession();
    } catch (error) {
      this._emitError("Couldn’t restore sign-in.", error);
    }
    this._emitState();
  }

  async signIn() {
    if (!this.config?.clientId) {
      throw new Error(
        "Google sign-in is not configured. Set VITE_GOOGLE_CLIENT_ID.",
      );
    }
    if (this.initError) throw this.initError;

    const result = await GoogleSignIn.signIn();
    // On web, signIn redirects. Native returns the Google credential directly.
    if (result) {
      await this._createSession(result.idToken);
      this._emitState();
    }
  }

  async signOut() {
    await this._requestSession("", { method: "DELETE" });
    this._clearUser();
    try {
      if (this.initialized) await GoogleSignIn.signOut();
    } finally {
      this._emitState();
    }
  }

  getRegistryBearerToken() {
    return this.user?.accessToken || null;
  }

  getState() {
    return {
      enabled: this.enabled,
      reason: this._getReason(),
      signedIn: this.signedIn,
      name: this.user?.name || null,
      email: this.user?.email || null,
      subject: this.user?.subject || null,
      registryBearerToken: this.getRegistryBearerToken(),
    };
  }

  _emitState() {
    this.dispatchEvent(
      new CustomEvent("statechange", { detail: this.getState() }),
    );
  }
}
