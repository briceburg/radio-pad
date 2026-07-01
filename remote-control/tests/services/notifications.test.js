import { beforeEach, describe, expect, it } from "vitest";
import {
  registrySummary,
  toastRegistryFailure,
} from "../../src/js/notifications.js";
import { toastStore } from "../../src/js/store.js";

describe("registry notifications", () => {
  beforeEach(() => toastStore.set({ id: 0 }));

  it("explains a refresh failure after settings were saved", () => {
    const error = new Error("offline");

    toastRegistryFailure("accounts", error, { fromSettingsSave: true });

    expect(toastStore.get()).toMatchObject({
      summary: "Settings saved, but couldn’t refresh accounts.",
      error,
      format: "registry",
      severity: "warning",
    });
  });

  it("does not mask a registry failure when its summary is empty", () => {
    expect(registrySummary("", { fromSettingsSave: true })).toBe(
      "Settings saved, but registry data couldn’t be refreshed.",
    );
  });
});
