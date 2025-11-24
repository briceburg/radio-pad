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

export function sanitizeUrl(targetUrl) {
  if (!targetUrl) return "<unknown>";
  try {
    const { origin, pathname } = new URL(targetUrl);
    return `${origin}${pathname}`;
  } catch {
    const safe = String(targetUrl);
    return safe.length > 80 ? `${safe.slice(0, 77)}...` : safe;
  }
}

export class RegistryRequestError extends Error {
  constructor({ url, status = "unknown", cause } = {}) {
    const sanitized = sanitizeUrl(url);
    super(`Registry request failed (${status}) for ${sanitized}`);
    this.name = "RegistryRequestError";
    this.status = status;
    this.url = url;
    this.sanitizedUrl = sanitized;
    if (cause) this.cause = cause;
  }

  toMessage() {
    return `Registry request failed (${this.status}) for ${this.sanitizedUrl}`;
  }

  static format(error) {
    if (error instanceof RegistryRequestError) {
      return error.toMessage();
    }
    if (error && typeof error.message === "string" && error.message.trim()) {
      return error.message;
    }
    return "Unknown registry error";
  }
}
