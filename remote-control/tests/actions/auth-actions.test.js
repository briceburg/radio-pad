import { beforeEach, describe, expect, it, vi } from "vitest";
import { createAuthActions } from "../../src/js/actions/auth-actions.js";
import { authStore, toastStore } from "../../src/js/store.js";

function createAuth(state = {}) {
  const auth = new EventTarget();
  auth.state = {
    enabled: true,
    reason: null,
    signedIn: false,
    registryBearerToken: null,
    ...state,
  };
  auth.getState = vi.fn(() => auth.state);
  auth.getRegistryBearerToken = vi.fn(() => auth.state.registryBearerToken);
  auth.signIn = vi.fn();
  auth.signOut = vi.fn();
  return auth;
}

describe("auth-actions", () => {
  beforeEach(() => {
    authStore.set({});
    toastStore.set({ id: 0 });
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: vi.fn() },
    });
  });

  it("synchronizes auth state and refreshes registry choices", async () => {
    const auth = createAuth();
    const refreshAccountsForCurrentRegistry = vi.fn();
    createAuthActions({ auth, refreshAccountsForCurrentRegistry });
    const nextState = {
      signedIn: true,
      name: "Test User",
      registryBearerToken: "token",
    };

    auth.dispatchEvent(new CustomEvent("statechange", { detail: nextState }));

    await vi.waitFor(() =>
      expect(refreshAccountsForCurrentRegistry).toHaveBeenCalledWith(
        "auth_accounts",
      ),
    );
    expect(authStore.get()).toMatchObject(nextState);
  });

  it("copies available tokens and explains when none is available", async () => {
    const auth = createAuth();
    const actions = createAuthActions({
      auth,
      refreshAccountsForCurrentRegistry: vi.fn(),
    });

    await actions.copyToken();
    expect(toastStore.get()).toMatchObject({
      summary: "No API test token is available.",
      severity: "warning",
    });

    auth.state.registryBearerToken = "token";
    await actions.copyToken();
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith("token");
    expect(toastStore.get()).toMatchObject({
      summary: "Copied API test token.",
      severity: "success",
    });
  });

  it("routes auth failures through the shared danger notification", async () => {
    const auth = createAuth();
    const error = new Error("denied");
    auth.signIn.mockRejectedValue(error);
    const actions = createAuthActions({
      auth,
      refreshAccountsForCurrentRegistry: vi.fn(),
    });

    await actions.signIn();

    expect(toastStore.get()).toMatchObject({
      summary: "Couldn’t start sign-in.",
      error,
      severity: "danger",
    });
  });
});
