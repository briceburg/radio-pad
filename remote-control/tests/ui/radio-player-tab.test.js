import { describe, expect, it } from "vitest";
import {
  getRegistryStatusText,
  getStationButtonColor,
  getStationVisualState,
  getTitlePrefix,
  getTitleSuffix,
  shouldRenderSkeleton,
} from "../../src/js/ui/radio-player-tab.js";

describe("radio-player-tab helpers", () => {
  it("uses the shared registry status text in titles", () => {
    expect(getRegistryStatusText({ phase: "loading", retryAttempt: 0 })).toBe(
      "Connecting to Registry",
    );
    expect(getRegistryStatusText({ phase: "retrying", retryAttempt: 1 })).toBe(
      "Connecting to Registry",
    );
  });

  it("derives control and listen title prefixes", () => {
    expect(getTitlePrefix("control", { player: { name: "Living Room" } })).toBe(
      "Living Room",
    );
    expect(getTitlePrefix("listen", { titleName: "Casa Briceburg" })).toBe(
      "Casa Briceburg",
    );
  });

  it("shows registry attempt messaging before station data is loaded", () => {
    expect(
      getTitleSuffix(
        "control",
        { currentStation: null, loading: false, player: { id: null } },
        { phase: "loading", retryAttempt: 0, errorText: "" },
      ),
    ).toBe("Connecting to Registry");

    expect(
      getTitleSuffix(
        "listen",
        { currentStation: null, loading: false, stationsData: null },
        { phase: "retrying", retryAttempt: 2, errorText: "" },
      ),
    ).toBe("Connecting to Registry");
  });

  it("renders skeletons for pending registry discovery", () => {
    expect(
      shouldRenderSkeleton(
        "control",
        { loading: false, player: { id: null }, stationsData: null },
        { phase: "loading" },
      ),
    ).toBe(true);
    expect(
      shouldRenderSkeleton(
        "listen",
        { loading: false, stationsData: null },
        { phase: "retrying" },
      ),
    ).toBe(true);
  });

  it("uses warning visuals for degraded control stations", () => {
    expect(
      getStationVisualState(
        "control",
        {
          loading: false,
          stationsData: { stations: [] },
          connectionState: "disconnected",
        },
        { phase: "ready" },
      ),
    ).toBe("warning");

    expect(getStationButtonColor("warning", false)).toBe("warning");
    expect(getStationButtonColor("warning", true)).toBe("success");
  });

  it("uses loading visuals while stations are still being fetched", () => {
    expect(
      getStationVisualState(
        "control",
        { loading: true, player: { id: "living-room" }, stationsData: null },
        { phase: "ready" },
      ),
    ).toBe("loading");

    expect(
      getStationVisualState(
        "listen",
        { loading: false, stationsData: null },
        { phase: "loading" },
      ),
    ).toBe("loading");
  });
});
