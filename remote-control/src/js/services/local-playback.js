// SPDX-FileCopyrightText: 2025 Brice Burgess (github.com/briceburg)
// SPDX-License-Identifier: AGPL-3.0-or-later

import { Capacitor } from "@capacitor/core";
import { AudioPlayer } from "@mediagrid/capacitor-native-audio";

const AUDIO_ID = "radio-pad-stream";
const NATIVE_START_TIMEOUT_MS = 30000;

function createWebAudioPlayer(station, onStatus, onError) {
  const audio = new Audio(station.stream_url);
  audio.addEventListener("error", () =>
    onError(audio.error || new Error("Audio stream failed.")),
  );
  audio.addEventListener("playing", () => onStatus("playing"));
  audio.addEventListener("pause", () => onStatus("stopped"));
  audio.addEventListener("ended", () => onStatus("stopped"));

  return {
    play: () => audio.play(),
    async stop() {
      audio.pause();
      audio.removeAttribute("src");
      audio.load();
    },
  };
}

function createNativeAudioPlayer() {
  const audioRef = { audioId: AUDIO_ID };
  let setup;
  let created = false;
  let initialized = false;
  let ready;
  let statusChanged;
  let registered = 0;
  // Callback IDs have no public removal API. Keep one source/callback set for the
  // service's entire app lifetime; stop pauses it and retains the prepared source.
  const listeners = [
    ["onAudioReady", () => ready?.()],
    ["onAudioEnd", () => statusChanged?.("stopped")],
    ["onPlaybackStatusChange", ({ status }) => statusChanged?.(status)],
  ];

  return {
    async prepare(station, onStatus) {
      let resolveReady;
      const readiness = new Promise((resolve) => {
        resolveReady = resolve;
      });
      setup = (async () => {
        statusChanged = onStatus;
        const newSource = !created;
        if (newSource) {
          await AudioPlayer.create({
            ...audioRef,
            audioSource: station.stream_url,
            friendlyTitle: station.call_sign,
            useForNotification: true,
            isBackgroundMusic: false,
            loop: false,
          });
          created = true;
        }
        while (registered < listeners.length) {
          const [method, callback] = listeners[registered];
          await AudioPlayer[method](audioRef, callback);
          registered += 1;
        }
        if (!initialized) {
          ready = newSource ? resolveReady : null;
          await AudioPlayer.initialize(audioRef);
          initialized = true;
        }
        if (!newSource) {
          await AudioPlayer.changeMetadata({
            ...audioRef,
            friendlyTitle: station.call_sign,
          });
          ready = resolveReady;
          await AudioPlayer.changeAudioSource({
            ...audioRef,
            source: station.stream_url,
          });
        }
      })();
      await setup;
      await readiness;
    },
    start: () => AudioPlayer.play(audioRef),
    async stop() {
      await setup?.catch(() => {});
      if (initialized) await AudioPlayer.stop(audioRef);
    },
  };
}

export class LocalPlayback extends EventTarget {
  constructor() {
    super();
    this.session = null;
    this.cleanup = Promise.resolve(true);
    this.nativePlayer = Capacitor.isNativePlatform()
      ? createNativeAudioPlayer()
      : null;
  }

  publish(callSign = null, requestedCallSign = null, failedCallSign = null) {
    this.dispatchEvent(
      new CustomEvent("playbackstate", {
        detail: { callSign, requestedCallSign, failedCallSign },
      }),
    );
  }

  reportError(error) {
    this.dispatchEvent(new CustomEvent("error", { detail: error }));
  }

  release() {
    const session = this.session;
    this.session = null;
    if (session) {
      session.cancelled = true;
      clearTimeout(session.timeout);
    }
    if (!session?.player) return this.cleanup;
    // Complete native setup/stop before reusing the notification player for another station.
    this.cleanup = session.player.stop().then(
      () => true,
      (error) => {
        this.reportError(error);
        return false;
      },
    );
    return this.cleanup;
  }

  // Commands publish acknowledgements and failures through events.
  play(station) {
    if (!station?.stream_url) {
      this.reportError(new Error("Station has no audio stream."));
      return;
    }
    const previousCleanup = this.release();
    const session = {
      cancelled: false,
      callSign: station.call_sign,
      currentStation: null,
      player: null,
      started: false,
    };
    this.session = session;
    const isCurrent = () => this.session === session;
    const mayStart = () => isCurrent() && !session.cancelled;
    const fail = (error) => {
      if (!isCurrent()) return;
      this.release();
      this.publish(null, null, station.call_sign);
      this.reportError(error);
    };
    const onStatus = (status) => {
      if (!isCurrent() || !session.started) return;
      session.currentStation = status === "playing" ? station.call_sign : null;
      this.publish(session.currentStation);
    };
    this.publish(null, station.call_sign);

    const start = async () => {
      if (this.nativePlayer) await previousCleanup;
      if (!mayStart()) return;
      session.player =
        this.nativePlayer || createWebAudioPlayer(station, onStatus, fail);
      if (this.nativePlayer) await session.player.prepare(station, onStatus);
      else await session.player.play();
      if (!mayStart()) return;
      if (this.nativePlayer) await session.player.start();
      if (!mayStart()) return;
      session.started = true;
      session.currentStation = station.call_sign;
      // Web play() confirms playback. Native acknowledges the selected source/play commands
      // after an unqualified ready signal; the plugin cannot prove audible output or source identity.
      this.publish(station.call_sign);
    };
    if (this.nativePlayer) {
      // The plugin has no stream-error callback; a source may otherwise never become ready.
      session.timeout = setTimeout(
        () => fail(new Error("Audio stream did not become ready in time.")),
        NATIVE_START_TIMEOUT_MS,
      );
    }
    start()
      .catch((error) => {
        if (mayStart()) fail(error);
      })
      .finally(() => clearTimeout(session.timeout));
  }

  async stop() {
    if (this.session?.stopping) return this.cleanup;
    const session = this.session;
    const cleanup = this.release();
    const stopping = { stopping: true };
    this.session = stopping;
    const stopped = await cleanup;
    if (this.session !== stopping) return;
    this.session = stopped ? null : session;
    if (stopped) this.publish();
    else
      this.publish(
        session?.currentStation,
        null,
        session?.currentStation ? null : session?.callSign,
      );
  }
}
