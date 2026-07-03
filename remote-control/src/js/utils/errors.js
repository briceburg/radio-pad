// SPDX-FileCopyrightText: 2025 Brice Burgess (github.com/briceburg)
// SPDX-License-Identifier: AGPL-3.0-or-later

function sanitizeUrl(targetUrl) {
  if (!targetUrl) return "<unknown>";
  try {
    const { origin, pathname } = new URL(targetUrl);
    return `${origin}${pathname}`;
  } catch {
    const safe = String(targetUrl);
    return safe.length > 80 ? `${safe.slice(0, 77)}...` : safe;
  }
}

export function formatErrorMessage(error, fallback = "") {
  if (typeof error?.message === "string") {
    const msg = error.message.trim();
    if (msg.includes("NetworkError") || msg.includes("Failed to fetch")) {
      return "Network connection failed.";
    }
    return msg;
  }
  return fallback;
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
    const msg = formatErrorMessage(error, "Unknown registry error");
    if (msg === "Network connection failed.") {
      return "Unable to connect. Check your Registry URL in Settings.";
    }
    return msg;
  }
}
