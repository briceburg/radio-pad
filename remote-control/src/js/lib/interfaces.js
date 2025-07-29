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

export class EventEmitter {
  constructor() {
    this._eventHandlers = {};
  }

  async registerEvent(event_name, handler) {
    if (!this._eventHandlers[event_name]) {
      this._eventHandlers[event_name] = [];
    }
    this._eventHandlers[event_name].push(handler);
  }

  async emitEvent(event_name, data) {
    const handlers = this._eventHandlers[event_name] || [];
    for (const handler of handlers) {
      const result = await handler(data);
      if (result === false) {
        throw new Error(`Event "${event_name}" propagation stopped by a handler.`);
      }
    }
  }
}