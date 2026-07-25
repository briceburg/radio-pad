import { access, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import sharp from "sharp";

const projectRoot = fileURLToPath(new URL(".", import.meta.url));
const dist = path.join(projectRoot, "dist");
const indexHtml = await readFile(path.join(dist, "index.html"), "utf8");

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function attribute(tag, name) {
  const match = tag?.match(
    new RegExp(`\\b${name}=(?:"([^"]*)"|'([^']*)')`, "i"),
  );
  return match?.[1] ?? match?.[2];
}

function findTag(element, attributeName, attributeValue, size) {
  return [...indexHtml.matchAll(new RegExp(`<${element}\\b[^>]*>`, "gi"))]
    .map(([tag]) => tag)
    .find(
      (tag) =>
        attribute(tag, attributeName) === attributeValue &&
        (!size || attribute(tag, "sizes") === `${size}x${size}`),
    );
}

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

const manifestLink = findTag("link", "rel", "manifest");
assert(manifestLink, "The production HTML does not link a web app manifest.");
const manifestHref = attribute(manifestLink, "href");
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

const appleCapable = findTag("meta", "name", "apple-mobile-web-app-capable");
assert(
  attribute(appleCapable, "content") === "yes",
  "The production HTML must enable legacy iOS standalone mode.",
);
const appleTitle = findTag("meta", "name", "apple-mobile-web-app-title");
assert(
  attribute(appleTitle, "content") === "RadioPad",
  "The production HTML must define the iOS Home Screen title.",
);

for (const [rel, expectedSize] of [
  ["icon", 16],
  ["icon", 32],
  ["icon", 256],
  ["apple-touch-icon", 180],
]) {
  const link = findTag("link", "rel", rel, expectedSize);
  assert(
    link,
    `The production HTML is missing rel=${rel} ${expectedSize}x${expectedSize}.`,
  );
  await assertPng(
    attribute(link, "href"),
    expectedSize,
    `The rel=${rel} asset`,
  );
}

const themeColor = findTag("meta", "name", "theme-color");
assert(
  attribute(themeColor, "content") === manifest.theme_color,
  "HTML and manifest theme colors must match.",
);
await access(path.join(dist, "privacy", "index.html"));

console.log("Validated production PWA metadata and assets.");
