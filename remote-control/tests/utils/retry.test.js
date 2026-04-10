import { describe, expect, it } from "vitest";
import {
  advanceRetryState,
  createRetryState,
  resetRetryState,
} from "../../src/js/utils/retry.js";

describe("retry helpers", () => {
  it("advances attempts and delay deterministically without jitter", () => {
    const state = createRetryState({
      initialDelayMs: 1000,
      factor: 2,
      jitterMs: 0,
      maxDelayMs: 5000,
    });

    expect(advanceRetryState(state)).toEqual({ attempt: 1, delayMs: 1000 });
    expect(advanceRetryState(state)).toEqual({ attempt: 2, delayMs: 2000 });
    expect(advanceRetryState(state)).toEqual({ attempt: 3, delayMs: 4000 });
    expect(advanceRetryState(state)).toEqual({ attempt: 4, delayMs: 5000 });
  });

  it("resets back to the initial delay and zero attempts", () => {
    const state = createRetryState({
      initialDelayMs: 750,
      factor: 2,
      jitterMs: 0,
      maxDelayMs: 5000,
    });

    advanceRetryState(state);
    advanceRetryState(state);
    resetRetryState(state);

    expect(state.attempt).toBe(0);
    expect(state.nextDelayMs).toBe(750);
  });
});
