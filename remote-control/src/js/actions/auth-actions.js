// SPDX-FileCopyrightText: 2025 Brice Burgess (github.com/briceburg)
// SPDX-License-Identifier: AGPL-3.0-or-later

import { authStore, patchStore } from "../store.js";
import { toastDanger, toastSuccess, toastWarning } from "../notifications.js";

export function createAuthActions({ auth, refreshAccountsForCurrentRegistry }) {
  const initialState = auth.getState();
  let subject = initialState.signedIn ? initialState.subject : null;
  auth.addEventListener("statechange", (event) => {
    patchStore(authStore, event.detail);
    const nextSubject = event.detail.signedIn ? event.detail.subject : null;
    if (nextSubject !== subject) {
      subject = nextSubject;
      void refreshAccountsForCurrentRegistry("auth_accounts");
    }
  });
  auth.addEventListener("error", (event) => {
    const { summary, error } = event.detail;
    toastDanger(summary, error);
  });

  patchStore(authStore, initialState);

  async function safeAction(fn, errorMsg) {
    try {
      return await fn();
    } catch (error) {
      toastDanger(errorMsg, error);
    }
  }

  return {
    signIn: () => safeAction(() => auth.signIn(), "Couldn’t start sign-in."),

    async signOut() {
      await safeAction(async () => {
        await auth.signOut();
        toastSuccess("Signed out.");
      }, "Couldn’t sign out.");
    },

    async copyToken() {
      const token = auth.getRegistryBearerToken();
      if (!token) {
        toastWarning("No API test token is available.");
        return;
      }
      await safeAction(async () => {
        await navigator.clipboard.writeText(token);
        toastSuccess("Copied API test token.");
      }, "Couldn’t copy API test token.");
    },
  };
}
