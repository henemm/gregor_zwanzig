// Fix-Loop 3 Issue #2794 S3a Teil-PR 3, Befund C2: Orts-Briefing mit Altformat
// `display_config.active_metrics` (Anzeige-Schluessel als Zeichenkette, z. B. `['snow_depth_cm']`)
// zeigte im Reiter Wetter 0 Zeilen, und das erste Speichern verlor die Auswahl.
//
// Vertrag (docs/reference/api_contract.md, `active_metrics`, #1373): das Altformat wird
// DAUERHAFT gelesen, auch gemischt mit dem Neuformat `{metric_id, aggregation}`, pro Element
// aufgeloest; geschrieben wird nur das Neuformat. Die Uebersetzung Anzeige-Schluessel ->
// Groesse kommt aus dem Vergleichs-Katalog (GET /api/compare/metrics), hier LIVE aus
// `output.renderers.compare_metric_catalog` (keine Frontend-Kopie).
//
// Gemessen dort, wo es wirkt: Lesen (`standAusAbo`), Speichern bis auf den Go-Merge-Pruefserver
// (Muster f003) und die Verdrahtung im ECHTEN Instanz-Skript von WetterTab.svelte.
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/fixloop3_c2_altformat_active_metrics.test.ts

import { test, describe, before, after, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { api } from '../../../../api.ts';
import { clearEtagRegistry } from '../../../../etagRegistry.ts';
import { createPutQueue } from '../../../compare/compareHubPersistenz.ts';
import { createController } from '../../__tests__/versandVergleichPruefstand.ts';
import { createGoMergeServer, vollerVergleich, type GoMergeServer } from '../../__tests__/goMergeServerPruefstand.ts';
import { umgebungFuer, type Knoten } from '../../__tests__/svelteInstanzPruefstand.ts';
import { toCompareSelectionEntries } from '../../weather-metrics-tab/compareMetricSelection.ts';
import { live, REPO } from './wetterTabDaten.ts';
import * as M from '../ampelModell.ts';
import { mitAlarmAb, standAusAbo, type AboSicht, type WetterStand } from '../wetterZustand.ts';
import { SPEICHERER, vergleichNutzlast } from '../wetterTabSpeicherung.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const WETTER_TAB = join(HIER, '..', 'WetterTab.svelte');

const PY_KATALOG = [
	'import sys, json',
	"sys.path.insert(0, 'src'); sys.path.insert(0, '.')",
	'from output.renderers.compare_metric_catalog import get_compare_metric_catalog',
	"print(json.dumps({'metrics': get_compare_metric_catalog(lang='de')}, ensure_ascii=False))"
].join('\n');
const KATALOG_ANTWORT = JSON.parse(execFileSync('uv', ['run', 'python3', '-c', PY_KATALOG], { cwd: REPO, encoding: 'utf-8' }).trim());
const KATALOG = toCompareSelectionEntries(KATALOG_ANTWORT);

const vorlagen = M.vorlagenAusTemplates(live().templates);
type AltSchluessel = Record<string, { metric_id: string; aggregation: string }>;
/** Uebersetzung aus dem Katalog; fehlt die Funktion (vor dem Fix), bleibt sie leer. */
const altSchluessel = (): AltSchluessel => {
	const f = (M as Record<string, unknown>).altSchluesselAusKatalog as ((k: unknown) => AltSchluessel) | undefined;
	return typeof f === 'function' ? f(KATALOG) : {};
};

/** Messaufbau: die Altformat-Schluessel des Tests stehen wirklich so im Live-Katalog. */
function katalogPaar(key: string): { metric_id: string; aggregation: string } {
	const e = KATALOG.find((k) => k.metric === key);
	assert.ok(e?.metric_id && e.aggregation, `Messaufbau: ${key} fehlt im Vergleichs-Katalog`);
	return { metric_id: e.metric_id!, aggregation: e.aggregation! };
}

const ID = 'cp-2794-c2';
function abo(activeMetrics: unknown[]): Record<string, unknown> {
	const v = vollerVergleich(ID);
	const dc = v.display_config as Record<string, unknown>;
	dc.active_metrics = activeMetrics;
	dc.ampel = { template: 'allgemein' };
	return v;
}

describe('C2: Altformat active_metrics wird gelesen (auch gemischt, Reihenfolge bleibt)', () => {
	test('[„snow_depth_cm"] ⇒ Auswahl Schneehoehe (eine Zeile statt 0)', () => {
		assert.equal(katalogPaar('snow_depth_cm').metric_id, 'snow_depth');
		const s = standAusAbo('vergleich', abo(['snow_depth_cm']) as AboSicht, vorlagen, altSchluessel());
		assert.deepEqual(s.auswahl, ['snow_depth']);
	});

	test('gemischt Alt/Neu ⇒ pro Element aufgeloest, Reihenfolge der Liste', () => {
		const s = standAusAbo(
			'vergleich',
			abo(['snow_depth_cm', { metric_id: 'wind', aggregation: 'max' }, 'temp_max_c']) as AboSicht,
			vorlagen,
			altSchluessel()
		);
		assert.deepEqual(s.auswahl, ['snow_depth', 'wind', katalogPaar('temp_max_c').metric_id]);
	});
});

// ── Speichern bis auf den Server (Muster f003) ────────────────────────────────────────────

let server: GoMergeServer;
afterEach(() => server?.restore());

async function speichereNachAenderung(start: unknown[], aendern: (s: WetterStand) => WetterStand): Promise<Record<string, unknown>> {
	clearEtagRegistry();
	server = createGoMergeServer({ [ID]: abo(start) });
	server.install();
	await api.get(`/api/compare/presets/${ID}`);
	const seite = abo(start) as AboSicht;
	const alt = altSchluessel();
	let stand = standAusAbo('vergleich', seite, vorlagen, alt);
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
		neuGeladen: () => {},
		aggregationFuer: (id) => KATALOG.find((e) => e.metric_id === id)?.aggregation ?? 'max',
		altSchluessel: alt
	} as Parameters<typeof SPEICHERER.vergleich>[0]);
	stand = aendern(stand);
	sp.melden();
	await ctl.flush();
	const puts = server.mitschnitt.filter((e) => e.method === 'PUT');
	assert.equal(puts.length, 1, `Messaufbau: genau ein PUT erwartet (Zustand ${ctl.state})`);
	assert.equal(puts[0].status, 200);
	return server.stand(ID).display_config as Record<string, unknown>;
}

describe('C2: erstes Speichern verliert die Altformat-Auswahl nicht', () => {
	test('[„snow_depth_cm"] + „Alarm ab" an Boeen ⇒ Schneehoehe bleibt gewaehlt (Neuformat)', async () => {
		const dc = await speichereNachAenderung(['snow_depth_cm'], (s) => mitAlarmAb(s, 'gust', 'red'));
		assert.deepEqual(dc.active_metrics, [katalogPaar('snow_depth_cm')], 'Auswahl verloren oder nicht ins Neuformat geschrieben');
	});

	test('gemischte Liste ⇒ Reihenfolge bleibt, Altformat-Eintrag wird an seinem Platz zum Neuformat', async () => {
		const dc = await speichereNachAenderung(
			['snow_depth_cm', { metric_id: 'wind', aggregation: 'max' }],
			(s) => mitAlarmAb(s, 'gust', 'red')
		);
		assert.deepEqual(dc.active_metrics, [katalogPaar('snow_depth_cm'), { metric_id: 'wind', aggregation: 'max' }]);
	});
});

// ── Verdrahtung im echten WetterTab-Skript (Hub, Orts-Briefing) ───────────────────────────

describe('C2: WetterTab (vergleich) liest und schreibt das Altformat', () => {
	let vorherFetch: typeof globalThis.fetch;
	before(() => {
		vorherFetch = globalThis.fetch;
		(globalThis as { fetch: unknown }).fetch = async (input: unknown) => {
			const pfad = new URL(String(input), 'http://gz.invalid').pathname;
			if (pfad === '/api/compare/metrics') return new Response(JSON.stringify(KATALOG_ANTWORT), { status: 200, headers: { 'Content-Type': 'application/json' } });
			return new Response('{}', { status: 404 });
		};
	});
	after(() => {
		(globalThis as { fetch: unknown }).fetch = vorherFetch;
	});
	beforeEach(() => {
		server = undefined as unknown as GoMergeServer;
	});

	const LIVE_API = {
		get: async (pfad: string) => {
			const d = live();
			if (pfad === '/api/metrics') return d.metrics;
			if (pfad === '/api/templates') return d.templates;
			if (pfad === '/api/metric-presets') return [];
			throw new Error(`unerwartet: ${pfad}`);
		}
	};

	test('Laden: [„snow_depth_cm"] ⇒ Zeile Schneehoehe; Speicher-Rumpf traegt sie im Neuformat', async () => {
		const { u } = await umgebungFuer(WETTER_TAB, {
			context: 'vergleich',
			preset: abo(['snow_depth_cm']),
			trip: undefined,
			createMode: false,
			saveController: undefined,
			enqueueHubWrite: undefined,
			onTripUpdate: undefined,
			onCompareUpdate: undefined,
			onAnlegeStand: undefined,
			api: LIVE_API
		});
		assert.equal(typeof u.laden, 'function', 'Messaufbau: laden() nicht herleitbar');
		await u.laden();
		assert.equal(u.phase, 'bereit', 'Messaufbau: WetterTab hat nicht geladen');
		assert.deepEqual(u.stand.auswahl, ['snow_depth'], 'der Reiter zeigt die Altformat-Auswahl nicht');
		const rumpf = vergleichNutzlast(u.optionen() as Knoten as Parameters<typeof vergleichNutzlast>[0]);
		assert.deepEqual(rumpf.display_config.active_metrics, [katalogPaar('snow_depth_cm')]);
	});
});
