import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Capacitor } from "@capacitor/core";
import { AudioPlayer } from "@mediagrid/capacitor-native-audio";
import { LocalPlayback } from "../../src/js/services/local-playback.js";
import { createControlActions } from "../../src/js/actions/control-actions.js";
import { listenStore, toastStore } from "../../src/js/store.js";

vi.mock("@capacitor/core", () => ({
  Capacitor: { isNativePlatform: vi.fn() },
}));
vi.mock("@mediagrid/capacitor-native-audio", () => ({
  AudioPlayer: Object.fromEntries(
    [
      "create",
      "initialize",
      "onAudioReady",
      "onAudioEnd",
      "onPlaybackStatusChange",
      "play",
      "stop",
      "destroy",
      "changeMetadata",
      "changeAudioSource",
    ].map((name) => [name, vi.fn()]),
  ),
}));

const STATION = { call_sign: "KEXP", stream_url: "https://example.test/kexp" };
const OTHER = { call_sign: "WXXI", stream_url: "https://example.test/wxxi" };

// Exercise the real service/action boundary. Plugin promises acknowledge commands;
// readiness and later playback changes arrive through separate native callbacks.
function createActions() {
  const playback = new LocalPlayback();
  const actions = createControlActions({
    localPlayback: playback,
    control: new EventTarget(),
  });
  return { playback, actions };
}

function expectState(
  currentStation,
  requestedStation = null,
  failedStation = null,
) {
  expect(listenStore.get()).toMatchObject({
    currentStation,
    requestedStation,
    failedStation,
  });
}

describe("Listen playback", () => {
  let audioInstances;
  let nativeCallbacks;
  let nextPlay;

  beforeEach(() => {
    vi.resetAllMocks();
    Capacitor.isNativePlatform.mockReturnValue(false);
    listenStore.set({
      radioDial: { name: "Radio", stations: [STATION, OTHER] },
      currentStation: null,
      requestedStation: null,
      failedStation: null,
      loading: false,
    });
    toastStore.set({ id: 0, summary: null, error: null });
    audioInstances = [];
    nativeCallbacks = [];
    nextPlay = Promise.resolve();
    AudioPlayer.create.mockImplementation(async () => nativeCallbacks.push({}));
    for (const [method, callback] of [
      ["onAudioReady", "ready"],
      ["onAudioEnd", "end"],
      ["onPlaybackStatusChange", "status"],
    ]) {
      AudioPlayer[method].mockImplementation(async (_ref, listener) => {
        nativeCallbacks.at(-1)[callback] = listener;
        return "callback-id";
      });
    }
    vi.stubGlobal(
      "Audio",
      vi.fn(function (url) {
        const audio = Object.assign(new EventTarget(), {
          url,
          load: vi.fn(),
          pause: vi.fn(),
          play: vi.fn().mockReturnValue(nextPlay),
          removeAttribute: vi.fn(),
        });
        audioInstances.push(audio);
        return audio;
      }),
    );
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("keeps web playback pending until play resolves, then releases the stopped stream", async () => {
    const playing = Promise.withResolvers();
    nextPlay = playing.promise;
    const { actions } = createActions();
    const selection = actions.clickStation("listen", "KEXP");
    expectState(null, "KEXP");
    playing.resolve();
    await selection;
    expectState("KEXP");
    await actions.stopStation("listen");
    expectState(null);
    expect(global.Audio).toHaveBeenCalledWith(STATION.stream_url);
    expect(audioInstances[0].pause).toHaveBeenCalledOnce();
    expect(audioInstances[0].removeAttribute).toHaveBeenCalledWith("src");
    expect(audioInstances[0].load).toHaveBeenCalledOnce();
  });

  it("reports a rejected web play and a later stream error", async () => {
    const { actions } = createActions();
    nextPlay = Promise.reject(new Error("Playback blocked"));
    await actions.clickStation("listen", "KEXP");
    expectState(null, null, "KEXP");
    expect(toastStore.get().error.message).toBe("Playback blocked");
    nextPlay = Promise.resolve();
    await actions.clickStation("listen", "WXXI");
    expectState("WXXI");
    audioInstances[1].error = new Error("Stream disconnected");
    audioInstances[1].dispatchEvent(new Event("error"));
    expectState(null, null, "WXXI");
    expect(toastStore.get().error.message).toBe("Stream disconnected");
  });

  it("ignores superseded web startup results and errors, including after stop", async () => {
    const first = Promise.withResolvers();
    nextPlay = first.promise;
    const { actions } = createActions();
    const selection = actions.clickStation("listen", "KEXP");
    nextPlay = Promise.resolve();
    await actions.clickStation("listen", "WXXI");
    first.reject(new Error("Old stream failed"));
    audioInstances[0].dispatchEvent(new Event("error"));
    await selection;
    expectState("WXXI");
    expect(toastStore.get().id).toBe(0);

    const last = Promise.withResolvers();
    nextPlay = last.promise;
    const stopped = actions.clickStation("listen", "KEXP");
    await actions.stopStation("listen");
    await stopped;
    expectState(null);
    last.resolve();
    await Promise.resolve();
    expectState(null);
  });

  it.each(["pause", "ended"])("clears web playback on %s", async (event) => {
    const { actions } = createActions();
    await actions.clickStation("listen", "KEXP");
    audioInstances[0].dispatchEvent(new Event(event));
    expectState(null);
    await actions.stopStation("listen");
  });

  it("awaits native readiness and play acceptance, then follows external controls", async () => {
    Capacitor.isNativePlatform.mockReturnValue(true);
    const playing = Promise.withResolvers();
    AudioPlayer.play.mockReturnValue(playing.promise);
    const { actions } = createActions();
    const selection = actions.clickStation("listen", "KEXP");
    await vi.waitFor(() =>
      expect(AudioPlayer.initialize).toHaveBeenCalledOnce(),
    );
    expectState(null, "KEXP");
    expect(AudioPlayer.play).not.toHaveBeenCalled();
    nativeCallbacks[0].ready();
    await vi.waitFor(() => expect(AudioPlayer.play).toHaveBeenCalledOnce());
    expectState(null, "KEXP");
    playing.resolve();
    await selection;
    expectState("KEXP");
    nativeCallbacks[0].ready();
    expect(AudioPlayer.play).toHaveBeenCalledOnce();
    nativeCallbacks[0].status({ status: "paused" });
    expectState(null);
    nativeCallbacks[0].status({ status: "playing" });
    expectState("KEXP");
    nativeCallbacks[0].end();
    expectState(null);
    await actions.stopStation("listen");
    expect(AudioPlayer.stop).toHaveBeenCalledWith({
      audioId: "radio-pad-stream",
    });
    expect(AudioPlayer.destroy).not.toHaveBeenCalled();
    const next = actions.clickStation("listen", "WXXI");
    await vi.waitFor(() =>
      expect(AudioPlayer.changeAudioSource).toHaveBeenCalledOnce(),
    );
    nativeCallbacks[0].ready();
    await next;
    expectState("WXXI");
    expect(AudioPlayer.create).toHaveBeenCalledOnce();
    expect(AudioPlayer.onAudioReady).toHaveBeenCalledOnce();
    expect(AudioPlayer.onAudioEnd).toHaveBeenCalledOnce();
    expect(AudioPlayer.onPlaybackStatusChange).toHaveBeenCalledOnce();
    await actions.stopStation("listen");
  });

  it.each(["create", "initialize", "play"])(
    "reports a native %s rejection",
    async (method) => {
      Capacitor.isNativePlatform.mockReturnValue(true);
      AudioPlayer[method].mockRejectedValueOnce(new Error(`${method} failed`));
      const { actions } = createActions();
      const selection = actions.clickStation("listen", "KEXP");
      if (method === "play") {
        await vi.waitFor(() =>
          expect(AudioPlayer.initialize).toHaveBeenCalledOnce(),
        );
        nativeCallbacks[0].ready();
      }
      await selection;
      expectState(null, null, "KEXP");
      expect(toastStore.get().error.message).toBe(`${method} failed`);
      await actions.stopStation("listen");
    },
  );

  it("bounds native readiness without an error callback and permits retry", async () => {
    vi.useFakeTimers();
    Capacitor.isNativePlatform.mockReturnValue(true);
    const { actions } = createActions();
    const selection = actions.clickStation("listen", "KEXP");
    await vi.advanceTimersByTimeAsync(30000);
    await selection;
    expectState(null, null, "KEXP");
    expect(toastStore.get().error.message).toContain("did not become ready");
    nativeCallbacks[0].ready();
    expect(AudioPlayer.play).not.toHaveBeenCalled();
    const retry = actions.clickStation("listen", "KEXP");
    await vi.advanceTimersByTimeAsync(0);
    nativeCallbacks[0].ready();
    await retry;
    expectState("KEXP");
    await actions.stopStation("listen");
    expect(vi.getTimerCount()).toBe(0);
  });

  it("retries failed native initialization without retaining more callbacks", async () => {
    Capacitor.isNativePlatform.mockReturnValue(true);
    AudioPlayer.initialize.mockRejectedValueOnce(
      new Error("Initialization failed"),
    );
    const { actions } = createActions();
    await actions.clickStation("listen", "KEXP");
    expectState(null, null, "KEXP");
    const retry = actions.clickStation("listen", "WXXI");
    await vi.waitFor(() =>
      expect(AudioPlayer.changeAudioSource).toHaveBeenCalledOnce(),
    );
    nativeCallbacks[0].ready();
    await retry;
    expectState("WXXI");
    expect(AudioPlayer.create).toHaveBeenCalledOnce();
    expect(AudioPlayer.initialize).toHaveBeenCalledTimes(2);
    expect(AudioPlayer.onAudioReady).toHaveBeenCalledOnce();
    await actions.stopStation("listen");
  });

  it("waits for native stop acknowledgement and preserves playback on rejection", async () => {
    Capacitor.isNativePlatform.mockReturnValue(true);
    const { actions } = createActions();
    const selection = actions.clickStation("listen", "KEXP");
    await vi.waitFor(() =>
      expect(AudioPlayer.initialize).toHaveBeenCalledOnce(),
    );
    nativeCallbacks[0].ready();
    await selection;
    const stopped = Promise.withResolvers();
    AudioPlayer.stop.mockReturnValueOnce(stopped.promise);
    const stopping = actions.stopStation("listen");
    expectState("KEXP");
    stopped.reject(new Error("Stop failed"));
    await stopping;
    expectState("KEXP");
    expect(toastStore.get().error.message).toBe("Stop failed");
    nativeCallbacks[0].status({ status: "paused" });
    expectState(null);
    nativeCallbacks[0].status({ status: "playing" });
    expectState("KEXP");
    await actions.stopStation("listen");
    expectState(null);
  });

  it.each(["success", "failure"])(
    "ignores slow stop %s after a newer station request",
    async (result) => {
      Capacitor.isNativePlatform.mockReturnValue(true);
      const { actions } = createActions();
      const first = actions.clickStation("listen", "KEXP");
      await vi.waitFor(() =>
        expect(AudioPlayer.initialize).toHaveBeenCalledOnce(),
      );
      nativeCallbacks[0].ready();
      await first;
      const stopped = Promise.withResolvers();
      AudioPlayer.stop.mockReturnValueOnce(stopped.promise);
      const stopping = actions.stopStation("listen");
      expectState("KEXP");
      const next = actions.clickStation("listen", "WXXI");
      expectState(null, "WXXI");
      if (result === "success") stopped.resolve();
      else stopped.reject(new Error("Old stop failed"));
      await stopping;
      expectState(null, "WXXI");
      await vi.waitFor(() =>
        expect(AudioPlayer.changeAudioSource).toHaveBeenCalledOnce(),
      );
      nativeCallbacks[0].ready();
      await next;
      expectState("WXXI");
      await actions.stopStation("listen");
    },
  );

  it("serializes rapid native selections and registers callbacks once for the service lifetime", async () => {
    Capacitor.isNativePlatform.mockReturnValue(true);
    const initializing = Promise.withResolvers();
    AudioPlayer.initialize.mockReturnValueOnce(initializing.promise);
    const { actions } = createActions();
    const first = actions.clickStation("listen", "KEXP");
    await vi.waitFor(() =>
      expect(AudioPlayer.initialize).toHaveBeenCalledOnce(),
    );
    const second = actions.clickStation("listen", "WXXI");
    const third = actions.clickStation("listen", "KEXP");
    expectState(null, "KEXP");
    expect(AudioPlayer.create).toHaveBeenCalledOnce();
    nativeCallbacks[0].ready();
    initializing.resolve();
    await vi.waitFor(() =>
      expect(AudioPlayer.changeAudioSource).toHaveBeenCalledOnce(),
    );
    expect(AudioPlayer.initialize).toHaveBeenCalledOnce();
    expect(AudioPlayer.destroy).not.toHaveBeenCalled();
    expect(AudioPlayer.onAudioReady).toHaveBeenCalledOnce();
    expect(AudioPlayer.changeAudioSource).toHaveBeenCalledWith({
      audioId: "radio-pad-stream",
      source: STATION.stream_url,
    });
    nativeCallbacks[0].status({ status: "playing" });
    expectState(null, "KEXP");
    expect(AudioPlayer.play).not.toHaveBeenCalled();
    nativeCallbacks[0].ready();
    await Promise.all([first, second, third]);
    expectState("KEXP");
    await actions.stopStation("listen");
    nativeCallbacks[0].ready();
    nativeCallbacks[0].status({ status: "playing" });
    expectState(null);
    expect(AudioPlayer.play).toHaveBeenCalledOnce();
  });

  it("stops a pending native request before create completes", async () => {
    Capacitor.isNativePlatform.mockReturnValue(true);
    const creating = Promise.withResolvers();
    AudioPlayer.create.mockImplementationOnce(async () => {
      nativeCallbacks.push({});
      await creating.promise;
    });
    const { actions } = createActions();
    const selection = actions.clickStation("listen", "KEXP");
    await vi.waitFor(() => expect(AudioPlayer.create).toHaveBeenCalledOnce());
    const stopping = actions.stopStation("listen");
    expectState(null, "KEXP");
    creating.resolve();
    await Promise.all([selection, stopping]);
    expectState(null);
    expect(AudioPlayer.play).not.toHaveBeenCalled();
    expect(AudioPlayer.destroy).not.toHaveBeenCalled();
  });
});
