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

import { LitElement } from "lit";

/**
 * Shared base for radio-pad web components.
 * - Renders into the light DOM (no Shadow DOM) so Ionic styles apply.
 * - Provides `_emit()` for dispatching bubbling custom events.
 * - Provides a static `register()` helper that is safe under Vite HMR.
 */
export class RadioElement extends LitElement {
  createRenderRoot() {
    return this;
  }

  _emit(name, detail) {
    this.dispatchEvent(
      new CustomEvent(name, { bubbles: true, composed: true, detail }),
    );
  }

  static register(tagName) {
    if (!customElements.get(tagName)) {
      customElements.define(tagName, this);
    }
  }
}
