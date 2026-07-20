// E2E — Issue #1232 Scheibe 2b: VersandTab context="vergleich" im Compare-Editor
//
// Spec: docs/specs/modules/versand_tab_vergleich.md
//
// Verhaltensnachweis der ACs als eingeloggter Nutzer gegen Staging/Preview.
// Echter Klick-Pfad (Tab-Klick, kein page.goto direkt in den Tab-Zustand),
// Doppel-Mount Desktop+Mobile beachtet (`:visible`-Filter, etabliertes Muster).
//
// Hinweis (RED-Probe #1232 Scheibe 2b): `alert-metric-level-table` rendert nur,
// wenn das Preset aktive Metriken (display_config.active_metrics) hat — sonst
// zeigt der geteilte AlarmeTab (Issue #1258 S4, ersetzt CompareAlarmSection)
// den Hinweis `alarme-no-metrics`. Presets in diesem Spec setzen deshalb
// bewusst `active_metrics: ['wind_max_kmh']`.
//
// Ausführen:
//   cd frontend && E2E_USER=admin E2E_PASS=test1234 \
//     npx playwright test e2e/versand-tab-vergleich.spec.ts --config playwright.config.ts

import { test, expect, type Page } from '@playwright/test';
import { createTestLocation } from './helpers';

async function createPreset(
	page: Page,
	overrides: Record<string, unknown> = {}
): Promise<{ id: string }> {
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name: 'E2E-GZ-VersandTab-Vergleich-' + Date.now(),
			location_ids: [],
			schedule: 'daily',
			profil: 'wandern',
			hour_from: 7,
			hour_to: 16,
			empfaenger: ['versand-vergleich-e2e@example.com'],
			display_config: { active_metrics: ['wind_max_kmh'] },
			...overrides
		}
	});
	expect(res.ok(), 'Preset-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	return { id: body.id };
}

async function openVersandTab(page: Page, id: string): Promise<void> {
	await page.goto(`/compare/${id}`);
	await page.waitForLoadState('networkidle');
	await page.locator('[data-testid="compare-detail-tab-versand"]:visible').first().click();
}

test.describe('Issue #1232 Scheibe 2b: VersandTab (vergleich) im Compare-Editor', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// ── AC-1: 3 Versand-Sektionen (Kanäle → Zeitplan → Laufzeit) ─────────────
	// Issue #1258 Scheibe S4 (E5, AC-18): die Alert-Zustellung (Cooldown/
	// Ruhezeiten) rendert nicht mehr im Versand-Tab, sondern im Alarme-Tab
	// (ersetzt die alte AC-4-Aussage aus versand_tab_vergleich.md).
	test('AC-1: Versand-Tab zeigt Kanäle → Zeitplan → Laufzeit, keine Alert-Zustellung mehr', async ({
		page
	}) => {
		const { id } = await createPreset(page);
		await openVersandTab(page, id);

		await expect(page.locator('[data-testid="compare-step5-channel-email"]:visible').first()).toBeVisible({
			timeout: 10_000
		});
		await expect(page.locator('[data-testid="morning-master-switch"]:visible').first()).toBeVisible();
		await expect(page.locator('[data-testid="briefings-laufzeit-vergleich"]:visible').first()).toBeVisible();
		await expect(page.locator('[data-testid="alert-cooldown-card"]:visible')).toHaveCount(0);
	});

	// ── AC-3: Laufzeit — "Bis auf Weiteres" löscht ein gesetztes end_date ────
	test('AC-3: "Bis auf Weiteres" löscht ein gesetztes Enddatum nach Speichern + Reload', async ({
		page
	}) => {
		const { id } = await createPreset(page, { end_date: '2026-09-01' });
		await openVersandTab(page, id);

		await page.locator('[data-testid="compare-versand-enddate-open"]:visible').first().click();
		await expect(page.locator('[data-testid="save-indicator"]')).toHaveAttribute('data-state', 'idle', {
			timeout: 10_000
		});

		const res = await page.request.get(`/api/compare/presets/${id}`);
		expect(res.ok()).toBeTruthy();
		const preset = await res.json();
		expect(preset.end_date, 'end_date muss nach dem Sentinel gelöscht sein').toBeFalsy();
	});

	// ── AC-3b: Laufzeit — "Bis Datum" + Datum setzt end_date reload-fest ─────
	test('AC-3b: "Bis Datum" + Datumsauswahl persistiert das Enddatum', async ({ page }) => {
		const { id } = await createPreset(page);
		await openVersandTab(page, id);

		await page.locator('[data-testid="compare-versand-enddate-date"]:visible').first().click();
		await page
			.locator('[data-testid="compare-versand-enddate-input"]:visible')
			.first()
			.fill('2026-10-15');
		await expect(page.locator('[data-testid="save-indicator"]')).toHaveAttribute('data-state', 'idle', {
			timeout: 10_000
		});

		const res = await page.request.get(`/api/compare/presets/${id}`);
		expect(res.ok()).toBeTruthy();
		const preset = await res.json();
		expect(preset.end_date).toBe('2026-10-15');
	});

	// ── AC-4 (Issue #1258 S4, AC-18 ersetzt die alte Aussage): Alarme-Tab hat
	// Cooldown/Quiet UND Level-Tabelle; Versand hat weder noch ────────────────
	test('AC-4: Alarme-Tab enthält Cooldown-Karte + Level-Tabelle, Versand-Tab keins von beidem', async ({
		page
	}) => {
		const { id } = await createPreset(page);
		await page.goto(`/compare/${id}`);
		await page.waitForLoadState('networkidle');
		// BEFUND: activeMetricKeys hydratisiert nur lazy beim Wetter-Metriken-Besuch.
		await page.locator('[data-testid="compare-detail-tab-wetter-metriken"]:visible').first().click();
		await page.waitForTimeout(300);
		await page.locator('[data-testid="compare-detail-tab-alarme"]:visible').first().click();

		await expect(page.locator('[data-testid="alarme-tab"]:visible').first()).toBeVisible({
			timeout: 10_000
		});
		// Level-Tabelle sichtbar (Preset hat aktive Metrik wind_max_kmh → wind_gust)
		await expect(page.locator('[data-testid="alert-metric-level-table"]:visible').first()).toBeVisible();
		// Cooldown-Karte JETZT im Alarme-Tab (zog aus dem Versand-Tab zurück, S4/AC-18).
		await expect(page.locator('[data-testid="alert-cooldown-card"]:visible').first()).toBeVisible();

		await page.locator('[data-testid="compare-detail-tab-versand"]:visible').first().click();
		await expect(page.locator('[data-testid="alert-cooldown-card"]:visible')).toHaveCount(0);
		await expect(page.locator('[data-testid="alert-metric-level-table"]:visible')).toHaveCount(0);
	});

	// ── AC-7: Kein Kanal aktiv → Warnbox statt Zeitplan-Karten ───────────────
	// sendEmail ist reiner UI-Zustand (kein Persistenz-Feld, #1230). Voraussetzung:
	// Testkonto braucht mail_to, sonst ist die E-Mail-Checkbox disabled
	// (VTBriefingChannels.svelte:108).
	test('AC-7: alle Kanäle aus zeigt "Kein Kanal aktiv" statt Zeitplan-Karten', async ({ page }) => {
		const prof = await (await page.request.get('/api/auth/profile')).json();
		const origMailTo = (prof.mail_to as string | null) ?? null;
		await page.request.put('/api/auth/profile', { data: { mail_to: 'ac7-versand@example.com' } });
		try {
			const { id } = await createPreset(page);
			await openVersandTab(page, id);

			// E-Mail abwählen (jetzt aktiv wegen mail_to) → hasActiveChannel false.
			// (Telegram/SMS sind ohne Kontaktfeld ohnehin aus.)
			const email = page
				.locator('[data-testid="compare-step5-channel-email"]:visible')
				.first()
				.locator('input[type="checkbox"]');
			if (await email.isChecked()) await email.uncheck();

			await expect(
				page.locator('[data-testid="briefings-channel-empty"]:visible').first()
			).toBeVisible({ timeout: 10_000 });
		} finally {
			// Leerstring statt null: Go überspringt JSON-null bei *string wie ein
			// fehlendes Feld (auth.go:578-Guard, gleiche Pointer-Semantik wie
			// trip.go:233) — sonst bliebe die Fremdadresse dauerhaft am Konto.
			await page.request.put('/api/auth/profile', { data: { mail_to: origMailTo ?? '' } });
		}
	});

	// ── AC-9/AC-10: Doppel-Mount Desktop+Mobile, kein horizontales Scrollen ──
	test('AC-10: mobiler Viewport — Versand-Tab ohne horizontales Scrollen', async ({ page }) => {
		const { id } = await createPreset(page);
		await page.setViewportSize({ width: 390, height: 844 });
		await page.goto(`/compare/${id}`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-versand"]:visible').first().click();

		await expect(page.locator('[data-testid="compare-step5-channel-email"]:visible').first()).toBeVisible({
			timeout: 10_000
		});
		const noHorizontalScroll = await page.evaluate(
			() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1
		);
		expect(noHorizontalScroll, 'horizontales Scrollen auf Mobile darf nicht auftreten').toBeTruthy();
	});

	// ── AC-2: Morgen-Uhrzeit ändern → Speichern → Reload → Wert bleibt ───────
	test('AC-2: geänderte Morgen-Uhrzeit übersteht Speichern + Reload', async ({ page }) => {
		const { id } = await createPreset(page); // Default: morning_enabled=true, morning_time=07:00:00
		await openVersandTab(page, id);

		const morningTime = () => page.locator('[data-testid="report-morning-time"]:visible').first();
		await expect(morningTime()).toHaveValue('07:00', { timeout: 10_000 });

		// Volle Stunde: report-morning-time-Input trägt step={3600} (VTSchedulePlan).
		await morningTime().fill('08:00');
		await morningTime().blur();
		await expect(page.locator('[data-testid="save-indicator"]')).toHaveAttribute('data-state', 'idle', {
			timeout: 10_000
		});

		await page.reload();
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-versand"]:visible').first().click();
		await expect(morningTime()).toHaveValue('08:00', { timeout: 10_000 });

		// Testdaten sauber: Ausgangswert wiederherstellen und speichern.
		await morningTime().fill('07:00');
		await expect(page.locator('[data-testid="save-indicator"]')).toHaveAttribute('data-state', 'idle', {
			timeout: 10_000
		});
	});

	// ── AC-6: Create-Flow — POST-Body enthält die 5 Slot-Felder + official_warnings ──
	// Issue #1258 Scheibe S4 (E1/E2, AC-28): die Tab-Kette waechst um die
	// reguläre Station "alarme" zwischen "layout" und "versand".
	test('AC-6: Create-Flow sendet die 5 Slot-Felder + official_warnings im POST-Body an /api/compare/presets', async ({
		page
	}) => {
		const suffix = Date.now();
		// #1329 Maßnahme B: zentralisiert über den geteilten Helfer (helpers.ts) —
		// diese Orte waren zuvor ein garantierter Leak (Kontext-Dok.).
		const [locA, locB] = await Promise.all([
			createTestLocation(page.request, { lat: 47.0, lon: 13.0, region: 'VersandVergleich-Region' }),
			createTestLocation(page.request, { lat: 47.1, lon: 13.1, region: 'VersandVergleich-Region' })
		]);
		const nameA = locA.name;
		const nameB = locB.name;

		await page.goto('/compare/new');
		await page.waitForLoadState('networkidle');
		const d = page.locator('.cm-desktop');

		await d.locator('[data-testid="compare-editor-name"]').fill('E2E-GZ-AC-6-Create-Flow-' + suffix);
		await d.locator('[data-testid="compare-editor-tab-orte"]').click();
		await d.locator('[data-testid="compare-step2-library"]').waitFor({ timeout: 8_000 });
		await d.locator('[data-testid="compare-step2-library"]').getByText(nameA, { exact: true }).click();
		await d.locator('[data-testid="compare-step2-library"]').getByText(nameB, { exact: true }).click();
		// Epic #1301 F2a: neue Kette — Wetter-Metriken-Tab besuchen schaltet
		// Wertebereiche frei (echter Klick, kein goto).
		await d.locator('[data-testid="compare-editor-tab-metriken"]').click();
		await d.locator('[data-testid="compare-editor-tab-idealwerte"]').click();
		await d.locator('[data-testid="compare-editor-tab-layout"]').click();
		await d.locator('[data-testid="compare-editor-tab-alarme"]').click();
		await d.locator('[data-testid="compare-editor-tab-versand"]').click();

		const [request] = await Promise.all([
			page.waitForRequest(
				(req) => req.url().includes('/api/compare/presets') && req.method() === 'POST'
			),
			d.locator('[data-testid="compare-editor-activate"]').click()
		]);
		const body = request.postDataJSON() as Record<string, unknown>;

		expect(body.morning_enabled).toBe(true);
		expect(body.morning_time).toBe('07:00:00');
		expect(body.evening_enabled).toBe(false);
		expect(body.evening_time).toBe('18:00:00');
		expect(body.end_date == null, 'end_date darf beim Create ohne Laufzeit-Auswahl fehlen/null sein').toBeTruthy();
		// Issue #1258 S4 (AC-27, E3): official_warnings wird unconditional gesendet
		// (F1-Neuanlage-Default false), kein sources-Key ohne Bestand.
		expect(body.official_warnings).toEqual({ enabled: false });
	});

	// Epic #1273 S4c: AC-8 („Verwerfen") entfernt — der Hub hat keinen
	// Verwerfen-Button (Autosave-Modell), die Interaktion ist gegenstandslos.

	// ── Staging-F001 (AC-5): Stundenverlauf-Toggle persistiert (Hub-Autosave) ─
	// Epic #1273 S4c: Top-N ist im Hub-Layout-Tab nicht editierbar (read-only
	// Pills, nur im Wizard) und entfällt. Die Stundenverlauf-Steuerung
	// (compare-layout-hourly-enabled-toggle) ist bewusst in den Hub geholt und
	// speichert per Autosave — sie bleibt hier der Regressionsanker.
	test('Staging-F001: Stundenverlauf-Toggle persistiert über Hub-Autosave', async ({
		page
	}) => {
		const { id } = await createPreset(page); // Default: hourly_enabled=true
		await page.goto(`/compare/${id}`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-layout"]:visible').first().click();

		const hourlyToggle = page
			.locator('[data-testid="compare-layout-hourly-enabled-toggle"]:visible')
			.first()
			.locator('input[type="checkbox"]');

		await expect(hourlyToggle).toBeChecked({ timeout: 10_000 });
		await hourlyToggle.uncheck();

		await expect(page.locator('[data-testid="save-indicator"]')).toHaveAttribute('data-state', 'idle', {
			timeout: 10_000
		});

		const res = await page.request.get(`/api/compare/presets/${id}`);
		expect(res.ok()).toBeTruthy();
		const preset = await res.json();
		expect(preset.hourly_enabled, 'Stundenverlauf-Toggle muss auf false persistieren').toBe(false);

		// Testdaten sauber: Ausgangswert wiederherstellen (Autosave).
		await hourlyToggle.check();
		await expect(page.locator('[data-testid="save-indicator"]')).toHaveAttribute('data-state', 'idle', {
			timeout: 10_000
		});
	});
});
