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

import { GoogleSignIn } from "@capawesome/capacitor-google-sign-in";
import { Capacitor } from "@capacitor/core";
import { Preferences } from "@capacitor/preferences";

const AUTH_STORAGE_KEY = "radio-pad.google-sign-in.user";

export class RadioPadAuth extends EventTarget {
  constructor() {
    super();
    this.isWeb = Capacitor.getPlatform() === "web";
    this.user = null;
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

  async _storeUser(profile) {
    if (!profile) return;
    this.user = {
      idToken: profile.idToken,
      subject: profile.userId || profile.subject,
      email: profile.email || null,
      name:
        profile.displayName || profile.name || profile.email || profile.userId,
    };
    await Preferences.set({
      key: AUTH_STORAGE_KEY,
      value: JSON.stringify(this.user),
    });
  }

  async init(currentUrl = window.location.href) {
    if (!this.config?.clientId) return this.emitAuthState();

    try {
      await GoogleSignIn.initialize({
        clientId: this.config.clientId,
        redirectUrl: this.isWeb ? this.config.redirectUrl : undefined,
      });
      this.initialized = true;
    } catch (error) {
      this.initError = error;
      this.dispatchEvent(
        new CustomEvent("error", {
          detail: { summary: "⚠️ Sign-in unavailable.", error },
        }),
      );
      return this.emitAuthState();
    }

    const isOauthCallback =
      this.isWeb &&
      currentUrl.includes("state=") &&
      (currentUrl.includes("id_token=") || currentUrl.includes("error="));

    if (isOauthCallback) {
      try {
        await this._storeUser(await GoogleSignIn.handleRedirectCallback());
      } catch (error) {
        this.dispatchEvent(
          new CustomEvent("error", {
            detail: { summary: "⚠️ Sign-in failed.", error },
          }),
        );
      }
    }

    if (!this.user) {
      const { value } = await Preferences.get({ key: AUTH_STORAGE_KEY });
      this.user = value ? JSON.parse(value) : null;
    }

    await this.emitAuthState();
    return isOauthCallback;
  }

  async signIn() {
    if (!this.config?.clientId) {
      throw new Error(
        "Google sign-in is not configured. Set VITE_GOOGLE_CLIENT_ID.",
      );
    }
    if (this.initError) throw this.initError;

    const result = await GoogleSignIn.signIn();
    // On web, signIn redirects so this won't execute. On native, it returns the result.
    if (result) {
      await this._storeUser(result);
      await this.emitAuthState();
    }
  }

  async signOut() {
    this.user = null;
    await Preferences.remove({ key: AUTH_STORAGE_KEY });
    if (this.initialized) await GoogleSignIn.signOut();
    await this.emitAuthState();
  }

  getRegistryBearerToken() {
    return this.user?.idToken || null;
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

  async emitAuthState() {
    this.dispatchEvent(
      new CustomEvent("statechange", { detail: this.getState() }),
    );
  }
}
