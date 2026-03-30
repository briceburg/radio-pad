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
  constructor(
    invokeAction,
    {
      copyTokenAvailable = false,
      rootSelector = 'ion-tab[tab="settings"]',
    } = {},
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
    this.status = this.root.querySelector("#auth-status");
    this.hint = this.root.querySelector("#auth-hint");
    this.identity = this.root.querySelector("#auth-identity");
    this.actionsItem = this.root.querySelector("#auth-actions-item");
    this.actions = this.root.querySelector("#auth-actions");

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
