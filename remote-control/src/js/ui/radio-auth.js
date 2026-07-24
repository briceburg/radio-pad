// SPDX-FileCopyrightText: 2025 Brice Burgess (github.com/briceburg)
// SPDX-License-Identifier: AGPL-3.0-or-later

import { html } from "lit";
import { RadioElement } from "./radio-element.js";
import { StoreController } from "@nanostores/lit";
import { authStore } from "../store.js";
import { Capacitor } from "@capacitor/core";

const AUTH_DISABLED_HINTS = {
  init_failed:
    "Sign-in couldn’t start. Check the Google client configuration, then reload.",
  not_configured: "Account sign-in is not configured for this build.",
};

export class RadioAuth extends RadioElement {
  authController = new StoreController(this, authStore);

  _renderBtn(label, event, fill = "solid") {
    return html`<ion-col size="12" size-sm="auto"
      ><ion-button expand="block" fill=${fill} @click=${() => this._emit(event)}
        >${label}</ion-button
      ></ion-col
    >`;
  }

  render() {
    const s = this.authController.value;

    let signInStatus = "";
    let signInHint = "";
    let identityText = "";
    if (!s.enabled) {
      signInStatus = "Sign-in unavailable";
      signInHint = AUTH_DISABLED_HINTS[s.reason] || "Sign-in is unavailable.";
    } else if (s.signedIn) {
      signInStatus = "Signed in";
      signInHint =
        "Accounts, players, and RadioDials reflect your current access.";
      identityText = [s.name, s.email, s.subject].filter(Boolean).join(" · ");
    } else {
      signInStatus = "Signed out";
      signInHint =
        "Sign in to see the accounts, players, and RadioDials available to you.";
    }

    let buttons = "";
    if (s.enabled) {
      if (!s.signedIn) {
        buttons = this._renderBtn("Sign in with Google", "auth-signin");
      } else {
        const signOutBtn = this._renderBtn(
          "Sign out",
          "auth-signout",
          "outline",
        );
        const copyTokenBtn = !Capacitor.isNativePlatform()
          ? this._renderBtn("Copy API test token", "auth-copytoken", "outline")
          : "";
        buttons = html`${signOutBtn}${copyTokenBtn}`;
      }
    }

    return html`
      <ion-item lines="none">
        <ion-label color="tertiary" role="status" aria-live="polite">
          <h3 id="auth-status">${signInStatus}</h3>
          <p id="auth-hint">${signInHint}</p>
          ${
            identityText
              ? html`<p id="auth-identity" class="ion-text-wrap">
                  ${identityText}
                </p>`
              : ""
          }
        </ion-label>
      </ion-item>
      <ion-item lines="none" ?hidden=${!s.enabled}>
        <ion-grid class="ion-no-padding">
          <ion-row class="ion-justify-content-start"> ${buttons} </ion-row>
        </ion-grid>
      </ion-item>
    `;
  }
}
RadioAuth.register("radio-auth");
