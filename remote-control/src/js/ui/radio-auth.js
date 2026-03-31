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

import { LitElement, html } from "lit";
import { StoreController } from "@nanostores/lit";
import { authStore } from "../store.js";
import { Capacitor } from "@capacitor/core";

const AUTH_DISABLED_HINTS = {
  init_failed:
    "Sign-in could not be initialized. Check the Google client configuration and try reloading.",
  not_configured: "This build does not have account sign-in configured.",
};

export class RadioAuth extends LitElement {
  authController = new StoreController(this, authStore);

  createRenderRoot() {
    return this;
  }

  _dispatch(name) {
    this.dispatchEvent(
      new CustomEvent(name, { bubbles: true, composed: true }),
    );
  }

  _renderBtn(label, event, fill = "solid") {
    return html`<ion-col size="12" size-sm="auto"
      ><ion-button
        expand="block"
        fill=${fill}
        @click=${() => this._dispatch(event)}
        >${label}</ion-button
      ></ion-col
    >`;
  }

  render() {
    const s = this.authController.value;
    const txt = s.enabled
      ? s.signedIn
        ? [
            "Signed in",
            "Your sign-in updates the Account and Player choices below.",
          ]
        : [
            "Signed out",
            "Sign in to load the accounts and players you can manage.",
          ]
      : [
          "Sign-in unavailable",
          AUTH_DISABLED_HINTS[s.reason] || "Sign-in is currently unavailable.",
        ];
    const identityText =
      s.enabled && s.signedIn
        ? [s.name, s.email, s.subject].filter(Boolean).join(" · ")
        : "";

    return html`
      <ion-item-group>
        <ion-item-divider color="tertiary"
          ><ion-icon name="person-circle" slot="start"></ion-icon
          ><ion-label>Account</ion-label></ion-item-divider
        >
        <ion-item lines="none">
          <ion-label
            ><h3 id="auth-status">${txt[0]}</h3>
            <p id="auth-hint">${txt[1]}</p>
            ${identityText
              ? html`<p id="auth-identity" class="ion-text-wrap auth-identity">
                  ${identityText}
                </p>`
              : ""}</ion-label
          >
        </ion-item>
        <ion-item lines="none" ?hidden=${!s.enabled}>
          <ion-grid class="ion-no-padding"
            ><ion-row class="ion-justify-content-start">
              ${s.enabled && !s.signedIn
                ? this._renderBtn("Sign in with Google", "auth-signin")
                : ""}
              ${s.enabled && s.signedIn
                ? html`${this._renderBtn("Sign out", "auth-signout", "outline")}
                  ${!Capacitor.isNativePlatform()
                    ? this._renderBtn(
                        "Copy API test token",
                        "auth-copytoken",
                        "outline",
                      )
                    : ""}`
                : ""}
            </ion-row></ion-grid
          >
        </ion-item>
      </ion-item-group>
    `;
  }
}
if (!customElements.get("radio-auth")) {
  customElements.define("radio-auth", RadioAuth);
}
