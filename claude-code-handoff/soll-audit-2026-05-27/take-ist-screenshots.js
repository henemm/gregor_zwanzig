// Epic #404 Phase 2: IST-Screenshots via Playwright gegen Staging
// Faehrt alle SvelteKit-Screens auf Staging ab und speichert IST-Screenshots
// mit derselben Namenskonvention wie die SOLL-Screenshots aus Phase 1.
// Aufruf: node take-ist-screenshots.js
// Spec: docs/specs/modules/epic_404_phase2_ist_screenshots.md

const { chromium } = require('/home/hem/gregor_zwanzig/frontend/node_modules/playwright');
const path = require('path');
const fs   = require('fs');

const BASE_URL = 'https://staging.gregor20.henemm.com';
const OUT_DIR  = path.join(__dirname, 'ist-screenshots');
const CREDS    = { user: 'default', pass: 'ZfDOKJTre8udPtG' };
const TRIP_ID  = 'e2e-cockpit-test';
const GPX_FILE = '/home/hem/gregor_zwanzig/frontend/e2e/fixtures/test-trip.gpx';

const DESKTOP_VIEWPORT = { width: 1440, height: 900 };
const MOBILE_VIEWPORT  = { width: 390, height: 844 };

// Vollstaendige Liste der erzeugten Screenshots (15 Desktop + 11 Mobile).
// Dient als Inventar und Manifest fuer den SOLL-IST-Vergleich in Phase 3.
// Die Wizard-Dateien werden im Lauf dynamisch via prefix erzeugt; hier
// stehen sie zur Vollstaendigkeit explizit.
const EXPECTED_FILES = [
  // Desktop
  'desktop-home.png',
  'desktop-trips-list.png',
  'desktop-trip-detail.png',
  'desktop-metrics.png',
  'desktop-alerts.png',
  'desktop-email-preview.png',
  'desktop-sms-preview.png',
  'desktop-wp-editor.png',
  'desktop-wizard-step1.png',
  'desktop-wizard-step2.png',
  'desktop-wizard-step3.png',
  'desktop-wizard-step4.png',
  'desktop-compare-main.png',
  'desktop-archive.png',
  'desktop-location-new.png',
  // Mobile
  'mobile-m-home.png',
  'mobile-m-trips.png',
  'mobile-m-trip-detail.png',
  'mobile-m-alerts.png',
  'mobile-m-metrics.png',
  'mobile-m-wiz-1.png',
  'mobile-m-wiz-2.png',
  'mobile-m-wiz-3.png',
  'mobile-m-wiz-4.png',
  'mobile-m-compare.png',
  'mobile-m-wp-editor.png',
];

let ERRORS = 0;

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

function isoDate(offsetDays) {
  return new Date(Date.now() + offsetDays * 86400000).toISOString().slice(0, 10);
}

async function login(page) {
  await page.goto(BASE_URL + '/login');
  await page.fill('input[name="username"]', CREDS.user);
  await page.fill('input[name="password"]', CREDS.pass);
  await page.click('button[type="submit"]');
  await page.waitForURL(BASE_URL + '/');
}

async function seedTrip(page) {
  const res = await page.request.get(BASE_URL + '/api/trips/' + TRIP_ID);
  if (res.status() !== 404) {
    return; // Trip existiert bereits
  }
  const today     = isoDate(0);
  const yesterday = isoDate(-1);
  const tomorrow  = isoDate(1);
  await page.request.post(BASE_URL + '/api/trips', {
    data: {
      id: TRIP_ID,
      name: 'E2E Cockpit Test Trip',
      region: 'Korsika',
      stages: [
        { id: 'e2e-stage-1', name: 'Gestern', date: yesterday, waypoints: [{ id: 'e2e-wp-1', name: 'Start', lat: 42.3, lon: 9.0, elevation_m: 100 }] },
        { id: 'e2e-stage-2', name: 'Heute',   date: today,     waypoints: [{ id: 'e2e-wp-2', name: 'Ziel',  lat: 42.4, lon: 9.1, elevation_m: 500 }] },
        { id: 'e2e-stage-3', name: 'Morgen',  date: tomorrow,  waypoints: [] }
      ],
      report_config: { enabled: true },
      aggregation: { activity_profile: 'wandern' }
    }
  });
}

async function shot(page, name) {
  try {
    await page.screenshot({ path: path.join(OUT_DIR, name), fullPage: false });
    console.log('  [ok] ' + name);
  } catch (err) {
    ERRORS++;
    console.error('  [FEHLER] ' + name + ': ' + err.message);
  }
}

// Faehrt eine einzelne Route an, wartet und schiesst einen Screenshot.
async function shotRoute(page, name, route, wait) {
  try {
    await page.goto(BASE_URL + route);
    if (wait && wait.selector) {
      await page.waitForSelector(wait.selector, { timeout: 15000 });
    }
    if (wait && wait.timeout) {
      await page.waitForTimeout(wait.timeout);
    }
  } catch (err) {
    ERRORS++;
    console.error('  [FEHLER] ' + name + ' (navigation): ' + err.message);
  }
  await shot(page, name);
}

// Wizard-Sequenz: erzeugt wiz-2, wiz-3, wiz-4 Screenshots mit GPX-Upload.
// wiz-1 (Step 1) wird vom Aufrufer separat erstellt.
async function wizardSteps(page, prefix) {
  try {
    await page.goto(BASE_URL + '/trips/new');
    await page.waitForSelector('[data-testid="trip-wizard-shell"]', { timeout: 15000 });

    // Step 1 ("Route", #300): Name + Startdatum + GPX-Upload + Commit.
    // (Aktivitaetsprofil wurde aus Step 1 entfernt — kein Chip mehr.)
    await page.fill('[data-testid="trip-wizard-step1-name"]', 'Audit Test').catch(() => {});
    await page.fill('[data-testid="trip-wizard-step1-startdate"]', isoDate(1)).catch(() => {});

    // GPX-Upload + Commit -> Etappen (Commit liegt in Step 1).
    await page.setInputFiles('input[type="file"][accept=".gpx"]', GPX_FILE);
    await page.waitForSelector('[data-testid="trip-wizard-step1-gpx-commit"]', { timeout: 10000 });
    await page.click('[data-testid="trip-wizard-step1-gpx-commit"]');

    // -> Step 2: Etappen-Rows erscheinen jetzt
    await page.click('[data-testid="trip-wizard-next"]');
    await page.waitForSelector('[data-testid="trip-wizard-step2-stage-row-0"]', { timeout: 15000 });
    await page.waitForTimeout(800);
    await shot(page, prefix + 'wiz-2.png');

    // -> Step 3
    await page.click('[data-testid="trip-wizard-next"]');
    await page.waitForTimeout(1000);
    await shot(page, prefix + 'wiz-3.png');

    // -> Step 4 (kein Save)
    await page.click('[data-testid="trip-wizard-next"]');
    await page.waitForTimeout(1000);
    await shot(page, prefix + 'wiz-4.png');
  } catch (err) {
    ERRORS++;
    console.error('  [FEHLER] wizardSteps (' + prefix + '): ' + err.message);
  }
}

// ---------------------------------------------------------------------------
// Desktop-Run (Viewport 1440x900)
// ---------------------------------------------------------------------------

async function desktopRun(browser) {
  console.log('\n=== DESKTOP (1440x900) ===');
  const ctx = await browser.newContext({ viewport: DESKTOP_VIEWPORT });
  const page = await ctx.newPage();

  await login(page);
  await seedTrip(page);

  await shotRoute(page, 'desktop-home.png',          '/',                              { selector: 'body' });
  await shotRoute(page, 'desktop-trips-list.png',    '/trips',                         { selector: 'body' });
  await shotRoute(page, 'desktop-trip-detail.png',   '/trips/' + TRIP_ID,              { selector: 'body' });
  await shotRoute(page, 'desktop-metrics.png',       '/trips/' + TRIP_ID + '#weather', { timeout: 1500 });
  await shotRoute(page, 'desktop-alerts.png',        '/trips/' + TRIP_ID + '#alerts',  { timeout: 1500 });
  await shotRoute(page, 'desktop-email-preview.png', '/trips/' + TRIP_ID + '#preview', { timeout: 1500 });

  // SMS-Vorschau: auf Preview-Tab bleiben, SMS-Radio aktivieren
  try {
    await page.click('input[type="radio"][value="sms"], [data-testid="preview-channel-sms"]').catch(() => {});
    await page.waitForTimeout(500);
  } catch (err) {
    ERRORS++;
    console.error('  [FEHLER] desktop-sms-preview.png (radio): ' + err.message);
  }
  await shot(page, 'desktop-sms-preview.png');

  await shotRoute(page, 'desktop-wp-editor.png',     '/trips/' + TRIP_ID + '/edit',  { selector: 'body' });

  // Wizard Step 1-4 (eigene Sequenz wegen abweichender Namenskonvention)
  await desktopWizard(page);

  await shotRoute(page, 'desktop-compare-main.png',  '/compare',                     { selector: 'body' });
  await shotRoute(page, 'desktop-archive.png',       '/archiv',                      { selector: 'body' });

  // Location-Dialog: /locations + "Neuer Ort" klicken
  try {
    await page.goto(BASE_URL + '/locations');
    await page.waitForSelector('body', { timeout: 15000 });
    await page.click('text=Neuer Ort').catch(() => {});
    await page.waitForSelector('[role="dialog"]', { timeout: 15000 });
  } catch (err) {
    ERRORS++;
    console.error('  [FEHLER] desktop-location-new.png (dialog): ' + err.message);
  }
  await shot(page, 'desktop-location-new.png');

  await ctx.close();
}

// Desktop-Wizard-Screenshots mit Namen desktop-wizard-step1..4.png.
async function desktopWizard(page) {
  try {
    await page.goto(BASE_URL + '/trips/new');
    await page.waitForSelector('[data-testid="trip-wizard-shell"]', { timeout: 15000 });
    await shot(page, 'desktop-wizard-step1.png');

    // Step 1 ("Route", #300): Name + Startdatum + GPX-Upload + Commit.
    // (Aktivitaetsprofil wurde aus Step 1 entfernt — kein Chip mehr.)
    await page.fill('[data-testid="trip-wizard-step1-name"]', 'Audit Test').catch(() => {});
    await page.fill('[data-testid="trip-wizard-step1-startdate"]', isoDate(1)).catch(() => {});

    await page.setInputFiles('input[type="file"][accept=".gpx"]', GPX_FILE);
    await page.waitForSelector('[data-testid="trip-wizard-step1-gpx-commit"]', { timeout: 10000 });
    await page.click('[data-testid="trip-wizard-step1-gpx-commit"]');

    // -> Step 2: Etappen-Rows erscheinen jetzt
    await page.click('[data-testid="trip-wizard-next"]');
    await page.waitForSelector('[data-testid="trip-wizard-step2-stage-row-0"]', { timeout: 15000 });
    await page.waitForTimeout(800);
    await shot(page, 'desktop-wizard-step2.png');

    await page.click('[data-testid="trip-wizard-next"]');
    await page.waitForTimeout(1000);
    await shot(page, 'desktop-wizard-step3.png');

    await page.click('[data-testid="trip-wizard-next"]');
    await page.waitForTimeout(1000);
    await shot(page, 'desktop-wizard-step4.png');
  } catch (err) {
    ERRORS++;
    console.error('  [FEHLER] desktopWizard: ' + err.message);
  }
}

// ---------------------------------------------------------------------------
// Mobile-Run (Viewport 390x844)
// ---------------------------------------------------------------------------

async function mobileRun(browser) {
  console.log('\n=== MOBILE (390x844) ===');
  const ctx = await browser.newContext({ viewport: MOBILE_VIEWPORT });
  const page = await ctx.newPage();

  await login(page);
  await seedTrip(page);

  await shotRoute(page, 'mobile-m-home.png',        '/',                              { selector: 'body' });
  await shotRoute(page, 'mobile-m-trips.png',       '/trips',                         { selector: 'body' });
  await shotRoute(page, 'mobile-m-trip-detail.png', '/trips/' + TRIP_ID,              { selector: 'body' });
  await shotRoute(page, 'mobile-m-alerts.png',      '/trips/' + TRIP_ID + '#alerts',  { timeout: 1500 });
  await shotRoute(page, 'mobile-m-metrics.png',     '/trips/' + TRIP_ID + '#weather', { timeout: 1500 });

  // Wizard: Step 1 separat, dann Step 2-4 via wizardSteps()
  await shotRoute(page, 'mobile-m-wiz-1.png',       '/trips/new',                   { selector: '[data-testid="trip-wizard-shell"]' });
  await wizardSteps(page, 'mobile-m-');

  await shotRoute(page, 'mobile-m-compare.png',     '/compare',                     { selector: 'body' });
  await shotRoute(page, 'mobile-m-wp-editor.png',   '/trips/' + TRIP_ID + '/edit',  { selector: 'body' });

  await ctx.close();
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function run() {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  const browser = await chromium.launch({ headless: true });

  try {
    await desktopRun(browser);
    await mobileRun(browser);
  } finally {
    await browser.close();
  }

  const onDisk = new Set(fs.readdirSync(OUT_DIR).filter((f) => f.endsWith('.png')));
  const count = onDisk.size;

  // Fehlende erwartete Dateien als Fehler melden
  const missing = EXPECTED_FILES.filter((name) => !onDisk.has(name));
  for (const name of missing) {
    ERRORS++;
    console.error('  [FEHLEND] erwartet aber nicht erzeugt: ' + name);
  }

  console.log('\nIST-Screenshots fertig.');
  console.log('Verzeichnis: ' + OUT_DIR);
  console.log('Anzahl Dateien: ' + count + ' / ' + EXPECTED_FILES.length);
  console.log('Fehler: ' + ERRORS);

  if (ERRORS > 0) {
    process.exit(1);
  }
}

run().catch((err) => {
  console.error('Fataler Fehler:', err);
  process.exit(1);
});
