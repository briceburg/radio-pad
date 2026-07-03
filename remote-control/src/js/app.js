// SPDX-FileCopyrightText: 2025 Brice Burgess (github.com/briceburg)
// SPDX-License-Identifier: AGPL-3.0-or-later

import "@ionic/core/css/ionic.bundle.css";
import { defineCustomElements } from "@ionic/core/loader/index.js";
import { addIcons } from "ionicons";
import * as appIcons from "./ui/icons.js";
import { createAuthActions } from "./actions/auth-actions.js";
import { createControlActions } from "./actions/control-actions.js";
import { createSettingsActions } from "./actions/settings-actions.js";
import { toastDanger, initNotifications } from "./notifications.js";
import { RadioPadAuth } from "./services/auth.js";
import { LocalPlayback } from "./services/local-playback.js";
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
  const localPlayback = new LocalPlayback();
  const control = new RadioControl();

  const controlActions = createControlActions({ localPlayback, control });
  const settingsActions = createSettingsActions({
    prefs,
    auth,
    onPlayerSelected: controlActions.selectPlayer,
    onRadioDialSelected: controlActions.selectRadioDial,
    onRegistryStatus: controlActions.setRegistryStatus,
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
    controlActions.clickStation(e.detail.tabName, e.detail.callSign),
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
    await document.querySelector("ion-tabs")?.select("settings");
  }
}

void bootstrap().catch((error) => {
  console.error("Failed bootstrapping remote control app", error);
  toastDanger("Couldn’t start remote control.", error);
});
