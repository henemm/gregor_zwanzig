// E2E-Tests für Issue #619 — Auswahl-/Schalter-UI für E-Mail-Elemente.
//
// Spec: docs/specs/modules/issue_619_mail_elements_ui.md
// Workflow: issue-619-mail-elements-ui
//
// Ziel-Oberfläche (migriert durch Fix #1047, docs/specs/modules/fix_1047_mail_content_tab_restore.md):
// Trip-Detail-Seite /trips/[id]?tab=wetter-metriken, Reiter "Wetter-Metriken" (= "Inhalt",
// MailInhaltCard.svelte eingebunden über WeatherMetricsTab.svelte). Der
// (Seit #1743 gibt es keinen eigenen Versand-Reiter mehr; der Versand-Abschnitt
// `#versand` steht im Reiter Wetter-Metriken und enthaelt die Karte NICHT.)
// Der fruehere Reiter "Briefing-Zeitplan" (?tab=versand) zeigte die Karte seit #736 bewusst NICHT
// mehr (Kanal-/Zeitplan-Reiter); zwischenzeitlich (#942) fehlte sie versehentlich auch
// im Wetter-Metriken-Reiter — Fix #1047 stellt sie dort wieder her.
//
// Aktuelle TestIDs (nach #664/#722/#785 — "Metriken-Überblick"-Checkbox seit #971/#774
// entfernt, `report-show-metrics-summary` existiert NICHT mehr im DOM):
//   report-mail-content               — Container des Abschnitts
//   report-show-outlook               — Schalter Ausblick
//   report-show-stage-stats           — Schalter Etappen-Kennzahlen
//   report-show-yesterday-comparison  — Schalter Vortagesvergleich (#785)
//   report-email-format-full / -compact — Format-Schalter (#722)
//
// #3154 (#3122 B3b, Spec feat_3122_was_steht_wo.md Teil B Nr. 14, AC-30): die Karte „E-Mail-Inhalt“ ist aus
// dem Übergangsblock des Reiters Zustellung entfernt. Etappen-Kennzahlen, Vortag-Vergleich, E-Mail-Format und
// der 3-Tages-Ausblick (je Briefing, `outlook_reports`) stehen genau einmal in der Karte „Was steht wo“ im
// Reiter Wetter; die Fälle unten laufen dort. Der alte Schalter `show_outlook` hat keine Bedienung mehr — das
// Feld bleibt gespeichert (Read-Modify-Write), AC-3 prüft genau das.

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

const TRIP_PREFIX = 'e2e-issue-619';

function tripId(suffix: string) {
	return `${TRIP_PREFIX}-${suffix}`;
}

async function createTrip(
	request: import('@playwright/test').APIRequestContext,
	id: string,
	report_config: Record<string, unknown> = { enabled: true, morning_time: '07:00', evening_time: '18:00' }
) {
	const res = await request.post('/api/trips', {
		data: {
			id,
			name: `Issue 619 ${id}`,
			stages: [
				{
					id: `${id}-stage-1`,
					name: 'Etappe',
					date: new Date().toISOString().slice(0, 10),
					waypoints: [{ id: `${id}-wp-1`, name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 500 }]
				}
			],
			report_config,
			alert_rules: []
		}
	});
	expect([200, 201]).toContain(res.status());
}

async function deleteTrip(
	request: import('@playwright/test').APIRequestContext,
	id: string
) {
	const res = await request.delete(`/api/trips/${id}`);
	expect([200, 204, 404]).toContain(res.status());
}

/** #3154: Reiter Zustellung (Briefing-Zeiten, Kanal-Tabelle). */
async function openZustellung(page: import('@playwright/test').Page, id: string) {
	await page.goto(`/trips/${id}?tab=zustellung`);
	await page.getByTestId('zustellung-kanal-tabelle').waitFor({ state: 'visible' });
}

/** #3154: die Schalter der Mail-Inhalte stehen in der Karte „Was steht wo“ im Reiter Wetter. */
async function openKarte(page: import('@playwright/test').Page, id: string) {
	await page.goto(`/trips/${id}?tab=wetter`);
	const karte = page.getByTestId('was-steht-wo');
	await karte.getByTestId('was-steht-wo-show_stage_stats').waitFor({ state: 'visible', timeout: 20_000 });
	return karte;
}

/** Klickt einen Schalter der Karte und wartet auf den erfolgreichen PUT des Trips. */
async function schalteUndSpeichere(page: import('@playwright/test').Page, id: string, testid: string) {
	const put = page.waitForResponse((r) => r.url().endsWith(`/api/trips/${id}`) && r.request().method() === 'PUT' && r.ok());
	await page.getByTestId('was-steht-wo').getByTestId(testid).click();
	await put;
}

test.describe('Issue #619: E-Mail-Elemente konfigurierbar', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	// ── AC-1: Drei verbleibende Bausteine + Ausblick sichtbar (Issue #723) ────────
	// Fix #1047: "Metriken-Überblick" (report-show-metrics-summary) hat seit #971/#774
	// keine UI-Checkbox mehr — ersetzt durch report-show-yesterday-comparison (#785).
	test('AC-1: Drei Bausteine (Ausblick/Etappen-Kennzahlen/Vortagesvergleich) sichtbar', async ({
		page,
		request
	}) => {
		const id = tripId('ac1');
		await createTrip(request, id, {
			enabled: true,
			morning_time: '07:00',
			evening_time: '18:00',
			show_stage_stats: true,
			show_outlook: true,
			show_yesterday_comparison: false
		});
		try {
			// #3154: Etappen-Kennzahlen, Vortag-Vergleich und 3-Tages-Ausblick (je Briefing) in der Karte.
			const karte = await openKarte(page, id);

			const stageStats = karte.getByTestId('was-steht-wo-show_stage_stats');
			const yesterdayComparison = karte.getByTestId('was-steht-wo-show_yesterday_comparison');
			await expect(stageStats).toBeVisible();
			await expect(yesterdayComparison).toBeVisible();
			await expect(karte.getByTestId('was-steht-wo-ausblick-morning')).toBeVisible();
			await expect(karte.getByTestId('was-steht-wo-ausblick-evening')).toBeVisible();

			// Spiegeln den gespeicherten Stand
			await expect(stageStats).toHaveAttribute('aria-checked', 'true');
			await expect(yesterdayComparison).toHaveAttribute('aria-checked', 'false');
			await expect(page.locator('[data-testid="report-show-outlook"], [data-testid="report-mail-content"]')).toHaveCount(0);

			// Entfernte Optionen nicht mehr im DOM
			await expect(page.locator('[data-testid="report-show-quick-take"]')).toHaveCount(0);
			await expect(page.locator('[data-testid="report-show-stability"]')).toHaveCount(0);
			await expect(page.locator('[data-testid="report-show-highlights"]')).toHaveCount(0);
			await expect(page.locator('[data-testid="report-show-metrics-summary"]')).toHaveCount(0);
		} finally {
			await deleteTrip(request, id);
		}
	});

	// ── Fix #1047 AC-2: Zeitplan-Karten NICHT im Wetter-Metriken-Reiter (#942-Regressionsschutz) ──
	// Issue #1743: der Zeitplan steht jetzt im Reiter Wetter-Metriken — aber
	// AUSSCHLIESSLICH im Versand-Abschnitt (#versand), nicht im Metriken-Teil.
	test('Fix #1047 AC-2 / #1743: Morgen-/Abend-Zeitplan nur im Versand-Abschnitt des Wetter-Metriken-Reiters', async ({
		page,
		request
	}) => {
		const id = tripId('fix1047-ac2');
		await createTrip(request, id);
		try {
			await openZustellung(page, id);

			// #2795 S3b 1b: Zeitplan = Briefing-Zeiten-Karten des Reiters Zustellung (Anker #versand, AC-2).
			const abschnitt = page.locator('#versand');
			await expect(abschnitt).toHaveAttribute('data-abschnitt', 'briefing-zeiten', { timeout: 15_000 });
			await expect(abschnitt.locator('[data-testid="zustellung-morgen-schalter"]')).toHaveCount(1);
			await expect(abschnitt.locator('[data-testid="zustellung-abend-schalter"]')).toHaveCount(1);
			await expect(page.locator('[data-testid="zustellung-morgen-schalter"]')).toHaveCount(1);
			await expect(page.locator('[data-testid="zustellung-abend-schalter"]')).toHaveCount(1);
			await expect(page.locator('[data-testid="morning-master-switch"], [data-testid="evening-master-switch"]')).toHaveCount(0);
		} finally {
			await deleteTrip(request, id);
		}
	});

	// ── Fix #1047 AC-3: Mail-Inhalt-Karte bleibt im Versand-Reiter unsichtbar (unverändert) ──
	// Issue #1743: kein Reiter `versand` mehr — die Karte steht nur EINMAL im Reiter,
	// und zwar nicht im Versand-Abschnitt.
	test('Fix #1047 AC-3 / #1743: E-Mail-Inhalt-Karte nicht im Versand-Abschnitt (keine Dopplung)', async ({
		page,
		request
	}) => {
		const id = tripId('fix1047-ac3');
		await createTrip(request, id);
		try {
			await page.goto(`/trips/${id}?tab=zustellung#versand`);
			// #2795 S3b 1b: der Anker #versand liegt auf den Briefing-Zeiten des Reiters Zustellung.
			// #3154: die Mail-Inhalt-Karte steht im Reiter Zustellung gar nicht mehr; das E-Mail-Format
			// steht genau einmal, in der Karte „Was steht wo“ im Reiter Wetter (AC-30).
			const abschnitt = page.locator('#versand');
			await page.getByTestId('zustellung-kanal-tabelle').waitFor({ state: 'visible' });
			await expect(abschnitt).toHaveAttribute('data-abschnitt', 'briefing-zeiten');
			await expect(page.locator('[data-testid="report-mail-content"], [data-testid="report-email-format-switcher"]')).toHaveCount(0);
			await openKarte(page, id);
			await expect(page.getByTestId('was-steht-wo-email-format')).toHaveCount(1);
			await expect(page.locator('[data-testid="report-mail-content"], [data-testid="report-email-format-switcher"]')).toHaveCount(0);
		} finally {
			await deleteTrip(request, id);
		}
	});

	// Fix #1047 AC-5 (Anlege-Assistent zeigt Karte nicht doppelt, #934-Regressionsschutz):
	// bewusst NICHT als automatisierter E2E-Test umgesetzt. Der Freischalt-Fluss des
	// Wetter-Metriken-Wizard-Schritts (GPX-Upload pro Etappe, `unlocked`-Ableitung) ist
	// eigenständig fragil und unabhängig von diesem Fix. Da der Fix lediglich den bereits
	// vor #942 vorhandenen `{#if !createMode}`-Schutz unverändert wiederverwendet (kein
	// neues Risiko), wird AC-5 stattdessen manuell in Phase 6 (Validierung) durchgeklickt.

	// ── AC-2: Tages-Summe-Metriken entfernt aus UI (Issue #723) ────────────────
	// Kein UI-Test für daily_summary_metrics mehr (kein DOM-Zugang).
	// Persistence-Test: Feld bleibt nach Save via Spread-Beibehaltung erhalten.
	test('AC-2: daily_summary_metrics bleiben nach Save erhalten (Bestandsdaten-Schutz)', async ({
		page,
		request
	}) => {
		const id = tripId('ac2');
		await createTrip(request, id, {
			enabled: true,
			morning_time: '07:00',
			evening_time: '18:00',
			daily_summary_metrics: ['precipitation', 'thunder']
		});
		try {
			// #3154: Etappen-Kennzahlen in der Karte umschalten (Teilfeld-PUT, Auto-Save).
			await openKarte(page, id);
			await schalteUndSpeichere(page, id, 'was-steht-wo-show_stage_stats');

			const after = await request.get(`/api/trips/${id}`);
			expect(after.ok()).toBe(true);
			const rc = (await after.json()).report_config;
			// daily_summary_metrics via Spread unverändert erhalten
			expect([...rc.daily_summary_metrics].sort()).toEqual(['precipitation', 'thunder'].sort());
		} finally {
			await deleteTrip(request, id);
		}
	});

	// ── AC-3: Ausblick umschalten + speichern + persistiert ────────────────────
	// #3154: der Ausblick wird je Briefing in der Karte geschaltet (`outlook_reports` der Tabelle); das
	// Altfeld `show_outlook` hat keine Bedienung mehr und bleibt beim Speichern unverändert erhalten.
	test('AC-3: Ausblick-Schalter ändern, speichern, persistiert', async ({
		page,
		request
	}) => {
		const id = tripId('ac3');
		await createTrip(request, id, {
			enabled: true,
			morning_time: '07:00',
			evening_time: '18:00',
			show_outlook: true
		});
		try {
			const karte = await openKarte(page, id);
			const abend = karte.getByTestId('was-steht-wo-ausblick-evening');
			const vorher = (await abend.getAttribute('aria-checked')) === 'true';
			const tabelle = page.waitForResponse(
				(r) => r.request().method() === 'PUT' && new URL(r.url()).pathname === `/api/briefings/${id}/placements` && r.ok()
			);
			await abend.click();
			await tabelle;

			// Reload via API: persistiert; das Altfeld show_outlook bleibt unberührt.
			const after = await request.get(`/api/trips/${id}`);
			expect(after.ok()).toBe(true);
			const trip = await after.json();
			expect((trip.display_config.placements.outlook_reports as string[]).includes('evening')).toBe(!vorher);
			expect(trip.report_config.show_outlook).toBe(true);
			await page.reload();
			await expect((await openKarte(page, id)).getByTestId('was-steht-wo-ausblick-evening')).toHaveAttribute('aria-checked', vorher ? 'false' : 'true');
		} finally {
			await deleteTrip(request, id);
		}
	});

	// ── AC-4: Read-Modify-Write — Fremdfelder bleiben erhalten ─────────────────
	test('AC-4: Unbekannte report_config-Felder bleiben nach Save erhalten', async ({
		page,
		request
	}) => {
		const id = tripId('ac4');
		await createTrip(request, id, {
			enabled: true,
			morning_time: '07:00',
			evening_time: '18:00',
			custom_unknown_field: 'preserve-me',
			change_threshold_temp_c: 5.0,
			change_threshold_wind_kmh: 20.0
		});
		try {
			// #3154: Vortag-Vergleich in der Karte umschalten (Teilfeld-PUT, Auto-Save).
			await openKarte(page, id);
			await schalteUndSpeichere(page, id, 'was-steht-wo-show_yesterday_comparison');

			const after = await request.get(`/api/trips/${id}`);
			expect(after.ok()).toBe(true);
			const rc = (await after.json()).report_config;
			expect(rc.custom_unknown_field).toBe('preserve-me');
			expect(rc.change_threshold_temp_c).toBe(5.0);
			expect(rc.change_threshold_wind_kmh).toBe(20.0);
		} finally {
			await deleteTrip(request, id);
		}
	});

	// ── AC-5 → Fix #1047 AC-6: show_metrics_summary bleibt Bestandsdaten-erhalten ──
	// show_metrics_summary hat seit #971/#774 kein UI-Element mehr (Checkbox entfernt,
	// Feld wird seit #790 im Mail-Renderer unconditional gerendert). Statt eines nicht
	// mehr möglichen UI-Klicks wird hier geprüft, dass das Feld beim Speichern eines
	// ANDEREN Bausteins unverändert erhalten bleibt (Read-Modify-Write-Beweis).
	test('Fix #1047 AC-6: show_metrics_summary bleibt nach Save eines anderen Bausteins erhalten', async ({
		page,
		request
	}) => {
		const id = tripId('ac5');
		await createTrip(request, id, {
			enabled: true,
			morning_time: '07:00',
			evening_time: '18:00',
			show_metrics_summary: true
		});
		try {
			await openKarte(page, id);

			// Kein UI-Element für show_metrics_summary mehr vorhanden.
			await expect(page.locator('[data-testid="report-show-metrics-summary"]')).toHaveCount(0);

			// Anderen Baustein in der Karte ändern und per Auto-Save speichern (#3154).
			await schalteUndSpeichere(page, id, 'was-steht-wo-show_stage_stats');

			const after = await request.get(`/api/trips/${id}`);
			const rc = (await after.json()).report_config;
			expect(rc.show_metrics_summary).toBe(true);
		} finally {
			await deleteTrip(request, id);
		}
	});
});
