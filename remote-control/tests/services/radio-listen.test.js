import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Capacitor } from "@capacitor/core";
import { AudioPlayer } from "@mediagrid/capacitor-native-audio";
import { RadioListen } from "../../src/js/services/radio-listen.js";

vi.mock("@capacitor/core", () => ({
  Capacitor: { isNativePlatform: vi.fn() },
}));

vi.mock("@mediagrid/capacitor-native-audio", () => ({
  AudioPlayer: {
    create: vi.fn(),
    initialize: vi.fn(),
    onAudioReady: vi.fn(),
    play: vi.fn(),
    stop: vi.fn(),
    destroy: vi.fn(),
    changeAudioSource: vi.fn(),
    changeMetadata: vi.fn(),
  },
}));

const STATION = {
  call_sign: "KEXP",
  stream_url: "https://example.test/kexp",
};

describe("RadioListen", () => {
  let audioInstances;
  let onAudioReady;
  let readyListener;

  beforeEach(() => {
    vi.clearAllMocks();
    audioInstances = [];
    readyListener = { remove: vi.fn() };
    AudioPlayer.onAudioReady.mockImplementation(async (_ref, listener) => {
      onAudioReady = listener;
      return readyListener;
    });
    vi.stubGlobal(
      "Audio",
      vi.fn(function (url) {
        const audio = {
          url,
          addEventListener: vi.fn(),
          load: vi.fn(),
          pause: vi.fn(),
          play: vi.fn().mockResolvedValue(),
          removeAttribute: vi.fn(),
        };
        audioInstances.push(audio);
        return audio;
      }),
    );
  });

  afterEach(() => vi.unstubAllGlobals());

  it("plays and cleans up browser audio", async () => {
    Capacitor.isNativePlatform.mockReturnValue(false);
    const listen = new RadioListen();

    await expect(listen.play({})).resolves.toBe(false);
    await expect(listen.play(STATION)).resolves.toBe(true);
    await listen.stop();

    expect(global.Audio).toHaveBeenCalledWith(STATION.stream_url);
    expect(audioInstances[0].play).toHaveBeenCalledOnce();
    expect(audioInstances[0].pause).toHaveBeenCalledOnce();
    expect(audioInstances[0].removeAttribute).toHaveBeenCalledWith("src");
    expect(audioInstances[0].load).toHaveBeenCalledOnce();
  });

  it("initializes, reuses, and tears down native audio", async () => {
    Capacitor.isNativePlatform.mockReturnValue(true);
    const listen = new RadioListen();

    await listen.play(STATION);
    expect(AudioPlayer.create).toHaveBeenCalledWith({
      audioId: "radio-pad-stream",
      audioSource: STATION.stream_url,
      friendlyTitle: STATION.call_sign,
      useForNotification: true,
      isBackgroundMusic: false,
      loop: false,
    });
    expect(AudioPlayer.initialize).toHaveBeenCalledWith({
      audioId: "radio-pad-stream",
    });

    await onAudioReady();
    expect(AudioPlayer.play).toHaveBeenCalledWith({
      audioId: "radio-pad-stream",
    });

    await listen.play({
      call_sign: "WXXI",
      stream_url: "https://example.test/wxxi",
    });
    expect(AudioPlayer.changeAudioSource).toHaveBeenCalledWith({
      audioId: "radio-pad-stream",
      source: "https://example.test/wxxi",
    });
    expect(AudioPlayer.changeMetadata).toHaveBeenCalledWith({
      audioId: "radio-pad-stream",
      friendlyTitle: "WXXI",
    });

    await listen.stop();
    expect(AudioPlayer.stop).toHaveBeenCalledWith({
      audioId: "radio-pad-stream",
    });
    expect(readyListener.remove).toHaveBeenCalledOnce();
    expect(AudioPlayer.destroy).toHaveBeenCalledWith({
      audioId: "radio-pad-stream",
    });
  });
});
