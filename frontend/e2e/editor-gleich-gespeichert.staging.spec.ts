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
// #3154 (#3122 B3b, Spec feat_3122_was_steht_wo.md Teil B Nr. 13/14, ADR-0124): die Kanal-Reiter der
// Metrik-Oberflaeche im Reiter Zustellung sind entfernt. Im Hub zeigt und schreibt die Karte „Was steht wo“
// im Reiter Wetter, was in welchem Kanal steht — mit EINER Reihenfolge fuer alle Stellen und einem Haken je
// Stelle; gespeichert wird `display_config.placements`, `channel_layouts` bleibt als Altfeld unberuehrt.
// Die Zusicherungen sind auf die heutige Wirkung umformuliert:
//   AC-10: je Stelle (E-Mail/Telegram/SMS) sind GENAU die Metriken der eingefrorenen Erwartung angehakt
//          (Menge; die Reihenfolge je Kanal gibt es nicht mehr, die eine Reihenfolge prueft WS-2).
//   AC-11: Speichern eines Schalters der Karte laesst `channel_layouts` und `metrics` bitgleich stehen.
//   AC-17: erstmalige SMS-Bearbeitung (cloud_total ab, gust/precipitation tauschen) steht so in `placements`
//          und in der Antwort des Endpoints (SMS-Spalte, Reihenfolge), die uebrigen Stellen unveraendert.
//
// Ausfuehren (lokal gegen ci-stack.sh mit der Haupt-Config, oder gegen Staging, aus frontend/):
//   npx playwright test --project=tests e2e/editor-gleich-gespeichert.staging.spec.ts
// Ausführen (gegen Staging, aus frontend/):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   npx playwright test --config=e2e/playwright.editor-gleich-gespeichert.staging.config.ts \
//     e2e/editor-gleich-gespeichert.staging.spec.ts

import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { test, expect, type APIRequestContext } from '@playwright/test';
import { folge, gespeichertAn, haken, oeffneKarte, schalterGespeichert, stand, tabelle, tabelleGespeichert, zeile } from './was-steht-wo.helpers';

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


const STELLEN = ['email', 'telegram', 'sms'] as const;

test.describe('Issue #2422 S2a: Karten-Anzeige = gespeicherter Stand (Golden C, Kaskadenquelle global)', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1440, height: 900 });
	});

	test.afterAll(async ({ request }) => {
		await request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
	});

	test('AC-10: je Stelle (email/telegram/sms) sind genau die Metriken der eingefrorenen Erwartung angehakt', async ({ page, request }) => {
		await createGoldenCTrip(request, TRIP_ID);
		const erwartung = ladeFixture<{ channels: Record<string, Array<{ metric_id: string }>> }>('erwartung_golden_c.json');
		const karte = await oeffneKarte(page, 'route', TRIP_ID);
		const zeilen = await folge(karte);
		for (const stelle of STELLEN) {
			const angehakt: string[] = [];
			for (const m of zeilen) {
				const h = haken(karte, m, stelle);
				if ((await h.count()) && (await h.isChecked())) angehakt.push(m);
			}
			expect([...angehakt].sort(), `AC-10: Stelle ${stelle}`).toEqual(erwartung.channels[stelle].map((m) => m.metric_id).sort());
		}
	});

	test('AC-11: Speichern in der Karte laesst channel_layouts und metrics bitgleich stehen (B9-Nachweis bei global)', async ({ page, request }) => {
		await createGoldenCTrip(request, TRIP_ID);
		const vorher = (await stand(request, 'route', TRIP_ID)).display_config;
		const karte = await oeffneKarte(page, 'route', TRIP_ID);
		const gespeichert = schalterGespeichert(page, 'route', TRIP_ID);
		await karte.getByTestId('was-steht-wo-show_yesterday_comparison').click();
		await gespeichert;
		const nachher = (await stand(request, 'route', TRIP_ID)).display_config;
		expect(nachher.channel_layouts, 'AC-11: channel_layouts veraendert').toEqual(vorher.channel_layouts);
		expect(nachher.metrics, 'AC-11: metrics (inkl. morning_enabled/evening_enabled) veraendert').toEqual(vorher.metrics);
	});

	test('AC-17: erstmalige SMS-Bearbeitung (Metrik abwaehlen + zwei benachbarte tauschen) kommt an wie eingestellt', async ({ page, request }) => {
		await createGoldenCTrip(request, TRIP_ID);
		const karte = await oeffneKarte(page, 'route', TRIP_ID);
		const vorher = await tabelle(request, 'route', TRIP_ID);
		let gespeichert = tabelleGespeichert(page, TRIP_ID);
		await haken(karte, 'cloud_total', 'sms').click();
		await gespeichert;

		const start = await folge(karte);
		const i = start.indexOf('gust');
		const j = start.indexOf('precipitation');
		expect(Math.abs(i - j), 'Messaufbau: gust und precipitation benachbart').toBe(1);
		const oben = i < j ? 'gust' : 'precipitation';
		gespeichert = tabelleGespeichert(page, TRIP_ID);
		await zeile(karte, oben).getByTestId('drag-handle').focus();
		await page.keyboard.press('Space');
		await page.keyboard.press('ArrowDown');
		await page.keyboard.press('Space');
		await gespeichert;

		const a = await tabelle(request, 'route', TRIP_ID);
		const ids = (a.placements.rows as Array<{ metric_id: string }>).map((r) => r.metric_id);
		expect(ids.indexOf('gust') - ids.indexOf('precipitation'), 'AC-17: Tausch gespeichert').toBe(i < j ? 1 : -1);
		expect(gespeichertAn(a.placements, 'cloud_total', 'sms'), 'AC-17: cloud_total in der SMS ab').toBe(false);
		for (const stelle of ['email', 'telegram'] as const) {
			const z = (vorher.rows as Array<{ metric_id: string; cells: Record<string, { state: string }> }>).find((r) => r.metric_id === 'cloud_total')?.cells?.[stelle]?.state;
			if (z === 'on' || z === 'off') expect(gespeichertAn(a.placements, 'cloud_total', stelle), `AC-17: ${stelle} unveraendert`).toBe(z === 'on');
		}
		expect((a.rows as Array<{ metric_id: string }>).map((r) => r.metric_id), 'AC-17: Antwort zeigt die neue Reihenfolge').toEqual(ids);
	});
});
