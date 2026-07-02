import { beforeEach, describe, expect, it, vi } from "vitest";
import { createControlActions } from "../../src/js/actions/control-actions.js";
import { authStore, controlStore, listenStore } from "../../src/js/store.js";

function createMockControl() {
  const control = new EventTarget();
  control.connect = vi.fn();
  control.disconnect = vi.fn();
  control.startPlayback = vi.fn();
  control.stopPlayback = vi.fn();
  return control;
}

function createMockListen() {
  return { play: vi.fn(), stop: vi.fn() };
}

function createActions() {
  const control = createMockControl();
  const listen = createMockListen();
  return {
    actions: createControlActions({ control, listen }),
    control,
    listen,
  };
}

const PLAYER = {
  id: "living-room",
  name: "Living Room",
  configured_radio_dial_url:
    "https://example.test/api/accounts/community/radio-dials/briceburg",
  switchboard_url: "wss://example.test/switchboard/briceburg/living-room",
};

describe("control-actions", () => {
  beforeEach(() => {
    global.fetch = vi.fn();
    authStore.set({ registryBearerToken: null });
    controlStore.set({
      player: null,
      radioDial: null,
      currentStation: null,
      requestedStation: null,
      loading: false,
      connectionState: "idle",
      playerConnected: null,
      playerStatuses: {},
      resourceStatuses: {},
    });
    listenStore.set({
      radioDial: null,
      currentStation: null,
      loading: false,
    });
  });

  it("selects a player, connects, and loads its RadioDial", async () => {
    const { actions, control } = createActions();
    const radioDial = {
      name: "Casa Briceburg",
      stations: [
        { call_sign: "KEXP", stream_url: "https://example.test/kexp" },
      ],
    };
    global.fetch.mockResolvedValue({
      ok: true,
      json: async () => radioDial,
    });

    await actions.selectPlayer(PLAYER);

    expect(control.connect).toHaveBeenCalledWith(PLAYER.switchboard_url, null);
    expect(global.fetch).toHaveBeenCalledWith(
      PLAYER.configured_radio_dial_url,
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    expect(controlStore.get()).toMatchObject({
      player: PLAYER,
      radioDial,
      loading: false,
    });
  });

  it("rejects RadioDials with ambiguous call signs", async () => {
    const { actions } = createActions();
    global.fetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        name: "Ambiguous",
        stations: [
          { call_sign: "KEXP", stream_url: "https://example.test/one" },
          { call_sign: "KEXP", stream_url: "https://example.test/two" },
        ],
      }),
    });

    await actions.selectPlayer(PLAYER);

    expect(controlStore.get()).toMatchObject({
      player: PLAYER,
      radioDial: null,
      loading: false,
      resourceStatuses: {
        radio_dial: {
          level: "warning",
          summary: "RadioDial unavailable.",
        },
      },
    });
  });

  it("reuses an in-flight load when the player reports the configured RadioDial", async () => {
    const { actions, control } = createActions();
    let resolveFetch;
    global.fetch.mockReturnValue(
      new Promise((resolve) => {
        resolveFetch = resolve;
      }),
    );

    const selection = actions.selectPlayer(PLAYER);
    await vi.waitFor(() => expect(global.fetch).toHaveBeenCalledOnce());
    control.dispatchEvent(
      new CustomEvent("radiodialurl", {
        detail:
          "http://registry:1980/api/accounts/community/radio-dials/briceburg",
      }),
    );

    expect(global.fetch).toHaveBeenCalledOnce();
    resolveFetch({
      ok: true,
      json: async () => ({ name: "Empty", stations: [] }),
    });
    await selection;
  });

  it("loads a different RadioDial reported by the running player", async () => {
    const { actions, control } = createActions();
    global.fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ name: "Empty", stations: [] }),
    });
    const reportedUrl =
      "https://player.test/accounts/briceburg/radio-dials/alternate";

    await actions.selectPlayer(PLAYER);
    control.dispatchEvent(
      new CustomEvent("radiodialurl", { detail: reportedUrl }),
    );

    await vi.waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(2));
    expect(global.fetch).toHaveBeenLastCalledWith(
      reportedUrl,
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("dispatches explicit playback commands for control stations", async () => {
    const { actions, control } = createActions();

    await actions.clickStation("control", "KEXP");
    await actions.stopStation("control");

    expect(control.startPlayback).toHaveBeenCalledWith("KEXP");
    expect(control.stopPlayback).toHaveBeenCalled();
  });

  it("applies authoritative playback state and clears it on disconnect", () => {
    const { control } = createActions();

    control.dispatchEvent(
      new CustomEvent("playbackstate", {
        detail: { callSign: "KEXP", requestedCallSign: "KGUT" },
      }),
    );
    expect(controlStore.get()).toMatchObject({
      currentStation: "KEXP",
      requestedStation: "KGUT",
    });

    control.dispatchEvent(new Event("disconnect"));
    expect(controlStore.get()).toMatchObject({
      currentStation: null,
      requestedStation: null,
    });
  });

  it("resolves listen stations from the loaded RadioDial", async () => {
    const station = {
      call_sign: "KEXP",
      stream_url: "https://example.test/kexp",
    };
    const { actions, listen } = createActions();
    listen.play.mockResolvedValue(true);
    listenStore.set({ radioDial: { stations: [station] } });

    await actions.clickStation("listen", "KEXP");

    expect(listen.play).toHaveBeenCalledWith(station);
    expect(listenStore.get().currentStation).toBe("KEXP");
  });
});
