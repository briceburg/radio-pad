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

import { html } from "lit";
import { RadioElement } from "./radio-element.js";
import { StoreController } from "@nanostores/lit";
import { authStore } from "../store.js";
import { Capacitor } from "@capacitor/core";

const AUTH_DISABLED_HINTS = {
  init_failed:
    "Sign-in could not be initialized. Check the Google client configuration and try reloading.",
  not_configured: "This build does not have account sign-in configured.",
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
      signInHint =
        AUTH_DISABLED_HINTS[s.reason] || "Sign-in is currently unavailable.";
    } else if (s.signedIn) {
      signInStatus = "Signed in";
      signInHint = "Your sign-in updates the Account and Player choices below.";
      identityText = [s.name, s.email, s.subject].filter(Boolean).join(" · ");
    } else {
      signInStatus = "Signed out";
      signInHint = "Sign in to load the accounts and players you can manage.";
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
        <ion-label color="tertiary">
          <h3 id="auth-status">${signInStatus}</h3>
          <p id="auth-hint">${signInHint}</p>
          ${identityText
            ? html`<p id="auth-identity" class="ion-text-wrap">
                ${identityText}
              </p>`
            : ""}
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
