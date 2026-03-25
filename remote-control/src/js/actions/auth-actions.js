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

import { authStore, patchStore } from "../store.js";
import { toastDanger, toastSuccess, toastWarning } from "../notifications.js";

export function createAuthActions({ auth, refreshAccountsForCurrentRegistry }) {
  auth.addEventListener("statechange", async (event) => {
    patchStore(authStore, event.detail);
    await refreshAccountsForCurrentRegistry("auth_accounts");
  });
  auth.addEventListener("error", async (event) => {
    const { summary, error } = event.detail;
    toastDanger(summary, error);
  });

  patchStore(authStore, auth.getState());

  return {
    async signIn() {
      try {
        await auth.signIn();
      } catch (error) {
        toastDanger("⚠️ Failed starting sign-in.", error);
      }
    },

    async signOut() {
      try {
        await auth.signOut();
        toastSuccess("Signed out.");
      } catch (error) {
        toastDanger("⚠️ Failed signing out.", error);
      }
    },

    async copyToken() {
      const token = auth.getRegistryBearerToken();
      if (!token) {
        toastWarning("No API test token is available.");
        return;
      }

      try {
        await navigator.clipboard.writeText(token);
        toastSuccess("Copied API test token.");
      } catch (error) {
        toastDanger("⚠️ Failed copying API test token.", error);
      }
    },
  };
}
