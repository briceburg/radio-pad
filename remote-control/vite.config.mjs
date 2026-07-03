import { defineConfig } from "vitest/config";

function trimEnv(name) {
  return process.env[name]?.trim();
}

export default defineConfig({
  root: "./src",
  envDir: "..",
  publicDir: "../node_modules/@ionic/core/dist/ionic",
  build: {
    outDir: "../dist",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks: undefined,
      },
      external: ["/ionic.esm.js"],
    },
  },
  server: {
    host: "0.0.0.0",
    proxy: {
      "/api": {
        target:
          trimEnv("RADIOPAD_REGISTRY_PROXY_TARGET") || "http://localhost:1980",
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
  },
});
