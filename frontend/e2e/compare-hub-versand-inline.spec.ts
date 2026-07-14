// E2E (Staging) — Issue #1256 Scheibe 7: Hub-Versand-Tab Inline-Edit-Parität
// durch eingebetteten VersandTab (context="vergleich") + Aktivierungs-Karte
// (AC-17, AC-18, AC-19, AC-35, AC-36, AC-37).
//
// Spec: docs/specs/modules/issue_1256_compare_ui_rewire.md § Scheibe 7
//
// Ausführen (gegen Staging, aus frontend/):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   npx playwright test --config=playwright.1256-s7.staging.config.ts

import { test, expect, type Page, type APIRequestContext } from '@playwright/test';

let createdIds: string[] = [];
let createdLocationIds: string[] = [];

// Testkonto (GZ_AUTH_USER=default, kein Produktiv-Nutzer, s. CLAUDE.md
// "KEINE aktiven Produktiv-User") hatte auf Staging keine telegram_chat_id
// gesetzt — der Telegram-Kanal-Switch in VTBriefingChannels bleibt sonst
// wegen `availableChannels.telegram = !!profile?.telegram_chat_id` disabled,
// unabhängig vom AC-35-Fix. Setzt vor der Suite eine Test-Chat-ID, stellt den
// Ursprungswert danach wieder her (Read-Modify-Write, kein anderes Feld berührt).
let apiCtx: APIRequestContext;
let originalTelegramChatId = '';

test.beforeAll(async ({ playwright }) => {
	const base = process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com';
	const user = process.env.GZ_VALIDATOR_USER!;
	const pass = process.env.GZ_VALIDATOR_PASS!;
	apiCtx = await playwright.request.newContext({
		baseURL: base,
		ignoreHTTPSErrors: true,
		httpCredentials: { username: user, password: pass },
		storageState: 'playwright/.auth/staging-1256-s7.json'
	});
	const profRes = await apiCtx.get('/api/auth/profile');
	expect(profRes.ok(), 'Profil-Lesen fehlgeschlagen: ' + profRes.status()).toBeTruthy();
	const profile = await profRes.json();
	originalTelegramChatId = profile.telegram_chat_id ?? '';
	const putRes = await apiCtx.put('/api/auth/profile', { data: { telegram_chat_id: 'e2e-s7-test-chat' } });
	expect(putRes.ok(), 'Test-Chat-ID setzen fehlgeschlagen: ' + putRes.status()).toBeTruthy();
});

test.afterAll(async () => {
	if (apiCtx) {
		await apiCtx.put('/api/auth/profile', { data: { telegram_chat_id: originalTelegramChatId } });
		await apiCtx.dispose();
	}
});

test.afterEach(async ({ page }) => {
	for (const id of createdIds) {
		try {
			await page.request.delete(`/api/compare/presets/${id}`);
		} catch {
			/* Staging-Hygiene: Cleanup-Fehler ist nicht test-kritisch */
		}
	}
	createdIds = [];
	for (const id of createdLocationIds) {
		try {
			await page.request.delete(`/api/locations/${id}`);
		} catch {
			/* Staging-Hygiene: Cleanup-Fehler ist nicht test-kritisch */
		}
	}
	createdLocationIds = [];
});

async function createLocation(page: Page, name: string, lat: number, lon: number): Promise<string> {
	const res = await page.request.post('/api/locations', { data: { name, lat, lon } });
	expect(res.ok(), 'Location-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	const id = body.id as string;
	createdLocationIds.push(id);
	return id;
}

async function createPresetWithLocations(
	page: Page,
	name: string,
	locationIds: string[],
	extra: Record<string, unknown> = {}
): Promise<string> {
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name,
			location_ids: locationIds,
			schedule: 'daily',
			profil: 'wandern',
			hour_from: 7,
			hour_to: 16,
			empfaenger: ['urlauber@example.com'],
			...extra
		}
	});
	expect(res.ok(), 'Preset-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	const id = body.id as string;
	createdIds.push(id);
	return id;
}

test.describe('Issue #1256 Scheibe 7: Hub-Versand-Tab (AC-35/36/37/17/18/19)', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// ── AC-35: Kanal-Switch reagiert sofort + PUT-Persistenz ────────────────────
	test('AC-35: Telegram-Switch im eingebetteten VersandTab schaltet sofort um und persistiert per PUT', async ({
		page
	}) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E-S7 Kanal-Ort-A ${suffix}`, 47.1, 11.2);
		const locB = await createLocation(page, `E2E-S7 Kanal-Ort-B ${suffix}`, 47.2, 11.3);
		const id = await createPresetWithLocations(page, `E2E-S7 Kanal ${suffix}`, [locA, locB]);

		await page.goto(`/compare/${id}?tab=versand`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-versand"]:visible').click();

		const versandTab = page.locator('[data-testid="versand-tab"]:visible');
		await expect(versandTab).toBeVisible({ timeout: 10_000 });

		const telegramCheckbox = page
			.locator('[data-testid="compare-step5-channel-telegram"]:visible')
			.locator('input[type="checkbox"]');
		await expect(telegramCheckbox).toBeVisible({ timeout: 10_000 });
		// AC-35 Kernaussage: der Switch ist NICHT mehr hart auf disabled={true}
		// verdrahtet (Ist vor S7: CompareTabs.svelte Kanal-Switches disabled={true}).
		await expect(telegramCheckbox).toBeEnabled();
		await expect(telegramCheckbox).not.toBeChecked();

		const putPromise = page.waitForResponse(
			(res) => res.url().includes(`/api/compare/presets/${id}`) && res.request().method() === 'PUT'
		);
		await telegramCheckbox.click();
		await expect(telegramCheckbox).toBeChecked({ timeout: 5_000 });
		const putRes = await putPromise;
		expect(putRes.ok(), 'PUT nach Kanal-Switch fehlgeschlagen: ' + putRes.status()).toBeTruthy();
		const putBody = putRes.request().postDataJSON() as { send_telegram: boolean };
		expect(putBody.send_telegram).toBe(true);

		await page.reload();
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-versand"]:visible').click();
		const reloadedCheckbox = page
			.locator('[data-testid="compare-step5-channel-telegram"]:visible')
			.locator('input[type="checkbox"]');
		await expect(reloadedCheckbox).toBeChecked({ timeout: 10_000 });
	});

	// ── AC-36: Uhrzeit-Änderung inline im Hub, keine Navigation ─────────────────
	test('AC-36: Briefing-Uhrzeit ändert sich inline im Hub ohne Navigation, überlebt Reload', async ({ page }) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E-S7 Zeit-Ort-A ${suffix}`, 46.9, 10.7);
		const locB = await createLocation(page, `E2E-S7 Zeit-Ort-B ${suffix}`, 47.0, 10.8);
		const id = await createPresetWithLocations(page, `E2E-S7 Zeit ${suffix}`, [locA, locB]);

		await page.goto(`/compare/${id}?tab=versand`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-versand"]:visible').click();

		const urlBefore = page.url();
		expect(urlBefore).not.toMatch(/\/edit/);

		const timeInput = page.locator('[data-testid="report-morning-time"]:visible');
		await expect(timeInput).toBeVisible({ timeout: 10_000 });

		const putPromise = page.waitForResponse(
			(res) => res.url().includes(`/api/compare/presets/${id}`) && res.request().method() === 'PUT'
		);
		await timeInput.fill('09:15');
		await timeInput.blur();
		const putRes = await putPromise;
		expect(putRes.ok(), 'PUT nach Uhrzeit-Änderung fehlgeschlagen: ' + putRes.status()).toBeTruthy();
		const putBody = putRes.request().postDataJSON() as { morning_time: string };
		expect(putBody.morning_time.slice(0, 5)).toBe('09:15');

		// AC-36 Kernaussage: keine goToEditVersand()-Navigation nach /edit.
		expect(page.url()).toBe(urlBefore);
		expect(page.url()).not.toMatch(/\/edit/);

		await page.reload();
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-versand"]:visible').click();
		const reloadedInput = page.locator('[data-testid="report-morning-time"]:visible');
		await expect(reloadedInput).toHaveValue('09:15', { timeout: 10_000 });
	});

	// ── AC-37 + AC-17 + AC-18: Aktivierungs-Karte ───────────────────────────────
	test('AC-37/AC-17/AC-18: Aktivierungs-Karte zeigt Status+Copy und togglet ohne Redirect', async ({ page }) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E-S7 Aktiv-Ort-A ${suffix}`, 47.3, 11.0);
		const locB = await createLocation(page, `E2E-S7 Aktiv-Ort-B ${suffix}`, 47.4, 11.1);
		const id = await createPresetWithLocations(page, `E2E-S7 Aktivierung ${suffix}`, [locA, locB]);

		await page.goto(`/compare/${id}?tab=versand`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-versand"]:visible').click();

		const card = page.locator('[data-testid="compare-hub-activation-card"]:visible');
		await expect(card).toBeVisible({ timeout: 10_000 });
		// AC-17: eigene Karte mit Status "Aktiv" + CTA "Pausieren".
		await expect(card).toContainText('Aktiv');
		const cta = page.locator('[data-testid="compare-hub-activation-cta"]:visible');
		await expect(cta).toHaveText('Pausieren');
		// AC-18: Copy nennt explizit "bis du pausierst", kein Enddatum-Feld hier.
		await expect(card).toContainText('bis du pausierst');

		const headerPill = page.locator('[data-status]:visible').first();
		await expect(headerPill).toBeVisible({ timeout: 10_000 });
		const statusBefore = await headerPill.getAttribute('data-status');
		expect(statusBefore).toBe('active');

		const urlBefore = page.url();
		const putPromise = page.waitForResponse(
			(res) => res.url().includes(`/api/compare/presets/${id}`) && res.request().method() === 'PUT'
		);
		await cta.click();
		const putRes = await putPromise;
		expect(putRes.ok(), 'PUT nach Pausieren-Klick fehlgeschlagen: ' + putRes.status()).toBeTruthy();

		// AC-37: kein Redirect zu /compare/{id}/edit, keine URL-Änderung.
		expect(page.url()).toBe(urlBefore);
		expect(page.url()).not.toMatch(/\/edit/);

		await expect(cta).toHaveText('Aktivieren', { timeout: 5_000 });
		const statusAfterPill = await page.locator('[data-status]:visible').first().getAttribute('data-status');

		await cta.click();
		await expect(cta).toHaveText('Pausieren', { timeout: 5_000 });

		// Evidence-Objekt fürs Reporting (kein Assert, nur Beobachtung).
		test.info().annotations.push({
			type: 'header-pill-status',
			description: `before=${statusBefore} afterPauseClick=${statusAfterPill}`
		});
	});

	// ── F001-Wächter: "Bis auf Weiteres" löscht das Enddatum inline ─────────────
	test('F001: "Bis auf Weiteres" löscht ein gesetztes Enddatum per PUT, überlebt Reload', async ({ page }) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E-S7 Enddatum-Ort-A ${suffix}`, 47.05, 10.6);
		const locB = await createLocation(page, `E2E-S7 Enddatum-Ort-B ${suffix}`, 47.15, 10.7);
		const id = await createPresetWithLocations(page, `E2E-S7 Enddatum ${suffix}`, [locA, locB], {
			end_date: '2027-01-15'
		});

		await page.goto(`/compare/${id}?tab=versand`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-versand"]:visible').click();

		const dateBtn = page.locator('[data-testid="compare-versand-enddate-date"]:visible');
		await expect(dateBtn).toBeVisible({ timeout: 10_000 });
		await expect(dateBtn).toHaveAttribute('aria-selected', 'true');
		const dateInput = page.locator('[data-testid="compare-versand-enddate-input"]:visible');
		await expect(dateInput).toHaveValue('2027-01-15');

		const openBtn = page.locator('[data-testid="compare-versand-enddate-open"]:visible');
		const putPromise = page.waitForResponse(
			(res) => res.url().includes(`/api/compare/presets/${id}`) && res.request().method() === 'PUT'
		);
		await openBtn.click();
		const putRes = await putPromise;
		expect(putRes.ok(), 'PUT nach "Bis auf Weiteres" fehlgeschlagen: ' + putRes.status()).toBeTruthy();
		const putBody = putRes.request().postDataJSON() as { end_date: string };
		expect(putBody.end_date).toBe('');

		await expect(openBtn).toHaveAttribute('aria-selected', 'true', { timeout: 5_000 });

		await page.reload();
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-versand"]:visible').click();
		const reloadedOpenBtn = page.locator('[data-testid="compare-versand-enddate-open"]:visible');
		await expect(reloadedOpenBtn).toHaveAttribute('aria-selected', 'true', { timeout: 10_000 });
		await expect(page.locator('.vt-laufzeit-hint:visible')).toContainText('ohne Enddatum');
	});

	// ── F002-Stichprobe: zwei schnell aufeinanderfolgende Hub-Edits ─────────────
	test('F002: Uhrzeit-Änderung + sofortiger Pausieren-Klick persistieren BEIDE', async ({ page }) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E-S7 F002-Ort-A ${suffix}`, 46.8, 10.5);
		const locB = await createLocation(page, `E2E-S7 F002-Ort-B ${suffix}`, 46.85, 10.55);
		const id = await createPresetWithLocations(page, `E2E-S7 F002 ${suffix}`, [locA, locB]);

		await page.goto(`/compare/${id}?tab=versand`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-versand"]:visible').click();

		const timeInput = page.locator('[data-testid="report-morning-time"]:visible');
		await expect(timeInput).toBeVisible({ timeout: 10_000 });
		const cta = page.locator('[data-testid="compare-hub-activation-cta"]:visible');
		await expect(cta).toHaveText('Pausieren');

		// Kein Warten zwischen den beiden Aktionen — Stresstest für die
		// gemeinsame hubPutQueue (Fix-Loop 1, F002, Adversary CRITICAL).
		await timeInput.fill('10:45');
		await cta.click();

		await page.waitForLoadState('networkidle');
		await expect(cta).toHaveText('Aktivieren', { timeout: 10_000 });

		await page.reload();
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-versand"]:visible').click();
		const reloadedInput = page.locator('[data-testid="report-morning-time"]:visible');
		await expect(reloadedInput).toHaveValue('10:45', { timeout: 10_000 });
		const reloadedCta = page.locator('[data-testid="compare-hub-activation-cta"]:visible');
		await expect(reloadedCta).toHaveText('Aktivieren', { timeout: 10_000 });
	});

	// ── F004: Kebab-Pausieren (Header) delegiert an denselben Schreibweg wie
	// die Hub-Aktivierungs-Karte — ein Feld-Edit VOR dem Kebab-Toggle darf
	// nicht verloren gehen (Fix f89b89af, Adversary R5 CRITICAL). ───────────
	test('F004: Uhrzeit-Änderung + Kebab-Pausieren (Header) persistieren BEIDE, kein Datenverlust', async ({
		page
	}) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E-S7 F004-Ort-A ${suffix}`, 46.6, 10.2);
		const locB = await createLocation(page, `E2E-S7 F004-Ort-B ${suffix}`, 46.65, 10.25);
		const id = await createPresetWithLocations(page, `E2E-S7 F004 ${suffix}`, [locA, locB]);

		await page.goto(`/compare/${id}?tab=versand`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-versand"]:visible').click();

		const timeInput = page.locator('[data-testid="report-morning-time"]:visible');
		await expect(timeInput).toBeVisible({ timeout: 10_000 });

		// Feld-Änderung im Hub-Versand-Tab, PUT abwarten (eigener Commit-Pfad).
		const fieldPutPromise = page.waitForResponse(
			(res) => res.url().includes(`/api/compare/presets/${id}`) && res.request().method() === 'PUT'
		);
		await timeInput.fill('11:20');
		await timeInput.blur();
		const fieldPutRes = await fieldPutPromise;
		expect(fieldPutRes.ok(), 'PUT nach Uhrzeit-Änderung fehlgeschlagen: ' + fieldPutRes.status()).toBeTruthy();

		// Header-Kebab öffnen und "Pausieren" wählen (F004: delegiert jetzt an
		// CompareTabs.toggleActiveFromParent() → dieselbe hubPutQueue/
		// currentPreset-Baseline wie die Aktivierungs-Karte).
		const kebabPutPromise = page.waitForResponse(
			(res) => res.url().includes(`/api/compare/presets/${id}`) && res.request().method() === 'PUT'
		);
		await page.locator('button[aria-label="Weitere Aktionen"]:visible').click();
		await page.getByRole('menuitem', { name: 'Pausieren' }).click();
		const kebabPutRes = await kebabPutPromise;
		expect(kebabPutRes.ok(), 'PUT nach Kebab-Pausieren fehlgeschlagen: ' + kebabPutRes.status()).toBeTruthy();
		const kebabPutBody = kebabPutRes.request().postDataJSON() as { schedule: string; morning_time: string };
		// Kernaussage F004: der Kebab-PUT trägt die VORHER im Hub-Tab geänderte
		// Uhrzeit mit (round-trip aus der gemeinsamen currentPreset-Baseline),
		// überschreibt sie NICHT mit einem veralteten data.preset-Stand.
		expect(kebabPutBody.schedule).toBe('manual');
		expect(kebabPutBody.morning_time.slice(0, 5)).toBe('11:20');

		await page.reload();
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-versand"]:visible').click();
		const reloadedInput = page.locator('[data-testid="report-morning-time"]:visible');
		await expect(reloadedInput).toHaveValue('11:20', { timeout: 10_000 });
		const reloadedCta = page.locator('[data-testid="compare-hub-activation-cta"]:visible');
		await expect(reloadedCta).toHaveText('Aktivieren', { timeout: 10_000 });

		// Aufräumen: Kebab "Aktivieren", damit der Test-Vergleich nicht pausiert
		// zurückbleibt (Preset wird ohnehin in afterEach gelöscht, aber
		// symmetrisch zum Auftrag).
		await page.locator('button[aria-label="Weitere Aktionen"]:visible').click();
		await page.getByRole('menuitem', { name: 'Aktivieren' }).click();
		await expect(reloadedCta).toHaveText('Pausieren', { timeout: 10_000 });
	});

	// ── AC-19 Regression: Vorschau-Tab Desktop/iPhone-Umschalter ────────────────
	test('AC-19: Vorschau-Tab Desktop-Inbox/iPhone-Mail-Umschalter bleibt funktionsfähig', async ({ page }) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E-S7 Vorschau-Ort-A ${suffix}`, 47.5, 10.3);
		const locB = await createLocation(page, `E2E-S7 Vorschau-Ort-B ${suffix}`, 47.55, 10.35);
		const id = await createPresetWithLocations(page, `E2E-S7 Vorschau ${suffix}`, [locA, locB]);

		await page.goto(`/compare/${id}?tab=vorschau`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-vorschau"]:visible').click();

		const panel = page.locator('[data-testid="compare-detail-panel-vorschau"]:visible');
		await expect(panel).toBeVisible({ timeout: 10_000 });

		const iphoneBtn = panel.getByRole('button', { name: 'iPhone-Mail' });
		const desktopBtn = panel.getByRole('button', { name: 'Desktop-Inbox' });
		await expect(iphoneBtn).toBeVisible({ timeout: 10_000 });
		await expect(desktopBtn).toBeVisible({ timeout: 10_000 });

		await iphoneBtn.click();
		await expect(iphoneBtn).toHaveCSS('font-weight', '600', { timeout: 5_000 });

		await desktopBtn.click();
		await expect(desktopBtn).toHaveCSS('font-weight', '600', { timeout: 5_000 });
	});
});
