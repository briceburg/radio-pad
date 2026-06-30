import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  discoverAccounts,
  discoverAuthEnabled,
  discoverPlayer,
  discoverPlayers,
  discoverRadioDials,
} from "../../src/js/services/registry-discovery.js";

const response = (value) => ({ ok: true, json: async () => value });
const page = (items, links = {}) => response({ items, links });

describe("Registry Discovery", () => {
  beforeEach(() => {
    global.fetch = vi.fn();
  });

  it("discoverAccounts handles basic pagination", async () => {
    // Mock the first fetch response containing a 'next' link
    global.fetch.mockResolvedValueOnce(
      page([{ id: "acct1", name: "Account One" }], {
        next: "/v1/accounts?page=2",
      }),
    );

    // Mock the second fetch response (no next link)
    global.fetch.mockResolvedValueOnce(
      page([{ id: "acct2", name: "Account Two" }]),
    );

    const accounts = await discoverAccounts("http://mock-registry");

    expect(global.fetch).toHaveBeenCalledTimes(2);
    // Should extract map { value, label } output correctly
    expect(accounts).toEqual([
      { value: "acct1", label: "Account One" },
      { value: "acct2", label: "Account Two" },
    ]);
  });

  it("discoverAccounts resolves relative registry paths against the browser origin", async () => {
    global.fetch.mockResolvedValueOnce(
      page([{ id: "acct1", name: "Account One" }]),
    );

    await discoverAccounts("/api/");

    expect(global.fetch).toHaveBeenCalledWith(
      "http://localhost:3000/api/accounts/",
      {},
    );
  });

  it("discovers whether registry auth is enabled", async () => {
    global.fetch.mockResolvedValueOnce(response({ enabled: false }));

    await expect(discoverAuthEnabled("/api/")).resolves.toBe(false);
    expect(global.fetch).toHaveBeenCalledWith(
      "http://localhost:3000/api/auth/status",
      {},
    );
  });

  it("keeps player reads public when the remote is signed out", async () => {
    global.fetch
      .mockResolvedValueOnce(page([{ id: "living-room", name: "Living Room" }]))
      .mockResolvedValueOnce(
        response({
          id: "living-room",
          name: "Living Room",
          radio_dial: "community/briceburg",
        }),
      );
    const auth = { signedIn: false };

    await expect(discoverPlayers("briceburg", "/api/", auth)).resolves.toEqual([
      { value: "living-room", label: "Living Room" },
    ]);
    await expect(
      discoverPlayer("briceburg", "living-room", "/api/", auth),
    ).resolves.toMatchObject({
      id: "living-room",
      configured_radio_dial_url:
        "http://localhost:3000/api/accounts/community/radio-dials/briceburg",
      switchboard_url: "ws://localhost:3000/switchboard/briceburg/living-room",
    });
  });

  it("discovers account and public community RadioDials", async () => {
    global.fetch
      .mockResolvedValueOnce(
        page([{ key: "briceburg/home", name: "Home", discoverable: false }]),
      )
      .mockResolvedValueOnce(
        page([
          { key: "community/shared", name: "Shared", discoverable: true },
          { key: "community/private", name: "Private", discoverable: false },
        ]),
      );

    const radioDials = await discoverRadioDials(
      "briceburg",
      "https://registry.example/api/",
    );

    expect(radioDials).toEqual([
      { value: "briceburg/home", label: "Home · briceburg" },
      { value: "community/shared", label: "Shared · community" },
    ]);
  });
});
