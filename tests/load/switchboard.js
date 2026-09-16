import exec from "k6/execution";
import http from "k6/http";
import { Counter, Rate, Trend } from "k6/metrics";
import { WebSocket } from "k6/websockets";

function required(name) {
  const value = __ENV[name];
  if (!value) {
    throw new Error(`${name} is required`);
  }
  return value.replace(/\/+$/, "");
}

function integer(name, fallback, minimum) {
  const value = Number(__ENV[name] ?? fallback);
  if (!Number.isInteger(value) || value < minimum) {
    throw new Error(`${name} must be an integer >= ${minimum}`);
  }
  return value;
}

function number(name, fallback, minimum) {
  const value = Number(__ENV[name] ?? fallback);
  if (!Number.isFinite(value) || value < minimum) {
    throw new Error(`${name} must be a number >= ${minimum}`);
  }
  return value;
}

function boolean(name, fallback) {
  const value = __ENV[name];
  if (value === undefined) {
    return fallback;
  }
  if (value !== "0" && value !== "1") {
    throw new Error(`${name} must be 0 or 1`);
  }
  return value === "1";
}

function slug(name, fallback) {
  const value = __ENV[name] ?? fallback;
  if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(value) || value.length > 36) {
    throw new Error(
      `${name} must be a lowercase slug of at most 36 characters`,
    );
  }
  return value;
}

const registryUrl = required("REGISTRY_URL");
const switchboardUrl = required("SWITCHBOARD_URL");
const players = integer("RADIOPAD_LOAD_PLAYERS", 10, 1);
const roomsPerVu = integer("RADIOPAD_LOAD_ROOMS_PER_VU", 10, 1);
const controllersPerPlayer = integer(
  "RADIOPAD_LOAD_CONTROLLERS_PER_PLAYER",
  1,
  0,
);
const rampSeconds = number("RADIOPAD_LOAD_RAMP_SECONDS", 10, 0);
const holdSeconds = number("RADIOPAD_LOAD_HOLD_SECONDS", 30, 1);
const drainSeconds = number("RADIOPAD_LOAD_DRAIN_SECONDS", 1, 0);
const eventIntervalMs = integer("RADIOPAD_LOAD_EVENT_INTERVAL_MS", 1000, 1);
const registerPlayers = boolean("RADIOPAD_LOAD_REGISTER_PLAYERS", true);
const accountId = slug("RADIOPAD_LOAD_ACCOUNT", "load-test");
const playerPrefix = slug("RADIOPAD_LOAD_PLAYER_PREFIX", "load-player");
const accessToken = __ENV.RADIOPAD_LOAD_ACCESS_TOKEN ?? null;
const radioDialUrl = (
  __ENV.RADIOPAD_LOAD_RADIO_DIAL_URL ??
  `${registryUrl}/accounts/community/radio-dials/briceburg`
).replace(/\/+$/, "");
const radioDialRevision =
  __ENV.RADIOPAD_LOAD_RADIO_DIAL_REVISION ?? '"load-test"';
const idWidth = Math.max(
  integer("RADIOPAD_LOAD_PLAYER_ID_WIDTH", 6, 1),
  String(players).length,
);
const virtualUsers = Math.ceil(players / roomsPerVu);
const maximumPlayerId = `${playerPrefix}-${String(players).padStart(idWidth, "0")}`;

if (maximumPlayerId.length > 36) {
  throw new Error(
    "generated player IDs exceed the Registry's 36-character limit",
  );
}

const outcomes = new Rate("outcomes");
const connectionLatency = new Trend("connection_latency", true);
const authenticationLatency = new Trend("authentication_latency", true);
const fanoutLatency = new Trend("fanout_latency", true);
const commandLatency = new Trend("command_latency", true);
const socketErrors = new Counter("socket_errors");

export const options = {
  discardResponseBodies: true,
  scenarios: {
    rooms: {
      executor: "per-vu-iterations",
      exec: "rooms",
      vus: virtualUsers,
      iterations: 1,
      maxDuration: `${Math.ceil(rampSeconds + holdSeconds + drainSeconds + 30)}s`,
    },
  },
  thresholds: {
    "outcomes{kind:connection}": ["rate>0.99"],
    "outcomes{kind:disconnect}": ["rate>0.99"],
    ...(controllersPerPlayer > 0
      ? {
          "outcomes{kind:authentication}": ["rate>0.99"],
          "outcomes{kind:fanout}": ["rate>0.99"],
          "outcomes{kind:command}": ["rate>0.99"],
        }
      : {}),
    socket_errors: ["count==0"],
  },
};

function playerId(index) {
  return `${playerPrefix}-${String(index + 1).padStart(idWidth, "0")}`;
}

export function setup() {
  if (!registerPlayers) {
    return;
  }

  const headers = { "Content-Type": "application/json" };
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }

  const registration = (index) => ({
    method: "PUT",
    url: `${registryUrl}/accounts/${accountId}/players/${playerId(index)}`,
    body: JSON.stringify({
      name: `Load player ${index + 1}`,
      radio_dial: null,
    }),
    params: { headers, tags: { operation: "register_load_player" } },
  });

  const first = registration(0);
  const firstResponse = http.put(first.url, first.body, first.params);
  if (firstResponse.status !== 200) {
    throw new Error(
      `player registration failed with HTTP ${firstResponse.status}`,
    );
  }

  for (let offset = 1; offset < players; offset += 100) {
    const requests = [];
    for (
      let index = offset;
      index < Math.min(offset + 100, players);
      index += 1
    ) {
      requests.push(registration(index));
    }

    const responses = http.batch(requests);
    const failure = responses.find((response) => response.status !== 200);
    if (failure) {
      throw new Error(`player registration failed with HTTP ${failure.status}`);
    }
  }
}

function parseMessage(message) {
  try {
    return JSON.parse(message.data);
  } catch (_error) {
    return null;
  }
}

function loadMarker(payload, expectedPlayerId) {
  const marker = payload && payload.data && payload.data.load_test;
  if (!marker || marker.player_id !== expectedPlayerId) {
    return null;
  }
  return marker;
}

function send(socket, event, data) {
  if (socket.readyState === 1) {
    socket.send(JSON.stringify({ event, data }));
    return true;
  }
  return false;
}

function openRoom(index, rampDelay) {
  const roomPlayerId = playerId(index);
  const roomUrl = `${switchboardUrl}/${accountId}/${roomPlayerId}`;
  const controllers = [];
  let authenticatedControllers = 0;
  let fanoutSent = 0;
  let commandsSent = 0;
  let trafficTimer = null;
  let closing = false;

  const playerState = {
    outcomeRecorded: false,
    commandsReceived: 0,
  };
  const playerStartedAt = Date.now();
  const player = new WebSocket(roomUrl, null, {
    headers: {
      "User-Agent": "RadioPad/load-test",
      "RadioPad-Radio-Dial-Url": radioDialUrl,
      "RadioPad-Radio-Dial-Revision": radioDialRevision,
    },
    tags: { role: "player" },
  });

  function recordConnection(state, succeeded, startedAt) {
    if (state.outcomeRecorded) {
      return;
    }
    state.outcomeRecorded = true;
    outcomes.add(succeeded, { kind: "connection" });
    if (succeeded) {
      connectionLatency.add(Date.now() - startedAt);
    }
  }

  function startTraffic() {
    if (
      trafficTimer !== null ||
      authenticatedControllers !== controllersPerPlayer
    ) {
      return;
    }

    const publish = () => {
      const sentAt = Date.now();
      fanoutSent += 1;
      send(player, "playback_state", {
        call_sign: null,
        requested_call_sign: null,
        failed_call_sign: null,
        load_test: {
          player_id: roomPlayerId,
          sequence: fanoutSent,
          sent_at: sentAt,
        },
      });

      if (controllers.length > 0) {
        commandsSent += 1;
        send(controllers[0].socket, "volume_up", {
          load_test: {
            player_id: roomPlayerId,
            sequence: commandsSent,
            sent_at: sentAt,
          },
        });
      }
    };

    publish();
    trafficTimer = setInterval(publish, eventIntervalMs);
  }

  function openControllers() {
    for (
      let controllerIndex = 0;
      controllerIndex < controllersPerPlayer;
      controllerIndex += 1
    ) {
      const state = {
        socket: null,
        outcomeRecorded: false,
        authenticationRecorded: false,
        fanoutReceived: 0,
      };
      const startedAt = Date.now();
      const controller = new WebSocket(roomUrl, null, {
        tags: { role: "controller" },
      });
      state.socket = controller;
      controllers.push(state);

      controller.addEventListener("open", () => {
        state.authenticationStartedAt = Date.now();
        recordConnection(state, true, startedAt);
        send(controller, "authenticate", { token: accessToken });
      });

      controller.addEventListener("message", (message) => {
        const payload = parseMessage(message);
        if (!payload) {
          return;
        }
        if (
          payload.event === "authenticated" &&
          !state.authenticationRecorded
        ) {
          state.authenticationRecorded = true;
          outcomes.add(true, { kind: "authentication" });
          authenticationLatency.add(Date.now() - state.authenticationStartedAt);
          authenticatedControllers += 1;
          startTraffic();
          return;
        }

        const marker = loadMarker(payload, roomPlayerId);
        if (payload.event === "playback_state" && marker) {
          state.fanoutReceived += 1;
          outcomes.add(true, { kind: "fanout" });
          fanoutLatency.add(Date.now() - marker.sent_at);
        }
      });

      controller.addEventListener("error", () => {
        if (!closing) {
          socketErrors.add(1, { role: "controller" });
          controller.close();
        }
      });

      controller.addEventListener("close", () => {
        recordConnection(state, false, startedAt);
        if (!state.authenticationRecorded) {
          state.authenticationRecorded = true;
          outcomes.add(false, { kind: "authentication" });
        }
        outcomes.add(closing, { kind: "disconnect" });
      });
    }
  }

  player.addEventListener("open", () => {
    recordConnection(playerState, true, playerStartedAt);
    openControllers();
    startTraffic();
  });

  player.addEventListener("message", (message) => {
    const payload = parseMessage(message);
    const marker = loadMarker(payload, roomPlayerId);
    if (payload && payload.event === "volume_up" && marker) {
      playerState.commandsReceived += 1;
      outcomes.add(true, { kind: "command" });
      commandLatency.add(Date.now() - marker.sent_at);
    }
  });

  player.addEventListener("error", () => {
    if (!closing) {
      socketErrors.add(1, { role: "player" });
      player.close();
    }
  });

  player.addEventListener("close", () => {
    recordConnection(playerState, false, playerStartedAt);
    outcomes.add(closing, { kind: "disconnect" });
  });

  const activeMilliseconds = (rampSeconds - rampDelay + holdSeconds) * 1000;
  setTimeout(() => {
    if (trafficTimer !== null) {
      clearInterval(trafficTimer);
    }

    setTimeout(() => {
      for (const controller of controllers) {
        const missing = Math.max(fanoutSent - controller.fanoutReceived, 0);
        for (let count = 0; count < missing; count += 1) {
          outcomes.add(false, { kind: "fanout" });
        }
      }
      for (
        let count = playerState.commandsReceived;
        count < commandsSent;
        count += 1
      ) {
        outcomes.add(false, { kind: "command" });
      }

      closing = true;
      for (const controller of controllers) {
        controller.socket.close();
      }
      player.close();
    }, drainSeconds * 1000);
  }, activeMilliseconds);
}

export function rooms() {
  const first = (exec.vu.idInTest - 1) * roomsPerVu;
  const last = Math.min(first + roomsPerVu, players);

  for (let index = first; index < last; index += 1) {
    const rampDelay = players === 1 ? 0 : (index / (players - 1)) * rampSeconds;
    setTimeout(() => openRoom(index, rampDelay), rampDelay * 1000);
  }
}
