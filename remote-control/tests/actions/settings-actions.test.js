import { beforeEach, describe, expect, it, vi } from "vitest";
import { createSettingsActions } from "../../src/js/actions/settings-actions.js";
import {
  discoverAccounts,
  discoverPlayer,
  discoverPlayers,
  discoverPresets,
} from "../../src/js/services/registry-discovery.js";

vi.mock("../../src/js/services/registry-discovery.js", () => ({
  discoverAccounts: vi.fn(),
  discoverPlayer: vi.fn(),
  discoverPlayers: vi.fn(),
  discoverPresets: vi.fn(),
}));

const PLAYER = {
  id: "living-room",
  name: "Living Room",
  stations_url: "https://example.test/stations.json",
  switchboard_url: "wss://example.test/switchboard/briceburg/living-room",
};

function createPrefs(values = {}) {
  const stored = {
    registryUrl: "https://registry.example/api/",
    accountId: "briceburg",
    playerId: "living-room",
    presetId: null,
    ...values,
  };
  const options = {
    accountId: [],
    playerId: [],
    presetId: [],
  };

  return {
    get: vi.fn(async (key) => stored[key] ?? null),
    getSnapshot: vi.fn(() => ({
      accountId: { options: options.accountId },
      playerId: { options: options.playerId },
      presetId: { options: options.presetId },
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
  const onPresetSelected = vi.fn(async () => {});
  const onRegistryStatus = vi.fn();

  return {
    actions: createSettingsActions({
      prefs,
      auth: { signedIn: true },
      onPlayerSelected,
      onPresetSelected,
      onRegistryStatus,
    }),
    onPlayerSelected,
    onPresetSelected,
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
    discoverPresets.mockResolvedValue([]);
    discoverPlayer.mockResolvedValue(PLAYER);
  });

  it("keeps the selected player when a later registry sync fails", async () => {
    const prefs = createPrefs();
    const { actions, onPlayerSelected, onRegistryStatus } =
      createActions(prefs);

    await actions.sync();
    expect(onPlayerSelected).toHaveBeenCalledWith(PLAYER);
    expect(onRegistryStatus).toHaveBeenLastCalledWith("ok");

    onPlayerSelected.mockClear();
    onRegistryStatus.mockClear();
    prefs.setOptions.mockClear();
    discoverPlayer.mockClear();
    discoverAccounts.mockRejectedValue(new Error("Failed to fetch"));
    discoverPlayers.mockRejectedValue(new Error("Failed to fetch"));
    discoverPresets.mockRejectedValue(new Error("Failed to fetch"));

    await actions.sync();

    expect(onPlayerSelected).not.toHaveBeenCalled();
    expect(discoverPlayer).not.toHaveBeenCalled();
    expect(prefs.setOptions).not.toHaveBeenCalledWith("playerId", []);
    expect(onRegistryStatus).toHaveBeenLastCalledWith(
      "warning",
      "Registry unavailable. Using last known selections.",
    );
  });
});
