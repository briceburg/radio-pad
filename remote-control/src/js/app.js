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
import { Capacitor } from "@capacitor/core";
import { defineCustomElements } from "@ionic/core/loader/index.js";
import { addIcons } from "ionicons";
import * as appIcons from "./ui/icons.js";
import { createAuthActions } from "./actions/auth-actions.js";
import { createControlActions } from "./actions/control-actions.js";
import { createSettingsActions } from "./actions/settings-actions.js";
import { toastDanger } from "./notifications.js";
import { RadioPadAuth } from "./services/auth.js";
import { RadioListen } from "./services/radio-listen.js";
import { RadioControl } from "./services/radio-control.js";
import { RadioPadPreferences } from "./services/preferences.js";
import {
  authStore,
  controlStore,
  listenStore,
  preferencesStore,
  settingsUiStore,
  toastStore,
} from "./store.js";
import { RadioPadUI } from "./ui/index.js";

addIcons(appIcons);
defineCustomElements(window);

function bindStore(store, render) {
  render(store.get());
  return store.subscribe(render);
}

async function bootstrap() {
  const copyTokenAvailable = !Capacitor.isNativePlatform();
  const prefs = new RadioPadPreferences();
  const auth = new RadioPadAuth();
  const listen = new RadioListen();
  const control = new RadioControl();
  const ui = new RadioPadUI({ copyTokenAvailable });

  await prefs.init();
  await auth.init();

  const controlActions = createControlActions({
    control,
    listen,
  });
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

  ui.init({
    onSettingsEdited: () => settingsActions.markDirty(),
    onSaveSettings: (settingsMap) => settingsActions.save(settingsMap),
    onSignIn: () => authActions.signIn(),
    onSignOut: () => authActions.signOut(),
    onCopyToken: () => authActions.copyToken(),
    onClickStation: (...args) => controlActions.clickStation(...args),
    onStopStation: (tabName) => controlActions.stopStation(tabName),
  });

  preferencesStore.set({ definitions: prefs.getSnapshot() });

  for (const [store, render] of [
    [preferencesStore, ({ definitions }) => ui.renderPreferences(definitions)],
    [authStore, (state) => ui.updateAuthState(state)],
    [settingsUiStore, ({ saveState }) => ui.setSettingsSaveState(saveState)],
    [controlStore, (state) => ui.renderTabState("control", state)],
    [listenStore, (state) => ui.renderTabState("listen", state)],
    [toastStore, (notification) => ui.presentNotification(notification)],
  ]) {
    bindStore(store, render);
  }

  await settingsActions.sync();
}

void bootstrap().catch((error) => {
  console.error("Failed bootstrapping remote control app", error);
  toastDanger("⚠️ Failed starting remote control.", error);
});
