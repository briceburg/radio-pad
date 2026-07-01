import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getVisiblePreferences,
  groupPreferencesByGroup,
  preferenceValues,
  RadioSettings,
} from "../../src/js/ui/radio-settings.js";
import { preferencesStore, settingsUiStore } from "../../src/js/store.js";

const SETTINGS_DEFINITIONS = {
  accountId: {
    type: "select",
    label: "Account",
    value: "briceburg",
    options: [
      { value: "briceburg", label: "Briceburg" },
      { value: "pinecrest", label: "Pinecrest" },
    ],
    group: "radio-account",
  },
  playerId: {
    type: "select",
    label: "Player",
    placeholder: "Choose a player",
    value: "living-room",
    options: [{ value: "living-room", label: "Living Room" }],
    group: "radio-control",
  },
  radioDial: {
    type: "select",
    label: "RadioDial",
    value: "community/briceburg",
    options: [{ value: "community/briceburg", label: "Casa Briceburg" }],
    group: "radio-listen",
  },
  registryUrl: {
    type: "text",
    label: "Registry URL",
    value: "https://registry.example/api/",
    group: "radio-advanced",
  },
};

afterEach(() => document.body.replaceChildren());

async function renderSettings(overrides = {}) {
  const definitions = Object.fromEntries(
    Object.entries(SETTINGS_DEFINITIONS).map(([key, pref]) => [
      key,
      {
        ...pref,
        ...overrides[key],
        options: [...(overrides[key]?.options || pref.options || [])],
      },
    ]),
  );
  preferencesStore.set({ definitions });
  settingsUiStore.set({ saveState: "idle" });

  const element = new RadioSettings();
  document.body.append(element);
  await element.updateComplete;
  return element;
}

describe("radio-settings helpers", () => {
  it("groups preference definitions by group and preserves their keys", () => {
    const grouped = groupPreferencesByGroup({
      accountId: { label: "Account", group: "radio-account" },
      radioDial: { label: "RadioDial", group: "radio-listen" },
      unnamed: { label: "Fallback" },
    });

    expect(grouped["radio-account"]).toEqual([
      { key: "accountId", label: "Account", group: "radio-account" },
    ]);
    expect(grouped["radio-listen"]).toEqual([
      { key: "radioDial", label: "RadioDial", group: "radio-listen" },
    ]);
    expect(grouped.default).toEqual([{ key: "unnamed", label: "Fallback" }]);
  });

  it("keeps only visible select preferences for the settings list", () => {
    const visiblePrefs = getVisiblePreferences([
      { key: "registryUrl", type: "text" },
      { key: "accountId", type: "select", options: [{ value: "only" }] },
      { key: "playerId", type: "select", options: [] },
      {
        key: "radioDial",
        type: "select",
        options: [{ value: "a" }, { value: "b" }],
      },
    ]);

    expect(visiblePrefs).toEqual([
      { key: "registryUrl", type: "text" },
      {
        key: "radioDial",
        type: "select",
        options: [{ value: "a" }, { value: "b" }],
      },
    ]);
  });

  it("overlays draft values without mutating persisted settings", () => {
    const preferences = {
      accountId: { value: "briceburg" },
      registryUrl: { value: "https://registry.example/api/" },
    };
    const drafts = { accountId: "pinecrest" };

    expect(preferenceValues(preferences, drafts)).toEqual({
      accountId: "pinecrest",
      registryUrl: "https://registry.example/api/",
    });
  });

  it("suppresses stale dependent choices until the changed account is saved", async () => {
    const element = await renderSettings();
    const saveButton = element.querySelector("#settings-save-button");
    expect(saveButton.disabled).toBe(true);

    const account = element.querySelector("#pref-accountId");
    expect(element.querySelector("#pref-playerId").placeholder).toBe(
      "Choose a player",
    );
    account.dispatchEvent(
      new CustomEvent("ionChange", { detail: { value: "pinecrest" } }),
    );
    await element.updateComplete;
    expect(saveButton.disabled).toBe(false);

    expect(element.querySelector("#pref-playerId")).toBeNull();
    expect(element.querySelector("#pref-radioDial")).toBeNull();
    const notice = element
      .querySelector("#account-save-required")
      ?.textContent.replace(/\s+/g, " ");
    expect(notice).toContain("Save this account change");
    expect(notice).toContain("Your current player stays active until then.");

    const onSave = vi.fn();
    element.addEventListener("settings-save", onSave);
    element.querySelector("#settings-save-button").click();
    expect(onSave.mock.calls[0][0].detail).toMatchObject({
      accountId: "pinecrest",
      playerId: "living-room",
      radioDial: "community/briceburg",
    });

    account.dispatchEvent(
      new CustomEvent("ionChange", { detail: { value: "briceburg" } }),
    );
    await element.updateComplete;

    expect(element.querySelector("#pref-playerId")).not.toBeNull();
    expect(element.querySelector("#pref-radioDial")).not.toBeNull();
    expect(element.querySelector("#account-save-required")).toBeNull();
    expect(saveButton.disabled).toBe(true);

    settingsUiStore.set({ saveState: "saving" });
    await element.updateComplete;
    settingsUiStore.set({ saveState: "saved" });
    await element.updateComplete;
    expect(element.draftValues).toEqual({});
    expect(saveButton.disabled).toBe(true);
    element.remove();
  });

  it("uses an Ionic accordion for Advanced without losing its draft", async () => {
    const element = await renderSettings();
    const accordion = element.querySelector("ion-accordion[value=advanced]");
    const header = accordion.querySelector("ion-item[slot=header]");
    const content = accordion.querySelector("[slot=content]");

    expect(accordion.closest("ion-accordion-group")).not.toBeNull();
    expect(header.getAttribute("color")).toBe("tertiary");
    expect(header.querySelector("ion-icon")?.getAttribute("aria-hidden")).toBe(
      "true",
    );
    expect(content.querySelector("#pref-registryUrl").label).toBe(
      "Registry URL",
    );

    content.querySelector("#pref-registryUrl").dispatchEvent(
      new CustomEvent("ionInput", {
        detail: { value: "https://new-registry.example/api/" },
      }),
    );
    await element.updateComplete;

    const onSave = vi.fn();
    element.addEventListener("settings-save", onSave);
    element.querySelector("#settings-save-button").click();
    expect(onSave.mock.calls[0][0].detail.registryUrl).toBe(
      "https://new-registry.example/api/",
    );
    element.remove();
  });

  it("updates select options without replacing the Ionic control", async () => {
    const element = await renderSettings();
    const select = element.querySelector("#pref-playerId");

    preferencesStore.set({
      definitions: {
        ...SETTINGS_DEFINITIONS,
        playerId: {
          ...SETTINGS_DEFINITIONS.playerId,
          value: "kitchen",
          options: [{ value: "kitchen", label: "Kitchen" }],
        },
      },
    });
    await element.updateComplete;

    expect(element.querySelector("#pref-playerId")).toBe(select);
    expect(
      select.querySelector("ion-select-option").getAttribute("value"),
    ).toBe("kitchen");
    expect(select.querySelector("ion-select-option").textContent).toContain(
      "Kitchen",
    );
    element.remove();
  });

  it("shows empty states for account-dependent options", async () => {
    const element = await renderSettings({
      playerId: { value: null, options: [] },
      radioDial: { value: null, options: [] },
    });

    expect(element.querySelector("#empty-playerId")?.textContent).toContain(
      "No players are available for this account.",
    );
    expect(element.querySelector("#empty-radioDial")?.textContent).toContain(
      "No RadioDials are available for this account.",
    );
    expect(element.querySelector("#pref-playerId")).toBeNull();
    expect(element.querySelector("#pref-radioDial")).toBeNull();
    element.remove();
  });
});
