import { defineConfig } from "vitest/config";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const sourceRoot = fileURLToPath(new URL("./src", import.meta.url));
const manifestPath = path.join(sourceRoot, "manifest.webmanifest");
const manifestIconRoot = path.join(sourceRoot, "assets", "icons");

function trimEnv(name) {
  return process.env[name]?.trim();
}

function emitManifestIcons() {
  return {
    name: "emit-manifest-icons",
    async generateBundle() {
      const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
      if (!Array.isArray(manifest.icons)) {
        throw new Error("The web app manifest must define an icons array.");
      }

      for (const icon of manifest.icons) {
        if (typeof icon.src !== "string") {
          throw new Error("Every web app manifest icon must define a path.");
        }
        const fileName = icon.src.replace(/^\/+/, "");
        const sourcePath = path.resolve(sourceRoot, fileName);
        const normalizedFileName = path
          .relative(sourceRoot, sourcePath)
          .split(path.sep)
          .join("/");
        if (
          fileName !== normalizedFileName ||
          path.dirname(sourcePath) !== manifestIconRoot
        ) {
          throw new Error(`Unexpected manifest icon path: ${icon.src}`);
        }
        this.emitFile({
          type: "asset",
          fileName,
          source: await readFile(sourcePath),
        });
      }
    },
  };
}

export default defineConfig({
  root: "./src",
  envDir: "..",
  publicDir: "../node_modules/@ionic/core/dist/ionic",
  plugins: [emitManifestIcons()],
  build: {
    outDir: "../dist",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        app: fileURLToPath(new URL("./src/index.html", import.meta.url)),
        privacy: fileURLToPath(
          new URL("./src/privacy/index.html", import.meta.url),
        ),
      },
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
