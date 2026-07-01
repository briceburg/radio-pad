import { beforeEach, describe, expect, it, vi } from "vitest";
import { Preferences } from "@capacitor/preferences";
import { RadioPadPreferences } from "../../src/js/services/preferences.js";

vi.mock("@capacitor/preferences", () => ({
  Preferences: {
    get: vi.fn(),
    set: vi.fn(),
    remove: vi.fn(),
  },
}));

function createPlayerPreferences() {
  return new RadioPadPreferences({
    playerId: {
      type: "select",
      label: "Player",
      options: [{ value: "living-room", label: "Living Room" }],
    },
  });
}

describe("RadioPadPreferences", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Preferences.get.mockResolvedValue({ value: null });
    Preferences.set.mockResolvedValue();
    Preferences.remove.mockResolvedValue();
  });

  it("initializes and persists default values", async () => {
    const prefs = new RadioPadPreferences({
      registryUrl: {
        type: "text",
        default: "https://registry.example/api/",
      },
    });

    await prefs.init();

    expect(prefs.getSnapshot().registryUrl.value).toBe(
      "https://registry.example/api/",
    );
    expect(Preferences.set).toHaveBeenCalledWith({
      key: "registryUrl",
      value: "https://registry.example/api/",
    });
  });

  it.each([
    ["adds an HTTPS scheme", "localhost:3000", "https://localhost:3000/"],
    ["accepts same-origin paths", "/api", "/api/"],
    [
      "preserves query and hash",
      "https://example.com/api?x=1#frag",
      "https://example.com/api/?x=1#frag",
    ],
  ])("normalizes Registry URLs: %s", (_case, value, expected) => {
    const result = new RadioPadPreferences().prepare("registryUrl", value);

    expect(result).toMatchObject({ status: "applied", value: expected });
  });

  it("rejects invalid Registry URLs", () => {
    const result = new RadioPadPreferences().prepare(
      "registryUrl",
      "http://:3000",
    );

    expect(result).toMatchObject({
      status: "invalid",
      reason: "validation_failed",
    });
  });

  it("does not partially persist an invalid settings batch", async () => {
    const prefs = new RadioPadPreferences();

    const result = await prefs.setMany({
      accountId: "pinecrest",
      registryUrl: "http://:3000",
    });

    expect(result.status).toBe("invalid");
    expect(Preferences.set).not.toHaveBeenCalled();
  });

  it.each([
    ["first", "kitchen", "set"],
    ["preserve", "living-room", null],
    ["clear", null, "remove"],
  ])(
    "%s reconciles an invalid option selection",
    async (invalidSelection, expected, storageAction) => {
      const prefs = createPlayerPreferences();
      await prefs.set("playerId", "living-room");
      vi.clearAllMocks();

      await prefs.setOptions(
        "playerId",
        [{ value: "kitchen", label: "Kitchen" }],
        { invalidSelection },
      );

      expect(await prefs.get("playerId")).toBe(expected);
      if (storageAction === "set") {
        expect(Preferences.set).toHaveBeenCalledWith({
          key: "playerId",
          value: "kitchen",
        });
      } else if (storageAction === "remove") {
        expect(Preferences.remove).toHaveBeenCalledWith({ key: "playerId" });
      } else {
        expect(Preferences.set).not.toHaveBeenCalled();
        expect(Preferences.remove).not.toHaveBeenCalled();
      }
    },
  );
});
