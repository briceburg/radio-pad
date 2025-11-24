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

/**
 * Web-based audio player using HTML5 Audio API
 */
class WebAudioPlayer {
  constructor() {
    this.audio = null;
  }

  async play(url, stationName) {
    if (!url) return;

    await this.stop();

    const audio = new Audio(url);
    this.audio = audio;

    const handleError = () => {
      if (this.audio === audio) {
        this.stop();
      }
    };

    audio.addEventListener("error", handleError, { once: true });
    audio.play().catch(handleError);
  }

  async stop() {
    if (this.audio) {
      this.audio.pause();
      this.audio = null;
    }
  }
}

/**
 * Native audio player using Capacitor Native Audio plugin
 * Supports background playback with system notification
 */
class NativeAudioPlayer {
  constructor() {
    this.audioId = "radio-pad-stream";
    this.isInitialized = false;
  }

  async play(url, stationName) {
    try {
      if (!this.isInitialized) {
        await this._initialize(url, stationName);
      } else {
        await this._changeStation(url, stationName);
      }
    } catch (error) {
      console.error("Native audio playback error:", error);
    }
  }

  async stop() {
    if (this.isInitialized) {
      try {
        await AudioPlayer.stop({ audioId: this.audioId });
      } catch (error) {
        console.error("Native audio stop error:", error);
      }
    }
  }

  async _initialize(url, stationName) {
    await AudioPlayer.create({
      audioId: this.audioId,
      audioSource: url,
      friendlyTitle: stationName,
      useForNotification: true,
      isBackgroundMusic: false,
      loop: false,
    });

    await AudioPlayer.onAudioReady({ audioId: this.audioId }, async () => {
      await AudioPlayer.play({ audioId: this.audioId });
    });

    await AudioPlayer.initialize({ audioId: this.audioId });
    this.isInitialized = true;
  }

  async _changeStation(url, stationName) {
    await AudioPlayer.changeAudioSource({
      audioId: this.audioId,
      source: url,
    });
    await AudioPlayer.changeMetadata({
      audioId: this.audioId,
      friendlyTitle: stationName,
    });
    await AudioPlayer.play({ audioId: this.audioId });
  }
}

export class RadioListen extends EventEmitter {
  constructor() {
    super();
    this.player = Capacitor.isNativePlatform()
      ? new NativeAudioPlayer()
      : new WebAudioPlayer();
    this.stations = new Map();
  }

  setStations(station_data) {
    this.stations = new Map(
      station_data.stations.map((station) => [station.name, station.url]),
    );
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
