// Fix-Loop 4 Issue #2794 S3a Teil-PR 3 (Adversary-Runde nach Fix-Loop 3).
//
// F001 (MEDIUM): Im Orts-Briefing braucht der Reiter Wetter den Vergleichs-Katalog
// (GET /api/compare/metrics), um Altformat-`active_metrics` (z. B. `['snow_depth_cm']`) zu lesen.
// Scheiterte der Abruf, lief der Reiter still mit leerer Uebersetzung weiter: keine Zeilen, und
// ein Speichern liess `ampel.metrics.*.enabled` und `active_metrics` auseinanderlaufen (AC-37).
// Tech-Lead-Entscheid: ein Katalogfehler im Vergleich ist ein Ladefehler wie der des Metrik-
// Katalogs ⇒ Fehlerzustand aus AC-9 („Die Metriken konnten nicht geladen werden …" + „Erneut
// laden"), keine Hydration, kein Schreibvorgang; „Erneut laden" holt auch den Katalog neu.
// Der Trip-Pfad braucht den Katalog nicht und bleibt unberuehrt.
//
// Nebenbefund: gleiche Metrik in Alt- UND Neuformat in einer Liste ⇒ beim Schreiben nur EIN
// Eintrag (erstes Vorkommen gewinnt, Reihenfolge bleibt) — wie die Leseseite.
// F002 (LOW): `klon` erhaelt NaN (eine JSON-Rundreise machte daraus null).
//
// Gemessen im ECHTEN Instanz-Skript von WetterTab.svelte; der Katalog-Abruf geht ueber das
// globale `api` (fetch), der Katalog kommt live aus dem Python-Core.
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/fixloop4_vergleich_katalog_ladefehler.test.ts

import { test, describe, after } from 'node:test';
import assert from 'node:assert/strict';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { umgebungFuer, type Knoten } from '../../__tests__/svelteInstanzPruefstand.ts';
import { toCompareSelectionEntries } from '../../weather-metrics-tab/compareMetricSelection.ts';
import { live, liveVergleichsKatalog, vergleichsKatalogFetch } from './wetterTabDaten.ts';
import { altSchluesselAusKatalog, vorlagenAusTemplates } from '../ampelModell.ts';
import { vergleichSpeicherPayload } from '../ampelSchreiben.ts';
import { standAusAbo } from '../wetterZustand.ts';
import { klon } from '../klon.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const WETTER_TAB = join(HIER, '..', 'WetterTab.svelte');

const LIVE_API = {
	get: async (pfad: string) => {
		const d = live();
		if (pfad === '/api/metrics') return d.metrics;
		if (pfad === '/api/templates') return d.templates;
		if (pfad === '/api/metric-presets') return [];
		throw new Error(`unerwartet: ${pfad}`);
	}
};

const ALTABO = {
	id: 'cp-2794-fl4',
	display_config: { active_metrics: ['snow_depth_cm', 'temp_max_c'], ampel: { template: 'allgemein' } }
};

describe('F001: Vergleichs-Katalog scheitert ⇒ Ladefehler (AC-9), kein Schreiben; „Erneut laden" heilt', () => {
	let katalogOk = false;
	const schreibende: string[] = [];
	const zurueck = vergleichsKatalogFetch(() => katalogOk);
	const mitKatalog = globalThis.fetch;
	// jeden nicht-lesenden Abruf mitschneiden (PUT/POST des Reiters = Schreibvorgang)
	(globalThis as { fetch: unknown }).fetch = async (input: unknown, init?: RequestInit) => {
		const m = (init?.method ?? 'GET').toUpperCase();
		if (m !== 'GET') schreibende.push(`${m} ${String(input)}`);
		return mitKatalog(input as RequestInfo, init);
	};
	after(() => zurueck());

	// Beide Einbettungen (Hub und Anlegen) in EINEM Test: der Katalog-Lader cacht eine Erfolgs-
	// antwort modulweit (je Seiten-Load) — nach dem ersten Heilen gaebe es keinen Fehler mehr.
	test('Hub und Anlegen: Fehlerzustand statt stiller leerer Zeilen, danach „Erneut laden"', async () => {
		katalogOk = false;
		schreibende.length = 0;
		const reiter: Array<{ wo: string; u: Knoten; berichte: unknown[] }> = [];
		for (const createMode of [false, true]) {
			const berichte: unknown[] = [];
			const { u } = await umgebungFuer(WETTER_TAB, {
				context: 'vergleich',
				preset: structuredClone(ALTABO),
				trip: undefined,
				createMode,
				saveController: undefined,
				enqueueHubWrite: undefined,
				onTripUpdate: undefined,
				onCompareUpdate: (p: unknown) => berichte.push(p),
				onAnlegeStand: (n: unknown) => berichte.push(n),
				api: LIVE_API
			});
			reiter.push({ wo: createMode ? 'Anlegen' : 'Hub', u, berichte });
		}
		for (const { wo, u, berichte } of reiter) {
			await u.laden();
			assert.equal(u.phase, 'fehler', `${wo}: Katalogfehler wird verschluckt — kein Ladefehler (AC-9)`);
			assert.equal(u.stand, null, `${wo}: der Reiter hydriert trotz Katalogfehler`);
			assert.deepEqual(berichte, [], `${wo}: der Reiter meldet trotz Katalogfehler einen Stand`);
		}
		assert.deepEqual(schreibende, [], 'der Reiter schreibt trotz Katalogfehler');

		katalogOk = true; // „Erneut laden"
		for (const { wo, u } of reiter) {
			await u.laden();
			assert.equal(u.phase, 'bereit', `${wo}: „Erneut laden" holt den Vergleichs-Katalog nicht neu`);
			assert.deepEqual(u.stand.auswahl, ['snow_depth', 'temperature'], `${wo}: nach „Erneut laden" fehlen die Zeilen`);
		}
	});
});

describe('Nebenbefund: gleiche Metrik in Alt- und Neuformat ⇒ ein Eintrag beim Schreiben', () => {
	test('[„snow_depth_cm", {snow_depth}, {wind}] ⇒ [{snow_depth}, {wind}] (erstes Vorkommen, Reihenfolge)', () => {
		const alt = altSchluesselAusKatalog(toCompareSelectionEntries(liveVergleichsKatalog()));
		assert.deepEqual(alt.snow_depth_cm, { metric_id: 'snow_depth', aggregation: 'max' }, 'Messaufbau: Katalog');
		const vorlagen = vorlagenAusTemplates(live().templates);
		const abo = {
			display_config: {
				active_metrics: ['snow_depth_cm', { metric_id: 'snow_depth', aggregation: 'max', extra: 1 }, { metric_id: 'wind', aggregation: 'max' }]
			}
		};
		const s = standAusAbo('vergleich', abo, vorlagen, alt);
		assert.deepEqual(s.auswahl, ['snow_depth', 'wind'], 'Messaufbau: Leseseite dedupliziert');
		const p = vergleichSpeicherPayload({
			vorlage: vorlagen[s.vorlageId],
			aufgeloest: s.ampel,
			auswahl: s.auswahl,
			displayConfig: abo.display_config as never,
			aggregationFuer: () => 'max',
			altSchluessel: alt,
			warnFelder: {},
			warnungenAn: false,
			radarAn: false,
			tagesfenster: { start: 4, end: 19 }
		});
		assert.deepEqual(p.display_config.active_metrics, [
			{ metric_id: 'snow_depth', aggregation: 'max' },
			{ metric_id: 'wind', aggregation: 'max' }
		]);
	});
});

describe('F002: klon erhaelt NaN und undefined (keine JSON-Rundreise)', () => {
	test('NaN in Grenzen bleibt NaN', () => {
		const k = klon({ lower: { yellow: NaN }, liste: [NaN, 1], leer: undefined });
		assert.ok(Number.isNaN(k.lower.yellow), `NaN wurde zu ${JSON.stringify(k.lower.yellow)}`);
		assert.ok(Number.isNaN(k.liste[0]));
		assert.ok('leer' in k);
	});
});
