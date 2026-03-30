import { describe, it, expect, vi, beforeEach } from "vitest";
import { RadioPadAuth } from "../../src/js/services/auth.js";

vi.mock("@capacitor/core", () => ({
  Capacitor: {
    getPlatform: vi.fn().mockReturnValue("web")
  }
}));

vi.mock("@capacitor/preferences", () => ({
  Preferences: {
    get: vi.fn().mockResolvedValue({ value: null }),
    set: vi.fn().mockResolvedValue(),
    remove: vi.fn().mockResolvedValue()
  }
}));

vi.mock("@capawesome/capacitor-google-sign-in", () => ({
  GoogleSignIn: {
    initialize: vi.fn().mockResolvedValue(),
    signIn: vi.fn().mockResolvedValue({
      idToken: "mock_token",
      email: "test@example.com",
      displayName: "Test User"
    }),
    signOut: vi.fn().mockResolvedValue()
  }
}));

describe("RadioPadAuth", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_GOOGLE_CLIENT_ID", "mock_client_id");
  });

  it("initializes as enabled when client ID is provided", async () => {
    const auth = new RadioPadAuth();
    await auth.init("http://localhost/");
    
    expect(auth.enabled).toBe(true);
    expect(auth.signedIn).toBe(false);
    expect(auth.getState().reason).toBeNull();
  });

  it("handles empty client ID gracefully", async () => {
    vi.stubEnv("VITE_GOOGLE_CLIENT_ID", "");
    const auth = new RadioPadAuth();
    await auth.init("http://localhost/");
    
    expect(auth.enabled).toBe(false);
    expect(auth.getState().reason).toBe("not_configured");
  });

  it("correctly identifies sign-in state callbacks", async () => {
    const auth = new RadioPadAuth();
    
    // We shouldn't actually call handleRedirectCallback because we mocked it simply above,
    // but we can ensure the logic flow works by throwing a controlled error that it catches
    // since we didn't mock handleRedirectCallback.
    const errorSpy = vi.fn();
    auth.addEventListener('error', errorSpy);
    
    await auth.init("http://localhost/?state=xyz&code=abc");
    
    expect(errorSpy).toHaveBeenCalled();
  });
});
