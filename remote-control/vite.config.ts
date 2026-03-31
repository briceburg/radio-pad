import { defineConfig } from "vite";

export default defineConfig({
  root: "./src",
  envDir: "..",
  build: {
    outDir: "../dist",
    emptyOutDir: true,
  },
  test: {
    root: "./",
    environment: "jsdom",
    include: ["tests/**/*.test.js", "tests/**/*.spec.js"],
    globals: true,
  }
});
