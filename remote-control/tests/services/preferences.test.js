import { describe, it, expect, vi } from "vitest";
import { RadioPadPreferences } from "../../src/js/services/preferences.js";

// Mock Capacitor Preferences
vi.mock("@capacitor/preferences", () => ({
  Preferences: {
    get: vi.fn().mockResolvedValue({ value: null }),
    set: vi.fn().mockResolvedValue(),
    remove: vi.fn().mockResolvedValue()
  }
}));

// Mock import.meta.env
vi.stubEnv('VITE_REGISTRY_URL', 'https://registry.radiopad.dev/api/');

describe("RadioPadPreferences", () => {
  it("initializes with default URL preference", async () => {
    const prefs = new RadioPadPreferences();
    await prefs.init();
    
    const snapshot = prefs.getSnapshot();
    expect(snapshot.registryUrl.value).toContain("registry.radiopad.dev");
  });

  it("normalizes preferences correctly", () => {
    const prefs = new RadioPadPreferences();
    const result = prefs.prepare("registryUrl", "localhost:3000");
    
    // Automatically Prepends https if missing
    expect(result.status).toBe("applied");
    expect(result.value).toBe("https://localhost:3000/");
  });

  it("accepts same-origin relative registry paths", () => {
    const prefs = new RadioPadPreferences();
    const result = prefs.prepare("registryUrl", "/api");

    expect(result.status).toBe("applied");
    expect(result.value).toBe("/api/");
  });

  it("preserves query and hash while normalizing absolute URLs", () => {
    const prefs = new RadioPadPreferences();
    const result = prefs.prepare("registryUrl", "https://example.com/api?x=1#frag");

    expect(result.status).toBe("applied");
    expect(result.value).toBe("https://example.com/api/?x=1#frag");
  });

  it("fails validation for invalid preferences", () => {
    const prefs = new RadioPadPreferences();
    // The previous test failed because "https://not_a_valid_url_at_all" is legally parsed by `new URL()` as having a hostname! 
    // Let's use an actually un-parseable URL string or check normalization behavior.
    const result = prefs.prepare("registryUrl", "http://:3000"); // Missing hostname causes URL parser to throw
    
    expect(result.status).toBe("invalid");
    expect(result.reason).toBe("validation_failed");
  });
});
