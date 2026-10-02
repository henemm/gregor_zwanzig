// TDD RED — Issue #2422 S3 (Kanal-An/Aus-Kette), AC-23 + AC-24.
// Spec: docs/specs/modules/fix_2422_s3_kanal_an_aus_kette.md
//       ("Semantik der Slot-Prüfung" -> Frontend, Verdikt N2).
//
// EINE Regel, drei Fassungen (Python `slot_aktiv`, Go `deriveFlatFields`, TS
// `reportSlotAktiv`), getrieben von DERSELBEN Fallzeilen-Tabelle
// `tests/fixtures/report_config_slot_faelle.json` (Felder name, report_config,
// slot_morning, slot_evening). Die Datei wird hier per relativem Pfad gelesen.
//
// Vier Naehte, weil "die Funktion stimmt" die Anzeige nicht traegt (Prüfort =
// Wirkort):
//   1. Helfer `reportSlotAktiv(rc, slot)` selbst (KÜNFTIG, existiert noch
//      nicht: frontend/src/lib/utils/reportSlotAktiv.ts).
//   2. Die ECHTEN Leser der Trip-Uebersicht, bestehende Module, die heute
//      strikt `=== true` lesen und damit Altdaten (enabled=true ohne
//      Per-Slot-Schluessel) als "aus" anzeigen (Defekt N2):
//        - getReportSchedule        (utils/rightColumn.ts)
//        - setupStepTrip            (utils/cockpitHelpers568.ts, Schritt "Reports")
//        - plannedBriefings         (routes/_home/cockpitHelpers.ts)
//        - TripKachel.svelte        (SSR-Render, "Reports ✓")
//      HINWEIS Spec-Zeilenverweis: die Spec nennt "deriveNextSend" in
//      cockpitHelpers.ts:151 — dort steht `plannedBriefings`. `deriveNextSend`
//      und `setupStepCompare` (cockpitHelpers568.ts:113/247) nehmen ein
//      ComparePreset; der Ortsvergleich-Zweig bleibt laut Spec unberuehrt und
//      wird hier bewusst NICHT gegen die Trip-Tabelle geprueft.
//   3. Editor-Startzustand: reine Regel (`editor_startzustand_folgt_der_regel`)
//      PLUS SSR-Render von VersandTab (route). (#2277 S5: die zweite Naht, die alte
//      Report-Config-Section, entfiel mit dem Code.)
//      ACHTUNG (Messgrenze): beide Komponenten setzen morning_enabled/
//      evening_enabled heute `$state(true)` und ueberschreiben sie ERST in
//      `onMount`, das unter svelte/server NIE laeuft. Die SSR-Zeilen mit
//      erwartet=false sind deshalb heute rot, die mit erwartet=true gruen aus
//      Zufall (Default). Die SSR-Naht wird nur dann zu einem gueltigen Nachweis
//      der Regel, wenn /50 den Startwert BEIM ERZEUGEN aus der Regel bildet
//      (`$state(untrack(() => reportSlotAktiv(reportConfig, 'morning')))`,
//      Muster der send_*-Flags, VersandTab.svelte:143). Diese Anforderung ist
//      Teil der Erwartung dieses Tests.
//   4. NICHT bewiesen (-> E2E AC-26): Klick auf "Abend aktiv", Speichern,
//      Rueckschreiben in den Editor, TripHeader.briefingValue, +page.svelte:127.
//
// Kein Mock. Echte Module, echte Komponenten (svelte/server `render`).
//
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/utils/__tests__/report_slot_aktiv.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

import { getReportSchedule } from '../rightColumn.ts';
import { setupStepTrip } from '../cockpitHelpers568.ts';
import { plannedBriefings, heroKanaele, reportChannels } from '../../../routes/_home/cockpitHelpers.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> utils -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../..');
// frontend -> Repo-Wurzel
const REPO = path.resolve(FRONTEND, '..');

register(
	pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

// ── Geteilte Fallzeilen-Tabelle ──────────────────────────────────────────────
interface Fall {
	name: string;
	report_config: Record<string, unknown> | null;
	slot_morning: boolean;
	slot_evening: boolean;
}
const TABELLE = path.join(REPO, 'tests', 'fixtures', 'report_config_slot_faelle.json');
assert.ok(existsSync(TABELLE), `Fallzeilen-Tabelle fehlt: ${TABELLE}`);
const FAELLE: Fall[] = JSON.parse(readFileSync(TABELLE, 'utf-8')).faelle;
assert.ok(FAELLE.length >= 12, 'Tabelle unerwartet kurz — Fallzeilen fehlen');

// ── Kuenftiger Helfer: dynamisch laden, damit die Leser-Tests unabhaengig
//    von seinem Fehlen an ihrer EIGENEN Sollaussage scheitern ────────────────
type SlotFn = (rc: unknown, slot: 'morning' | 'evening') => boolean;
async function ladeHelfer(): Promise<SlotFn> {
	const datei = path.join(HERE, '..', 'reportSlotAktiv.ts');
	if (!existsSync(datei)) {
		assert.fail(
			'reportSlotAktiv.ts fehlt — Helfer `reportSlotAktiv(rc, slot)` entsteht in /50 ' +
				'(frontend/src/lib/utils/reportSlotAktiv.ts)'
		);
	}
	const mod = await import(pathToFileURL(datei).href);
	assert.equal(typeof mod.reportSlotAktiv, 'function', 'reportSlotAktiv ist nicht exportiert');
	return mod.reportSlotAktiv as SlotFn;
}

const rcOf = (f: Fall) => (f.report_config === null ? undefined : f.report_config);
const tripOf = (f: Fall) =>
	({ id: 't1', name: 'Tabellen-Trip', stages: [], report_config: rcOf(f) }) as never;

// ─────────────────────────────────────────────────────────────────────────────
describe('AC-23 Naht 1 — reportSlotAktiv gegen die geteilte Tabelle', () => {
	for (const f of FAELLE) {
		test(`reportSlotAktiv — ${f.name}`, async () => {
			const reportSlotAktiv = await ladeHelfer();
			assert.equal(
				reportSlotAktiv(rcOf(f), 'morning'),
				f.slot_morning,
				`Morgen: erwartet ${f.slot_morning} fuer ${JSON.stringify(f.report_config)}`
			);
			assert.equal(
				reportSlotAktiv(rcOf(f), 'evening'),
				f.slot_evening,
				`Abend: erwartet ${f.slot_evening} fuer ${JSON.stringify(f.report_config)}`
			);
		});
	}
});

// ─────────────────────────────────────────────────────────────────────────────
describe('AC-23 Naht 2a — getReportSchedule (rechte Spalte / Trip-Uebersicht)', () => {
	for (const f of FAELLE) {
		test(`getReportSchedule — ${f.name}`, () => {
			const s = getReportSchedule(tripOf(f));
			assert.equal(
				s.morning_enabled,
				f.slot_morning,
				`Anzeige "Morgen" fuer ${JSON.stringify(f.report_config)}: erwartet ${f.slot_morning}, ` +
					`ist ${s.morning_enabled} (rightColumn.ts liest strikt === true)`
			);
			assert.equal(
				s.evening_enabled,
				f.slot_evening,
				`Anzeige "Abend" fuer ${JSON.stringify(f.report_config)}: erwartet ${f.slot_evening}, ` +
					`ist ${s.evening_enabled}`
			);
		});
	}
});

describe('AC-23 Naht 2b — setupStepTrip, Schritt "Reports" (cockpitHelpers568)', () => {
	for (const f of FAELLE) {
		test(`setupStepTrip.Reports — ${f.name}`, () => {
			const schritt = setupStepTrip(tripOf(f)).find((s) => s.label === 'Reports');
			assert.ok(schritt, 'Schritt "Reports" fehlt');
			const erwartet = f.slot_morning || f.slot_evening;
			assert.equal(
				schritt.done,
				erwartet,
				`Reports-Haken fuer ${JSON.stringify(f.report_config)}: erwartet ${erwartet} ` +
					'(morning || evening nach Tabelle), cockpitHelpers568.ts:61-62 liest strikt === true'
			);
		});
	}
});

describe('AC-23 Naht 2c — plannedBriefings (Startseite, routes/_home/cockpitHelpers)', () => {
	for (const f of FAELLE) {
		test(`plannedBriefings — ${f.name}`, () => {
			// Ohne sentLog/tripId: rein aus report_config (kein Datum-Einfluss auf die Zeilenanzahl).
			const kinds = plannedBriefings(rcOf(f) as never).map((r) => r.kind);
			assert.equal(
				kinds.includes('morgen'),
				f.slot_morning,
				`Zeile "morgen" fuer ${JSON.stringify(f.report_config)}: erwartet ${f.slot_morning}, Zeilen=${JSON.stringify(kinds)}`
			);
			assert.equal(
				kinds.includes('abend'),
				f.slot_evening,
				`Zeile "abend" fuer ${JSON.stringify(f.report_config)}: erwartet ${f.slot_evening}, Zeilen=${JSON.stringify(kinds)}`
			);
		});
	}
});

describe('AC-23 Naht 2d — TripKachel.svelte (SSR): "Reports ✓"', () => {
	for (const f of FAELLE) {
		test(`TripKachel — ${f.name}`, async () => {
			const { render } = await import('svelte/server');
			const TripKachel = (
				await import(
					pathToFileURL(path.join(FRONTEND, 'src/routes/_home/TripKachel.svelte')).href
				)
			).default;
			const html = render(TripKachel, { props: { trip: tripOf(f) } }).body;
			const erwartet = f.slot_morning || f.slot_evening;
			assert.equal(
				html.includes('Reports ✓'),
				erwartet,
				`Kachel-Hinweis "Reports ✓" fuer ${JSON.stringify(f.report_config)}: erwartet ${erwartet} ` +
					'(TripKachel.svelte:39 liest truthy morning_enabled/evening_enabled)'
			);
		});
	}
});

describe('AC-23 Naht 2e — heroKanaele (Startseite, Kanal-Dots des Hero-Trips)', () => {
	// Fix-Loop 1 (Adversary F003): +page.svelte leitet die Dots aus diesem Helfer ab.
	for (const f of FAELLE) {
		test(`heroKanaele — ${f.name}`, () => {
			const dots = heroKanaele(rcOf(f) as never);
			const aktiv = f.slot_morning || f.slot_evening;
			// Kein Tabellenfall setzt send_email=false => E-Mail geht raus, sobald ein Slot aktiv ist.
			assert.deepEqual(
				dots,
				aktiv ? ['Email'] : [],
				`Kanal-Dots fuer ${JSON.stringify(f.report_config)}: erwartet ${aktiv ? "['Email']" : '[]'}`
			);
		});
	}

	test('heroKanaele — alle vier Kanaele gleichrangig, Beschriftung je Kanal', () => {
		const rc = { enabled: true, send_email: true, send_telegram: true, send_sms: true, send_premium_sms: true };
		assert.deepEqual(heroKanaele(rc as never), ['Email', 'Telegram', 'SMS', 'Premium-SMS']);
	});

	test('heroKanaele — send_email=false und nur Premium-SMS', () => {
		const rc = { enabled: true, send_email: false, send_premium_sms: true };
		assert.deepEqual(heroKanaele(rc as never), ['Premium-SMS']);
	});
});

describe('Kanal-Defaults der Startseite gleich Editor/Versand (reportChannels, plannedBriefings)', () => {
	test('ohne report_config: Briefing-Zeilen tragen E-Mail', () => {
		const rows = plannedBriefings(undefined);
		assert.equal(rows.length, 2);
		for (const r of rows) assert.deepEqual(r.channels, ['email'], `Zeile ${r.kind} ohne E-Mail-Kanal`);
	});

	test('send_email fehlt => an; Telegram/SMS/Premium fehlen => aus', () => {
		assert.deepEqual(reportChannels({ enabled: true } as never), ['email']);
	});

	test('send_email=false => kein E-Mail-Kanal; Premium-SMS wird genannt', () => {
		assert.deepEqual(
			reportChannels({ send_email: false, send_telegram: true, send_premium_sms: true } as never),
			['telegram', 'premium-sms']
		);
	});
});

// ─────────────────────────────────────────────────────────────────────────────
describe('AC-24 — Editor-Startzustand folgt derselben Regel', () => {
	test('editor_startzustand_folgt_der_regel', async () => {
		const reportSlotAktiv = await ladeHelfer();
		// (1) enabled=true, OHNE Per-Slot-Schluessel, OHNE Zeitfelder => beide an
		//     (bisher "aus": VersandTab.svelte:163-170 verlangte typeof morning_time === 'string').
		const altdaten = { enabled: true };
		assert.equal(reportSlotAktiv(altdaten, 'morning'), true, 'enabled=true ohne Schluessel: Morgen an');
		assert.equal(reportSlotAktiv(altdaten, 'evening'), true, 'enabled=true ohne Schluessel: Abend an');
		// (2) enabled=false => beide aus, auch mit gesetzten Zeitfeldern.
		const aus = { enabled: false, morning_time: '07:00:00', evening_time: '18:00:00' };
		assert.equal(reportSlotAktiv(aus, 'morning'), false, 'enabled=false: Morgen aus');
		assert.equal(reportSlotAktiv(aus, 'evening'), false, 'enabled=false: Abend aus');
		// (3) Mit Per-Slot-Schluesseln zaehlen diese.
		const perSlot = { enabled: true, morning_enabled: true, evening_enabled: false };
		assert.equal(reportSlotAktiv(perSlot, 'morning'), true, 'Per-Slot: Morgen an');
		assert.equal(reportSlotAktiv(perSlot, 'evening'), false, 'Per-Slot: Abend aus');
	});
});

/** true nur, wenn das boolsche `checked`-Attribut im Tag steht (Svelte-SSR: `checked=""`). */
function istAngehakt(html: string, testid: string): boolean {
	const marker = `data-testid="${testid}"`;
	const i = html.indexOf(marker);
	assert.notEqual(i, -1, `Testid "${testid}" nicht im gerenderten HTML gefunden.`);
	const start = html.indexOf('<input', i);
	assert.notEqual(start, -1, `Kein <input> nach Testid "${testid}".`);
	const tag = html.slice(start, html.indexOf('>', start) + 1);
	return /\bchecked(=""|(?=[\s/>]))/.test(tag);
}

describe('AC-24 Naht 3 — Versand-Reiter setzt die Haekchen beim ERZEUGEN nach der Regel (SSR)', () => {
	for (const f of FAELLE) {
		test(`VersandTab(route) — ${f.name}`, async () => {
			const { render } = await import('svelte/server');
			const VersandTab = (
				await import(pathToFileURL(path.join(FRONTEND, 'src/lib/components/shared/VersandTab.svelte')).href)
			).default;
			const html = render(VersandTab, { props: { context: 'route', reportConfig: rcOf(f) } }).body;
			assert.equal(
				istAngehakt(html, 'morning-master-switch'),
				f.slot_morning,
				`VersandTab "Morgen aktiv" fuer ${JSON.stringify(f.report_config)}: erwartet ${f.slot_morning}`
			);
			assert.equal(
				istAngehakt(html, 'evening-master-switch'),
				f.slot_evening,
				`VersandTab "Abend aktiv" fuer ${JSON.stringify(f.report_config)}: erwartet ${f.slot_evening}`
			);
		});
	}
});
