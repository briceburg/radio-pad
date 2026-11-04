import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import sharp from "sharp";
import { JSDOM } from "jsdom";

const projectRoot = fileURLToPath(new URL(".", import.meta.url));
const dist = path.join(projectRoot, "dist");
const index = new JSDOM(await readFile(path.join(dist, "index.html"), "utf8"))
  .window.document;
const privacy = new JSDOM(
  await readFile(path.join(dist, "privacy", "index.html"), "utf8"),
).window.document;

function distPathFromUrl(url) {
  const parsed = new URL(url, "https://remote.radiopad.dev/");
  assert(
    parsed.origin === "https://remote.radiopad.dev",
    `Expected a same-origin asset URL, received ${url}`,
  );
  return path.join(
    dist,
    decodeURIComponent(parsed.pathname).replace(/^\/+/, ""),
  );
}

async function assertPng(url, size, description) {
  const assetPath = distPathFromUrl(url);
  await access(assetPath);
  const metadata = await sharp(assetPath).metadata();
  assert(
    metadata.format === "png" &&
      metadata.width === size &&
      metadata.height === size,
    `${description} must be a ${size}x${size} PNG.`,
  );
}

async function assertHtmlIcon(document, page, rel, size) {
  const link = document.querySelector(
    `link[rel="${rel}"][sizes="${size}x${size}"]`,
  );
  assert(link, `The ${page} HTML is missing rel=${rel} ${size}x${size}.`);
  await assertPng(link.getAttribute("href"), size, `The rel=${rel} asset`);
}

const manifestLink = index.querySelector('link[rel="manifest"]');
assert(manifestLink, "The production HTML does not link a web app manifest.");
const manifestHref = manifestLink.getAttribute("href");
const manifest = JSON.parse(
  await readFile(distPathFromUrl(manifestHref), "utf8"),
);

const expectedManifest = {
  id: "/",
  name: "RadioPad Remote Control",
  short_name: "RadioPad",
  start_url: "/",
  scope: "/",
  display: "standalone",
  background_color: "#ffffff",
  theme_color: "#31d53d",
};

for (const [key, expected] of Object.entries(expectedManifest)) {
  assert(
    manifest[key] === expected,
    `Expected manifest ${key} to be ${JSON.stringify(expected)}.`,
  );
}

assert(Array.isArray(manifest.icons), "The manifest must define icons.");
const manifestBase = new URL(manifestHref, "https://remote.radiopad.dev/");
const iconPurposes = new Set();
for (const icon of manifest.icons) {
  assert(icon.type === "image/png", `${icon.src} must declare image/png.`);
  assert(
    /^\d+x\d+$/.test(icon.sizes),
    `${icon.src} must declare one concrete size.`,
  );
  const [width, height] = icon.sizes.split("x").map(Number);
  assert(width === height, `${icon.src} must be square.`);
  await assertPng(
    new URL(icon.src, manifestBase).href,
    width,
    `${icon.src} content`,
  );
  iconPurposes.add(`${icon.purpose || "any"}:${icon.sizes}`);
}

for (const requiredIcon of ["any:192x192", "any:512x512"]) {
  assert(
    iconPurposes.has(requiredIcon),
    `The manifest is missing ${requiredIcon}.`,
  );
}

assert(
  index.querySelector('meta[name="apple-mobile-web-app-capable"]')?.content ===
    "yes",
  "The production HTML must enable legacy iOS standalone mode.",
);
assert(
  index.querySelector('meta[name="apple-mobile-web-app-title"]')?.content ===
    "RadioPad",
  "The production HTML must define the iOS Home Screen title.",
);

for (const [page, document] of [
  ["application", index],
  ["privacy", privacy],
]) {
  for (const size of [16, 32, 256]) {
    await assertHtmlIcon(document, page, "icon", size);
  }
}
await assertHtmlIcon(index, "application", "apple-touch-icon", 180);

assert(
  index.querySelector('meta[name="theme-color"]')?.content ===
    manifest.theme_color,
  "HTML and manifest theme colors must match.",
);

console.log("Validated production PWA metadata and assets.");
