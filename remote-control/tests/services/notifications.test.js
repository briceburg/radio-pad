import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  initNotifications,
  registrySummary,
  toastRegistryFailure,
  toastSuccess,
  toastWarning,
} from "../../src/js/notifications.js";
import { toastStore } from "../../src/js/store.js";

describe("registry notifications", () => {
  beforeEach(() => toastStore.set({ id: 0 }));
  afterEach(() => document.body.replaceChildren());

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

  it("replaces and automatically dismisses inline Ionic toasts", async () => {
    const presentations = [];
    const toast = document.createElement("ion-toast");
    toast.id = "global-toast";
    toast.dismiss = vi.fn().mockResolvedValue(false);
    toast.present = vi.fn(async () => {
      presentations.push({
        header: toast.header,
        message: toast.message,
        duration: toast.duration,
        color: toast.color,
        buttons: toast.buttons,
        position: toast.position,
        positionAnchor: toast.positionAnchor,
        swipeGesture: toast.swipeGesture,
      });
    });
    document.body.append(toast);
    const unsubscribe = initNotifications();

    toastWarning("Connection interrupted.");
    toastSuccess("Reconnected.");
    await vi.waitFor(() => expect(toast.present).toHaveBeenCalledTimes(2));
    unsubscribe();

    expect(toast.dismiss).toHaveBeenCalledTimes(2);
    expect(presentations).toEqual([
      expect.objectContaining({
        header: "Warning",
        message: "Connection interrupted.",
        duration: 8000,
        color: "warning",
        buttons: [{ text: "Dismiss", role: "cancel" }],
        position: "top",
        positionAnchor: undefined,
        swipeGesture: "vertical",
      }),
      expect.objectContaining({
        header: "Success",
        message: "Reconnected.",
        duration: 3000,
        color: "success",
        buttons: [],
        position: "bottom",
        positionAnchor: "main-tab-bar",
        swipeGesture: "vertical",
      }),
    ]);
  });
});
