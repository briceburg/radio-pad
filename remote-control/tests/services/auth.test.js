import { beforeEach, describe, expect, it, vi } from "vitest";
import { Capacitor } from "@capacitor/core";
import { Preferences } from "@capacitor/preferences";
import { GoogleSignIn } from "@capawesome/capacitor-google-sign-in";
import { RadioPadAuth } from "../../src/js/services/auth.js";

vi.mock("@capacitor/core", () => ({
  Capacitor: { getPlatform: vi.fn() },
}));

vi.mock("@capacitor/preferences", () => ({
  Preferences: {
    get: vi.fn(),
    set: vi.fn(),
    remove: vi.fn(),
  },
}));

vi.mock("@capawesome/capacitor-google-sign-in", () => ({
  GoogleSignIn: {
    initialize: vi.fn(),
    handleRedirectCallback: vi.fn(),
    signIn: vi.fn(),
    signOut: vi.fn(),
  },
}));

const PROFILE = {
  idToken: "mock-token",
  userId: "user-1",
  email: "test@example.com",
  displayName: "Test User",
};

describe("RadioPadAuth", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubEnv("VITE_GOOGLE_CLIENT_ID", "mock-client-id");
    vi.stubEnv("VITE_GOOGLE_REDIRECT_URL", "");
    Capacitor.getPlatform.mockReturnValue("web");
    Preferences.get.mockResolvedValue({ value: null });
    Preferences.set.mockResolvedValue();
    Preferences.remove.mockResolvedValue();
    GoogleSignIn.initialize.mockResolvedValue();
    GoogleSignIn.handleRedirectCallback.mockResolvedValue(PROFILE);
  });

  it("initializes configured web auth", async () => {
    const auth = new RadioPadAuth();

    await expect(auth.init("http://localhost/")).resolves.toBe(false);

    expect(GoogleSignIn.initialize).toHaveBeenCalledWith({
      clientId: "mock-client-id",
      redirectUrl: "http://localhost:3000/",
    });
    expect(auth.getState()).toMatchObject({
      enabled: true,
      signedIn: false,
      reason: null,
    });
  });

  it("does not initialize Google when auth is not configured", async () => {
    vi.stubEnv("VITE_GOOGLE_CLIENT_ID", "");
    const auth = new RadioPadAuth();

    await auth.init();

    expect(GoogleSignIn.initialize).not.toHaveBeenCalled();
    expect(auth.getState()).toMatchObject({
      enabled: false,
      signedIn: false,
      reason: "not_configured",
    });
  });

  it("stores and exposes a successful web callback profile", async () => {
    const auth = new RadioPadAuth();

    await expect(
      auth.init("http://localhost/#state=xyz&id_token=abc"),
    ).resolves.toBe(true);

    expect(GoogleSignIn.handleRedirectCallback).toHaveBeenCalledOnce();
    expect(auth.getState()).toMatchObject({
      signedIn: true,
      name: "Test User",
      email: "test@example.com",
      subject: "user-1",
      registryBearerToken: "mock-token",
    });
    expect(JSON.parse(Preferences.set.mock.calls[0][0].value)).toEqual({
      idToken: "mock-token",
      subject: "user-1",
      email: "test@example.com",
      name: "Test User",
    });
  });

  it("reports initialization failures without enabling auth", async () => {
    const error = new Error("bad client");
    GoogleSignIn.initialize.mockRejectedValue(error);
    const auth = new RadioPadAuth();
    const onError = vi.fn();
    auth.addEventListener("error", onError);

    await auth.init();

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
