import { describe, expect, it } from "vitest";
import {
  formatRegistryAttempt,
  getRegistryPendingTitle,
  isRegistryPending,
} from "../../src/js/ui/registry-status.js";

describe("registry-status helpers", () => {
  it("treats loading and retrying as pending", () => {
    expect(isRegistryPending({ phase: "loading" })).toBe(true);
    expect(isRegistryPending({ phase: "retrying" })).toBe(true);
    expect(isRegistryPending({ phase: "ready" })).toBe(false);
  });

  it("formats attempt counts starting at one and caps at 10+", () => {
    expect(formatRegistryAttempt(0)).toBe("1");
    expect(formatRegistryAttempt(1)).toBe("2");
    expect(formatRegistryAttempt(9)).toBe("10+");
  });

  it("builds the shared registry title for loading and retrying states", () => {
    expect(getRegistryPendingTitle({ phase: "loading", retryAttempt: 0 })).toBe(
      "Connecting to Registry (attempt 1)",
    );
    expect(
      getRegistryPendingTitle({ phase: "retrying", retryAttempt: 2 }),
    ).toBe("Connecting to Registry (attempt 3)");
    expect(getRegistryPendingTitle({ phase: "ready", retryAttempt: 0 })).toBe(
      null,
    );
  });
});
