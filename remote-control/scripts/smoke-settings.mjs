import { chromium } from "playwright-core";

function parseArgs(argv) {
  const options = {
    url: "http://127.0.0.1:5173/",
    screenshot: null,
    expectStatus: null,
    expectButton: [],
    expectSignInButtonVisible: null,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    switch (arg) {
      case "--url":
        options.url = argv[++index];
        break;
      case "--screenshot":
        options.screenshot = argv[++index];
        break;
      case "--expect-status":
        options.expectStatus = argv[++index];
        break;
      case "--expect-button":
        options.expectButton.push(argv[++index]);
        break;
      case "--expect-sign-in-button-visible":
      case "--expect-google-button-visible":
        options.expectSignInButtonVisible = argv[++index] === "true";
        break;
      case "--help":
        console.log(`Usage: npm run smoke:settings -- [options]

Options:
  --url <url>                     App URL (default: http://127.0.0.1:5173/)
  --screenshot <path>             Save a screenshot
  --expect-status <text>          Fail if #auth-status does not match
  --expect-button <text>          Fail unless a visible auth button matches
  --expect-sign-in-button-visible <bool>
                                  Fail unless the Sign in with Google button visibility matches
`);
        process.exit(0);
      default:
        throw new Error(`Unknown argument: ${arg}`);
    }
  }

  return options;
}

async function readText(locator) {
  if ((await locator.count()) === 0) {
    return null;
  }
  const text = await locator.textContent();
  return text?.trim() || null;
}

function assertCondition(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

const options = parseArgs(process.argv.slice(2));
const browser = await chromium.launch({ headless: true });

try {
  const page = await browser.newPage({ viewport: { width: 430, height: 932 } });
  await page.goto(options.url, { waitUntil: "domcontentloaded" });
  await page.getByRole("tab", { name: "Settings" }).waitFor({
    state: "visible",
  });
  await page.getByRole("tab", { name: "Settings" }).click();
  await page.locator("#auth-status").waitFor({ state: "visible" });

  if (options.screenshot) {
    await page.screenshot({ path: options.screenshot, fullPage: true });
  }

  const visibleButtons = await page
    .locator(".auth-actions ion-button:visible")
    .allTextContents();

  const result = {
    url: options.url,
    authStatus: await readText(page.locator("#auth-status")),
    authHint: await readText(page.locator("#auth-hint")),
    authIdentity: await readText(page.locator("#auth-identity")),
    visibleButtons,
    signInButtonVisible: visibleButtons.includes("Sign in with Google"),
    settingsGroups: await page
      .locator("#settings-list ion-item-divider ion-label")
      .allTextContents(),
  };

  if (options.expectStatus !== null) {
    assertCondition(
      result.authStatus === options.expectStatus,
      `Expected auth status "${options.expectStatus}" but found "${result.authStatus}".`,
    );
  }

  if (options.expectSignInButtonVisible !== null) {
    assertCondition(
      result.signInButtonVisible === options.expectSignInButtonVisible,
      `Expected signInButtonVisible=${options.expectSignInButtonVisible} but found ${result.signInButtonVisible}.`,
    );
  }

  for (const button of options.expectButton) {
    assertCondition(
      result.visibleButtons.includes(button),
      `Expected visible auth button "${button}" but only found: ${result.visibleButtons.join(", ")}.`,
    );
  }

  console.log(JSON.stringify(result, null, 2));
} finally {
  await browser.close();
}
