import { chromium } from 'playwright';
import { writeFileSync, appendFileSync } from 'fs';

const STAGING = 'https://staging.gregor20.henemm.com';
const COOKIE = 'validator-issue110.1778492099.6c745ade1e4dc4abed070b2e7b1d74bccfc1d69c92e1a6308097b38d92dbd085';
const SS = '/home/hem/gregor_zwanzig/docs/artifacts/issue-164-wizard-step4-channels/validator-screenshots';
const GPX = '/home/hem/gregor_zwanzig/frontend/e2e/fixtures/test-trip.gpx';
const LOG = `${SS}/walkthrough-nothresh.log`;
writeFileSync(LOG, `--- NoThresh ${new Date().toISOString()} ---\n`);
const log = (msg) => { console.log(msg); appendFileSync(LOG, msg + '\n'); };

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 1200 } });
await ctx.addCookies([{ name: 'gz_session', value: COOKIE, domain: 'staging.gregor20.henemm.com', path: '/' }]);
const page = await ctx.newPage();

await page.goto(`${STAGING}/trips/new`, { waitUntil: 'networkidle' });
await page.getByTestId('trip-wizard-step1-chip-trekking').click();
await page.getByTestId('trip-wizard-step1-name').fill('Validator NoThresh Final');
await page.getByTestId('trip-wizard-step1-startdate').fill('2026-06-01');
await page.getByTestId('trip-wizard-next').click();
await page.waitForTimeout(500);

// Step 2
await page.locator('[data-testid="trip-wizard-step2-dropzone"] input[type="file"]').setInputFiles(GPX);
await page.getByTestId('trip-wizard-step2-pending').waitFor({ state: 'visible' });
await page.getByTestId('trip-wizard-step2-bulk-startdate').fill('2026-06-01');
await page.getByTestId('trip-wizard-step2-bulk-commit').click();
await page.waitForTimeout(1500);
await page.getByTestId('trip-wizard-next').click();
await page.waitForTimeout(1500);

// Step 3
await page.getByTestId('trip-wizard-next').click();
await page.waitForTimeout(1500);

// Step 4: no threshold changes — just save
await page.getByTestId('trip-wizard-step4-container').waitFor({ state: 'visible', timeout: 10000 });
const initialURL = page.url();
log(`URL before save: ${initialURL}`);

await page.screenshot({ path: `${SS}/v07-nothresh-initial.png`, fullPage: true });
await page.getByTestId('trip-wizard-save').click();
// Wait for URL change away from /trips/new
let savedURL = null;
for (let i = 0; i < 30; i++) {
  const u = page.url();
  if (u !== initialURL && !u.endsWith('/trips/new')) { savedURL = u; break; }
  await page.waitForTimeout(500);
}
log(`URL after save: ${savedURL || page.url()}`);
await page.screenshot({ path: `${SS}/v08-nothresh-after-save.png`, fullPage: true });
await browser.close();
