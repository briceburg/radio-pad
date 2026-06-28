import { beforeEach, describe, expect, it, vi } from "vitest";
import { createSettingsActions } from "../../src/js/actions/settings-actions.js";
import {
  discoverAccounts,
  discoverPlayer,
  discoverPlayers,
  discoverRadioDials,
  radioDialUrl,
} from "../../src/js/services/registry-discovery.js";

vi.mock("../../src/js/services/registry-discovery.js", () => ({
  discoverAccounts: vi.fn(),
  discoverPlayer: vi.fn(),
  discoverPlayers: vi.fn(),
  discoverRadioDials: vi.fn(),
  radioDialUrl: vi.fn(
    (key) => `https://registry.example/api/radio-dials/${key}`,
  ),
}));

const PLAYER = {
  id: "living-room",
  name: "Living Room",
  configured_radio_dial_url: "https://example.test/radio-dial.json",
  switchboard_url: "wss://example.test/switchboard/briceburg/living-room",
};

function createPrefs(values = {}) {
  const stored = {
    registryUrl: "https://registry.example/api/",
    accountId: "briceburg",
    playerId: "living-room",
    radioDial: null,
    ...values,
  };
  const options = {
    accountId: [],
    playerId: [],
    radioDial: [],
  };

  return {
    get: vi.fn(async (key) => stored[key] ?? null),
    getSnapshot: vi.fn(() => ({
      accountId: { options: options.accountId },
      playerId: { options: options.playerId },
      radioDial: { options: options.radioDial },
      registryUrl: { value: stored.registryUrl },
    })),
    setOptions: vi.fn(async (key, nextOptions) => {
      options[key] = nextOptions;
      return { value: stored[key] ?? null, selection: null };
    }),
  };
}

function createActions(prefs) {
  const onPlayerSelected = vi.fn(async () => {});
  const onRadioDialSelected = vi.fn(async () => {});
  const onRegistryStatus = vi.fn();

  return {
    actions: createSettingsActions({
      prefs,
      auth: { signedIn: true },
      onPlayerSelected,
      onRadioDialSelected,
      onRegistryStatus,
    }),
    onPlayerSelected,
    onRadioDialSelected,
    onRegistryStatus,
  };
}

describe("settings-actions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    discoverAccounts.mockResolvedValue([
      { value: "briceburg", label: "Briceburg" },
    ]);
    discoverPlayers.mockResolvedValue([
      { value: "living-room", label: "Living Room" },
    ]);
    discoverRadioDials.mockResolvedValue([]);
    discoverPlayer.mockResolvedValue(PLAYER);
  });

  it("keeps the selected player when a later registry sync fails", async () => {
    const prefs = createPrefs();
    const { actions, onPlayerSelected, onRegistryStatus } =
      createActions(prefs);

    await actions.sync();
    expect(onPlayerSelected).toHaveBeenCalledWith(PLAYER);
    expect(onRegistryStatus).toHaveBeenLastCalledWith({ level: "ok" });

    onPlayerSelected.mockClear();
    onRegistryStatus.mockClear();
    prefs.setOptions.mockClear();
    discoverPlayer.mockClear();
    discoverAccounts.mockRejectedValue(new Error("Failed to fetch"));
    discoverPlayers.mockRejectedValue(new Error("Failed to fetch"));
    discoverRadioDials.mockRejectedValue(new Error("Failed to fetch"));

    await actions.sync();

    expect(onPlayerSelected).not.toHaveBeenCalled();
    expect(discoverPlayer).not.toHaveBeenCalled();
    expect(prefs.setOptions).not.toHaveBeenCalledWith("playerId", []);
    expect(onRegistryStatus).toHaveBeenLastCalledWith(
      expect.objectContaining({
        level: "warning",
        summary: "Registry unavailable. Using last known selections.",
      }),
    );
  });

  it("reloads the selected RadioDial on each sync", async () => {
    const prefs = createPrefs({ radioDial: "community/briceburg" });
    discoverRadioDials.mockResolvedValue([
      { value: "community/briceburg", label: "Casa Briceburg" },
    ]);
    const { actions, onRadioDialSelected } = createActions(prefs);

    await actions.sync();
    await actions.sync();

    expect(radioDialUrl).toHaveBeenCalledWith(
      "community/briceburg",
      "https://registry.example/api/",
    );
    expect(onRadioDialSelected).toHaveBeenCalledTimes(2);
  });
});
