// Issue #3020 R1 (G29): eine EIGENE Vorlage übernehmen speichert ihre Grenzen und Alarmstufen; „Als eigene Vorlage
// speichern“ ändert am Stand des Reiters und an seiner Nutzlast nichts.
//
// Gemessen im ECHTEN Instanz-Skript von WetterTabInhalt.svelte samt echtem Speicherer (wetterTabSpeicherung.ts) bis
// zum PUT-Rumpf; Katalog und Vorlagen live aus dem Python-Core. Zwei Nutzer: A (Trip), B (Orts-Vergleich).
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/eigene_vorlage_im_put_3020.test.ts

import { test, describe, after } from 'node:test';
import assert from 'node:assert/strict';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { umgebungFuer } from '../../__tests__/svelteInstanzPruefstand.ts';
import { aufloesungPost, live, vergleichsKatalogFetch } from './wetterTabDaten.ts';
import { vorlagenAusTemplates } from '../ampelModell.ts';
import { tripNutzlast, vergleichNutzlast } from '../wetterTabSpeicherung.ts';

type J = any; // eslint-disable-line @typescript-eslint/no-explicit-any
const HIER = dirname(fileURLToPath(import.meta.url));
const REITER = join(HIER, '..', '..', '..', 'organisms', 'wetter-tab', 'WetterTabInhalt.svelte');
after(vergleichsKatalogFetch());

const VORLAGEN = vorlagenAusTemplates(live().templates);
const GRENZEN = { yellow: 33, orange: 47, red: 61 };
/** Eigene Vorlage auf Basis „wandern“: Wind mit eigenen Grenzen oben und Alarm ab Gelb. */
function eigeneVorlage(id: string, kind: 'route' | 'vergleich', grenzen: J = GRENZEN): J {
	const ampel: J = structuredClone(VORLAGEN.wandern);
	ampel.template = 'wandern';
	ampel.metrics.wind = { ...ampel.metrics.wind, enabled: true, upper: grenzen, alarm_ab: 'yellow' };
	return { id, name: `Vorlage ${id}`, is_default: false, metrics: [], created_at: '2026-11-01T00:00:00Z', kind, ampel };
}
const ABO: Record<'route' | 'vergleich', J> = {
	route: { id: 'trip-a-g29', name: 'A', stages: [], display_config: { metrics: [{ metric_id: 'wind', enabled: true, bucket: 'primary', order: 0 }], ampel: { template: 'allgemein' } }, report_config: {} },
	vergleich: { id: 'orte-b-g29', name: 'B', location_ids: ['o1'], display_config: { active_metrics: [{ metric_id: 'wind', aggregation: 'max' }], ampel: { template: 'allgemein' } } }
};

async function reiter(context: 'route' | 'vergleich') {
	const puts: { pfad: string; rumpf: J }[] = [];
	const geplant: (() => Promise<void>)[] = [];
	const { u } = await umgebungFuer(REITER, {
		context,
		trip: context === 'route' ? structuredClone(ABO.route) : undefined,
		preset: context === 'vergleich' ? structuredClone(ABO.vergleich) : undefined,
		createMode: false,
		saveController: { schedule: (fn: () => Promise<void>) => void geplant.push(fn), cancel: () => {} },
		enqueueHubWrite: undefined,
		onTripUpdate: () => {},
		onCompareUpdate: () => {},
		onAnlegeStand: undefined,
		api: {
			get: async (pfad: string) => {
				if (pfad === '/api/metrics') return live().metrics;
				if (pfad === '/api/templates') return live().templates;
				if (pfad === '/api/metric-presets') return [eigeneVorlage('eigene-route', 'route'), eigeneVorlage('eigene-vergleich', 'vergleich')];
				throw new Error(`unerwartet: ${pfad}`);
			},
			post: aufloesungPost(),
			put: async (pfad: string, rumpf: J) => {
				puts.push({ pfad, rumpf: JSON.parse(JSON.stringify(rumpf)) });
				return {};
			}
		}
	});
	await u.laden();
	assert.equal(u.phase, 'bereit', 'Messaufbau: der Reiter ist geladen');
	const speichern = async () => {
		for (const fn of geplant.splice(0)) await fn();
		return puts.splice(0);
	};
	const nutzlast = () => JSON.stringify(context === 'route' ? tripNutzlast(u.optionen()) : vergleichNutzlast(u.optionen()));
	return { u, speichern, geplant, nutzlast };
}

/** Wo die Ampel im PUT des Kontexts steht. */
const AMPEL_IM_PUT = {
	route: (puts: { pfad: string; rumpf: J }[]) => puts.find((p) => p.pfad.endsWith(`/api/trips/${ABO.route.id}/weather-config`))?.rumpf.ampel,
	vergleich: (puts: { pfad: string; rumpf: J }[]) => puts.find((p) => p.pfad.endsWith(`/api/compare/presets/${ABO.vergleich.id}`))?.rumpf.display_config.ampel
};

async function imPut(context: 'route' | 'vergleich'): Promise<void> {
	const r = await reiter(context);
	assert.notDeepEqual(VORLAGEN.wandern.metrics?.wind?.upper, GRENZEN, 'Messaufbau: die Grenzen weichen von der Systemvorlage ab');
	assert.deepEqual(r.u.daten.eigene.map((e: J) => e.id), [`eigene-${context}`], 'nur eigene Vorlagen dieser Art');
	r.u.eigeneUebernehmen(`eigene-${context}`);
	const ampel = AMPEL_IM_PUT[context](await r.speichern());
	assert.ok(ampel, 'kein PUT mit Ampel');
	assert.equal(ampel.template, 'wandern', 'Systemvorlage der eigenen Vorlage');
	assert.deepEqual(ampel.metrics?.wind?.upper, GRENZEN, 'Grenzen der eigenen Vorlage');
	assert.equal(ampel.metrics?.wind?.alarm_ab, 'yellow', 'Alarmstufe der eigenen Vorlage');
}

describe('#3020 G29: eigene Vorlage im PUT', () => {
	test('route: eigene Vorlage übernehmen, PUT trägt Grenzen und alarm_ab der Vorlage', () => imPut('route'));
	test('vergleich: eigene Vorlage übernehmen, PUT trägt Grenzen und alarm_ab der Vorlage', () => imPut('vergleich'));

	test('als eigene Vorlage gespeichert: Stand und Nutzlast bleiben unverändert', async () => {
		for (const context of ['route', 'vergleich'] as const) {
			const r = await reiter(context);
			r.u.eigeneUebernehmen(`eigene-${context}`);
			await r.speichern();
			const stand = structuredClone(r.u.stand);
			const nutzlast = r.nutzlast();
			// Die frisch gespeicherte Vorlage trägt andere Grenzen: übernähme der Reiter sie, sähe man es.
			r.u.vorlageGespeichert(eigeneVorlage('frisch', context, { yellow: 11, orange: 12, red: 13 }));
			assert.deepEqual(r.u.daten.eigene.map((e: J) => e.id), ['frisch', `eigene-${context}`], `${context}: steht in der Liste`);
			assert.deepEqual(r.u.stand, stand, `${context}: Stand geändert`);
			assert.equal(r.nutzlast(), nutzlast, `${context}: Nutzlast geändert`);
			assert.deepEqual(r.geplant, [], `${context}: Speichervorgang geplant`);
		}
	});
});
