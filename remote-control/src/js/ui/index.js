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

import { formatErrorMessage, RegistryRequestError } from "../utils/errors.js";
import { AuthView } from "./auth-view.js";
import { PlayerTabsView } from "./player-tabs-view.js";
import { SettingsView } from "./settings-view.js";

const TOAST_SEVERITY = {
  danger: { color: "danger", duration: 0, position: "top" },
  warning: {
    color: "warning",
    duration: 0,
    position: "top",
  },
  success: {
    color: "success",
    duration: 3000,
    position: "bottom",
  },
};

export class RadioPadUI {
  constructor({ actions = {}, copyTokenAvailable = false, selectors = {} } = {}) {
    this.actions = actions;
    this.auth = new AuthView((...args) => this.invokeAction(...args), {
      copyTokenAvailable,
      rootSelector: selectors.authRoot || 'ion-tab[tab="settings"]'
    });
    this.playerTabs = new PlayerTabsView((...args) => this.invokeAction(...args), {
      templateSelector: selectors.playerTemplate || '#tab-player'
    });
    this.settings = new SettingsView((...args) => this.invokeAction(...args), {
      rootSelector: selectors.settingsRoot || 'ion-tab[tab="settings"]'
    });
    this._toast = null;
    this._lastToastId = 0;
  }

  setActions(actions = {}) {
    this.actions = actions;
  }

  invokeAction(actionName, ...args) {
    const handler = this.actions[actionName];
    if (handler) {
      void Promise.resolve(handler(...args)).catch((error) => {
        console.error(`UI action "${actionName}" failed`, error);
      });
    }
  }

  init(actions = this.actions, { toastSelector = "#global-toast" } = {}) {
    this.setActions(actions);
    this._toast = document.querySelector(toastSelector);

    this.auth.init();
    this.settings.init();
    this.playerTabs.init();
  }

  setTabInfo(message, tabName = "control") {
    this.playerTabs.setTabInfo(message, tabName);
  }

  presentNotification(notification) {
    if (!(notification?.summary && notification.id !== this._lastToastId)) {
      return;
    }

    this._lastToastId = notification.id;
    const toastConfig =
      TOAST_SEVERITY[notification.severity] || TOAST_SEVERITY.warning;
    const detailText =
      notification.format === "registry"
        ? RegistryRequestError.format(notification.error)
        : formatErrorMessage(notification.error);
    const message = detailText
      ? `${notification.summary} ${detailText}`.trim()
      : notification.summary;

    void this.toast(message, {
      color: toastConfig.color,
      duration: notification.persistent ? 0 : toastConfig.duration,
      buttons: notification.persistent
        ? [{ text: "Dismiss", role: "cancel" }]
        : [],
      position: toastConfig.position,
    });
  }

  async toast(
    message,
    {
      color = "tertiary",
      duration = 3000,
      buttons = [],
      position = "bottom",
    } = {},
  ) {
    if (!this._toast) return;
    this._toast.message = message;
    this._toast.duration = duration;
    this._toast.color = color;
    this._toast.buttons = buttons;
    this._toast.position = position;
    await this._toast.present();
  }

  renderPreferences(preferences) {
    this.settings.renderPreferences(preferences);
  }

  updateAuthState(state) {
    this.auth.updateState(state);
  }

  setSettingsSaveState(state = "idle") {
    this.settings.setSaveState(state);
  }

  renderTabState(tabName, state) {
    this.playerTabs.renderTabState(tabName, state);
  }
}
