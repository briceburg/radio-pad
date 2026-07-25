import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import sharp from "sharp";

const projectRoot = fileURLToPath(new URL("..", import.meta.url));
const repositoryRoot = path.resolve(projectRoot, "..");
const sharedAssets = path.join(repositoryRoot, "shared", "assets");
const webAssets = path.join(projectRoot, "src", "assets", "icons");
const androidResources = path.join(
  projectRoot,
  "android",
  "app",
  "src",
  "main",
  "res",
);
const iosAssets = path.join(
  projectRoot,
  "ios",
  "App",
  "App",
  "Assets.xcassets",
);

// The green glow mimics a keycap LED; app-icon-background.svg owns its geometry.
const sources = {
  foreground: path.join(sharedAssets, "app-icon-foreground.svg"),
  background: path.join(sharedAssets, "app-icon-background.svg"),
  splash: path.join(sharedAssets, "app-splash.svg"),
  splashDark: path.join(sharedAssets, "app-splash-dark.svg"),
};

const conventionalIconPadding = 0.1;
const adaptiveForegroundPadding = 0.14;
// Use a density-scaled base with modest low-density optical sizing.
const androidSplashLogoWidthDp = 96;
const androidLowDensitySplashOpticalScale = 1.125;
const iosSplashLogoScale = 0.22;

const pngOptions = {
  compressionLevel: 9,
  effort: 10,
};

let generatedCount = 0;

async function writePng(pipeline, destination) {
  await mkdir(path.dirname(destination), { recursive: true });
  await pipeline.png(pngOptions).toFile(destination);
  generatedCount += 1;
}

function sourceImage(source) {
  return sharp(source, { density: 384 });
}

async function renderSource(source, size, padding = 0) {
  const innerSize = Math.round(size * (1 - padding * 2));
  let pipeline = sourceImage(source).resize({
    width: innerSize,
    height: innerSize,
    fit: "contain",
  });
  if (innerSize > size) {
    const offset = Math.floor((innerSize - size) / 2);
    pipeline = pipeline.extract({
      left: offset,
      top: offset,
      width: size,
      height: size,
    });
  }
  return pipeline.png().toBuffer();
}

async function renderAsset(source, destination, size) {
  await writePng(sharp(await renderSource(source, size)), destination);
}

async function renderIcon(
  destination,
  size,
  { background, glow = false, padding = 0, round = false } = {},
) {
  const foreground = await renderSource(sources.foreground, size, padding);
  const layers = [{ input: foreground, gravity: "centre" }];
  let pipeline;

  if (round) {
    layers.push({
      input: Buffer.from(
        `<svg width="${size}" height="${size}"><circle cx="${size / 2}" cy="${size / 2}" r="${size / 2}" fill="#fff"/></svg>`,
      ),
      blend: "dest-in",
    });
  }

  if (glow) {
    const glowImage = await renderSource(sources.background, size);
    pipeline = background
      ? sharp({
          create: {
            width: size,
            height: size,
            channels: 4,
            background,
          },
        }).composite([{ input: glowImage }, ...layers])
      : sharp(glowImage).composite(layers);
  } else if (background || padding > 0 || round) {
    pipeline = sharp({
      create: {
        width: size,
        height: size,
        channels: 4,
        background: background ?? { r: 0, g: 0, b: 0, alpha: 0 },
      },
    }).composite(layers);
  } else {
    pipeline = sharp(foreground);
  }

  await writePng(
    background ? pipeline.flatten({ background }) : pipeline,
    destination,
  );
}

async function renderFavicons() {
  // Isolate the blue-plus keycap from the canonical 256px render without duplicating its artwork.
  const keycapBounds = { left: 80, top: 108, width: 100, height: 100 };
  const croppedKeycap = await sharp(await renderSource(sources.foreground, 256))
    .extract(keycapBounds)
    .png()
    .toBuffer();
  const keycap = await sharp(croppedKeycap)
    .trim()
    .resize({
      width: 192,
      height: 192,
      fit: "contain",
      background: "transparent",
    })
    .png()
    .toBuffer();
  // The solid green badge and thin edge stay visible on light and dark browser chrome.
  const badge = Buffer.from(
    '<svg width="256" height="256" xmlns="http://www.w3.org/2000/svg"><defs><radialGradient id="green" cx="50%" cy="62%" r="74%"><stop offset="0" stop-color="#86ff80"/><stop offset="64%" stop-color="#41db47"/><stop offset="100%" stop-color="#22a832"/></radialGradient></defs><rect x="6" y="6" width="244" height="244" rx="52" fill="url(#green)" stroke="#111111" stroke-width="8"/></svg>',
  );
  const favicon = await sharp(badge)
    .composite([{ input: keycap, gravity: "centre" }])
    .png()
    .toBuffer();
  await Promise.all(
    [16, 32, 256].map((outputSize) =>
      writePng(
        sharp(favicon).resize(outputSize, outputSize),
        path.join(webAssets, `favicon-${outputSize}.png`),
      ),
    ),
  );
}

async function validateGlow() {
  const alpha = (
    await sharp(await renderSource(sources.background, 160)).stats()
  ).channels[3];
  if (!alpha || alpha.min !== 0 || alpha.max !== 255) {
    throw new Error("The icon glow must fade to transparency.");
  }
}

async function renderSplash(
  source,
  destination,
  width,
  height,
  background,
  logoWidth,
) {
  let logoPipeline = sourceImage(source).resize({
    width: logoWidth,
    fit: "inside",
  });
  // Preserve small path and lettering edges after rasterization.
  if (
    logoWidth <=
    androidSplashLogoWidthDp * androidLowDensitySplashOpticalScale
  ) {
    logoPipeline = logoPipeline.sharpen();
  }
  const logo = await logoPipeline.png().toBuffer();
  const canvas = sharp({
    create: {
      width,
      height,
      channels: 4,
      background,
    },
  }).composite([{ input: logo, gravity: "centre" }]);
  await writePng(canvas.flatten({ background }), destination);
}

async function generateWebAssets() {
  await Promise.all([
    renderFavicons(),
    renderIcon(path.join(webAssets, "apple-touch-icon-180.png"), 180, {
      background: "#ffffff",
      glow: true,
      padding: conventionalIconPadding,
    }),
    renderIcon(path.join(webAssets, "icon-192.png"), 192),
    renderIcon(path.join(webAssets, "icon-512.png"), 512),
  ]);
}

const androidDensityScales = {
  ldpi: 0.75,
  mdpi: 1,
  hdpi: 1.5,
  xhdpi: 2,
  xxhdpi: 3,
  xxxhdpi: 4,
};

async function generateAndroidIcons() {
  const operations = [];
  for (const [density, scale] of Object.entries(androidDensityScales)) {
    const directory = path.join(androidResources, `mipmap-${density}`);
    const conventionalSize = Math.round(48 * scale);
    const adaptiveSize = Math.round(108 * scale);
    operations.push(
      renderIcon(path.join(directory, "ic_launcher.png"), conventionalSize, {
        padding: conventionalIconPadding,
      }),
      renderIcon(
        path.join(directory, "ic_launcher_round.png"),
        conventionalSize,
        {
          glow: true,
          padding: adaptiveForegroundPadding,
          round: true,
        },
      ),
      renderIcon(
        path.join(directory, "ic_launcher_foreground.png"),
        adaptiveSize,
        { padding: adaptiveForegroundPadding },
      ),
      renderAsset(
        sources.background,
        path.join(directory, "ic_launcher_background.png"),
        adaptiveSize,
      ),
    );
  }
  await Promise.all(operations);
}

const androidSplashDimensions = {
  ldpi: [240, 320],
  mdpi: [320, 480],
  hdpi: [480, 800],
  xhdpi: [720, 1280],
  xxhdpi: [960, 1600],
  xxxhdpi: [1280, 1920],
};

function darkAndroidDirectory(directory) {
  if (directory === "drawable") {
    return "drawable-night";
  }
  const [prefix, orientation, density] = directory.split("-");
  return [prefix, orientation, "night", density].join("-");
}

async function generateAndroidSplashes() {
  const operations = [];
  const variants = [["drawable", "mdpi", 320, 480]];
  for (const [density, [width, height]] of Object.entries(
    androidSplashDimensions,
  )) {
    variants.push(
      [`drawable-port-${density}`, density, width, height],
      [`drawable-land-${density}`, density, height, width],
    );
  }
  for (const [directory, density, width, height] of variants) {
    const opticalScale = ["ldpi", "mdpi"].includes(density)
      ? androidLowDensitySplashOpticalScale
      : 1;
    const logoWidth = Math.round(
      androidSplashLogoWidthDp * androidDensityScales[density] * opticalScale,
    );
    operations.push(
      renderSplash(
        sources.splash,
        path.join(androidResources, directory, "splash.png"),
        width,
        height,
        "#ffffff",
        logoWidth,
      ),
      renderSplash(
        sources.splashDark,
        path.join(
          androidResources,
          darkAndroidDirectory(directory),
          "splash.png",
        ),
        width,
        height,
        "#111111",
        logoWidth,
      ),
    );
  }
  await Promise.all(operations);
}

async function generateIosAssets() {
  const appIcon = path.join(
    iosAssets,
    "AppIcon.appiconset",
    "AppIcon-512@2x.png",
  );
  const splashDirectory = path.join(iosAssets, "Splash.imageset");
  const splashSuffixes = ["", "-1", "-2"];
  const splashLogoWidth = Math.round(2732 * iosSplashLogoScale);
  await Promise.all([
    renderIcon(appIcon, 1024, {
      background: "#ffffff",
      glow: true,
      padding: conventionalIconPadding,
    }),
    ...splashSuffixes.map((suffix) =>
      renderSplash(
        sources.splash,
        path.join(splashDirectory, `splash-2732x2732${suffix}.png`),
        2732,
        2732,
        "#ffffff",
        splashLogoWidth,
      ),
    ),
    ...splashSuffixes.map((suffix) =>
      renderSplash(
        sources.splashDark,
        path.join(splashDirectory, `splash-dark-2732x2732${suffix}.png`),
        2732,
        2732,
        "#111111",
        splashLogoWidth,
      ),
    ),
  ]);
}

await validateGlow();
await Promise.all([
  generateWebAssets(),
  generateAndroidIcons(),
  generateAndroidSplashes(),
  generateIosAssets(),
]);

console.log(`Generated ${generatedCount} application assets.`);
