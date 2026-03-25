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

const AUTH_DISABLED_HINTS = {
  init_failed:
    "Sign-in could not be initialized. Check the Google client configuration and try reloading.",
  not_configured: "This build does not have account sign-in configured.",
};

import { html, render } from "lit-html";

export class AuthView {
  constructor(
    invokeAction,
    { copyTokenAvailable = false, rootSelector = "#auth-container" } = {},
  ) {
    this.invokeAction = invokeAction;
    this.copyTokenAvailable = copyTokenAvailable;
    this.rootSelector = rootSelector;
  }

  init() {
    this.root =
      typeof this.rootSelector === "string"
        ? document.querySelector(this.rootSelector)
        : this.rootSelector;

    // Initial empty state
    this.updateState({ enabled: false });
  }

  updateState(state) {
    if (!this.root) return;

    const statusText = state.enabled
      ? state.signedIn
        ? "Signed in"
        : "Signed out"
      : "Sign-in unavailable";

    const hintText = state.enabled
      ? state.signedIn
        ? "Your sign-in updates the Account and Player choices below."
        : "Sign in to load the accounts and players you can manage."
      : AUTH_DISABLED_HINTS[state.reason] ||
        "Sign-in is currently unavailable.";

    const identityText =
      state.enabled && state.signedIn
        ? [state.name, state.email, state.subject].filter(Boolean).join(" · ")
        : "";

    const renderControls = () => {
      if (!state.enabled) return "";

      if (!state.signedIn) {
        return html`<ion-button
          expand="block"
          @click=${() => this.invokeAction("onSignIn")}
          >Sign in with Google</ion-button
        >`;
      }

      return html`
        <ion-button
          expand="block"
          fill="outline"
          @click=${() => this.invokeAction("onSignOut")}
          >Sign out</ion-button
        >
        ${this.copyTokenAvailable
          ? html`<ion-button
              expand="block"
              fill="outline"
              @click=${() => this.invokeAction("onCopyToken")}
              >Copy API test token</ion-button
            >`
          : ""}
      `;
    };

    const template = html`
      <ion-item-divider color="tertiary">
        <ion-icon name="person-circle" slot="start"></ion-icon>
        <ion-label>Account Sign-In</ion-label>
      </ion-item-divider>
      <ion-item lines="none">
        <ion-label>
          <h3 id="auth-status">${statusText}</h3>
          <p id="auth-hint">${hintText}</p>
          ${identityText
            ? html`<p id="auth-identity" class="auth-identity">
                ${identityText}
              </p>`
            : ""}
        </ion-label>
      </ion-item>
      <ion-item lines="none" ?hidden=${!state.enabled}>
        <div class="auth-actions" style="width: 100%;">${renderControls()}</div>
      </ion-item>
    `;

    render(template, this.root);
  }
}
