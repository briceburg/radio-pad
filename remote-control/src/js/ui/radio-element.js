// SPDX-FileCopyrightText: 2025 Brice Burgess (github.com/briceburg)
// SPDX-License-Identifier: AGPL-3.0-or-later

import { LitElement } from "lit";

export class RadioElement extends LitElement {
  createRenderRoot() {
    return this;
  }

  _emit(name, detail = null) {
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
