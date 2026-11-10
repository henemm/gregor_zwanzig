// Fix-Loop 3 Issue #2794 S3a Teil-PR 3, Befund C1 (kritisch): Speichern im Reiter Wetter
// scheiterte immer mit „Failed to execute 'structuredClone'…" (DataCloneError).
//
// Ursache: Im Browser sind `stand` (WetterTab `$state`) und die Abo-Props (`trip`/`preset` aus
// dem `$state` der Seite) Svelte-5-Proxys. `structuredClone` kann Proxys nicht klonen. Die
// bisherigen Kern-Tests fuetterten die Modell-Funktionen nur mit Plain-Objekten — die
// Zusicherung „klont den Stand" war also nie dort geprueft, wo sie wirkt.
//
// Gemessen mit ECHTEN Svelte-Proxys: `proxy()` aus `svelte/internal/client` ist genau das, was
// der Compiler aus `$state({...})` macht (tief: auch verschachtelte Objekte sind Proxys).
// Jede Funktion muss mit Proxy-Eingabe dasselbe liefern wie mit der Plain-Eingabe; der
// Vergleichs-Speicherer muss mit Proxy-Stand und Proxy-Abo wirklich einen PUT absetzen.
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/fixloop3_c1_svelte_proxy_klon.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../../api.ts';
import { clearEtagRegistry } from '../../../../etagRegistry.ts';
import { createPutQueue } from '../../../compare/compareHubPersistenz.ts';
import { createController } from '../../__tests__/versandVergleichPruefstand.ts';
import { createGoMergeServer, vollerVergleich, type GoMergeServer } from '../../__tests__/goMergeServerPruefstand.ts';
import { live } from './wetterTabDaten.ts';
import { alarmAbFuerAlle, eigenschaftenAusKatalog, vorlagenAusTemplates } from '../ampelModell.ts';
import { eigeneVorlagePayload, tripSpeicherPayload, vergleichSpeicherPayload } from '../ampelSchreiben.ts';
import { amtlicheWarnungenFelder } from '../amtlicheWarnungen.ts';
import { mitAlarmAb, mitEigenerVorlage, mitEntwurf, standAusAbo, type AboSicht, type WetterStand } from '../wetterZustand.ts';
import { SPEICHERER, tripNutzlast } from '../wetterTabSpeicherung.ts';
import { ampelBeimAnwenden } from '../../weather-metrics-tab/weatherMetricsSavePayload.ts';

// `svelte/internal/client` bringt keine Typdeklaration mit — Laufzeit-Import ueber eine Variable.
const SVELTE_CLIENT = 'svelte/internal/client';
const { proxy } = (await import(SVELTE_CLIENT)) as { proxy: <T>(v: T) => T };

const daten = live();
const vorlagen = vorlagenAusTemplates(daten.templates);
const eig = eigenschaftenAusKatalog(daten.metrics);

/** Echter Svelte-5-`$state`-Proxy einer tiefen Kopie (die Plain-Vorlage bleibt unberuehrt). */
const alsState = <T>(x: T): T => proxy(JSON.parse(JSON.stringify(x))) as T;

/** Messaufbau-Pruefung: der Proxy ist wirklich einer, an dem structuredClone scheitert. */
function istProxy(x: unknown): void {
	assert.throws(() => structuredClone(x), { name: 'DataCloneError' }, 'Messaufbau: kein echter Svelte-Proxy');
}

const TRIP_ABO: AboSicht = {
	id: 't-c1',
	display_config: {
		metrics: [
			{ metric_id: 'wind', enabled: true, format_mode: 'raw' },
			{ metric_id: 'gust', enabled: true }
		],
		ampel: { template: 'wandern', metrics: { wind: { alarm_ab: 'red' } } }
	},
	report_config: { enabled: true, morning_time: '06:00:00', day_window_start_hour: 5, day_window_end_hour: 20 },
	official_alerts_enabled: true,
	official_warnings: { enabled: false, sources: ['dwd'] }
};

describe('C1: Modell-Funktionen klonen Svelte-$state-Proxys (Stand und Abo aus dem Browser)', () => {
	test('wetterZustand: mitAlarmAb / mitEntwurf / mitEigenerVorlage mit Proxy-Stand', () => {
		const plain = standAusAbo('route', TRIP_ABO, vorlagen);
		const stand = alsState(plain);
		istProxy(stand);
		assert.deepEqual(mitAlarmAb(stand, 'gust', 'red'), mitAlarmAb(plain, 'gust', 'red'), '„Alarm ab" an einer Zeile');
		const e = { id: 'wind', upper: { orange: 50 } };
		assert.deepEqual(mitEntwurf(stand, e), mitEntwurf(plain, e), 'Eingabe in „Grenzen ändern"');
		assert.deepEqual(mitEntwurf(stand, e, true), mitEntwurf(plain, e, true), 'Anzeige waehrend der Eingabe');
		const eigene = alsState(vorlagen.wassersport);
		istProxy(eigene);
		assert.deepEqual(mitEigenerVorlage(plain, eigene, vorlagen), mitEigenerVorlage(plain, vorlagen.wassersport, vorlagen), 'eigene Vorlage uebernehmen');
	});

	test('ampelModell: alarmAbFuerAlle und vorlagenAusTemplates mit Proxy-Eingabe', () => {
		const plain = standAusAbo('route', TRIP_ABO, vorlagen);
		const ampel = alsState(plain.ampel);
		istProxy(ampel);
		assert.deepEqual(alarmAbFuerAlle(ampel, plain.auswahl, 'orange', eig), alarmAbFuerAlle(plain.ampel, plain.auswahl, 'orange', eig));
		const templates = alsState(daten.templates);
		assert.deepEqual(vorlagenAusTemplates(templates), vorlagen);
	});

	test('amtlicheWarnungen: amtlicheWarnungenFelder mit Proxy-Abo behaelt sources', () => {
		const abo = alsState(TRIP_ABO);
		istProxy(abo);
		assert.deepEqual(amtlicheWarnungenFelder(true, abo as never), {
			official_alerts_enabled: true,
			official_warnings: { enabled: true, sources: ['dwd'] }
		});
	});

	test('ampelSchreiben: Trip-, Vergleichs- und Vorlagen-Payload mit Proxy-Eingaben', () => {
		const plain = standAusAbo('route', TRIP_ABO, vorlagen);
		const dc = TRIP_ABO.display_config as Record<string, unknown>;
		const eingabe = (x: <T>(v: T) => T) => ({
			vorlage: vorlagen[plain.vorlageId],
			aufgeloest: x(plain.ampel),
			auswahl: x(plain.auswahl),
			displayConfig: x(dc),
			reportConfig: x(TRIP_ABO.report_config),
			warnFelder: x(TRIP_ABO),
			warnungenAn: true,
			tagesfenster: { start: 6, end: 21 }
		});
		const ohne = <T>(v: T): T => v;
		assert.deepEqual(tripSpeicherPayload(eingabe(alsState) as never), tripSpeicherPayload(eingabe(ohne) as never));

		const vglDc = { active_metrics: [{ metric_id: 'wind', aggregation: 'max' }], ideal_ranges: { wind_max_kmh: { min: 0, max: 30 } } };
		const vgl = (x: <T>(v: T) => T) => ({
			vorlage: vorlagen[plain.vorlageId],
			aufgeloest: x(plain.ampel),
			auswahl: ['wind', 'gust'],
			displayConfig: x(vglDc),
			aggregationFuer: () => 'max',
			warnFelder: x(TRIP_ABO),
			warnungenAn: false,
			radarAn: true,
			tagesfenster: { start: 6, end: 21 }
		});
		assert.deepEqual(vergleichSpeicherPayload(vgl(alsState) as never), vergleichSpeicherPayload(vgl(ohne) as never));

		const dialog = (a: unknown) => ({ name: 'Meine', beschreibung: '', alsStandard: false, kind: 'route' as const, ampel: a as never });
		assert.deepEqual(eigeneVorlagePayload(dialog(alsState(plain.ampel))), eigeneVorlagePayload(dialog(plain.ampel)));
	});

	test('Trip-Speicherer: tripNutzlast mit Proxy-Stand und Proxy-Abo (wie WetterTab.svelte)', () => {
		const plain = standAusAbo('route', TRIP_ABO, vorlagen);
		const o = (s: WetterStand, abo: AboSicht) => ({ client: api, stand: () => s, vorlagen: () => vorlagen, abo: () => abo });
		assert.deepEqual(
			tripNutzlast(o(alsState(mitAlarmAb(plain, 'gust', 'red')), alsState(TRIP_ABO))),
			tripNutzlast(o(mitAlarmAb(plain, 'gust', 'red'), TRIP_ABO))
		);
	});

	test('Reiter Wetter in der Zustellung (Teil 2): ampelBeimAnwenden mit Proxy-Vorlage', () => {
		const preset = alsState({ ampel: { template: 'wandern', metrics: { gust: { alarm_ab: 'red' } } } });
		istProxy(preset.ampel);
		assert.deepEqual(ampelBeimAnwenden(preset, 'wandern'), { template: 'wandern', metrics: { gust: { alarm_ab: 'red' } } });
	});
});

// ── Vergleich: Speicherer mit Proxy-Stand und Proxy-Abo bis zum PUT (Muster f003) ─────────────

const ID = 'cp-2794-c1';
let server: GoMergeServer;

function vergleichAbo(): Record<string, unknown> {
	const v = vollerVergleich(ID);
	const dc = v.display_config as Record<string, unknown>;
	dc.active_metrics = [
		{ metric_id: 'temperature', aggregation: 'max' },
		{ metric_id: 'wind', aggregation: 'max' },
		{ metric_id: 'gust', aggregation: 'max' }
	];
	dc.ampel = { template: 'allgemein' };
	return v;
}

beforeEach(async () => {
	clearEtagRegistry();
	server = createGoMergeServer({ [ID]: vergleichAbo() });
	server.install();
	await api.get(`/api/compare/presets/${ID}`);
});
afterEach(() => server.restore());

describe('C1: Vergleichs-Speicherer setzt mit Svelte-Proxys den PUT ab', () => {
	test('„Alarm ab" an Boeen ⇒ genau ein PUT 200, Ampel auf dem Server', async () => {
		const seite = alsState(vergleichAbo()) as AboSicht;
		istProxy(seite);
		let stand: WetterStand = alsState(standAusAbo('vergleich', seite, vorlagen));
		istProxy(stand);
		const ctl = createController(ID);
		const queue = createPutQueue();
		const sp = SPEICHERER.vergleich({
			client: api,
			stand: () => stand,
			vorlagen: () => vorlagen,
			abo: () => seite,
			saveController: ctl,
			enqueueHubWrite: (fn) => queue.enqueue(fn),
			uebernehmen: () => {},
			neuGeladen: () => {}
		});
		stand = alsState(mitAlarmAb(stand, 'gust', 'red'));
		sp.melden();
		await ctl.flush();
		const puts = server.mitschnitt.filter((e) => e.method === 'PUT');
		assert.equal(puts.length, 1, `kein PUT — Speichern scheitert vorher (Zustand: ${ctl.state})`);
		assert.equal(puts[0].status, 200);
		const ampel = (server.stand(ID).display_config as Record<string, unknown>).ampel as Record<string, unknown>;
		assert.deepEqual((ampel.metrics as Record<string, unknown>).gust, { alarm_ab: 'red' });
	});
});
