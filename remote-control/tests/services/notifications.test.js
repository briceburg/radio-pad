import { beforeEach, describe, expect, it } from "vitest";
import { toastRegistryFailure } from "../../src/js/notifications.js";
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
});
