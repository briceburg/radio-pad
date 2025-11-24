/*
This file is part of the radio-pad project.
https://github.com/briceburg/radio-pad

Copyright (c) 2025 Brice Burgess <https://github.com/briceburg>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.
You should have received a copy of the GNU General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.
*/

import { Capacitor } from "@capacitor/core";
import { AudioPlayer } from "@mediagrid/capacitor-native-audio";
import { EventEmitter } from "./interfaces.js";

const AUDIO_ID = "radio-pad-stream";

const createWebAudioPlayer = () => {
  let audio;

  const cleanup = () => {
    if (!audio) return;
    audio.pause();
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

  const ensureInitialized = async (url, stationName) => {
    if (initialized) {
      await AudioPlayer.changeAudioSource(audioRef({ source: url }));
      await AudioPlayer.changeMetadata(
        audioRef({ friendlyTitle: stationName }),
      );
      await AudioPlayer.play(audioRef());
      return;
    }

    await AudioPlayer.create({
      audioId: AUDIO_ID,
      audioSource: url,
      friendlyTitle: stationName,
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
    async play(url, stationName) {
      if (!url) return;
      try {
        await ensureInitialized(url, stationName);
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

export class RadioListen extends EventEmitter {
  constructor() {
    super();
    this.player = Capacitor.isNativePlatform()
      ? createNativeAudioPlayer()
      : createWebAudioPlayer();
    this.stations = new Map();
  }

  setStations(stationsPayload = {}) {
    const { stations = [] } = stationsPayload;
    this.stations = new Map(stations.map(({ name, url }) => [name, url]));
  }

  async play(stationName) {
    const url = this.stations.get(stationName);
    // TODO: support .pls URLS
    if (url) {
      await this.player.play(url, stationName);
      this.emitEvent("station-playing", stationName);
    }
  }

  async stop() {
    await this.player.stop();
    this.emitEvent("station-playing", null);
  }

  setVolume(level) {
    // TODO: Implement volume control for local player
  }
}
