// SPDX-FileCopyrightText: 2025 Brice Burgess (github.com/briceburg)
// SPDX-License-Identifier: AGPL-3.0-or-later

import { Capacitor } from "@capacitor/core";
import { AudioPlayer } from "@mediagrid/capacitor-native-audio";

const AUDIO_ID = "radio-pad-stream";

const createWebAudioPlayer = () => {
  let audio;

  const cleanup = () => {
    if (!audio) return;
    audio.pause();
    audio.removeAttribute("src");
    audio.load();
    audio = null;
  };

  return {
    async play(url) {
      if (!url) return;
      cleanup();

      const next = new Audio(url);
      audio = next;

      const bail = () => {
        if (audio === next) {
          cleanup();
        }
      };

      next.addEventListener("error", bail, { once: true });
      next.play().catch(bail);
    },
    async stop() {
      cleanup();
    },
  };
};

const createNativeAudioPlayer = () => {
  let initialized = false;
  let readyListener;

  const audioRef = (extra = {}) => ({ audioId: AUDIO_ID, ...extra });

  const teardown = async () => {
    if (readyListener) {
      try {
        await readyListener.remove();
      } catch (error) {
        console.warn("Failed to remove audio ready listener", error);
      }
      readyListener = null;
    }

    try {
      await AudioPlayer.destroy(audioRef());
    } catch (error) {
      if (initialized) {
        console.error("Native audio destroy error:", error);
      }
    }

    initialized = false;
  };

  const ensureInitialized = async (url, title) => {
    if (initialized) {
      await AudioPlayer.changeAudioSource(audioRef({ source: url }));
      await AudioPlayer.changeMetadata(audioRef({ friendlyTitle: title }));
      await AudioPlayer.play(audioRef());
      return;
    }

    await AudioPlayer.create({
      audioId: AUDIO_ID,
      audioSource: url,
      friendlyTitle: title,
      useForNotification: true,
      isBackgroundMusic: false,
      loop: false,
    });

    try {
      readyListener = await AudioPlayer.onAudioReady(audioRef(), async () => {
        await AudioPlayer.play(audioRef());
      });

      await AudioPlayer.initialize(audioRef());
      initialized = true;
    } catch (error) {
      await teardown();
      throw error;
    }
  };

  return {
    async play(url, title) {
      if (!url) return;
      try {
        await ensureInitialized(url, title);
      } catch (error) {
        console.error("Native audio playback error:", error);
      }
    },
    async stop() {
      if (!initialized) return;

      try {
        await AudioPlayer.stop(audioRef());
      } catch (error) {
        console.error("Native audio stop error:", error);
      }

      await teardown();
    },
  };
};

export class RadioListen {
  constructor() {
    this.player = Capacitor.isNativePlatform()
      ? createNativeAudioPlayer()
      : createWebAudioPlayer();
  }

  async play(station) {
    if (!station?.stream_url) return false;

    await this.player.play(station.stream_url, station.call_sign);
    return true;
  }

  async stop() {
    await this.player.stop();
  }
}
