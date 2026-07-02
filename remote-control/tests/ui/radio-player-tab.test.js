import { afterEach, describe, expect, it } from "vitest";
import {
  getControlTitleStatus,
  getStationVisualState,
  isControlDegraded,
  RadioPlayerTab,
} from "../../src/js/ui/radio-player-tab.js";
import { controlStore } from "../../src/js/store.js";

afterEach(() => document.body.replaceChildren());

describe("radio-player-tab", () => {
  it("treats disconnected and offline control states as degraded", () => {
    expect(isControlDegraded({ connectionState: "disconnected" })).toBe(true);
    expect(isControlDegraded({ playerConnected: false })).toBe(true);
  });

  it("treats protocol and resource warnings as degraded", () => {
    expect(
      isControlDegraded({
        connectionState: "connected",
        playerConnected: true,
        playerStatuses: {
          switchboard: { level: "warning", summary: "Switchboard down" },
        },
      }),
    ).toBe(true);
    expect(
      isControlDegraded({
        resourceStatuses: {
          registry: { level: "warning", summary: "Registry unavailable." },
        },
      }),
    ).toBe(true);
  });

  it("derives control title status from connection and retained statuses", () => {
    expect(
      getControlTitleStatus({
        playerConnected: false,
        resourceStatuses: {
          registry: { level: "warning", summary: "Registry unavailable." },
        },
      }),
    ).toBe("Offline");
    expect(
      getControlTitleStatus({
        connectionState: "connected",
        player: { name: "Living Room" },
        resourceStatuses: {
          radio_dial: {
            level: "warning",
            summary: "RadioDial unavailable.",
          },
        },
      }),
    ).toBe("RadioDial unavailable.");
  });

  it("derives station visual states", () => {
    expect(
      getStationVisualState("control", {
        connectionState: "connected",
        playerConnected: true,
        loading: true,
      }),
    ).toBe("loading");
    expect(
      getStationVisualState("control", {
        connectionState: "connected",
        playerConnected: false,
        loading: false,
      }),
    ).toBe("warning");
  });

  it("reactively exposes player state through Ionic and ARIA semantics", async () => {
    controlStore.set({
      player: null,
      radioDial: null,
      currentStation: null,
      requestedStation: null,
      failedStation: null,
      loading: false,
      connectionState: "idle",
      playerConnected: null,
      playerStatuses: {},
      resourceStatuses: {},
    });
    const element = new RadioPlayerTab();
    document.body.append(element);
    await element.updateComplete;
    expect(element.querySelector("ion-title").textContent.trim()).toBe(
      "Control",
    );

    controlStore.set({
      player: { name: "Living Room" },
      radioDial: {
        stations: [{ call_sign: "KEXP", stream_url: "https://example.test" }],
      },
      currentStation: "KEXP",
      requestedStation: null,
      failedStation: null,
      loading: false,
      connectionState: "connected",
      playerConnected: true,
      playerStatuses: {},
      resourceStatuses: {},
    });
    await element.updateComplete;

    const title = element.querySelector("ion-title");
    const station = element.querySelector("ion-button[aria-pressed]");
    expect(title.textContent.trim()).toBe("Living Room: KEXP");
    expect(title.getAttribute("aria-level")).toBe("1");
    expect(title.getAttribute("aria-live")).toBe("polite");
    expect(element.querySelector('[role="status"]')).toBeNull();
    expect(station.getAttribute("aria-pressed")).toBe("true");

    controlStore.set({
      ...controlStore.get(),
      currentStation: null,
    });
    await element.updateComplete;
    expect(title.textContent.trim()).toBe("Living Room");

    controlStore.set({
      ...controlStore.get(),
      requestedStation: "KEXP",
    });
    await element.updateComplete;

    expect(title.textContent.trim()).toBe("Living Room: Starting KEXP...");
    expect(station.getAttribute("color")).toBe("warning");
    expect(station.getAttribute("fill")).toBe("outline");
    expect(station.getAttribute("aria-busy")).toBe("true");
    expect(station.getAttribute("aria-pressed")).toBe("false");

    controlStore.set({
      ...controlStore.get(),
      requestedStation: null,
      failedStation: "KEXP",
    });
    await element.updateComplete;

    expect(title.textContent.trim()).toBe("Living Room: Failed KEXP");
    expect(station.getAttribute("color")).toBe("danger");
    expect(station.getAttribute("aria-invalid")).toBe("true");

    controlStore.set({
      ...controlStore.get(),
      requestedStation: "KEXP",
      failedStation: null,
    });
    await element.updateComplete;

    expect(station.getAttribute("color")).toBe("warning");
    expect(station.getAttribute("aria-busy")).toBe("true");
    expect(station.getAttribute("aria-invalid")).toBe("false");
  });
});
