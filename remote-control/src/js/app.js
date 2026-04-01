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

import "@ionic/core/css/ionic.bundle.css";
import { defineCustomElements } from "@ionic/core/loader/index.js";
import { addIcons } from "ionicons";
import * as appIcons from "./ui/icons.js";
import { createAuthActions } from "./actions/auth-actions.js";
import { createControlActions } from "./actions/control-actions.js";
import { createSettingsActions } from "./actions/settings-actions.js";
import { toastDanger, initNotifications } from "./notifications.js";
import { RadioPadAuth } from "./services/auth.js";
import { RadioListen } from "./services/radio-listen.js";
import { RadioControl } from "./services/radio-control.js";
import { RadioPadPreferences } from "./services/preferences.js";

// Import our Lit Web Components to register them
import "./ui/radio-auth.js";
import "./ui/radio-player-tab.js";
import "./ui/radio-settings.js";

addIcons(appIcons);
defineCustomElements(window);

async function bootstrap() {
  const prefs = new RadioPadPreferences();
  const auth = new RadioPadAuth();
  const listen = new RadioListen();
  const control = new RadioControl();

  const controlActions = createControlActions({ control, listen });
  const settingsActions = createSettingsActions({
    prefs,
    auth,
    onPlayerSelected: (player) => controlActions.selectPlayer(player),
    onPresetSelected: (presetId) => controlActions.selectPreset(presetId),
  });
  const authActions = createAuthActions({
    auth,
    refreshAccountsForCurrentRegistry:
      settingsActions.refreshAccountsForCurrentRegistry,
  });

  // Attach global event listeners from the Lit web components
  document.addEventListener("auth-signin", () => authActions.signIn());
  document.addEventListener("auth-signout", () => authActions.signOut());
  document.addEventListener("auth-copytoken", () => authActions.copyToken());

  document.addEventListener("station-click", (e) =>
    controlActions.clickStation(e.detail.tabName, e.detail.stationName),
  );
  document.addEventListener("station-stop", (e) =>
    controlActions.stopStation(e.detail.tabName),
  );

  document.addEventListener("settings-edited", () =>
    settingsActions.markDirty(),
  );
  document.addEventListener("settings-save", (e) =>
    settingsActions.save(e.detail),
  );

  initNotifications();

  const wasOauthCallback = await settingsActions.initialize();
  if (wasOauthCallback) {
    const settingsTab = document.querySelector(
      'ion-tab-button[tab="settings"]',
    );
    if (settingsTab) setTimeout(() => settingsTab.click(), 100);
  }
}

void bootstrap().catch((error) => {
  console.error("Failed bootstrapping remote control app", error);
  toastDanger("⚠️ Failed starting remote control.", error);
});
