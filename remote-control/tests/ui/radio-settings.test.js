import { describe, expect, it } from "vitest";
import {
  getVisiblePreferences,
  groupPreferencesByGroup,
} from "../../src/js/ui/radio-settings.js";

describe("radio-settings helpers", () => {
  it("groups preference definitions by group and preserves their keys", () => {
    const grouped = groupPreferencesByGroup({
      accountId: { label: "Account", group: "radio-account" },
      presetId: { label: "Preset", group: "radio-listen" },
      unnamed: { label: "Fallback" },
    });

    expect(grouped["radio-account"]).toEqual([
      { key: "accountId", label: "Account", group: "radio-account" },
    ]);
    expect(grouped["radio-listen"]).toEqual([
      { key: "presetId", label: "Preset", group: "radio-listen" },
    ]);
    expect(grouped.default).toEqual([{ key: "unnamed", label: "Fallback" }]);
  });

  it("keeps only visible select preferences for the settings list", () => {
    const visiblePrefs = getVisiblePreferences([
      { key: "registryUrl", type: "text" },
      { key: "accountId", type: "select", options: [{ value: "only" }] },
      { key: "playerId", type: "select", options: [] },
      {
        key: "presetId",
        type: "select",
        options: [{ value: "a" }, { value: "b" }],
      },
    ]);

    expect(visiblePrefs).toEqual([
      { key: "registryUrl", type: "text" },
      {
        key: "presetId",
        type: "select",
        options: [{ value: "a" }, { value: "b" }],
      },
    ]);
  });
});
