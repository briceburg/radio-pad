import { beforeEach, describe, expect, it, vi } from "vitest";
import { createSettingsActions } from "../../src/js/actions/settings-actions.js";
import {
  discoverAccounts,
  discoverAuthEnabled,
  discoverPlayer,
  discoverPlayers,
  discoverRadioDials,
  radioDialUrl,
} from "../../src/js/services/registry-discovery.js";
import { settingsUiStore, toastStore } from "../../src/js/store.js";

vi.mock("../../src/js/services/registry-discovery.js", () => ({
  discoverAccounts: vi.fn(),
  discoverAuthEnabled: vi.fn(),
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
    setMany: vi.fn(async (settingsMap) => {
      const results = Object.fromEntries(
        Object.entries(settingsMap).map(([key, value]) => {
          const status = stored[key] === value ? "unchanged" : "applied";
          if (status === "applied") stored[key] = value;
          return [key, { key, value, status }];
        }),
      );
      return { status: "ok", results };
    }),
    setOptions: vi.fn(
      async (key, nextOptions, { invalidSelection = "first" } = {}) => {
        options[key] = nextOptions;
        const valid = nextOptions.some(
          (option) => option.value === stored[key],
        );
        if (!valid && invalidSelection === "first" && nextOptions.length > 0) {
          stored[key] = nextOptions[0].value;
        } else if (!valid && invalidSelection === "clear") {
          stored[key] = null;
        }
        return { value: stored[key] ?? null };
      },
    ),
  };
}

function createActions(prefs, auth = { signedIn: true }) {
  const onPlayerSelected = vi.fn(async () => {});
  const onRadioDialSelected = vi.fn(async () => {});
  const onRegistryStatus = vi.fn();

  return {
    actions: createSettingsActions({
      prefs,
      auth,
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
    settingsUiStore.set({ saveState: "idle" });
    toastStore.set({ id: 0 });
    discoverAccounts.mockResolvedValue([
      { value: "briceburg", label: "Briceburg" },
    ]);
    discoverAuthEnabled.mockResolvedValue(false);
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

  it("does not switch to the first replacement on a later refresh", async () => {
    const prefs = createPrefs();
    const { actions, onPlayerSelected } = createActions(prefs);

    await actions.sync();
    onPlayerSelected.mockClear();
    discoverPlayer.mockClear();
    discoverPlayers.mockResolvedValue([{ value: "kitchen", label: "Kitchen" }]);

    await actions.sync();

    expect(prefs.setOptions).toHaveBeenCalledWith(
      "playerId",
      [{ value: "kitchen", label: "Kitchen" }],
      { invalidSelection: "preserve" },
    );
    expect(discoverPlayer).not.toHaveBeenCalled();
    expect(onPlayerSelected).toHaveBeenCalledWith(null);
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

  it("loads a player while signed out when registry auth is disabled", async () => {
    const prefs = createPrefs();
    const { actions, onPlayerSelected } = createActions(prefs, {
      signedIn: false,
    });

    await actions.sync();

    expect(discoverPlayers).toHaveBeenCalled();
    expect(discoverPlayer).toHaveBeenCalled();
    expect(onPlayerSelected).toHaveBeenCalledWith(PLAYER);
  });

  it("hides players while signed out when registry auth is enabled", async () => {
    discoverAuthEnabled.mockResolvedValue(true);
    const prefs = createPrefs();
    const { actions, onPlayerSelected } = createActions(prefs, {
      signedIn: false,
    });

    await actions.sync();

    expect(discoverPlayers).not.toHaveBeenCalled();
    expect(discoverPlayer).not.toHaveBeenCalled();
    expect(prefs.setOptions).toHaveBeenCalledWith("playerId", [], {
      invalidSelection: "first",
    });
    expect(onPlayerSelected).toHaveBeenCalledWith(null);
  });

  it("refreshes a changed account on save and clears invalid dependent selections", async () => {
    const prefs = createPrefs({ radioDial: "community/briceburg" });
    discoverAccounts.mockResolvedValue([
      { value: "briceburg", label: "Briceburg" },
      { value: "pinecrest", label: "Pinecrest" },
    ]);
    discoverPlayers.mockResolvedValue([{ value: "kitchen", label: "Kitchen" }]);
    discoverRadioDials.mockResolvedValue([
      { value: "pinecrest/daytime", label: "Daytime" },
    ]);
    const { actions, onPlayerSelected, onRadioDialSelected } =
      createActions(prefs);

    await actions.save({ accountId: "pinecrest" });

    expect(discoverPlayers).toHaveBeenCalledWith(
      "pinecrest",
      "https://registry.example/api/",
      expect.anything(),
    );
    expect(prefs.setOptions).toHaveBeenCalledWith(
      "playerId",
      [{ value: "kitchen", label: "Kitchen" }],
      { invalidSelection: "clear" },
    );
    expect(prefs.setOptions).toHaveBeenCalledWith(
      "radioDial",
      [{ value: "pinecrest/daytime", label: "Daytime" }],
      { invalidSelection: "clear" },
    );
    expect(discoverPlayer).not.toHaveBeenCalled();
    expect(onPlayerSelected).toHaveBeenCalledWith(null);
    expect(onRadioDialSelected).toHaveBeenCalledWith(null);
  });

  it("refreshes saved account choices after an in-flight sync completes", async () => {
    const prefs = createPrefs();
    const { actions } = createActions(prefs);
    discoverAccounts.mockResolvedValue([
      { value: "briceburg", label: "Briceburg" },
      { value: "pinecrest", label: "Pinecrest" },
    ]);
    let resolveInitialPlayers;
    discoverPlayers
      .mockReturnValueOnce(
        new Promise((resolve) => {
          resolveInitialPlayers = resolve;
        }),
      )
      .mockResolvedValueOnce([{ value: "kitchen", label: "Kitchen" }]);

    const initialSync = actions.sync();
    await vi.waitFor(() =>
      expect(discoverPlayers).toHaveBeenCalledWith(
        "briceburg",
        expect.anything(),
        expect.anything(),
      ),
    );
    const save = actions.save({ accountId: "pinecrest" });
    resolveInitialPlayers([{ value: "living-room", label: "Living Room" }]);

    await Promise.all([initialSync, save]);

    expect(discoverPlayers).toHaveBeenLastCalledWith(
      "pinecrest",
      expect.anything(),
      expect.anything(),
    );
    expect(discoverPlayers).toHaveBeenCalledTimes(2);
    expect(settingsUiStore.get().saveState).toBe("saved");
  });

  it("refreshes access-dependent choices after auth changes during a sync", async () => {
    const auth = { signedIn: false };
    const prefs = createPrefs();
    const { actions } = createActions(prefs, auth);
    discoverAuthEnabled.mockResolvedValue(true);
    let resolveInitialRadioDials;
    discoverRadioDials
      .mockReturnValueOnce(
        new Promise((resolve) => {
          resolveInitialRadioDials = resolve;
        }),
      )
      .mockResolvedValueOnce([]);

    const initialSync = actions.sync();
    await vi.waitFor(() => expect(discoverRadioDials).toHaveBeenCalledOnce());

    auth.signedIn = true;
    const authRefresh =
      actions.refreshAccountsForCurrentRegistry("auth_accounts");
    resolveInitialRadioDials([]);
    await Promise.all([initialSync, authRefresh]);

    expect(discoverRadioDials).toHaveBeenCalledTimes(2);
    expect(discoverPlayers).toHaveBeenCalledOnce();
  });

  it("reports persistence failures and leaves settings retryable", async () => {
    const error = new Error("storage unavailable");
    const prefs = createPrefs();
    prefs.setMany.mockRejectedValue(error);
    const { actions } = createActions(prefs);

    await expect(actions.save({ accountId: "pinecrest" })).resolves.toEqual({
      status: "error",
      error,
    });

    expect(settingsUiStore.get().saveState).toBe("error");
    expect(toastStore.get()).toMatchObject({
      summary: "Couldn’t save settings.",
      error,
      severity: "danger",
    });
    expect(discoverAccounts).not.toHaveBeenCalled();
  });
});
