import { defineConfig } from "vitest/config";

function trimEnv(name: string) {
  return process.env[name]?.trim();
}

export default defineConfig({
  root: "./src",
  envDir: "..",
  build: {
    outDir: "../dist",
    emptyOutDir: true,
  },
  server: {
    host: "0.0.0.0",
    proxy: {
      "/api": {
        target: trimEnv("RADIOPAD_REGISTRY_PROXY_TARGET") || "http://localhost:1980",
        changeOrigin: true,
      },
      "/switchboard": {
        target:
          trimEnv("RADIOPAD_SWITCHBOARD_PROXY_TARGET") ||
          trimEnv("RADIOPAD_REGISTRY_PROXY_TARGET") ||
          "ws://localhost:1980",
        changeOrigin: true,
        ws: true,
      },
    },
  },
  test: {
    root: "./",
    environment: "jsdom",
    include: ["tests/**/*.test.js", "tests/**/*.spec.js"],
    globals: true,
  }
});
