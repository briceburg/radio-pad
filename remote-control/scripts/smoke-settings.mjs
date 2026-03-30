import { chromium } from "playwright-core";

function parseArgs(argv) {
  const options = {
    url: "http://127.0.0.1:5173/",
    screenshot: null,
    expectStatus: null,
    expectButton: [],
    expectSignInButtonVisible: null,
    setPreference: {},
    expectPreference: {},
    expectToastContains: null,
    expectToastDuration: null,
    resetStorage: false,
    reloadAfterSave: false,
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
      case "--set-pref": {
        const [key, ...rest] = (argv[++index] || "").split("=");
        options.setPreference[key] = rest.join("=");
        break;
      }
      case "--expect-pref": {
        const [key, ...rest] = (argv[++index] || "").split("=");
        options.expectPreference[key] = rest.join("=");
        break;
      }
      case "--expect-toast-contains":
        options.expectToastContains = argv[++index];
        break;
      case "--expect-toast-duration":
        options.expectToastDuration = Number(argv[++index]);
        break;
      case "--reset-storage":
        options.resetStorage = true;
        break;
      case "--reload-after-save":
        options.reloadAfterSave = true;
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
  --set-pref <key=value>          Set a settings preference before Save
  --expect-pref <key=value>       Fail unless the settings preference matches
  --expect-toast-contains <text>  Fail unless the global toast message contains text
  --expect-toast-duration <ms>    Fail unless the global toast duration matches
  --reset-storage                 Clear local storage before loading the app
  --reload-after-save             Reload the page after Save before assertions
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

async function openSettings(page) {
  await page.getByRole("tab", { name: "Settings" }).waitFor({
    state: "visible",
  });
  await page.getByRole("tab", { name: "Settings" }).click();
  await page.locator("#auth-status").waitFor({ state: "visible" });
  await page.locator("#pref-registryUrl").waitFor({ state: "attached" });
}

async function setPreference(page, key, value) {
  const locator = page.locator(`#pref-${key}`);
  await locator.waitFor({ state: "attached" });
  const count = await locator.count();
  assertCondition(count > 0, `Could not find preference "${key}".`);
  await locator.evaluate((element, nextValue) => {
    element.value = nextValue;
    element.dispatchEvent(
      new CustomEvent("ionInput", {
        bubbles: true,
        detail: { value: nextValue },
      }),
    );
    element.dispatchEvent(
      new CustomEvent("ionChange", {
        bubbles: true,
        detail: { value: nextValue },
      }),
    );
  }, value);
}

async function readPreferences(page) {
  return page
    .locator("#settings-list ion-input, #settings-list ion-select")
    .evaluateAll((inputs) =>
      Object.fromEntries(
        inputs
          .map((input) => [
            input.id?.replace(/^pref-/, "") || null,
            input.value ?? null,
          ])
          .filter(([key]) => key),
      ),
    );
}

async function waitForToastMessage(page, text) {
  await page.waitForFunction(
    (expected) =>
      document.getElementById("global-toast")?.message?.includes(expected),
    text,
  );
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
  if (options.resetStorage) {
    await page.evaluate(() => {
      window.localStorage.clear();
      window.sessionStorage.clear();
    });
    await page.reload({ waitUntil: "domcontentloaded" });
  }
  await openSettings(page);

  if (Object.keys(options.setPreference).length > 0) {
    for (const [key, value] of Object.entries(options.setPreference)) {
      await setPreference(page, key, value);
    }
    await page.locator("#settings-save-button").evaluate((button) => {
      button.click();
    });
    await page.locator('#settings-save-button[aria-busy="false"]').waitFor({
      state: "attached",
    });
    if (options.expectToastContains) {
      await waitForToastMessage(page, options.expectToastContains);
    }
    if (options.reloadAfterSave) {
      await page.reload({ waitUntil: "domcontentloaded" });
      await openSettings(page);
    }
  }

  if (options.screenshot) {
    await page.screenshot({ path: options.screenshot, fullPage: true });
  }

  const visibleButtons = await page
    .locator(".auth-actions ion-button:visible")
    .allTextContents();
  const preferences = await readPreferences(page);
  const toastState = await page.locator("#global-toast").evaluate((toast) => ({
    message: toast.message || null,
    duration: toast.duration ?? null,
  }));

  const result = {
    url: options.url,
    authStatus: await readText(page.locator("#auth-status")),
    authHint: await readText(page.locator("#auth-hint")),
    authIdentity: await readText(page.locator("#auth-identity")),
    visibleButtons,
    signInButtonVisible: visibleButtons.includes("Sign in with Google"),
    preferences,
    toast: toastState,
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

  for (const [key, value] of Object.entries(options.expectPreference)) {
    assertCondition(
      result.preferences[key] === value,
      `Expected preference "${key}" to be "${value}" but found "${result.preferences[key]}".`,
    );
  }

  if (options.expectToastContains !== null) {
    assertCondition(
      result.toast.message?.includes(options.expectToastContains),
      `Expected toast to contain "${options.expectToastContains}" but found "${result.toast.message}".`,
    );
  }

  if (options.expectToastDuration !== null) {
    assertCondition(
      result.toast.duration === options.expectToastDuration,
      `Expected toast duration ${options.expectToastDuration} but found ${result.toast.duration}.`,
    );
  }

  console.log(JSON.stringify(result, null, 2));
} finally {
  await browser.close();
}
