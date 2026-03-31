/*
This file is part of the radio-pad project.
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
    // Disable shadow DOM so Ionic styles apply seamlessly.
    return this;
  }

  get copyTokenAvailable() {
    return !Capacitor.isNativePlatform();
  }

  _onSignIn() {
    this.dispatchEvent(
      new CustomEvent("auth-signin", { bubbles: true, composed: true }),
    );
  }

  _onSignOut() {
    this.dispatchEvent(
      new CustomEvent("auth-signout", { bubbles: true, composed: true }),
    );
  }

  _onCopyToken() {
    this.dispatchEvent(
      new CustomEvent("auth-copytoken", { bubbles: true, composed: true }),
    );
  }

  render() {
    const state = this.authController.value;

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

    return html`
      <ion-item-group>
        <ion-item-divider color="tertiary">
          <ion-icon name="person-circle" slot="start"></ion-icon>
          <ion-label>Account</ion-label>
        </ion-item-divider>
        <ion-item lines="none">
          <ion-label>
            <h3 id="auth-status">${statusText}</h3>
            <p id="auth-hint">${hintText}</p>
            ${identityText
              ? html`<p id="auth-identity" class="ion-text-wrap auth-identity">
                  ${identityText}
                </p>`
              : ""}
          </ion-label>
        </ion-item>
        <ion-item lines="none" ?hidden=${!state.enabled}>
          <ion-grid class="ion-no-padding">
            <ion-row class="ion-justify-content-start">
              ${this._renderControls(state)}
            </ion-row>
          </ion-grid>
        </ion-item>
      </ion-item-group>
    `;
  }

  _renderControls(state) {
    if (!state.enabled) return "";

    if (!state.signedIn) {
      return html`
        <ion-col size="12" size-sm="auto">
          <ion-button expand="block" @click=${this._onSignIn}
            >Sign in with Google</ion-button
          >
        </ion-col>
      `;
    }

    return html`
      <ion-col size="12" size-sm="auto">
        <ion-button expand="block" fill="outline" @click=${this._onSignOut}
          >Sign out</ion-button
        >
      </ion-col>
      ${this.copyTokenAvailable
        ? html`
            <ion-col size="12" size-sm="auto">
              <ion-button
                expand="block"
                fill="outline"
                @click=${this._onCopyToken}
                >Copy API test token</ion-button
              >
            </ion-col>
          `
        : ""}
    `;
  }
}

customElements.define("radio-auth", RadioAuth);
