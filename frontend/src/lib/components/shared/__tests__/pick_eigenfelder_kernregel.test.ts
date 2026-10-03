// TDD RED — Issue #1433: die generische Teilfeld-Auswahl `pickEigenfelder`
// (neu, `shared/pickEigenfelder.ts`) und ihre Kernregeln.
//
// Spec: docs/specs/bugfix/trip_mehrreiter_konfliktschutz.md — §2 „Regeln der
// Tabelle" 1-3, §3, AC-16, AC-17, AC-21.
//
//   Regel 1: alles ausserhalb der Allowlist wird NIE gesendet (auch wenn die
//            lokale Kopie es haelt) — erzwingt „Python-eigene Schluessel nie".
//   Regel 2: Loeschsemantik — `[]`, `{}`, `""`, `false`, `0`, `null` werden
//            gesendet; nur `undefined` wird uebersprungen.
//   AC-21:   `waehleEigenfelder` (Compare, compareEditorSave.ts:319) wird ein
//            Adapter und liefert unveraendert dieselben Teil-Bodies.
//
// Zielschnittstelle (existiert noch NICHT → RED per fehlendem Export, dynamischer
// Import je Test, damit die uebrigen Tests der Datei laufen):
//   pickEigenfelder(quelle, { top?, display?, report? }) → Teil-Nutzlast
//     - `top`: Top-Level-Schluessel; `display`: Schluessel unter display_config;
//       `report`: Schluessel unter report_config
//     - `display_config`/`report_config` erscheinen nur, wenn mindestens ein
//       Schluessel definiert ist (wie buildComparePresetPartialPayload)
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/shared/__tests__/pick_eigenfelder_kernregel.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { waehleEigenfelder } from '../../compare/compareEditorSave.ts';

type Auswahl = { top?: readonly string[]; display?: readonly string[]; report?: readonly string[] };
type Pick = (quelle: Record<string, unknown>, a: Auswahl) => Record<string, unknown>;

async function ladePick(): Promise<Pick> {
	let mod: { pickEigenfelder?: Pick };
	try {
		mod = (await import('../pickEigenfelder.ts')) as { pickEigenfelder?: Pick };
	} catch {
		assert.fail('shared/pickEigenfelder.ts fehlt (neues Modul der Spec, §3)');
	}
	assert.equal(typeof mod.pickEigenfelder, 'function', 'shared/pickEigenfelder.ts muss `pickEigenfelder` exportieren');
	return mod.pickEigenfelder as Pick;
}

describe('Regel 2 / AC-17: Loeschsemantik', () => {
	test('[], {}, "", false, 0, null gehen durch — undefined wird uebersprungen', async () => {
		const pick = await ladePick();
		const out = pick(
			{ a: [], b: {}, c: '', d: false, e: 0, f: null, g: undefined, h: 'x' },
			{ top: ['a', 'b', 'c', 'd', 'e', 'f', 'g'] }
		);
		assert.deepStrictEqual(out, { a: [], b: {}, c: '', d: false, e: 0, f: null });
		assert.ok(!('g' in out), 'undefined darf nicht als Schluessel im Ergebnis stehen');
		assert.ok(!('h' in out), 'ein Schluessel ausserhalb der Allowlist darf nicht mitkommen');
	});

	test('display/report: dieselbe Loeschsemantik, leere Werte gehen durch', async () => {
		const pick = await ladePick();
		const out = pick(
			{
				display_config: { metrics: [], outlook_metrics: [], fmt: {}, nie_gesetzt: undefined },
				report_config: { show_outlook: false, email_format: '', day_window_start_hour: 0 }
			},
			{
				display: ['metrics', 'outlook_metrics', 'fmt', 'nie_gesetzt'],
				report: ['show_outlook', 'email_format', 'day_window_start_hour']
			}
		);
		assert.deepStrictEqual(out, {
			display_config: { metrics: [], outlook_metrics: [], fmt: {} },
			report_config: { show_outlook: false, email_format: '', day_window_start_hour: 0 }
		});
	});
});

describe('Regel 1 / AC-16: nur Allowlist — Python-eigene und unbekannte Schluessel nie', () => {
	test('skip_next, paused_until, updated_at, change_threshold_* und Unbekanntes bleiben draussen', async () => {
		const pick = await ladePick();
		const out = pick(
			{
				name: 'N',
				skip_next: true,
				updated_at: 'x',
				report_config: {
					morning_time: '07:00:00',
					skip_next: true,
					paused_until: '2026-01-01',
					updated_at: 'y',
					change_threshold_temp_c: 5,
					change_threshold_wind_kmh: 20,
					change_threshold_precip_mm: 3,
					unbekannt: 1
				},
				display_config: { metrics: [], show_night_block: true, trip_id: 't', unbekannt: 2 }
			},
			{ top: ['name'], display: ['metrics'], report: ['morning_time'] }
		);
		assert.deepStrictEqual(out, {
			name: 'N',
			display_config: { metrics: [] },
			report_config: { morning_time: '07:00:00' }
		});
	});

	test('display_config/report_config erscheinen nur, wenn mindestens ein Schluessel definiert ist', async () => {
		const pick = await ladePick();
		const out = pick(
			{ name: 'N', display_config: { x: undefined }, report_config: {} },
			{ top: ['name'], display: ['x', 'y'], report: ['z'] }
		);
		assert.deepStrictEqual(out, { name: 'N' });
		assert.ok(!('display_config' in out), 'ein leeres display_config: {} wuerde nach dem Server-Merge nichts loeschen, aber Fremdwerte suggerieren');
		assert.ok(!('report_config' in out));
	});

	test('ohne display/report-Liste: weder display_config noch report_config im Ergebnis', async () => {
		const pick = await ladePick();
		const out = pick(
			{ corridors: [], display_config: { metrics: ['a'] }, report_config: { skip_next: true } },
			{ top: ['corridors'] }
		);
		assert.deepStrictEqual(out, { corridors: [] }, 'Wertebereiche sendet {corridors} OHNE display_config (AC-12)');
	});
});

describe('Regel 3: Pick aendert die Quelle nicht (nur beim Senden)', () => {
	test('die Quelle (lokaler Zustand des Reiters) bleibt unveraendert', async () => {
		const pick = await ladePick();
		const quelle = { a: [1], display_config: { m: { k: 1 } } };
		const vorher = JSON.stringify(quelle);
		const out = pick(quelle, { top: ['a'], display: ['m'] }) as { a: number[] };
		assert.equal(JSON.stringify(quelle), vorher, 'pickEigenfelder darf die Quelle nicht veraendern');
		assert.deepStrictEqual(out.a, [1]);
	});
});

describe('AC-21: waehleEigenfelder bleibt ein Adapter mit unveraendertem Ergebnis', () => {
	const voll = {
		url: '/api/compare/presets/p1',
		body: {
			id: 'p1',
			name: 'Fremd',
			radar_alert_enabled: true,
			alert_cooldown_minutes: 45,
			official_warnings: { enabled: true },
			display_config: {
				metric_alert_levels: { wind: 'standard' },
				telegram_style: 'rich',
				active_metrics: ['wind'],
				region: 'Tirol'
			}
		}
	} as never;

	test('liefert die gleichen Teil-Bodies wie vor dem Umbau (Festwert-Probe)', () => {
		const out = waehleEigenfelder(
			voll,
			['radar_alert_enabled', 'alert_cooldown_minutes', 'official_warnings', 'nicht_da', 'display_config'],
			['metric_alert_levels', 'telegram_style', 'nicht_da'],
			{ extra: 1 }
		);
		assert.strictEqual(out.url, '/api/compare/presets/p1');
		assert.deepStrictEqual(out.body, {
			radar_alert_enabled: true,
			alert_cooldown_minutes: 45,
			official_warnings: { enabled: true },
			// `display_config` als Top-Key ist ein Eigenfeld-Name der Alarme-Tabelle: der Wert
			// der Quelle geht durch (Adapter reicht Top-Keys 1:1, Pick darunter ersetzt ihn)
			display_config: { metric_alert_levels: { wind: 'standard' }, telegram_style: 'rich', extra: 1 }
		});
	});

	test('der Adapter und pickEigenfelder liefern fuer dieselben Listen dieselben Schluessel', async () => {
		const pick = await ladePick();
		const top = ['radar_alert_enabled', 'official_warnings'];
		const display = ['metric_alert_levels'];
		const adapter = waehleEigenfelder(voll, top, display);
		const direkt = pick((voll as { body: Record<string, unknown> }).body, { top, display });
		assert.deepStrictEqual(adapter.body, direkt, 'waehleEigenfelder muss auf pickEigenfelder aufsetzen — gleiche Allowlist, gleiche Nutzlast');
	});
});
