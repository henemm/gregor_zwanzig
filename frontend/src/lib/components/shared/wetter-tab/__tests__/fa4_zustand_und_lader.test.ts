// Fix-Loop 2 Issue #2794 S3a Teil-PR 3, Adversary-Finding F-A4 (AC-10 bis AC-13, AC-21, AC-42):
// Zustandsfunktionen und Lader des Reiters an der Wirkstelle.
//   D6: Vorlagenwechsel/Zuruecksetzen ersetzt die Metrik-Auswahl (`mitVorlage`).
//   D1/D2: eigene Vorlagen nur der passenden Art; Bestand ohne `kind` gilt als `route`
//          (`ladeWetterDaten` mit echtem Katalog/Vorlagen aus dem Python-Core).
//   D4: ohne gespeichertes Tagesfenster gilt 4–19 (beide Kontexte).
// (D8, Konfliktschluessel, steht im Hub-Test f003_vergleich_speicherer_hub_schlange.test.ts.)
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/fa4_zustand_und_lader.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { live } from './wetterTabDaten.ts';
import { aktiveMetriken, vorlagenAusTemplates } from '../ampelModell.ts';
import { mitMetrik, mitVorlage, ohneMetrik, standAusAbo, tagesfensterLesen } from '../wetterZustand.ts';
import { ladeWetterDaten } from '../wetterTabLaden.ts';

const sortiert = (a: string[]) => [...a].sort();
const vorlagen = () => vorlagenAusTemplates(live().templates);

describe('F-A4 (D6): Vorlagenwechsel und Zuruecksetzen ersetzen die Auswahl', () => {
	test('Wechsel allgemein → wassersport: Auswahl = aktive Metriken von Wassersport', () => {
		const v = vorlagen();
		const s = standAusAbo('vergleich', { display_config: { ampel: { template: 'allgemein' } } }, v);
		assert.notDeepEqual(sortiert(aktiveMetriken(v.allgemein)), sortiert(aktiveMetriken(v.wassersport)), 'Messaufbau');
		const n = mitVorlage(s, 'wassersport', v);
		assert.equal(n.vorlageId, 'wassersport');
		assert.deepEqual(sortiert(n.auswahl), sortiert(aktiveMetriken(v.wassersport)), 'Vorlagenwechsel ersetzt die Auswahl nicht');
	});

	test('Zuruecksetzen nach „−"/„+": Auswahl wieder wie die Vorlage', () => {
		const v = vorlagen();
		const s0 = standAusAbo('vergleich', { display_config: { ampel: { template: 'wandern' } } }, v);
		const weg = s0.auswahl[0];
		const geaendert = mitMetrik(ohneMetrik(s0, weg), 'dewpoint');
		assert.notDeepEqual(sortiert(geaendert.auswahl), sortiert(s0.auswahl), 'Messaufbau');
		assert.deepEqual(sortiert(mitVorlage(geaendert, 'wandern', v).auswahl), sortiert(aktiveMetriken(v.wandern)));
	});
});

describe('F-A4 (D4): Standard-Tagesfenster 4–19', () => {
	for (const k of ['route', 'vergleich'] as const) {
		test(`${k}: leeres Abo ⇒ 4–19`, () => {
			assert.deepEqual(tagesfensterLesen(k, {}), { start: 4, end: 19 });
			assert.deepEqual(tagesfensterLesen(k, null), { start: 4, end: 19 });
		});
	}
});

describe('F-A4 (D1/D2): eigene Vorlagen nur der passenden Art (ladeWetterDaten)', () => {
	const presets = [
		{ id: 'p-route', name: 'Meine Route', kind: 'route', metrics: [{ metric_id: 'wind', enabled: true }] },
		{ id: 'p-orte', name: 'Meine Orte', kind: 'vergleich', metrics: [{ metric_id: 'gust', enabled: true }] },
		{ id: 'p-alt', name: 'Alt ohne Art', metrics: [{ metric_id: 'temperature', enabled: true }] }
	];
	const client = {
		get: async <T>(pfad: string): Promise<T> => {
			const d = live();
			if (pfad === '/api/metrics') return d.metrics as T;
			if (pfad === '/api/templates') return d.templates as T;
			if (pfad === '/api/metric-presets') return presets as T;
			throw new Error(`unerwartet: ${pfad}`);
		}
	};

	test('Trip: eigene Vorlagen der Art route plus Bestand ohne Art', async () => {
		const d = await ladeWetterDaten(client, 'route');
		assert.deepEqual(d.eigene.map((e) => e.id).sort(), ['p-alt', 'p-route']);
	});

	test('Orts-Briefing: nur eigene Vorlagen der Art vergleich', async () => {
		const d = await ladeWetterDaten(client, 'vergleich');
		assert.deepEqual(d.eigene.map((e) => e.id), ['p-orte']);
	});

	test('AC-10: sieben Systemvorlagen, Kurzbeschreibung mit Metrikzahl aus den Vorlagen-Daten', async () => {
		const d = await ladeWetterDaten(client, 'route');
		assert.equal(d.liste.length, 7);
		for (const e of d.liste) assert.equal(e.anzahl, aktiveMetriken(d.vorlagen[e.id]).length, `${e.id}: Metrikzahl`);
	});
});
