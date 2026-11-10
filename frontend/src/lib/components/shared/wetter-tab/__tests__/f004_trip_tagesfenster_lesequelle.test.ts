// Fix-Loop 1 Issue #2794 S3a Teil-PR 3, Adversary-Finding F004 (AC-21):
// Das Trip-Tagesfenster steht in `report_config.day_window_*_hour`, das des
// Orts-Briefings top-level. Gemessen wird dort, wo die Zusicherung WIRKT:
// Ein gespeichertes Fenster muss beim Oeffnen des Reiters angezeigt werden
// (Erst-Hydration `standAusAbo`) und beim naechsten Speichern unveraendert
// zurueckgeschrieben werden (Rundlauf ueber den echten Speicher-Baustein
// `tripNutzlast`). Liest der Trip die falsche Quelle, zeigt er den Standard
// 4–19 und ueberschreibt damit das eingestellte Fenster des Nutzers.
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/f004_trip_tagesfenster_lesequelle.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { live } from './wetterTabDaten.ts';
import { vorlagenAusTemplates } from '../ampelModell.ts';
import { standAusAbo, tagesfensterLesen, type AboSicht } from '../wetterZustand.ts';
import { tripNutzlast, vergleichNutzlast } from '../wetterTabSpeicherung.ts';

const vorlagen = () => vorlagenAusTemplates(live().templates);

/** Trip mit gespeichertem Fenster 7–18 in report_config; top-level steht ein
 *  abweichender Altwert, der NICHT gelesen werden darf. */
const TRIP: AboSicht = {
	id: 'trip-f004',
	day_window_start_hour: 3,
	day_window_end_hour: 22,
	report_config: { send_email: true, day_window_start_hour: 7, day_window_end_hour: 18 },
	display_config: { metrics: [{ metric_id: 'wind', enabled: true }] }
};

/** Orts-Briefing: Fenster top-level, ein report_config-Wert darf NICHT gelesen werden. */
const VERGLEICH: AboSicht = {
	id: 'cp-f004',
	day_window_start_hour: 6,
	day_window_end_hour: 17,
	report_config: { day_window_start_hour: 1, day_window_end_hour: 23 },
	display_config: { active_metrics: [{ metric_id: 'wind', aggregation: 'max' }] }
};

describe('F004/AC-21: Tagesfenster-Lesequelle je Kontext', () => {
	test('Trip liest report_config.day_window_*_hour (nicht top-level, nicht den Standard)', () => {
		assert.deepEqual(tagesfensterLesen('route', TRIP), { start: 7, end: 18 });
	});

	test('Orts-Briefing liest top-level (nicht report_config)', () => {
		assert.deepEqual(tagesfensterLesen('vergleich', VERGLEICH), { start: 6, end: 17 });
	});

	test('Trip: Oeffnen zeigt das gespeicherte Fenster, Speichern schreibt es unveraendert zurueck', () => {
		const v = vorlagen();
		const stand = standAusAbo('route', TRIP, v);
		assert.deepEqual(stand.tagesfenster, { start: 7, end: 18 }, 'Reiter zeigt nicht das gespeicherte Trip-Fenster');
		const n = tripNutzlast({ client: null as never, stand: () => stand, vorlagen: () => v, abo: () => TRIP });
		assert.equal(n.tripFelder.report_config.day_window_start_hour, 7, 'Speichern ueberschreibt das Trip-Fenster (Start)');
		assert.equal(n.tripFelder.report_config.day_window_end_hour, 18, 'Speichern ueberschreibt das Trip-Fenster (Ende)');
		assert.equal((n.tripFelder.report_config as Record<string, unknown>).send_email, true, 'uebrige report_config-Felder bleiben');
	});

	test('Orts-Briefing: Oeffnen und Speichern behalten das top-level-Fenster', () => {
		const v = vorlagen();
		const stand = standAusAbo('vergleich', VERGLEICH, v);
		assert.deepEqual(stand.tagesfenster, { start: 6, end: 17 });
		const n = vergleichNutzlast({ client: null as never, stand: () => stand, vorlagen: () => v, abo: () => VERGLEICH });
		assert.equal(n.day_window_start_hour, 6);
		assert.equal(n.day_window_end_hour, 17);
	});
});
