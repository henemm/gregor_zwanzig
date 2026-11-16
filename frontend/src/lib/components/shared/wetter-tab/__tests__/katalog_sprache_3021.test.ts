// Issue #3021 (Epic #2644, ADR-0104): der Vergleichs-Metrik-Katalog wird in der
// Nutzersprache geladen. Spec: docs/specs/modules/i18n_katalog_sprache_3021.md
//
// Bug aus Nutzersicht: ein englischsprachiger Nutzer sieht im Stundenverlauf-Block
// des Ortsvergleichs die Begruendung „stuendlich nicht waehlbar" (Sonnenstunden)
// auf Deutsch, weil der Lader `/api/compare/metrics` ohne `lang` abruft und die
// Antwort einmal je Seiten-Load fuer ALLE Sprachen zwischenspeichert.
//
// Netzgrenze ist `globalThis.fetch` (kein Mock der eigenen Annahme): die Antwort
// je Sprache ist die ECHTE Katalogausgabe des Python-Core
// (`get_compare_metric_catalog(lang)`), und der Stub waehlt die Sprache genau wie
// der Endpoint (`lang=en` -> englisch, alles andere -> deutsch,
// api/routers/compare.py). Ohne `lang` antwortet er also deutsch — wie in Echt.
//
// Jeder Test laedt eine frische Kopie des Lader-Moduls (Cache-Brecher in der URL),
// damit der modulweite Zwischenspeicher nicht zwischen Tests durchsickert. Der
// `locale`-Store bleibt dieselbe Instanz, die auch der Lader liest.
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/katalog_sprache_3021.test.ts

import { test, describe, before, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { locale } from '../../../../i18n/locale.ts';
import { toCompareSelectionEntries } from '../../weather-metrics-tab/compareMetricSelection.ts';

type Lang = 'de' | 'en';
type Katalog = { metrics: Array<Record<string, unknown>> };
type LaderModul = typeof import('../compareMetricCatalogLoader.ts');

const HIER = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(HIER, ...Array(7).fill('..'));
const LADER_URL = pathToFileURL(resolve(HIER, '..', 'compareMetricCatalogLoader.ts')).href;

const PY_SCRIPT =
	'import sys, json\n' +
	"sys.path.insert(0, 'src')\n" +
	'from output.renderers.compare_metric_catalog import get_compare_metric_catalog\n' +
	"print(json.dumps({'de': {'metrics': get_compare_metric_catalog(lang='de')}, 'en': {'metrics': get_compare_metric_catalog(lang='en')}}))\n";

let LIVE: Record<Lang, Katalog>;
let frisch = 0;

async function frischerLader(): Promise<LaderModul> {
	frisch += 1;
	return (await import(`${LADER_URL}?katalog_sprache_3021=${frisch}`)) as LaderModul;
}

/** Netzgrenze: zeichnet jeden Katalog-Abruf auf und antwortet wie der Endpoint. */
const abrufe: string[] = [];
let fehlerFuer: Set<Lang> = new Set();
const echtesFetch = globalThis.fetch;

function langAusUrl(url: string): Lang {
	const q = new URL(url, 'http://gregor.test').searchParams.get('lang');
	return q === 'en' ? 'en' : 'de';
}

function katalogFetch(input: unknown): Promise<Response> {
	const url = String(input);
	if (!url.includes('/api/compare/metrics')) {
		return Promise.reject(new Error(`unerwarteter Abruf: ${url}`));
	}
	abrufe.push(url);
	const lang = langAusUrl(url);
	if (fehlerFuer.has(lang)) {
		fehlerFuer.delete(lang); // einmaliger Fehler — „Wiederholen" muss heilen
		return Promise.resolve(new Response('{"detail":"boom"}', { status: 500, headers: { 'content-type': 'application/json' } }));
	}
	return Promise.resolve(
		new Response(JSON.stringify(LIVE[lang]), { status: 200, headers: { 'content-type': 'application/json' } })
	);
}

function sonnenGrund(entries: Array<Record<string, unknown>>): unknown {
	const e = entries.find((x) => x.metric_id === 'sunshine' && x.hourlyNotSelectableReason);
	assert.ok(e, 'Katalog enthaelt keinen Sonnenstunden-Eintrag mit Begruendung');
	return e.hourlyNotSelectableReason;
}

function langDerAbrufe(): Array<string | null> {
	return abrufe.map((u) => new URL(u, 'http://gregor.test').searchParams.get('lang'));
}

before(() => {
	const stdout = execFileSync('uv', ['run', 'python3', '-c', PY_SCRIPT], { cwd: REPO_ROOT, encoding: 'utf-8' });
	LIVE = JSON.parse(stdout.trim());
	// Vorbedingung des Bugs: die echte Quelle liefert je Sprache einen anderen Text.
	assert.notEqual(
		sonnenGrund(LIVE.en.metrics),
		sonnenGrund(LIVE.de.metrics),
		'Vorbedingung: Python-Katalog liefert die Sonnenstunden-Begruendung je Sprache verschieden'
	);
});

beforeEach(() => {
	abrufe.length = 0;
	fehlerFuer = new Set();
	(globalThis as { fetch: unknown }).fetch = katalogFetch;
	locale.set('de');
});

afterEach(() => {
	(globalThis as { fetch: unknown }).fetch = echtesFetch;
	locale.set('de');
});

describe('#3021 Vergleichs-Katalog in Nutzersprache', () => {
	test('AC-1: Sprache Englisch ⇒ Anfrage traegt lang=en, Sonnenstunden-Begruendung kommt englisch an', async () => {
		const lader = await frischerLader();
		locale.set('en');
		const entries = (await lader.loadCompareSelectionEntries()) as unknown as Array<Record<string, unknown>>;
		assert.deepEqual(langDerAbrufe(), ['en'], `Abruf ohne/mit falscher Sprache: ${abrufe.join(', ')}`);
		assert.equal(
			sonnenGrund(entries),
			sonnenGrund(LIVE.en.metrics),
			'Englischer Nutzer sieht die Begruendung nicht englisch'
		);
	});

	test('AC-2: Sprache Deutsch ⇒ Anfrage traegt lang=de, Eintraege wie bisher', async () => {
		const lader = await frischerLader();
		locale.set('de');
		const entries = await lader.loadCompareSelectionEntries();
		assert.deepEqual(langDerAbrufe(), ['de'], `Abruf ohne/mit falscher Sprache: ${abrufe.join(', ')}`);
		assert.deepEqual(entries, toCompareSelectionEntries(LIVE.de as never), 'Deutsche Eintraege veraendert');
	});

	test('AC-3: Sprachwechsel ohne Neuladen ⇒ neuer Abruf in der neuen Sprache, kein veralteter Zwischenspeicher', async () => {
		const lader = await frischerLader();
		locale.set('de');
		const vorher = (await lader.loadCompareSelectionEntries()) as unknown as Array<Record<string, unknown>>;
		assert.equal(sonnenGrund(vorher), sonnenGrund(LIVE.de.metrics));
		locale.set('en');
		const nachher = (await lader.loadCompareSelectionEntries()) as unknown as Array<Record<string, unknown>>;
		assert.deepEqual(langDerAbrufe(), ['de', 'en'], `Abrufe nach Sprachwechsel: ${abrufe.join(', ')}`);
		assert.equal(
			sonnenGrund(nachher),
			sonnenGrund(LIVE.en.metrics),
			'Nach dem Wechsel auf Englisch bleibt die deutsche Begruendung stehen'
		);
	});

	test('AC-4: gleiche Sprache ⇒ alle Ableitungen teilen EINEN Abruf (mit lang)', async () => {
		const lader = await frischerLader();
		locale.set('en');
		await Promise.all([
			lader.loadCompareMetricCatalog(),
			lader.loadRouteExtraMetricDefs(),
			lader.loadCompareSelectionEntries()
		]);
		await lader.loadCompareSelectionEntries();
		assert.deepEqual(langDerAbrufe(), ['en'], `Erwartet genau einen Abruf mit lang=en: ${abrufe.join(', ')}`);
	});

	test('AC-5: Fehler ⇒ „Wiederholen" laedt neu; der Katalog der anderen Sprache bleibt ohne neuen Abruf', async () => {
		const lader = await frischerLader();
		locale.set('de');
		await lader.loadCompareSelectionEntries();
		locale.set('en');
		fehlerFuer.add('en');
		await assert.rejects(lader.loadCompareSelectionEntries(), 'Der fehlgeschlagene englische Abruf muss als Fehler ankommen');
		const geheilt = (await lader.loadCompareSelectionEntries()) as unknown as Array<Record<string, unknown>>;
		assert.equal(sonnenGrund(geheilt), sonnenGrund(LIVE.en.metrics), 'Wiederholen liefert den englischen Katalog nicht');
		locale.set('de');
		const deWieder = await lader.loadCompareSelectionEntries();
		assert.deepEqual(deWieder, toCompareSelectionEntries(LIVE.de as never));
		assert.deepEqual(
			langDerAbrufe(),
			['de', 'en', 'en'],
			`Erwartet: de einmal, en Fehler + Wiederholung, de aus dem Zwischenspeicher: ${abrufe.join(', ')}`
		);
	});

	test('AC-6: Kennungen sind in beiden Sprachen gleich, nur die Begruendung unterscheidet sich (kein Schein-Diff)', async () => {
		const lader = await frischerLader();
		locale.set('en');
		const en = (await lader.loadCompareSelectionEntries()) as unknown as Array<Record<string, unknown>>;
		locale.set('de');
		const de = (await lader.loadCompareSelectionEntries()) as unknown as Array<Record<string, unknown>>;
		const kennung = (xs: Array<Record<string, unknown>>) =>
			xs.map((x) => ({ metric: x.metric, metric_id: x.metric_id, aggregation: x.aggregation, ordinalLabels: x.ordinalLabels }));
		assert.deepEqual(kennung(en), kennung(de), 'Kennungen unterscheiden sich je Sprache — Schein-Diff im Hub');
		assert.notEqual(sonnenGrund(en), sonnenGrund(de), 'Begruendung muss sich je Sprache unterscheiden');
		assert.deepEqual(langDerAbrufe(), ['en', 'de']);
	});
});
