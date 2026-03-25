import { defineConfig } from "vite";

export default defineConfig({
  root: "./src",
  envDir: "..",
  build: {
    outDir: "../dist",
    minify: false,
    emptyOutDir: true,
  },
});
