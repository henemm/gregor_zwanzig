// #2988 S4 (AC-18): der Frontend-Spiegel der Auflösung ist entfernt.
// Spec: docs/specs/modules/rework_2988_ampel_ableitung.md (AC-18, „S4 – Übersichten").
// Geprüft am geladenen Modul (was es exportiert), nicht am Dateitext. Der Ort liegt bewusst unter
// hub-uebersicht/__tests__ (Absprache mit #3020: keine neuen Dateien unter wetter-tab/__tests__).
//
//   cd frontend && npm test -- src/lib/components/shared/hub-uebersicht/__tests__/spiegel_entfernt_2988.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '..', '..', '..', '..', '..', '..');
const WT = join(HIER, '..', '..', 'wetter-tab');
const basis = pathToFileURL(FRONTEND + '/').href;
register(pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href, basis);
register(pathToFileURL(join(FRONTEND, 'test-app-environment-stub-hooks.mjs')).href, basis);

type Json = any; // eslint-disable-line @typescript-eslint/no-explicit-any
const am: Json = await import(pathToFileURL(join(WT, 'ampelModell.ts')).href);
const hub: Json = await import(pathToFileURL(join(HIER, '..', 'hubUebersichtModell.ts')).href);

/** Spiegel von `app.ampel` (`_verschmelzen`, `validate_ampel`, Vorlagen-Wahl, Abweichungszähler). */
const ENTFERNT = [
	'verschmelzen',
	'vorlageIdVon',
	'zaehleAbweichungen',
	'zaehleAbweichungenGegen',
	'eigeneVorlageAmpel',
	'ampelFehler',
	'metrikFehler',
	'windrichtungUngueltig',
	'zeileWeichtAb',
	'richtungWeichtAb',
	'WIND_MODI',
	'WIND_SEKTOREN'
];

/** Bleibt: vom Reiter, vom Schreiben und von den Übersichten genutzt (keine Auflösung). */
const BLEIBT = ['zuruecksetzen', 'alarmZaehler', 'auswahlLesen', 'ausgebbarTeilen', 'grenzenFehler', 'gewitterFehler', 'gleicheSeite', 'aktiveMetriken', 'vorlagenAusTemplates', 'eigenschaftenAusKatalog'];

describe('AC-18 (#2988 S4): kein Spiegel der Auflösung im Frontend', () => {
	for (const name of ENTFERNT) {
		test(`ampelModell_exportiert_${name}_nicht`, () => {
			assert.equal(name in am, false, `ampelModell.ts exportiert noch ${name}`);
		});
	}
	test('uebersicht_exportiert_keine_lokale_aufloesung', () => {
		for (const name of ['lokalAufgeloest', 'verschmelzen', 'vorlageIdVon']) assert.equal(name in hub, false, `hubUebersichtModell.ts exportiert ${name}`);
	});
	test('messaufbau_genutzte_funktionen_bleiben', () => {
		for (const name of BLEIBT) assert.equal(typeof am[name], 'function', `ampelModell.ts: ${name} fehlt`);
	});
	test('zuruecksetzen_kopiert_die_vorlage_ohne_verschmelzen', () => {
		// Die Vorlage ist fertig aufgelöst (aus /api/templates); Zurücksetzen ist eine tiefe Kopie.
		const v = { wandern: { template: 'wandern', metrics: { gust: { enabled: true, lower: {}, upper: { yellow: 40 }, alarm_ab: 'orange' } }, thunder: { mittel: 'orange', hoch: 'red' } } };
		const r = am.zuruecksetzen('wandern', v);
		assert.deepEqual(r.ampel, v.wandern);
		assert.notEqual(r.ampel.metrics.gust, v.wandern.metrics.gust);
		assert.deepEqual(r.auswahl, ['gust']);
	});
});
