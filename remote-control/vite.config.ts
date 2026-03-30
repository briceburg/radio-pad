import { defineConfig } from "vite";

export default defineConfig({
  root: "./src",
  envDir: "..",
  build: {
    outDir: "../dist",
    minify: false,
    emptyOutDir: true,
  },
  test: {
    root: "./",
    environment: "jsdom",
    include: ["tests/**/*.test.js", "tests/**/*.spec.js"],
    globals: true,
  }
});
