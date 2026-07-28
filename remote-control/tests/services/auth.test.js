import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Capacitor } from "@capacitor/core";
import { Preferences } from "@capacitor/preferences";
import { GoogleSignIn } from "@capawesome/capacitor-google-sign-in";
import { RadioPadAuth } from "../../src/js/services/auth.js";

vi.mock("@capacitor/core", () => ({
  Capacitor: { getPlatform: vi.fn() },
}));

vi.mock("@capawesome/capacitor-google-sign-in", () => ({
  GoogleSignIn: {
    initialize: vi.fn(),
    handleRedirectCallback: vi.fn(),
    signIn: vi.fn(),
    signOut: vi.fn(),
  },
}));

vi.mock("@capacitor/preferences", () => ({
  Preferences: { remove: vi.fn() },
}));

const PROFILE = {
  idToken: "google-token",
  userId: "user-1",
  email: "test@example.com",
  displayName: "Test User",
};

function registrySession(accessToken = "access-token") {
  return {
    access_token: accessToken,
    token_type: "bearer",
    expires_at: Math.floor(Date.now() / 1000) + 3600,
    identity: {
      subject: "user-1",
      email: "test@example.com",
      name: "Test User",
    },
  };
}

function response(body = null, status = 200) {
  return new Response(body === null ? null : JSON.stringify(body), {
    status,
    headers: body === null ? {} : { "Content-Type": "application/json" },
  });
}

describe("RadioPadAuth", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-27T12:00:00Z"));
    vi.stubEnv("VITE_GOOGLE_CLIENT_ID", "mock-client-id");
    vi.stubEnv("VITE_GOOGLE_REDIRECT_URL", "");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(null, 401)));
    Capacitor.getPlatform.mockReturnValue("web");
    Preferences.remove.mockResolvedValue();
    GoogleSignIn.initialize.mockResolvedValue();
    GoogleSignIn.handleRedirectCallback.mockResolvedValue(PROFILE);
    GoogleSignIn.signOut.mockResolvedValue();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("initializes Google and attempts to restore the registry session", async () => {
    const auth = new RadioPadAuth();

    await expect(auth.init("/api/", "http://localhost/")).resolves.toBe(false);

    expect(GoogleSignIn.initialize).toHaveBeenCalledWith({
      clientId: "mock-client-id",
      redirectUrl: "http://localhost:3000/",
    });
    expect(Preferences.remove).toHaveBeenCalledWith({
      key: "radio-pad.google-sign-in.user",
    });
    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:3000/api/auth/session/refresh",
      {
        method: "POST",
        credentials: "include",
        headers: { "RadioPad-Session": "refresh" },
      },
    );
    expect(auth.getState()).toMatchObject({
      enabled: true,
      signedIn: false,
      reason: null,
    });
  });

  it("does not initialize auth when Google is not configured", async () => {
    vi.stubEnv("VITE_GOOGLE_CLIENT_ID", "");
    const auth = new RadioPadAuth();

    await auth.init("/api/");

    expect(GoogleSignIn.initialize).not.toHaveBeenCalled();
    expect(fetch).not.toHaveBeenCalled();
    expect(auth.getState()).toMatchObject({
      enabled: false,
      signedIn: false,
      reason: "not_configured",
    });
  });

  it("exchanges a successful web callback without persisting the Google token", async () => {
    fetch.mockResolvedValueOnce(response(registrySession()));
    const auth = new RadioPadAuth();

    await expect(
      auth.init("/api/", "http://localhost/#state=xyz&id_token=abc"),
    ).resolves.toBe(true);

    expect(GoogleSignIn.handleRedirectCallback).toHaveBeenCalledOnce();
    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:3000/api/auth/session",
      {
        method: "POST",
        credentials: "include",
        headers: { Authorization: "Bearer google-token" },
      },
    );
    expect(auth.getState()).toMatchObject({
      signedIn: true,
      name: "Test User",
      email: "test@example.com",
      subject: "user-1",
      registryBearerToken: "access-token",
    });
  });

  it("refreshes the short-lived access token while the app remains active", async () => {
    fetch
      .mockResolvedValueOnce(response(registrySession("first-token")))
      .mockResolvedValueOnce(response(registrySession("second-token")));
    const auth = new RadioPadAuth();
    await auth.init("/api/");

    await vi.advanceTimersByTimeAsync(59 * 60 * 1000);

    expect(auth.getRegistryBearerToken()).toBe("second-token");
    expect(fetch).toHaveBeenLastCalledWith(
      "http://localhost:3000/api/auth/session/refresh",
      {
        method: "POST",
        credentials: "include",
        headers: { "RadioPad-Session": "refresh" },
      },
    );
  });

  it("clears the registry and Google sessions on sign-out", async () => {
    fetch
      .mockResolvedValueOnce(response(registrySession()))
      .mockResolvedValueOnce(response(null, 204));
    const auth = new RadioPadAuth();
    await auth.init("/api/");

    await auth.signOut();

    expect(fetch).toHaveBeenLastCalledWith(
      "http://localhost:3000/api/auth/session",
      { method: "DELETE", credentials: "include" },
    );
    expect(GoogleSignIn.signOut).toHaveBeenCalledOnce();
    expect(auth.signedIn).toBe(false);
  });

  it("reports initialization failures without enabling auth", async () => {
    const error = new Error("bad client");
    GoogleSignIn.initialize.mockRejectedValue(error);
    const auth = new RadioPadAuth();
    const onError = vi.fn();
    auth.addEventListener("error", onError);

    await auth.init("/api/");

    expect(auth.getState()).toMatchObject({
      enabled: false,
      reason: "init_failed",
    });
    expect(onError).toHaveBeenCalledWith(
      expect.objectContaining({
        detail: { summary: "Sign-in unavailable.", error },
      }),
    );
  });
});
