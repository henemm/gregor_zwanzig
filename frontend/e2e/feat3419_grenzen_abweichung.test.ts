// Paket #3419 Fix-Loop (Staging-Messlauf 26.11.): Der Grenzen-Prüfdatensatz trug die Mockup-Werte (#3421); wo sie
// mit der Vorlage übereinstimmen, zeigt live der Grenzen-Editor den Satz „Abweichend von der Vorlage …“ nicht
// (WetterTabInhalt.grenzenAbweichend → ampelSchreiben.abweichungsMenge), das Soll-Bild (Zustand „mit Abweichung“)
// aber schon. Spec: docs/specs/modules/feat_3419_elementliste_nachzug.md (AC-2, AC-7).
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --experimental-test-module-mocks --test e2e/feat3419_grenzen_abweichung.test.ts
//
// Kern-Schicht, ohne Netz. Vorlagenwerte wie src/app/ampel_templates.py („alpen-trekking“, „allgemein“) in der Form
// der Antwort von GET /api/templates ({id, ampel: {metrics: {id: {lower: {red, orange, yellow}, upper: …}}}}).

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as L from './elementliste_abgleich_logik.ts';
import type { ListenElement } from './elementliste_abgleich_logik.ts';

const HERE = dirname(fileURLToPath(import.meta.url));
const EINST = join(HERE, '..', '..', 'docs', 'context', 'einstellungen_neu');
const LISTE = (JSON.parse(readFileSync(join(EINST, 'elementliste.json'), 'utf8')) as { elemente: ListenElement[] }).elemente;
const MOCKUP = readFileSync(join(EINST, 'seiten', 'mockup-hub-fassung4.html'), 'utf8');

const seite = (r: number | null, o: number | null, y: number | null) => ({ red: r, orange: o, yellow: y });
const oben = (y: number | null, o: number | null, r: number | null) => ({ yellow: y, orange: o, red: r });
const LEER = seite(null, null, null);
/** Auszug der Vorlagen wie GET /api/templates (Werte aus src/app/ampel_templates.py). */
const VORLAGEN = [
	{
		id: 'alpen-trekking',
		ampel: {
			metrics: {
				temperature: { enabled: true, lower: seite(-10, -3, 2), upper: oben(27, 30, 33) },
				gust: { enabled: true, lower: LEER, upper: oben(35, 50, 70) },
				uv_index: { enabled: true, lower: LEER, upper: oben(6, 8, 10) },
				visibility: { enabled: true, lower: seite(100, 300, 1000), upper: LEER }
			}
		}
	},
	{ id: 'allgemein', ampel: { metrics: { temperature: { enabled: true, lower: seite(-15, -5, 0), upper: oben(28, 31, 34) } } } }
];
const EIG: Record<string, { allowed_sides: string | null }> = {
	temperature: { allowed_sides: 'both' }, temperature_night: { allowed_sides: 'both' }, wind_chill: { allowed_sides: 'both' },
	wind: { allowed_sides: 'both' }, gust: { allowed_sides: 'upper' }, precipitation: { allowed_sides: 'upper' },
	thunder: { allowed_sides: 'level' }, rain_probability: { allowed_sides: 'upper' }, visibility: { allowed_sides: 'lower' },
	cloud_total: { allowed_sides: 'upper' }, cloud_low: { allowed_sides: 'upper' }, uv_index: { allowed_sides: 'upper' },
	sunshine: { allowed_sides: 'lower' }, freezing_level: { allowed_sides: 'both' }, snowfall_limit: { allowed_sides: 'both' }
};
type Ampel = { metrics: Record<string, L.AmpelMetrik> };
const payload = (ctx: 'trip' | 'orte', vorlagen: Record<string, unknown>[]) =>
	(
		L.wetterPruefPayload(ctx, 'mit_abweichung', {
			liste: LISTE, vorlagen, eig: EIG, ortIds: ['o1', 'o2', 'o3'], datum: '2026-02-23', grenzen: L.grenzenAusMockup(MOCKUP, ctx)
		}) as { display_config: { ampel: Ampel } }
	).display_config.ampel;

describe('#3419 Fix-Loop: Grenzen-Prüfdatensatz weicht in jeder Metrik von der Vorlage ab (Satz „Abweichend …“)', () => {
	test('Trip: Mockup = Vorlage (Temperatur, Böen, UV, Sicht) ⇒ Rot rückt um 1 nach außen, Vorzeichen bleibt', () => {
		// GIVEN Mockup-Grenzen gleich der Vorlage „Alpen-Trekking“  WHEN der Datensatz „mit Abweichung“ gebaut wird
		// THEN  weicht jede dieser Metriken in genau einer Zahl ab (lower Rot −1 bzw. upper Rot +1)
		const a = payload('trip', VORLAGEN);
		assert.deepEqual(a.metrics.temperature.lower, { red: -11, orange: -3, yellow: 2 });
		assert.deepEqual(a.metrics.temperature.upper, { yellow: 27, orange: 30, red: 33 });
		assert.deepEqual(a.metrics.gust.upper, { yellow: 35, orange: 50, red: 71 });
		assert.deepEqual(a.metrics.uv_index.upper, { yellow: 6, orange: 8, red: 11 });
		assert.deepEqual(a.metrics.visibility.lower, { red: 99, orange: 300, yellow: 1000 });
	});

	test('Trip: Metrik, die schon abweicht oder nicht in der Vorlage steht, behält die Mockup-Werte', () => {
		const a = payload('trip', VORLAGEN);
		// temperature_night steht nicht im Vorlagen-Auszug; freezing_level ebenfalls (Mockup −300 bleibt)
		assert.equal(a.metrics.freezing_level.lower?.red, -300);
		assert.equal(a.metrics.temperature_night.lower?.red, -8);
	});

	test('Orte: Vorlage „Allgemein“ (Temperatur −15/−5/0, 28/31/34) ⇒ lower Rot −16', () => {
		const a = payload('orte', VORLAGEN);
		assert.deepEqual(a.metrics.temperature.lower, { red: -16, orange: -5, yellow: 0 });
	});

	test('jede Metrik weicht von ihrer Vorlage ab und bleibt gültig (#3192 AC-1)', () => {
		const a = payload('trip', VORLAGEN);
		const v = (VORLAGEN[0].ampel.metrics as Record<string, { lower: Record<string, number | null>; upper: Record<string, number | null> }>);
		for (const [id, z] of Object.entries(v)) {
			const m = a.metrics[id];
			const gleich = (s: Record<string, number> | undefined, t: Record<string, number | null>) => !s || (s.red === t.red && s.orange === t.orange && s.yellow === t.yellow);
			assert.ok(!(gleich(m.lower, z.lower) && gleich(m.upper, z.upper)), `${id} gleich der Vorlage`);
			if (m.lower) assert.ok(m.lower.red < m.lower.orange && m.lower.orange < m.lower.yellow, `${id} lower`);
			if (m.upper) assert.ok(m.upper.yellow < m.upper.orange && m.upper.orange < m.upper.red, `${id} upper`);
		}
	});

	test('ohne Vorlagen-Antwort bleibt der Datensatz bei den Mockup-Werten', () => {
		assert.deepEqual(payload('trip', []).metrics.temperature.lower, { red: -10, orange: -3, yellow: 2 });
	});
});
