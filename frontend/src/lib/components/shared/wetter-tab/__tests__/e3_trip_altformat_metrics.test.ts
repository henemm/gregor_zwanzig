// Issue #3047 Runde 7, Befund E3 (hoch): Trip-Altformat in `display_config.metrics[]`.
// Spec: docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md (§2 Punkt 8, Altbestand).
//
// Python (`src/app/loader.py::_coerce_metric_entry`, #1262) wertet eine Zeichenkette `"wind"` und ein
// Objekt ohne `enabled` als GEWAEHLT — die Mail zeigt beide. Der Reiter Wetter zaehlte nur
// `enabled === true` und zeigte sie als „Nicht im Briefing"; eine beliebige Speicherung spreizte die
// Zeichenkette zu `{"0":"w","1":"i",...}`, woran der Python-Loader den ganzen Trip verwarf.
//
// Gemessen dort, wo es wirkt: Lesen (`standAusAbo`) und die echte Speicher-Nutzlast (`tripNutzlast`).
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/e3_trip_altformat_metrics.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { aufgeloestVon, live } from './wetterTabDaten.ts';
import { vorlagenAusTemplates } from '../ampelModell.ts';
import { standAusAbo, type AboSicht } from '../wetterZustand.ts';
import { tripNutzlast } from '../wetterTabSpeicherung.ts';

const vorlagen = () => vorlagenAusTemplates(live().templates);

function trip(metrics: unknown[]): AboSicht {
	return {
		id: 'trip-e3',
		profil: 'wandern',
		report_config: { day_window_start_hour: 6, day_window_end_hour: 18 },
		display_config: { metrics, ampel: { template: 'wandern' } }
	};
}

const ALTFORMAT = () => ['wind', { metric_id: 'gust', bucket: 'primary', order: 1 }, { metric_id: 'temperature', enabled: false }];

function nutzlastFuer(abo: AboSicht) {
	const v = vorlagen();
	const s = standAusAbo('route', abo, aufgeloestVon(abo));
	return { s, n: tripNutzlast({ client: null as never, stand: () => s, vorlagen: () => v, abo: () => abo }) };
}

describe('E3: Trip-Altformat metrics[] wird wie in Python gelesen', () => {
	test('Zeichenkette und Objekt ohne enabled gelten als gewaehlt, enabled:false nicht', () => {
		const abo = trip(ALTFORMAT());
		const s = standAusAbo('route', abo, aufgeloestVon(abo));
		assert.deepEqual(s.auswahl, ['wind', 'gust']);
	});

	test('Eintrag ohne metric_id (gespreizte Zeichenkette) zaehlt nicht als Auswahl', () => {
		const kaputt = { 0: 'w', 1: 'i', 2: 'n', 3: 'd', enabled: true };
		const abo = trip([kaputt, { metric_id: 'gust', enabled: true }]);
		const s = standAusAbo('route', abo, aufgeloestVon(abo));
		assert.deepEqual(s.auswahl, ['gust']);
	});
});

describe('E3: unbeteiligte Speicherung schreibt nur Objekte mit metric_id, Bestand bleibt', () => {
	test('Nutzlast = Wind/Boeen an, Temperatur aus, uebrige Felder erhalten, Reihenfolge bleibt', () => {
		const { n } = nutzlastFuer(trip(ALTFORMAT()));
		assert.deepEqual(n.weatherConfig.metrics, [
			{ metric_id: 'wind', enabled: true },
			{ metric_id: 'gust', bucket: 'primary', order: 1, enabled: true },
			{ metric_id: 'temperature', enabled: false }
		]);
	});

	test('jeder Eintrag der Nutzlast ist ein Objekt mit metric_id (nie gespreizte Zeichenkette)', () => {
		const kaputt = { 0: 'w', 1: 'i', 2: 'n', 3: 'd', enabled: false };
		const { n } = nutzlastFuer(trip([...ALTFORMAT(), kaputt]));
		for (const e of n.weatherConfig.metrics as unknown[]) {
			assert.equal(typeof e, 'object');
			assert.equal(typeof (e as { metric_id?: unknown }).metric_id, 'string', `Eintrag ohne metric_id: ${JSON.stringify(e)}`);
		}
		assert.deepEqual(
			(n.weatherConfig.metrics as { metric_id: string }[]).map((e) => e.metric_id),
			['wind', 'gust', 'temperature']
		);
	});

	test('der Lese-Bestand am Abo wird nicht veraendert', () => {
		const abo = trip(ALTFORMAT());
		nutzlastFuer(abo);
		assert.deepEqual((abo.display_config as { metrics: unknown[] }).metrics, ALTFORMAT());
	});
});
