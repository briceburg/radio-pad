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

import { PreferencesManager, preferencesConfig } from './preferences.js';
import { SwitchboardClient } from './switchboard.js';
import { renderStationGrid, showStationSkeletons, highlightCurrentStation } from './ui.js';

class RadioApp {
  constructor() {
    // --- DOM Elements ---
    this.radioInfo = document.getElementById('radio-info');
    this.nowPlaying = document.getElementById('now-playing');
    this.stationGrid = document.getElementById('station-grid');
    this.stopButton = document.getElementById('stop-button');

    // --- State Management ---
    this.registryUrl = import.meta.env.VITE_REGISTRY_URL || 'https://registry.radiopad.dev';
    this.playerId = null;
    this.stationsUrl = null;
    this.stationButtons = {};
    this.currentPlayingStation = null;

    // --- Services ---
    this.preferencesManager = new PreferencesManager(
      preferencesConfig,
      'settings-list',
      'settings-save',
      (key, value) => this.handlePreferenceChange(key, value)
    );
    this.switchboardClient = null;
  }

  /**
   * Main entry point for the application.
   */
  async init() {
    const savedRegistryUrl = await this.preferencesManager.get('registryUrl');
    if (savedRegistryUrl) {
      this.registryUrl = savedRegistryUrl;
    }
    preferencesConfig.find(p => p.key === 'playerId').options = await this.fetchPlayers();
    await this.preferencesManager.render();

    this.playerId = await this.preferencesManager.get('playerId');
    if (!this.checkPlayerSelection()) {
      return;
    }

    await this.initialize();
  }

  /**
   * Initializes the connection to the player.
   */
  async initialize() {
    this.resetStations();
    
    if (this.switchboardClient) {
      this.switchboardClient.disconnect();
    }

    this.switchboardClient = new SwitchboardClient(this.registryUrl, this.playerId, {
      onConnecting: (url) => { this.radioInfo.innerText = `🔄 Connecting...`; },
      onConnect: (url) => { this.radioInfo.innerText = `✅ Connected`; },
      onDisconnect: () => { this.radioInfo.innerText = '🔌 Disconnected. Reconnecting...'; },
      onError: (message) => { this.radioInfo.innerText = `⚠️ Error: ${message}`; },
      onStationPlaying: (station) => {
        this.currentPlayingStation = station;
        highlightCurrentStation(
          this.currentPlayingStation,
          this.stationButtons,
          this.stopButton,
          this.nowPlaying
        );
      },
      onStationsUrl: (url) => {
        this.stationsUrl = url;
        this.loadStations();
      },
    });

    await this.switchboardClient.connect();
  }

  // --- Core Logic Methods ---

  playStation(stationName, button) {
    button.setAttribute("color", "light");
    this.switchboardClient?.sendStationRequest(stationName);
  }

  stopStation() {
    this.switchboardClient?.sendStationRequest(null);
  }

  // --- UI & State Methods ---

  resetStations() {
    this.stationButtons = {};
    showStationSkeletons(this.stationGrid);
  }

  async loadStations() {
    this.resetStations();
    try {
      const response = await fetch(this.stationsUrl);
      const stations = await response.json();
      renderStationGrid(
        stations,
        this.stationGrid,
        (stationName, button) => this.playStation(stationName, button),
        this.stationButtons
      );
      this.stopButton.addEventListener("click", () => this.stopStation());
      highlightCurrentStation(
        this.currentPlayingStation,
        this.stationButtons,
        this.stopButton,
        this.nowPlaying
      );
    } catch (error) {
      console.error("Error loading stations:", error);
    }
  }

  // --- API & Event Handlers ---

  async handlePreferenceChange(key, value) {
    if (key === 'registryUrl') {
      this.registryUrl = value;
      preferencesConfig.find(p => p.key === 'playerId').options = await this.fetchPlayers();
      await this.preferencesManager.render();
    }

    this.playerId = await this.preferencesManager.get('playerId');

    if (this.checkPlayerSelection()) {
      await this.initialize();
    }
  }

  checkPlayerSelection() {
    const playerSelect = this.preferencesManager.inputs.playerId;
    const hasOptions = playerSelect && playerSelect.querySelectorAll('ion-select-option').length > 0;

    if (!this.playerId) {
      this.radioInfo.innerText = hasOptions
        ? '⚠️ Please select a player from Settings.'
        : '⚠️ No players found. Check Registry URL in Settings.';
      return false;
    }

    this.radioInfo.innerText = '';
    return true;
  }

  async fetchPlayers() {
    let players = [];
    let page = 1;
    try {
      do {
        const url = `${this.registryUrl}/v1/players?page=${page}&per_page=50`;
        const response = await fetch(url);
        const data = await response.json();
        if (Array.isArray(data.items)) {
          players = players.concat(data.items);
        }
        page = data.page < data.total_pages ? data.page + 1 : -1;
      } while (page !== -1);
    } catch (e) {
      console.error('Failed to fetch players from registry:', e);
    }
    return players.map(p => ({ value: p.id, label: p.name || p.id }));
  }
}

// --- App Startup ---
document.addEventListener('DOMContentLoaded', () => {
  const app = new RadioApp();
  app.init();
});

