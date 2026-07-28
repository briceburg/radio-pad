import { afterEach, describe, expect, it } from "vitest";
import {
  getControlTitle,
  getStationVisualState,
  isControlDegraded,
  RadioPlayerTab,
} from "../../src/js/ui/radio-player-tab.js";
import { controlStore } from "../../src/js/store.js";
import controllerTitleCases from "../../../shared/controller-title-cases.json";

afterEach(() => document.body.replaceChildren());

function controlTitleState(titleCase) {
  const playbackState = titleCase.playback_state;
  const playerStatuses = Object.fromEntries(
    titleCase.player_statuses.map(({ scope, ...status }) => [scope, status]),
  );

  return {
    connectionState: "connected",
    playerConnected: titleCase.player_available,
    player: { id: "living-room", name: "Living Room" },
    radioDial:
      titleCase.station_menu === null
        ? null
        : {
            name: "iCEBURG Radio",
            stations: titleCase.station_menu.map((callSign) => ({
              call_sign: callSign,
            })),
          },
    currentStation: playbackState.call_sign,
    requestedStation: playbackState.requested_call_sign,
    failedStation: playbackState.failed_call_sign,
    loading: titleCase.station_menu === null,
    playerStatuses,
    resourceStatuses: {},
  };
}

describe("radio-player-tab", () => {
  it("treats disconnected, unauthorized, and offline control states as degraded", () => {
    expect(isControlDegraded({ connectionState: "disconnected" })).toBe(true);
    expect(isControlDegraded({ connectionState: "unauthorized" })).toBe(true);
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

  it("derives a complete control title from controller state", () => {
    expect(
      getControlTitle({
        playerConnected: false,
        resourceStatuses: {
          registry: { level: "warning", summary: "Registry unavailable." },
        },
      }),
    ).toBe("Waiting for Player");
    expect(
      getControlTitle({
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
    expect(
      getControlTitle({
        connectionState: "unauthorized",
        connectionMessage: "Session expired—sign in again.",
      }),
    ).toBe("Session expired—sign in again.");
    expect(
      getControlTitle({
        connectionState: "connected",
        playerConnected: true,
        player: { name: "Living Room" },
        radioDial: { name: "iCEBURG Radio" },
        currentStation: "WWOZ",
        resourceStatuses: {
          registry: {
            level: "warning",
            summary: "Registry unavailable.",
          },
        },
      }),
    ).toBe("WWOZ");
  });

  it.each(controllerTitleCases)(
    "aligns the $name title with the shared controller contract",
    (titleCase) => {
      expect(getControlTitle(controlTitleState(titleCase))).toBe(
        titleCase.expected_title,
      );
    },
  );

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
      connectionMessage: null,
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
    expect(title.textContent.trim()).toBe("KEXP");
    expect(title.hasAttribute("size")).toBe(false);
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

    expect(title.textContent.trim()).toBe("Starting KEXP");
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

    expect(title.textContent.trim()).toBe("Failed KEXP");
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
