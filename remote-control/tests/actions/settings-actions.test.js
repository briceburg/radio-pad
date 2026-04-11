import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../src/js/services/registry-discovery.js", () => ({
  discoverAccounts: vi.fn(),
  discoverPlayer: vi.fn(),
  discoverPlayers: vi.fn(),
  discoverPresets: vi.fn(),
}));

vi.mock("../../src/js/notifications.js", () => ({
  dismissRegistryUnavailableToast: vi.fn(),
  toastDanger: vi.fn(),
  toastRegistryUnavailable: vi.fn(),
}));

import { createSettingsActions } from "../../src/js/actions/settings-actions.js";
import { preferencesStore, registryStore } from "../../src/js/store.js";
import {
  discoverAccounts,
  discoverPlayer,
  discoverPlayers,
  discoverPresets,
} from "../../src/js/services/registry-discovery.js";

describe("settings-actions", () => {
  beforeEach(() => {
    preferencesStore.set({ definitions: {} });
    registryStore.set({
      phase: "idle",
      errorText: "",
      retryAttempt: 0,
      retryDelayMs: 0,
    });
    vi.clearAllMocks();
  });

  it("reconnects the selected player after registry recovery without resetting control state", async () => {
    const player = {
      id: "living-room",
      name: "Living Room",
      stations_url: "http://localhost:3000/api/presets/briceburg",
      switchboard_url: "ws://localhost:3000/switchboard/briceburg/living-room",
    };
    const prefs = {
      get: vi.fn(async (key) => {
        if (key === "registryUrl") return "/api/";
        if (key === "accountId") return "briceburg";
        if (key === "playerId") return "living-room";
        if (key === "presetId")
          return "http://localhost:3000/api/presets/briceburg";
        return null;
      }),
      setOptions: vi.fn(async () => {}),
      getSnapshot: vi.fn(() => ({})),
      init: vi.fn(async () => {}),
    };
    const auth = {
      signedIn: true,
      init: vi.fn(async () => false),
      addEventListener: vi.fn(),
      getState: vi.fn(() => ({})),
    };

    discoverAccounts.mockResolvedValue([
      { value: "briceburg", label: "Briceburg" },
    ]);
    discoverPlayers.mockResolvedValue([
      { value: "living-room", label: "Living Room" },
    ]);
    discoverPresets.mockResolvedValue([
      {
        value: "http://localhost:3000/api/presets/briceburg",
        label: "Casa Briceburg",
      },
    ]);
    discoverPlayer.mockResolvedValue(player);

    const onPlayerSelected = vi.fn(async () => {});
    const onPresetSelected = vi.fn(async () => {});
    const actions = createSettingsActions({
      prefs,
      auth,
      onPlayerSelected,
      onPresetSelected,
    });

    await actions.sync();
    expect(onPlayerSelected).toHaveBeenLastCalledWith(player);

    registryStore.set({
      phase: "retrying",
      errorText: "Registry unavailable",
      retryAttempt: 2,
      retryDelayMs: 1000,
    });

    await actions.sync();

    expect(onPlayerSelected).toHaveBeenLastCalledWith(player, {
      reconnectOnly: true,
    });
  });

  it("sets phase to ready after successful sync", async () => {
    const prefs = {
      get: vi.fn(async (key) => {
        if (key === "registryUrl") return "/api/";
        return null;
      }),
      setOptions: vi.fn(async () => {}),
      getSnapshot: vi.fn(() => ({})),
    };
    const auth = { signedIn: false };

    discoverAccounts.mockResolvedValue([]);
    discoverPlayers.mockResolvedValue([]);
    discoverPresets.mockResolvedValue([]);

    const actions = createSettingsActions({
      prefs,
      auth,
      onPlayerSelected: vi.fn(async () => {}),
      onPresetSelected: vi.fn(async () => {}),
    });

    await actions.sync();
    expect(registryStore.get().phase).toBe("ready");
  });

  it("schedules retry on sync failure", async () => {
    vi.useFakeTimers();

    const prefs = {
      get: vi.fn(async () => "/api/"),
      setOptions: vi.fn(async () => {}),
      getSnapshot: vi.fn(() => ({})),
    };
    const auth = { signedIn: false };

    discoverAccounts.mockRejectedValue(new Error("Network error"));

    const actions = createSettingsActions({
      prefs,
      auth,
      onPlayerSelected: vi.fn(async () => {}),
      onPresetSelected: vi.fn(async () => {}),
    });

    await actions.sync();
    expect(registryStore.get().phase).toBe("retrying");
    expect(registryStore.get().retryAttempt).toBe(1);

    vi.useRealTimers();
  });
});
