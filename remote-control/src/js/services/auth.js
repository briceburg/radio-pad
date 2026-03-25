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
const CALLBACK_QUERY_KEYS = [
  "code",
  "state",
  "scope",
  "authuser",
  "prompt",
  "error",
  "error_description",
  "hd",
];

function getString(value) {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function hasAuthCallbackParams(currentUrl) {
  const url = new URL(currentUrl);
  return ["code", "state", "error"].some((key) => url.searchParams.has(key));
}

function buildCallbackCleanupUrl(currentUrl) {
  const url = new URL(currentUrl);
  for (const key of CALLBACK_QUERY_KEYS) {
    url.searchParams.delete(key);
  }
  return `${url.pathname}${url.search}${url.hash}`;
}

function normalizeUser(profile) {
  if (!profile || typeof profile !== "object") {
    return null;
  }

  const idToken = getString(profile.idToken);
  const subject = getString(profile.userId) || getString(profile.subject);
  const email = getString(profile.email);
  const name =
    getString(profile.displayName) ||
    getString(profile.name) ||
    email ||
    subject;

  if (!idToken) {
    return null;
  }

  return {
    idToken,
    subject,
    email,
    name,
  };
}

function isWebPlatform() {
  return Capacitor.getPlatform() === "web";
}

export class RadioPadAuth extends EventTarget {
  constructor() {
    super();
    this.config = this._buildConfig();
    this.isWeb = isWebPlatform();
    this.user = null;
    this.initialized = false;
    this.initError = null;
  }

  _buildConfig() {
    const currentPath = `${window.location.origin}${window.location.pathname}`;
    const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID?.trim() || null;

    if (!clientId) {
      return null;
    }

    return {
      clientId,
      redirectUrl:
        import.meta.env.VITE_GOOGLE_REDIRECT_URL?.trim() || currentPath,
    };
  }

  async _storeUser(user) {
    await Preferences.set({
      key: AUTH_STORAGE_KEY,
      value: JSON.stringify(user),
    });
  }

  async _restoreStoredUser() {
    const { value } = await Preferences.get({ key: AUTH_STORAGE_KEY });
    if (!value) {
      return null;
    }

    try {
      const user = normalizeUser(JSON.parse(value));
      if (!user) {
        await this._clearStoredUser();
        return null;
      }
      return user;
    } catch (error) {
      console.warn("Failed restoring Google sign-in state", error);
      await this._clearStoredUser();
      return null;
    }
  }

  async _clearStoredUser() {
    await Preferences.remove({ key: AUTH_STORAGE_KEY });
  }

  async _applySignInResult(result) {
    this.user = normalizeUser(result);
    if (!this.user) {
      throw new Error("Google sign-in did not return a valid user.");
    }
    await this._storeUser(this.user);
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
    if (!this.config?.clientId) {
      return "not_configured";
    }
    if (this.initError) {
      return "init_failed";
    }
    return null;
  }

  async init(currentUrl = window.location.href) {
    if (!this.config?.clientId) {
      await this.emitAuthState();
      return;
    }

    try {
      await GoogleSignIn.initialize({
        clientId: this.config.clientId,
        redirectUrl: this.isWeb ? this.config.redirectUrl : undefined,
      });
      this.initialized = true;
      this.initError = null;
    } catch (error) {
      this.initError = error;
      this.dispatchEvent(
        new CustomEvent("error", {
          detail: { summary: "⚠️ Sign-in unavailable.", error },
        }),
      );
      await this.emitAuthState();
      return;
    }

    if (this.isWeb && hasAuthCallbackParams(currentUrl)) {
      try {
        await this._applySignInResult(
          await GoogleSignIn.handleRedirectCallback(),
        );
      } catch (error) {
        this.dispatchEvent(
          new CustomEvent("error", {
            detail: { summary: "⚠️ Sign-in failed.", error },
          }),
        );
      } finally {
        window.history.replaceState(
          {},
          document.title,
          buildCallbackCleanupUrl(currentUrl),
        );
      }
    } else {
      this.user = await this._restoreStoredUser();
    }

    await this.emitAuthState();
  }

  async signIn() {
    if (!this.config?.clientId) {
      throw new Error(
        "Google sign-in is not configured. Set VITE_GOOGLE_CLIENT_ID.",
      );
    }

    if (this.initError) {
      throw this.initError;
    }

    if (this.isWeb) {
      await GoogleSignIn.signIn();
      return;
    }

    await this._applySignInResult(await GoogleSignIn.signIn());
    await this.emitAuthState();
  }

  async signOut() {
    if (this.initialized) {
      await GoogleSignIn.signOut();
    }

    await this._clearStoredUser();
    this.user = null;
    await this.emitAuthState();
  }

  getRegistryBearerToken() {
    return this.user?.idToken || null;
  }

  getState() {
    const user = this.user;

    return {
      enabled: this.enabled,
      reason: this._getReason(),
      signedIn: Boolean(user),
      name: user?.name || null,
      email: user?.email || null,
      subject: user?.subject || null,
      registryBearerToken: this.getRegistryBearerToken(),
    };
  }

  async emitAuthState() {
    this.dispatchEvent(
      new CustomEvent("statechange", { detail: this.getState() }),
    );
  }
}
