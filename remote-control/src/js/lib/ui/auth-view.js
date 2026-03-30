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

function setText(node, text = "") {
  if (node) {
    node.innerText = text;
  }
}

export class AuthView {
  constructor(invokeAction, { copyTokenAvailable = false } = {}) {
    this.invokeAction = invokeAction;
    this.copyTokenAvailable = copyTokenAvailable;
    this.state = null;
  }

  init() {
    this.status = document.getElementById("auth-status");
    this.hint = document.getElementById("auth-hint");
    this.identity = document.getElementById("auth-identity");
    this.actionsItem = document.getElementById("auth-actions-item");
    this.actions = document.getElementById("auth-actions");
  }

  updateState(state) {
    if (!this.status) {
      return;
    }

    this.state = state;
    const signedIn = state.enabled && state.signedIn;
    setText(
      this.status,
      state.enabled
        ? signedIn
          ? "Signed in"
          : "Signed out"
        : "Sign-in unavailable",
    );
    setText(
      this.hint,
      state.enabled
        ? signedIn
          ? "Your sign-in updates the Account and Player choices below."
          : "Sign in to load the accounts and players you can manage."
        : AUTH_DISABLED_HINTS[state.reason] ||
            "Sign-in is currently unavailable.",
    );
    setText(
      this.identity,
      signedIn
        ? [state.name, state.email, state.subject].filter(Boolean).join(" · ")
        : "",
    );

    this._renderControls();
  }

  _renderControls() {
    if (!(this.actions && this.actionsItem)) {
      return;
    }

    const controls = this._controls();
    this.actionsItem.hidden = controls.length === 0;
    this.actions.replaceChildren(...controls);
  }

  _controls() {
    if (!this.state?.enabled) {
      return [];
    }

    if (!this.state.signedIn) {
      return [this._createActionButton("Sign in with Google", "onSignIn")];
    }

    const controls = [
      this._createActionButton("Sign out", "onSignOut", {
        fill: "outline",
      }),
    ];

    if (this.copyTokenAvailable) {
      controls.push(
        this._createActionButton("Copy API test token", "onCopyToken", {
          fill: "outline",
        }),
      );
    }

    return controls;
  }

  _createActionButton(label, actionName, options = {}) {
    return this._createButton(
      label,
      () => {
        this.invokeAction(actionName);
      },
      options,
    );
  }

  _createButton(label, onClick, { fill = null } = {}) {
    const button = document.createElement("ion-button");
    button.expand = "block";
    if (fill) {
      button.fill = fill;
    }
    button.innerText = label;
    button.addEventListener("click", onClick);
    return button;
  }
}
