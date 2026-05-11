import { chromium } from 'playwright';
import { writeFileSync, appendFileSync } from 'fs';

const STAGING = 'https://staging.gregor20.henemm.com';
const COOKIE_VALUE = 'validator-issue110.1778492099.6c745ade1e4dc4abed070b2e7b1d74bccfc1d69c92e1a6308097b38d92dbd085';
const SCREENSHOTS = '/home/hem/gregor_zwanzig/docs/artifacts/issue-164-wizard-step4-channels/validator-screenshots';
const GPX = '/home/hem/gregor_zwanzig/frontend/e2e/fixtures/test-trip.gpx';
const LOG = `${SCREENSHOTS}/walkthrough.log`;

writeFileSync(LOG, `--- Validator Step4 Walkthrough ${new Date().toISOString()} ---\n`);
const log = (msg) => { console.log(msg); appendFileSync(LOG, msg + '\n'); };
const results = {};

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 1200 } });
  await context.addCookies([{ name: 'gz_session', value: COOKIE_VALUE, domain: 'staging.gregor20.henemm.com', path: '/' }]);
  const page = await context.newPage();
  page.on('pageerror', (e) => log(`[pageerror] ${e.message}`));

  // ---- Step 1 ----
  log('=== STEP 1 ===');
  await page.goto(`${STAGING}/trips/new`, { waitUntil: 'networkidle' });
  await page.waitForSelector('[data-testid="trip-wizard-step1-profile"]', { timeout: 15000 });
  await page.getByTestId('trip-wizard-step1-chip-trekking').click();
  await page.getByTestId('trip-wizard-step1-name').fill('Validator Final Step4');
  await page.getByTestId('trip-wizard-step1-startdate').fill('2026-06-01');
  await page.screenshot({ path: `${SCREENSHOTS}/v01-step1-filled.png`, fullPage: true });
  await page.getByTestId('trip-wizard-next').click();
  await page.waitForTimeout(800);

  // ---- Step 2: upload GPX ----
  log('=== STEP 2 (GPX upload) ===');
  await page.waitForSelector('[data-testid="trip-wizard-step2-dropzone"]', { timeout: 10000 });
  const fileInput = page.locator('[data-testid="trip-wizard-step2-dropzone"] input[type="file"]');
  await fileInput.setInputFiles(GPX);
  // Wait for pending UI
  await page.getByTestId('trip-wizard-step2-pending').waitFor({ state: 'visible', timeout: 10000 });
  // Set start date and commit
  await page.getByTestId('trip-wizard-step2-bulk-startdate').fill('2026-06-01');
  await page.getByTestId('trip-wizard-step2-bulk-commit').click();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${SCREENSHOTS}/v02-step2-committed.png`, fullPage: true });

  for (let i = 0; i < 30; i++) {
    const next = await page.getByTestId('trip-wizard-next').isEnabled();
    if (next) break;
    await page.waitForTimeout(500);
  }
  const next2Enabled = await page.getByTestId('trip-wizard-next').isEnabled();
  log(`Step2 next enabled after commit: ${next2Enabled}`);
  if (!next2Enabled) {
    log('Step2 cannot proceed — abort');
    await browser.close();
    return;
  }
  await page.getByTestId('trip-wizard-next').click();
  await page.waitForTimeout(1500);

  // ---- Step 3 ----
  log('=== STEP 3 ===');
  await page.screenshot({ path: `${SCREENSHOTS}/v03-step3.png`, fullPage: true });
  // Just click next — step3 has canAdvance=true semantics
  for (let i = 0; i < 20; i++) {
    const e = await page.getByTestId('trip-wizard-next').isEnabled();
    if (e) break;
    await page.waitForTimeout(500);
  }
  await page.getByTestId('trip-wizard-next').click();
  await page.waitForTimeout(1500);

  // ---- Step 4 ----
  log('=== STEP 4 ===');
  const container = page.getByTestId('trip-wizard-step4-container');
  const containerVisible = await container.isVisible().catch(() => false);
  results.AC1 = containerVisible ? 'PASS' : 'FAIL';
  log(`AC#1 trip-wizard-step4-container visible: ${containerVisible}`);
  await page.screenshot({ path: `${SCREENSHOTS}/v04-step4-initial.png`, fullPage: true });

  const step4Testids = await page.locator('[data-testid]').evaluateAll(
    (els) => els.map((e) => e.getAttribute('data-testid')).filter(Boolean)
  );
  log(`Step4 testids: ${JSON.stringify(step4Testids)}`);

  // Check OLD testid is NOT used (AC#26)
  const oldTestidVisible = await page.getByTestId('trip-wizard-step4-briefings').isVisible().catch(() => false);
  results.AC26 = (!oldTestidVisible && containerVisible) ? 'PASS' : 'FAIL';
  log(`AC#26 old testid 'trip-wizard-step4-briefings' visible: ${oldTestidVisible} (expected: false)`);

  // AC#2
  const channelsList = await page.getByTestId('trip-wizard-step4-channels-list').isVisible().catch(() => false);
  const channelEmail = await page.getByTestId('trip-wizard-step4-channel-email').isVisible().catch(() => false);
  const channelSignal = await page.getByTestId('trip-wizard-step4-channel-signal').isVisible().catch(() => false);
  const channelTelegram = await page.getByTestId('trip-wizard-step4-channel-telegram').isVisible().catch(() => false);
  const channelSms = await page.getByTestId('trip-wizard-step4-channel-sms').isVisible().catch(() => false);
  results.AC2 = (channelsList && channelEmail && channelSignal && channelTelegram && channelSms) ? 'PASS' : 'FAIL';
  log(`AC#2 list=${channelsList} email=${channelEmail} signal=${channelSignal} tele=${channelTelegram} sms=${channelSms}`);

  // AC#3-#7
  const emailChecked = await page.getByTestId('trip-wizard-step4-channel-email').locator('input[type="checkbox"]').isChecked();
  const signalChecked = await page.getByTestId('trip-wizard-step4-channel-signal').locator('input[type="checkbox"]').isChecked();
  const telegramChecked = await page.getByTestId('trip-wizard-step4-channel-telegram').locator('input[type="checkbox"]').isChecked();
  const smsDisabled = await page.getByTestId('trip-wizard-step4-channel-sms').locator('input[type="checkbox"]').isDisabled();
  results.AC3 = emailChecked ? 'PASS' : 'FAIL';
  results.AC4 = (!signalChecked && !telegramChecked) ? 'PASS' : 'FAIL';
  results.AC5 = smsDisabled ? 'PASS' : 'FAIL';
  log(`AC#3 email checked: ${emailChecked}`);
  log(`AC#4 signal=${signalChecked}, telegram=${telegramChecked}`);
  log(`AC#5 sms disabled: ${smsDisabled}`);

  const smsHint = page.getByTestId('trip-wizard-step4-channel-sms-hint');
  const smsHintVisible = await smsHint.isVisible().catch(() => false);
  const smsHintText = smsHintVisible ? await smsHint.textContent() : null;
  results.AC6 = (smsHintVisible && smsHintText && /demnaechst|demnächst/i.test(smsHintText)) ? 'PASS' : 'FAIL';
  log(`AC#6 sms hint: visible=${smsHintVisible} text="${smsHintText}"`);

  // AC#7: Toggle email
  const emailToggle = page.getByTestId('trip-wizard-step4-channel-email').locator('input[type="checkbox"]');
  await emailToggle.click();
  await page.waitForTimeout(100);
  const emailAfter1 = await emailToggle.isChecked();
  await emailToggle.click();
  await page.waitForTimeout(100);
  const emailAfter2 = await emailToggle.isChecked();
  results.AC7 = (emailAfter1 === false && emailAfter2 === true) ? 'PASS' : 'FAIL';
  log(`AC#7 email toggle: true→${emailAfter1}→${emailAfter2}`);

  // AC#8
  const reportsList = await page.getByTestId('trip-wizard-step4-reports-list').isVisible().catch(() => false);
  const morningToggle = await page.getByTestId('trip-wizard-step4-report-morning-toggle').isVisible().catch(() => false);
  const morningTime = await page.getByTestId('trip-wizard-step4-report-morning-time').isVisible().catch(() => false);
  const eveningToggle = await page.getByTestId('trip-wizard-step4-report-evening-toggle').isVisible().catch(() => false);
  const eveningTime = await page.getByTestId('trip-wizard-step4-report-evening-time').isVisible().catch(() => false);
  results.AC8 = (reportsList && morningToggle && morningTime && eveningToggle && eveningTime) ? 'PASS' : 'FAIL';
  log(`AC#8 reports list/toggles/times: ${reportsList}/${morningToggle}/${morningTime}/${eveningToggle}/${eveningTime}`);

  // AC#9-10
  const morningChecked = await page.getByTestId('trip-wizard-step4-report-morning-toggle').isChecked();
  const morningTimeVal = await page.getByTestId('trip-wizard-step4-report-morning-time').inputValue();
  results.AC9 = (morningChecked && morningTimeVal === '06:00') ? 'PASS' : 'FAIL';
  log(`AC#9 morning: checked=${morningChecked} time="${morningTimeVal}"`);

  const eveningChecked = await page.getByTestId('trip-wizard-step4-report-evening-toggle').isChecked();
  const eveningTimeVal = await page.getByTestId('trip-wizard-step4-report-evening-time').inputValue();
  results.AC10 = (eveningChecked && eveningTimeVal === '18:00') ? 'PASS' : 'FAIL';
  log(`AC#10 evening: checked=${eveningChecked} time="${eveningTimeVal}"`);

  // AC#11
  await page.getByTestId('trip-wizard-step4-report-morning-toggle').click();
  await page.waitForTimeout(200);
  const morningTimeDisabled = await page.getByTestId('trip-wizard-step4-report-morning-time').isDisabled();
  await page.getByTestId('trip-wizard-step4-report-morning-toggle').click();
  await page.waitForTimeout(200);
  const morningTimeReEnabled = !(await page.getByTestId('trip-wizard-step4-report-morning-time').isDisabled());
  results.AC11 = (morningTimeDisabled && morningTimeReEnabled) ? 'PASS' : 'FAIL';
  log(`AC#11 morning-time disabled-when-off: ${morningTimeDisabled} / re-enabled: ${morningTimeReEnabled}`);

  // AC#12
  await page.getByTestId('trip-wizard-step4-report-morning-time').fill('07:30');
  await page.waitForTimeout(200);
  const morningTimeNew = await page.getByTestId('trip-wizard-step4-report-morning-time').inputValue();
  results.AC12 = (morningTimeNew === '07:30') ? 'PASS' : 'FAIL';
  log(`AC#12 morning time set to 07:30: actual="${morningTimeNew}"`);

  // AC#13
  const thresholdsList = await page.getByTestId('trip-wizard-step4-thresholds-list').isVisible().catch(() => false);
  const thrGust = await page.getByTestId('trip-wizard-step4-threshold-gust').isVisible().catch(() => false);
  const thrPrecip = await page.getByTestId('trip-wizard-step4-threshold-precip').isVisible().catch(() => false);
  const thrThunder = await page.getByTestId('trip-wizard-step4-threshold-thunder').isVisible().catch(() => false);
  const thrSnow = await page.getByTestId('trip-wizard-step4-threshold-snow').isVisible().catch(() => false);
  results.AC13 = (thresholdsList && thrGust && thrPrecip && thrThunder && thrSnow) ? 'PASS' : 'FAIL';
  log(`AC#13 thresholds: list=${thresholdsList} gust=${thrGust} precip=${thrPrecip} thunder=${thrThunder} snow=${thrSnow}`);

  // AC#14
  const gustVal = await page.getByTestId('trip-wizard-step4-threshold-gust').inputValue();
  const precipVal = await page.getByTestId('trip-wizard-step4-threshold-precip').inputValue();
  const thunderVal = await page.getByTestId('trip-wizard-step4-threshold-thunder').inputValue();
  const snowVal = await page.getByTestId('trip-wizard-step4-threshold-snow').inputValue();
  results.AC14 = (gustVal === '' && precipVal === '' && thunderVal === '' && snowVal === '') ? 'PASS' : 'FAIL';
  log(`AC#14 initial: gust="${gustVal}" precip="${precipVal}" thunder="${thunderVal}" snow="${snowVal}"`);

  // AC#16
  const thunderOptions = await page.getByTestId('trip-wizard-step4-threshold-thunder').evaluate(
    (el) => Array.from(el.querySelectorAll('option')).map(o => ({ value: o.value, text: o.textContent }))
  );
  log(`AC#16 thunder options: ${JSON.stringify(thunderOptions)}`);
  const expectedTexts = ['—', 'Kein', 'Mittel', 'Hoch'];
  const actualTexts = thunderOptions.map(o => (o.text || '').trim());
  const allOptionsPresent = expectedTexts.every(t => actualTexts.includes(t));
  results.AC16 = allOptionsPresent ? 'PASS' : 'FAIL';

  // AC#15: fill values
  await page.getByTestId('trip-wizard-step4-threshold-gust').fill('80');
  await page.getByTestId('trip-wizard-step4-threshold-precip').fill('10');
  await page.getByTestId('trip-wizard-step4-threshold-snow').fill('2500');
  await page.getByTestId('trip-wizard-step4-threshold-thunder').selectOption('MED');
  await page.waitForTimeout(200);
  const gustFilled = await page.getByTestId('trip-wizard-step4-threshold-gust').inputValue();
  results.AC15 = (gustFilled === '80') ? 'PASS' : 'FAIL';
  log(`AC#15 gust accept 80: actual="${gustFilled}"`);

  // AC#19
  const saveBtn = page.getByTestId('trip-wizard-save');
  const saveVisible = await saveBtn.isVisible();
  const saveEnabled = await saveBtn.isEnabled();
  results.AC19 = (saveVisible && saveEnabled) ? 'PASS' : 'FAIL';
  log(`AC#19 save: visible=${saveVisible} enabled=${saveEnabled}`);

  await page.screenshot({ path: `${SCREENSHOTS}/v05-step4-filled.png`, fullPage: true });

  // Save & Verify
  log('=== SAVE & VERIFY ===');
  await saveBtn.click();
  let savedTripId = null;
  try {
    await page.waitForURL(/\/trips\/[^/]+$/, { timeout: 15000 });
    savedTripId = page.url().split('/').pop();
    log(`Saved trip id from URL: ${savedTripId}`);
    results.AC25 = 'PASS';
  } catch (e) {
    log(`AC#25 save+redirect FAILED: ${e.message}`);
    results.AC25 = 'FAIL';
  }
  await page.screenshot({ path: `${SCREENSHOTS}/v06-after-save.png`, fullPage: true });

  log(`\nFinal results: ${JSON.stringify(results, null, 2)}`);
  writeFileSync(`${SCREENSHOTS}/results.json`, JSON.stringify({ results, savedTripId, timestamp: new Date().toISOString() }, null, 2));
  await browser.close();
})().catch((e) => {
  console.error('FATAL', e);
  appendFileSync(LOG, `FATAL: ${e.message}\n${e.stack}\n`);
  process.exit(1);
});
