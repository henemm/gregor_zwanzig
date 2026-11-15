// TDD RED — Issue #3031 (Inhalt je Kanal A1), Implementation Details 8 / AC-11 / AC-7:
// Die Kanallisten haben genau EINEN Bediener und genau EINEN Speicherer — die Karte im Reiter
// Wetter (wetterTabSpeicherung.ts). Der alte Zustellungs-Baustein (WeatherMetricsTab im
// Uebergangsblock, bereich="zustellung") zeigt `layout_kanal` nicht mehr und darf die Felder
// deshalb auch nicht mehr SCHREIBEN: er haelt nur eine beim Laden eingefrorene Kopie, und jede
// Zustellungs-Geste (Stundenverlauf, Ausblick, Telegram-Kurzform …) wuerde damit den Stand der
// Karte still ueberschreiben (Stale-Payload zweier Bediener desselben Feldes,
// reference_etag_schuetzt_nicht_gegen_stale_payload_im_selben_tab).
//
//   Vergleich: `baueWetterMetrikenNutzlast` traegt weder `channel_active_metrics` noch `channel_layouts`.
//   Trip:      das Teilfeld des alten Reiters (`WETTER_DISPLAY_KEYS`, pickEigenfelder) laesst
//              `channel_layouts` weg.
//
// Gemessen am gesendeten Rumpf (echter Speicherer, echte Hub-Schlange, echter Controller, echtes
// `api` gegen den Go-Merge-Pruefserver) — Muster f006_zustellung_schreibt_keine_wetterfelder.test.ts.
//
//   cd frontend && npm test -- src/lib/components/shared/weather-metrics-tab/__tests__/kanal_inhalt_3031_zustellung_ohne_kanallisten.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../../api.ts';
import { clearEtagRegistry } from '../../../../etagRegistry.ts';
import { createGoMergeServer, type GoMergeServer } from '../../__tests__/goMergeServerPruefstand.ts';
import type { ComparePreset } from '../../../../types.ts';
import { createPutQueue } from '../../../compare/compareHubPersistenz.ts';
import { baueWetterMetrikenNutzlast, erstelleWetterMetrikenVergleichSpeicherung, wetterMetrikenSnapshotAus } from '../weatherMetricsCompareSave.ts';
import { pickEigenfelder, WETTER_DISPLAY_KEYS } from '../../pickEigenfelder.ts';
import { createController, hydrierterWs, makePreset, wetterMetrikenBedienung } from './wetterMetrikenVergleichPruefstand.ts';

const ID = 'cp-3031-zustellung';
const KANAL_FELDER = ['channel_active_metrics', 'channel_layouts'];
const ALT_AKTIV = { email: ['wind_max_kmh'], telegram: ['temp_max_c'], sms: ['wind_max_kmh'] };

function preset(): ComparePreset {
	const p = makePreset(ID);
	(p.display_config as Record<string, unknown>).channel_active_metrics = structuredClone(ALT_AKTIV);
	return p;
}

function ohneKanalFelder(body: unknown, wo: string): void {
	const dc = ((body as Record<string, unknown>)?.display_config as Record<string, unknown>) ?? {};
	for (const k of KANAL_FELDER) assert.ok(!(k in dc), `${wo}: der Zustellungs-Baustein schreibt display_config.${k} (zweiter Bediener der Kanallisten)`);
}

describe('#3031: Nutzlast des Zustellungs-Speicherers (Vergleich) ohne Kanallisten', () => {
	const gesten: Array<[string, (ws: Record<string, unknown>) => void]> = [
		['Stundenverlauf-Reihenfolge', (ws) => wetterMetrikenBedienung(ws).hourlyDragEnd(['temp_max_c', 'wind_max_kmh'])],
		['Ausblick-Auswahl', (ws) => wetterMetrikenBedienung(ws).outlookSelect(['wind_max_kmh'])],
		['Ausblick Roh/Einfach', (ws) => wetterMetrikenBedienung(ws).outlookFormatToggle('temp_max_c', false)]
	];
	for (const [was, geste] of gesten) {
		test(`${was}: baueWetterMetrikenNutzlast traegt keine Kanallisten`, () => {
			const p = preset();
			const ws = hydrierterWs(p);
			geste(ws);
			ohneKanalFelder(baueWetterMetrikenNutzlast(p, wetterMetrikenSnapshotAus(ws)).body, was);
		});
	}
});

describe('#3031: echter Speicherweg — die Karte hat gespeichert, danach eine Zustellungs-Geste', () => {
	let server: GoMergeServer;
	beforeEach(() => {
		clearEtagRegistry();
		server = createGoMergeServer({ [ID]: preset() as unknown as Record<string, unknown> });
		server.install();
	});
	afterEach(() => server.restore());

	test('Kanallisten der Karte bleiben auf dem Server stehen (keine eingefrorene Kopie des alten Bausteins)', async () => {
		let basis = preset();
		const ws = hydrierterWs(basis); // eingefrorene Kopie beim Laden der Seite
		const ctl = createController(ID);
		const queue = createPutQueue();
		const sp = erstelleWetterMetrikenVergleichSpeicherung({
			client: api,
			zustand: ws,
			preset: () => basis,
			enqueueHubWrite: (fn) => queue.enqueue(fn),
			onCompareUpdate: (p: ComparePreset) => {
				basis = p;
			},
			saveController: ctl
		});
		// Die Karte im Reiter Wetter speichert (anderer Speicherer, gleiche Seite).
		const karte = {
			channel_layouts: { email: [{ metric_id: 'temp_max_c', enabled: true, use_friendly_format: false }], telegram: [], sms: [] },
			channel_active_metrics: { email: ['temp_max_c'], telegram: [], sms: [] }
		};
		server.fremdSchreiben(ID, { display_config: karte });
		basis = server.stand(ID) as unknown as ComparePreset; // Seite uebernimmt die Serverantwort
		await api.get(`/api/compare/presets/${ID}`);

		wetterMetrikenBedienung(ws).hourlyDragEnd(['temp_max_c', 'wind_max_kmh']);
		sp.aenderungMelden();
		await ctl.flush();

		const puts = server.putRuempfe();
		assert.equal(puts.length, 1, 'Messaufbau: die Zustellungs-Geste muss genau einen PUT ausloesen');
		ohneKanalFelder(puts[0], 'PUT');
		const dc = server.stand(ID).display_config as Record<string, unknown>;
		assert.deepEqual(dc.channel_active_metrics, karte.channel_active_metrics, 'Kanal-Auswahl der Karte durch die alte Kopie ueberschrieben');
		assert.deepEqual(dc.channel_layouts, karte.channel_layouts, 'Kanallisten der Karte veraendert');
		assert.deepEqual(dc.hourly_metrics, ['temp_max_c', 'wind_max_kmh'], 'die Zustellungs-Geste selbst wurde nicht gespeichert');
	});
});

describe('#3031: Teilfeld des alten Reiters im Trip ohne channel_layouts', () => {
	test('pickEigenfelder(…, WETTER_DISPLAY_KEYS) laesst channel_layouts weg, behaelt Zustellungs-Felder', () => {
		const body = pickEigenfelder(
			{
				display_config: {
					channel_layouts: { email: [{ metric_id: 'wind', enabled: true }] },
					telegram_kurzform: true,
					outlook_metrics: ['temperature']
				}
			},
			{ display: WETTER_DISPLAY_KEYS }
		);
		ohneKanalFelder(body, 'Trip-Teilfeld');
		const dc = body.display_config as Record<string, unknown>;
		assert.equal(dc.telegram_kurzform, true, 'Zustellungs-Feld telegram_kurzform verloren');
		assert.deepEqual(dc.outlook_metrics, ['temperature'], 'Zustellungs-Feld outlook_metrics verloren');
	});
});
