import { describe, expect, it } from "vitest";
import {
  getControlStatusText,
  getStationButtonColor,
  getStationVisualState,
  isControlDegraded,
} from "../../src/js/ui/radio-player-tab.js";

describe("radio-player-tab visual helpers", () => {
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

  it("derives control status text from connection and retained statuses", () => {
    expect(
      getControlStatusText({
        playerConnected: false,
        resourceStatuses: {
          registry: { level: "warning", summary: "Registry unavailable." },
        },
      }),
    ).toBe("Player offline.");
    expect(
      getControlStatusText({
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

  it("derives station visual states and button colors", () => {
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
    expect(getStationButtonColor("warning", false)).toBe("warning");
    expect(getStationButtonColor("warning", true)).toBe("success");
  });
});
