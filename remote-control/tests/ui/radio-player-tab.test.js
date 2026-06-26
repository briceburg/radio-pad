import { describe, expect, it } from "vitest";
import {
  getStationButtonColor,
  getStationVisualState,
  isControlDegraded,
} from "../../src/js/ui/radio-player-tab.js";

describe("radio-player-tab visual helpers", () => {
  it("treats disconnected and offline control states as degraded", () => {
    expect(isControlDegraded({ connectionState: "disconnected" })).toBe(true);
    expect(isControlDegraded({ playerConnected: false })).toBe(true);
  });

  it("treats station and switchboard warnings as degraded", () => {
    expect(
      isControlDegraded({
        connectionState: "connected",
        playerConnected: true,
        playerStatuses: {
          switchboard: { level: "warning", summary: "Switchboard down" },
        },
      }),
    ).toBe(true);
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
