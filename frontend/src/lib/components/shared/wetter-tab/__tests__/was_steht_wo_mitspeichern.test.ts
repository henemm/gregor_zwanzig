// Issue #3122 B3b (Spec Teil B Nr. 13, AC-32): „−“/„+“ im Reiter Wetter schreibt die Tabelle „Was steht wo“ im
// SELBEN Speichervorgang mit. Gemessen am gesendeten Rumpf der echten Speicher-Bausteine (tripNutzlast:
// PUT /weather-config, vergleichNutzlast: PUT des Presets). Ohne gespeicherte Tabelle liefert die Karte keinen Stand
// (`undefined`) — dann fehlt der Schlüssel, und das Abo wechselt nicht unbemerkt auf den neuen Eingang.
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/was_steht_wo_mitspeichern.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { live } from './wetterTabDaten.ts';
import { vorlagenAusTemplates } from '../ampelModell.ts';
import { standAusAbo, type AboSicht } from '../wetterZustand.ts';
import { tripNutzlast, vergleichNutzlast } from '../wetterTabSpeicherung.ts';

const v = () => vorlagenAusTemplates(live().templates);
const TRIP: AboSicht = { id: 't', report_config: {}, display_config: { metrics: [{ metric_id: 'wind', enabled: true }] } };
const ORTE: AboSicht = { id: 'cp', display_config: { active_metrics: [{ metric_id: 'wind', aggregation: 'max' }] } };
const STAND = { version: 1, rows: [{ metric_id: 'gust', places: { sms: false } }], outlook_reports: ['evening'] };

const opt = (kind: 'route' | 'vergleich', abo: AboSicht, placements?: () => unknown) => {
	const vv = v();
	const stand = standAusAbo(kind, abo, vv);
	return { client: null as never, stand: () => stand, vorlagen: () => vv, abo: () => abo, placements };
};

describe('placements im Rumpf des Reiters', () => {
	test('Trip: im display_config-Teil (PUT /weather-config), vollständig', () => {
		const n = tripNutzlast(opt('route', TRIP, () => STAND));
		assert.deepEqual((n.weatherConfig as Record<string, unknown>).placements, STAND);
		assert.equal('placements' in n.tripFelder, false);
	});
	test('Orte: in display_config des Presets, vollständig', () => {
		const n = vergleichNutzlast(opt('vergleich', ORTE, () => STAND));
		assert.deepEqual((n.display_config as Record<string, unknown>).placements, STAND);
	});
	test('ohne gespeicherte Tabelle (Karte liefert nichts) fehlt der Schlüssel', () => {
		assert.equal('placements' in tripNutzlast(opt('route', TRIP, () => undefined)).weatherConfig, false);
		assert.equal('placements' in (vergleichNutzlast(opt('vergleich', ORTE)).display_config as object), false);
	});
});
