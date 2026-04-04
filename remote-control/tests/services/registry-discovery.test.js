import { describe, it, expect, vi, beforeEach } from "vitest";
import { discoverAccounts } from "../../src/js/services/registry-discovery.js";

describe("Registry Discovery", () => {
  beforeEach(() => {
    global.fetch = vi.fn();
  });

  it("discoverAccounts handles basic pagination", async () => {
    // Mock the first fetch response containing a 'next' link
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        items: [{ id: "acct1", name: "Account One" }],
        links: { next: "/v1/accounts?page=2" }
      })
    });

    // Mock the second fetch response (no next link)
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        items: [{ id: "acct2", name: "Account Two" }],
        links: {}
      })
    });

    const accounts = await discoverAccounts("http://mock-registry");
    
    expect(global.fetch).toHaveBeenCalledTimes(2);
    // Should extract map { value, label } output correctly
    expect(accounts).toEqual([
      { value: "acct1", label: "Account One" },
      { value: "acct2", label: "Account Two" }
    ]);
  });

  it("discoverAccounts resolves relative registry paths against the browser origin", async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        items: [{ id: "acct1", name: "Account One" }],
        links: {}
      })
    });

    await discoverAccounts("/api/");

    expect(global.fetch).toHaveBeenCalledWith(
      "http://localhost:3000/api/accounts/",
      {},
    );
  });
});
