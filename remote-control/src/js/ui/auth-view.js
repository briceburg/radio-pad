/*
This file is part of the radio-pad project.
https://github.com/briceburg/radio-pad
*/

const AUTH_DISABLED_HINTS = {
  init_failed:
    "Sign-in could not be initialized. Check the Google client configuration and try reloading.",
  not_configured: "This build does not have account sign-in configured.",
};

export class AuthView {
  constructor(invokeAction, { copyTokenAvailable = false } = {}) {
    this.invokeAction = invokeAction;
    this.copyTokenAvailable = copyTokenAvailable;
  }

  init() {
    this.status = document.getElementById("auth-status");
    this.hint = document.getElementById("auth-hint");
    this.identity = document.getElementById("auth-identity");
    this.actionsItem = document.getElementById("auth-actions-item");
    this.actions = document.getElementById("auth-actions");

    this.actions.addEventListener("click", (e) => {
      const btn = e.target.closest("ion-button");
      if (btn?.dataset.action) this.invokeAction(btn.dataset.action);
    });
  }

  updateState(state) {
    if (!this.status) return;

    this.status.innerText = state.enabled
      ? state.signedIn
        ? "Signed in"
        : "Signed out"
      : "Sign-in unavailable";
    this.hint.innerText = state.enabled
      ? state.signedIn
        ? "Your sign-in updates the Account and Player choices below."
        : "Sign in to load the accounts and players you can manage."
      : AUTH_DISABLED_HINTS[state.reason] ||
        "Sign-in is currently unavailable.";

    this.identity.innerText =
      state.enabled && state.signedIn
        ? [state.name, state.email, state.subject].filter(Boolean).join(" · ")
        : "";

    this._renderControls(state);
  }

  _renderControls(state) {
    if (!(this.actions && this.actionsItem)) return;

    let html = "";
    if (state?.enabled) {
      if (!state.signedIn) {
        html += `<ion-button expand="block" data-action="onSignIn">Sign in with Google</ion-button>`;
      } else {
        html += `<ion-button expand="block" fill="outline" data-action="onSignOut">Sign out</ion-button>`;
        if (this.copyTokenAvailable) {
          html += `<ion-button expand="block" fill="outline" data-action="onCopyToken">Copy API test token</ion-button>`;
        }
      }
    }

    this.actionsItem.hidden = !html;
    this.actions.innerHTML = html;
  }
}
