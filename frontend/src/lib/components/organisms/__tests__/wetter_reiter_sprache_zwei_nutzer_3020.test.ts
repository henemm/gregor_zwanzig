// Issue #3020 R1 (G55, AC-3 der Altdatei wertebereiche_sprache.test.ts): zwei Nutzer, zwei Sprachen im Reiter Wetter —
// jeder sieht SEINE Auswahl in SEINER Sprache, die gespeicherte Nutzlast hängt nicht an der Sprache.
//
// Sprache je Sitzung über den ECHTEN Layout-Loader (routes/+layout.server.ts; ersetzt ist nur die Netzgrenze, fetch je
// Sitzungs-Cookie), Anzeige und Speichern am ECHTEN Instanz-Skript von WetterTabInhalt.svelte, Katalog live aus dem
// Python-Core (label_de/label_en).
//
//   cd frontend && npm test -- src/lib/components/organisms/__tests__/wetter_reiter_sprache_zwei_nutzer_3020.test.ts

import { test, describe, after } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { umgebungFuer } from '../../shared/__tests__/svelteInstanzPruefstand.ts';
import { aufloesungPost, live } from '../../shared/wetter-tab/__tests__/wetterTabDaten.ts';

type J = any; // eslint-disable-line @typescript-eslint/no-explicit-any
const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../../..');
const REITER = path.resolve(HERE, '..', 'wetter-tab', 'WetterTabInhalt.svelte');

const base = pathToFileURL(FRONTEND + '/').href;
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, base);
register(pathToFileURL(path.join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href, base);
register(pathToFileURL(path.join(FRONTEND, 'src/routes/admin/__tests__/server-load-resolve.hooks.mjs')).href, base);
const layoutLoad = (await import(pathToFileURL(path.join(FRONTEND, 'src/routes/+layout.server.ts')).href)).load;
const { locale } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/index.ts')).href);
after(() => locale.set('de'));

const PROFIL: Record<string, J> = { A: { id: 'anna', language: 'en' }, B: { id: 'bert', language: 'de' } };
async function spracheDerSitzung(sitzung: string): Promise<'de' | 'en'> {
	const echt = globalThis.fetch;
	(globalThis as J).fetch = async (u: string, init?: J) => {
		const s = /gz_session=([^;]+)/.exec(init?.headers?.Cookie ?? '')?.[1] ?? '';
		return new URL(String(u), 'http://core').pathname === '/api/auth/profile' && PROFIL[s]
			? new Response(JSON.stringify(PROFIL[s]), { status: 200 })
			: new Response('{}', { status: 404 });
	};
	try {
		const cookies = { get: (n: string) => (n === 'gz_session' ? sitzung : undefined) };
		// Vorgabe der Anfrage ist die jeweils ANDERE Sprache: nur das Profil der Sitzung entscheidet.
		const vorgabe = PROFIL[sitzung].language === 'de' ? 'en' : 'de';
		return (await layoutLoad({ locals: { userId: PROFIL[sitzung].id, lang: vorgabe }, cookies } as never)).lang;
	} finally {
		globalThis.fetch = echt;
	}
}

const trip = (id: string, metriken: string[]): J => ({
	id,
	name: id,
	stages: [],
	display_config: { metrics: metriken.map((metric_id, order) => ({ metric_id, enabled: true, bucket: 'primary', order })), ampel: { template: 'allgemein' } },
	report_config: {}
});

async function reiter(t: J) {
	const puts: { pfad: string; rumpf: J }[] = [];
	const geplant: (() => Promise<void>)[] = [];
	const { u } = await umgebungFuer(REITER, {
		context: 'route',
		trip: structuredClone(t),
		preset: undefined,
		createMode: false,
		saveController: { schedule: (fn: () => Promise<void>) => void geplant.push(fn), cancel: () => {} },
		enqueueHubWrite: undefined,
		onTripUpdate: () => {},
		onCompareUpdate: undefined,
		onAnlegeStand: undefined,
		api: {
			get: async (pfad: string) => ({ '/api/metrics': live().metrics, '/api/templates': live().templates, '/api/metric-presets': [] })[pfad],
			post: aufloesungPost(),
			put: async (pfad: string, rumpf: J) => {
				puts.push({ pfad, rumpf: JSON.parse(JSON.stringify(rumpf)) });
				return {};
			}
		}
	});
	await u.laden();
	assert.equal(u.phase, 'bereit', 'Messaufbau: der Reiter ist geladen');
	return {
		u,
		namen: () => u.stand.auswahl.map((id: string) => u.name(id)) as string[],
		async speichern() {
			for (const fn of geplant.splice(0)) await fn();
			return puts.splice(0);
		}
	};
}

const KATALOG: Record<string, J> = Object.fromEntries(Object.values(live().metrics).flat().map((m) => [m.id, m]));
const label = (ids: string[], lang: 'de' | 'en') => ids.map((id) => KATALOG[id][`label_${lang}`]);
/** Alle Schlüssel und Zeichenketten eines Rumpfs. */
function inhalt(x: J, aus: string[] = []): string[] {
	if (typeof x === 'string') aus.push(x);
	else if (x && typeof x === 'object') for (const [k, v] of Object.entries(x)) (Array.isArray(x) ? aus : (aus.push(k), aus)), inhalt(v, aus);
	return aus;
}

describe('#3020 G55: zwei Nutzer, zwei Sprachen, gleiche Nutzlast', () => {
	test('A englisch, B deutsch: jeder sieht seine Auswahl in seiner Sprache; PUT-Nutzlast identisch und ohne Anzeigetexte', async () => {
		const EIGENE = { A: ['gust', 'humidity'], B: ['precipitation', 'cloud_total'] } as const;
		const GLEICH = ['gust', 'precipitation', 'humidity'];
		const rumpf: Record<string, J[]> = {};
		for (const sitzung of ['A', 'B'] as const) {
			const lang = await spracheDerSitzung(sitzung);
			assert.equal(lang, PROFIL[sitzung].language, `${sitzung}: Sprache der Sitzung`);
			locale.set(lang);
			try {
				const eigen = await reiter(trip(`trip-${sitzung}`, [...EIGENE[sitzung]]));
				assert.deepEqual(eigen.u.stand.auswahl, [...EIGENE[sitzung]], `${sitzung}: eigene Auswahl`);
				assert.deepEqual(eigen.namen(), label([...EIGENE[sitzung]], lang), `${sitzung}: Namen in ${lang}`);

				const r = await reiter(trip(`gleich-${sitzung}`, GLEICH));
				r.u.hinzufuegen('wind');
				assert.deepEqual(r.namen(), label([...GLEICH, 'wind'], lang), `${sitzung}: nach „+“`);
				assert.equal(r.u.hinzu, KATALOG.wind[`label_${lang}`], `${sitzung}: Meldung „jetzt im Briefing“`);
				rumpf[sitzung] = await r.speichern();
				assert.ok(rumpf[sitzung].length > 0, `${sitzung}: kein PUT`);
			} finally {
				locale.set('de');
			}
		}
		for (const id of [...EIGENE.A, ...EIGENE.B, ...GLEICH]) assert.notEqual(KATALOG[id].label_de, KATALOG[id].label_en, `Messaufbau: ${id} heißt in beiden Sprachen gleich`);
		const ohneId = (x: J, sitzung: string) => JSON.parse(JSON.stringify(x).replaceAll(`gleich-${sitzung}`, 'ID'));
		assert.deepEqual(ohneId(rumpf.A, 'A'), ohneId(rumpf.B, 'B'), 'die Nutzlast hängt an der Sprache');

		const texte = inhalt(rumpf.A.map((p) => p.rumpf));
		assert.ok(texte.includes('wind'), 'Messaufbau: der Rumpf trägt die Metrik');
		const verboten = new Set(['label', 'name', 'label_de', 'label_en', ...label([...GLEICH, 'wind'], 'de'), ...label([...GLEICH, 'wind'], 'en')]);
		assert.deepEqual(texte.filter((t) => verboten.has(t)), [], 'Anzeigetext in der Nutzlast');
	});
});
