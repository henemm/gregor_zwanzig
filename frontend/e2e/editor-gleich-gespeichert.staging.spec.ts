// E2E (Staging) — Issue #2422 S2a: AC-10/AC-11/AC-17.
//
// Spec: docs/specs/modules/fix_2422_s2a_editor_gleich_gespeichert.md
//   AC-10 (Anzeige = Erwartung im echten Browser), AC-11 (Speichern -> GET =
//   eingefrorener Stand, inkl. Feld-Erhalt UND B9-Nachweis bei Kaskadenquelle
//   'global'), AC-17 (erstmalige SMS-Bearbeitung kommt an wie eingestellt).
//
// Golden C (`tests/fixtures/einstellung_auslieferung/golden_c.json`): SMS/
// Telegram OHNE eigenes Kanal-Layout -> Kaskadenquelle 'global' fuer
// sms/telegram_kurzform/premium_sms (ADR-0049, SMS-Reiter deckt Premium-SMS
// mit ab, kein eigener E2E-Reiter noetig).
//
// Datei-Form der eingefrorenen `nach_speichern_*`/`nach_aenderung_*`-Dateien
// (siehe `_editor_kette.ts::flacherMerge`): VOLLSTAENDIGER Trip-Zustand
// (`{ ...trip, display_config: {...} }`), NICHT nur das display_config-
// Fragment -- `GET /api/trips/{id}/weather-config` liefert dagegen NUR
// `trip.DisplayConfig` (flach, ohne `display_config`-Wrapper,
// weather_config.go:51). Die Vergleiche unten lesen deshalb bewusst
// `eingefroren.display_config.*` gegen `gespeichert.*`.
//
// Vorbild: weather-metrics-tab-autosave.spec.ts (createTrip/fetchTrip/GET-
// Zurücklesen, `report-show-outlook`-Checkbox als Save-Ausloeser ausserhalb
// der Metrik-Liste), Reihenfolge-Drag:
// kuerzel-marken-sichtbar.staging.spec.ts::ziehe() (VOLLSTAENDIG uebernommen,
// inkl. `.sortable-zone`-`finalize`-Warten). Toggle-/Reiter-Selektoren:
// metrik-abwahl-schreibt-alle-kanaele-durch.staging.spec.ts,
// kanal-abwahl-bleibt-reversibel.staging.spec.ts (testids `channel-tab-{email,
// telegram,sms}`, `wm2-reihenfolge-row`/`wm2-aus-row` mit `data-metric-id`,
// `wm2-grundauswahl` mit `.toggle-btn[title=...]`, `save-indicator`).
//
// GREEN erreicht (B9-/K8-Fix produktiv, alle eingefrorenen Dateien aus /50
// erzeugt: `erwartung_golden_c.json`, `nach_speichern_golden_c.json`,
// `nach_aenderung_fall4_sms_erstbearbeitung.json`). Lauf ueber eine EIGENE
// Playwright-Staging-Config (`playwright.editor-gleich-gespeichert.staging.config.ts`,
// eigene `.staging.setup.ts`) statt Aufnahme in `.github/ci_e2e_specs.txt` --
// Filter A dort schliesst `.staging.spec.ts`-Dateien strukturell aus (die
// CI-Positivliste laeuft gegen den isolierten LOKALEN Stack, nicht gegen
// Staging; Tech-Lead-Entscheid, Spec erlaubt ausdruecklich "eigene
// `*.staging.spec.ts`"). Ausgefuehrt in `/e2e-verify` nach dem Merge, nicht
// in der CI-Ampel.
//
// report_config.enabled=false im Seed (unten): Golden C hat send_sms/
// send_premium_sms=true -- ohne diese Sperre koennte ein echter Staging-
// Scheduler-Lauf waehrend des Tests einen echten Versand an die konfigurierte
// Testnummer ausloesen (#1477-Nachbarschaft). Der Editor selbst rendert alle
// drei Kanal-Reiter unabhaengig von `enabled`.
//
// Ausführen (gegen Staging, aus frontend/):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   npx playwright test --config=e2e/playwright.editor-gleich-gespeichert.staging.config.ts \
//     e2e/editor-gleich-gespeichert.staging.spec.ts

import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { test, expect, type APIRequestContext, type Page, type Locator } from '@playwright/test';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE_DIR = path.resolve(__dirname, '../../tests/fixtures/einstellung_auslieferung');

function ladeFixture<T = unknown>(name: string): T {
	return JSON.parse(readFileSync(path.join(FIXTURE_DIR, name), 'utf-8')) as T;
}

// Eindeutige Trip-ID je Lauf -- vermeidet Kollisionen zwischen parallelen
// Staging-Sitzungen (Memory: "Ein Projektordner = höchstens eine Session").
const TRIP_ID = `e2e-2422-s2a-golden-c-${Date.now()}`;

/** Golden C 1:1 uebernehmen, NUR die Stage-Daten relativ zu HEUTE nachziehen
 * -- exakt wie ``tests/tdd/_einstellung_auslieferung_fixtures.py::golden_dict``,
 * sonst behandelt Staging die Tour als archiviert (Stage-Daten liegen im
 * Fixture auf Jan-Maerz 2026). `report_config.enabled=false`: kein echter
 * Versand waehrend des Tests (s.o.). */
function goldenCAlsTripBody(id: string): Record<string, unknown> {
	const golden = ladeFixture<{
		stages: Array<{ date: string; [k: string]: unknown }>;
		report_config?: Record<string, unknown>;
		[k: string]: unknown;
	}>('golden_c.json');
	const heute = new Date();
	const stages = golden.stages.map((s, i) => {
		const d = new Date(heute);
		d.setDate(d.getDate() + i - 1);
		return { ...s, date: d.toISOString().slice(0, 10) };
	});
	return {
		...golden,
		id,
		name: `E2E #2422 S2a ${id}`,
		stages,
		report_config: { ...(golden.report_config ?? {}), enabled: false },
	};
}

async function createGoldenCTrip(request: APIRequestContext, id: string) {
	await request.delete(`/api/trips/${id}`).catch(() => {});
	const res = await request.post('/api/trips', { data: goldenCAlsTripBody(id) });
	expect([200, 201], `Seed HTTP ${res.status()}`).toContain(res.status());
}

async function fetchWeatherConfig(request: APIRequestContext, id: string) {
	const res = await request.get(`/api/trips/${id}/weather-config`);
	expect(res.ok(), `GET weather-config HTTP ${res.status()}`).toBeTruthy();
	return res.json();
}

/** Liest die Reihenfolge-Zeilen EINES Reiters in DOM-Reihenfolge -- prueft
 * damit auch die REIHENFOLGE (nicht nur "ist irgendwo sichtbar"), was der
 * eigentliche B9-Anzeige-Nachweis ist (AC-10). */
// Scope auf den Kanal-Reiter-Block: `wm2-aus-gruppe`/`wm2-aus-row`/`wm2-reihenfolge-row`
// gibt es auf der Seite ZWEIMAL (Kanal-Reiter + 3-Tages-Vorschau), siehe
// WeatherMetricsTab.svelte:1741-1745 (Anker `weather-metrics-kanal-reihenfolge`).
function kanalBlock(tab: Locator): Locator {
	return tab.getByTestId('weather-metrics-kanal-reihenfolge');
}

async function geleseneReihenfolge(tab: Locator): Promise<string[]> {
	return kanalBlock(tab).locator('[data-testid="wm2-reihenfolge-row"]').evaluateAll((rows) =>
		rows.map((r) => r.getAttribute('data-metric-id') ?? ''),
	);
}

/** Reihenfolge-Drag (VOLLSTAENDIG uebernommen aus
 * kuerzel-marken-sichtbar.staging.spec.ts::ziehe -- inkl. `.sortable-zone`-
 * `finalize`-Warten, sonst liest eine feste Pause danach faelschlich einen
 * `consider`-Zwischenstand als abgeschlossene Geste). */
async function ziehe(page: Page, quelle: Locator, ziel: Locator): Promise<void> {
	await quelle.scrollIntoViewIfNeeded();
	await ziel.scrollIntoViewIfNeeded();
	const q = await quelle.boundingBox();
	const z = await ziel.boundingBox();
	if (!q || !z) throw new Error('ziehe: Quelle/Ziel ohne BoundingBox');

	await page.evaluate(() => {
		const zone = document.querySelector('.sortable-zone');
		if (!zone) throw new Error('ziehe: .sortable-zone nicht im DOM gefunden');
		(window as unknown as { __gzDndFinalize?: Promise<void> }).__gzDndFinalize = new Promise((resolve) =>
			zone.addEventListener('finalize', () => resolve(), { once: true }),
		);
	});

	await page.mouse.move(q.x + q.width / 2, q.y + q.height / 2);
	await page.mouse.down();
	await page.mouse.move(q.x + q.width / 2, q.y + q.height / 2 - 12, { steps: 6 });
	await page.waitForTimeout(120);
	await page.mouse.move(z.x + z.width / 2, z.y + z.height / 2, { steps: 15 });
	await page.waitForTimeout(120);
	await page.mouse.up();

	const gefeuert = await page.evaluate(({ ms }) => {
		const w = window as unknown as { __gzDndFinalize?: Promise<void> };
		if (!w.__gzDndFinalize) return Promise.resolve(false);
		return Promise.race([
			w.__gzDndFinalize.then(() => true),
			new Promise<boolean>((resolve) => setTimeout(() => resolve(false), ms)),
		]);
	}, { ms: 3_000 });
	if (!gefeuert) throw new Error('ziehe: "finalize"-Ereignis der Sortable-Zone kam nicht rechtzeitig');
}

test.describe('Issue #2422 S2a: Editor-Anzeige = gespeicherter Stand (Golden C, Kaskadenquelle global)', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1440, height: 900 });
	});

	test.afterAll(async ({ request }) => {
		await request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
	});

	test('AC-10: jeder Kanal-Reiter (email/telegram/sms) zeigt die eingefrorene Erwartung in EXAKT dieser Reihenfolge, ohne Ausnahme', async ({
		page,
		request,
	}) => {
		await createGoldenCTrip(request, TRIP_ID);
		const erwartung = ladeFixture<{ channels: Record<string, Array<{ metric_id: string }>> }>(
			'erwartung_golden_c.json',
		);

		await page.goto(`/trips/${TRIP_ID}?tab=weather`);
		await page.getByTestId('trip-detail-tab-weather').click();
		const tab = page.getByTestId('weather-metrics-tab');
		await expect(tab).toBeVisible({ timeout: 10_000 });
		await expect(tab.getByTestId('wm2-grundauswahl').locator('.toggle-btn').first()).toBeVisible({
			timeout: 10_000,
		});

		for (const reiter of ['email', 'telegram', 'sms'] as const) {
			await tab.getByTestId(`channel-tab-${reiter}`).click();
			const erwarteteReihenfolge = erwartung.channels[reiter].map((m) => m.metric_id);
			await expect
				.poll(() => geleseneReihenfolge(tab), { timeout: 10_000 })
				.toEqual(erwarteteReihenfolge);
		}
	});

	test('AC-11: Speichern ohne Aenderung (SMS-Reiter bleibt unbearbeitet) -> GET = eingefrorener Stand (B9-Nachweis bei global)', async ({
		page,
		request,
	}) => {
		await createGoldenCTrip(request, TRIP_ID);
		await page.goto(`/trips/${TRIP_ID}?tab=weather`);
		await page.getByTestId('trip-detail-tab-weather').click();
		const tab = page.getByTestId('weather-metrics-tab');
		await expect(tab).toBeVisible({ timeout: 10_000 });

		// Auto-Save OHNE die SMS-Metrik-Auswahl anzufassen UND ohne den
		// gespeicherten Endzustand zu veraendern: ein Tab-Besuch allein loest
		// laut bestehender Gate-Semantik (weatherSaveGate) KEINEN Speichervorgang
		// aus (Vorbild: "Reiter öffnen ohne Änderung → kein PUT" im Bestand) --
		// `report-show-outlook` (EditReportConfigSection.svelte) ist NICHT
		// geeignet, weil dieses Feld ausserhalb von display_config liegt und
		// laut Bestandstest NUR den Trip-PUT (nicht weather-config) ausloest.
		// Stattdessen: im E-Mail-Reiter (SMS bleibt unberuehrt) eine aktuell
		// AUSGESCHALTETE Metrik (uv_index, golden_c.json::channel_layouts.email)
		// AN- und wieder AUSSCHALTEN -- der Netto-Endzustand ist identisch zu
		// Golden C, aber `userTouched` wird gesetzt (das Gate prueft nur "wurde
		// je beruehrt", nicht "weicht vom Original ab" -- Kommentar bei
		// handleSave() oben in WeatherMetricsTab.svelte), der reale
		// Speicherpfad (buildWeatherPayload -> PUT /weather-config) laeuft
		// also echt, mit dem GLEICHEN Ergebnis wie "nichts angefasst".
		await tab.getByTestId('channel-tab-email').click();
		const uvOffToggle = kanalBlock(tab).locator(
			'[data-testid="wm2-aus-gruppe"] [data-testid="wm2-aus-row"][data-metric-id="uv_index"] button',
		);
		await expect(uvOffToggle).toBeVisible();
		await uvOffToggle.click();
		const uvOnRow = kanalBlock(tab).locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="uv_index"]');
		await expect(uvOnRow).toBeVisible();
		const [putResponse] = await Promise.all([
			page.waitForResponse(
				(r) => r.url().includes(`/api/trips/${TRIP_ID}/weather-config`) && r.request().method() === 'PUT',
				{ timeout: 10_000 },
			),
			uvOnRow.getByRole('button', { name: 'Aus' }).click(),
		]);
		expect(putResponse.ok(), `weather-config PUT HTTP ${putResponse.status()}`).toBeTruthy();

		const gespeichert = await fetchWeatherConfig(request, TRIP_ID);
		const eingefroren = ladeFixture<{ display_config: { channel_layouts: unknown; metrics: unknown } }>(
			'nach_speichern_golden_c.json',
		);
		expect(gespeichert.channel_layouts, 'AC-11: channel_layouts weicht vom eingefrorenen Stand ab').toEqual(
			eingefroren.display_config.channel_layouts,
		);
		expect(
			gespeichert.metrics,
			'AC-11: metrics (inkl. morning_enabled/evening_enabled) weicht ab (K8-Fix)',
		).toEqual(eingefroren.display_config.metrics);
	});

	test('AC-17: erstmalige SMS-Bearbeitung (Metrik abwaehlen + zwei benachbarte tauschen) kommt an wie eingestellt', async ({
		page,
		request,
	}) => {
		await createGoldenCTrip(request, TRIP_ID);
		await page.goto(`/trips/${TRIP_ID}?tab=weather`);
		await page.getByTestId('trip-detail-tab-weather').click();
		const tab = page.getByTestId('weather-metrics-tab');
		await expect(tab).toBeVisible({ timeout: 10_000 });

		await tab.getByTestId('channel-tab-sms').click();

		// Fall 4 (aenderungsfaelle.json::fall4_sms_erstbearbeitung): cloud_total
		// abwaehlen, dann gust/precipitation (im SMS-Reiter BENACHBART, Position
		// 0/1 -- ein Drag ist ein Verschieben, kein reiner Tausch; ein
		// nicht-benachbartes Paar wie gust/wind wuerde bei einem einzelnen Drag
		// eine ANDERE Zielreihenfolge ergeben als der Tausch-Nachbau im TS-Kern)
		// tauschen -- dieselbe Bedienung wie in `_editor_kette.ts::wendeAenderungAn`.
		const cloudTotalRow = kanalBlock(tab).locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="cloud_total"]');
		await expect(cloudTotalRow).toBeVisible();
		await cloudTotalRow.getByRole('button', { name: 'Aus' }).click();
		await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });

		const gustRow = kanalBlock(tab).locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="gust"]');
		const precipRow = kanalBlock(tab).locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="precipitation"]');
		const [putResponse] = await Promise.all([
			page.waitForResponse(
				(r) => r.url().includes(`/api/trips/${TRIP_ID}/weather-config`) && r.request().method() === 'PUT',
				{ timeout: 10_000 },
			),
			ziehe(page, gustRow, precipRow),
		]);
		expect(putResponse.ok(), `weather-config PUT HTTP ${putResponse.status()}`).toBeTruthy();
		await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });

		const gespeichert = await fetchWeatherConfig(request, TRIP_ID);
		const eingefroren = ladeFixture<{ display_config: { channel_layouts: unknown; metrics: unknown } }>(
			'nach_aenderung_fall4_sms_erstbearbeitung.json',
		);
		expect(
			gespeichert.channel_layouts,
			'AC-17: channel_layouts.sms weicht vom eingefrorenen Aenderungsstand ab',
		).toEqual(eingefroren.display_config.channel_layouts);
		expect(
			gespeichert.metrics,
			'AC-17: die globale metrics-Liste muss unveraendert bleiben (nur SMS wurde bearbeitet)',
		).toEqual(eingefroren.display_config.metrics);
	});
});
