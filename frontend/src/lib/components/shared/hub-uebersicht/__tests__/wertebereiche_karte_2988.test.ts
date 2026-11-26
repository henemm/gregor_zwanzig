// #2988 S4 (AC-17): die Karte „Wetter" der Vergleichs-Übersicht zählt nach dem Umbau dieselben Metriken
// wie vorher und fragt dafür die Auflösung (POST /api/ampel/aufloesung) nie an.
// Spec: docs/specs/modules/rework_2988_ampel_ableitung.md (AC-17, „S4 – Übersichten":
// `wertebereicheKarte` liest `auswahlLesen` direkt, bei geladenem Katalog greift die Ampel dort nie).
//
// Referenz: tests/fixtures/wertebereiche_karte_referenz_2988.json, einmalig mit dem Code VOR S4 erzeugt
// (Vorlagen aus /api/templates, Katalog über den echten Lader aus /api/compare/metrics, Sprache de).
// Wächter: gegen den Code vor S4 grün, nach S4 muss er grün bleiben.
// Netz: der echte Baustein HubUebersicht (Instanz-Skript über den Prüfstand, echte Lader unter der
// Svelte-Client-Laufzeit, Fetch-Ersatz am Ausgang zählt jeden Abruf; Aufbau wie
// hub_uebersicht_verdrahtung_laufzeit.test.ts).
//
//   cd frontend && npm test -- src/lib/components/shared/hub-uebersicht/__tests__/wertebereiche_karte_2988.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { umgebungFuer, ohneTypen, werte, type Knoten } from '../../__tests__/svelteInstanzPruefstand.ts';
import { fixture, live, liveVergleichsKatalog, vergleichsKatalogFetch } from '../../wetter-tab/__tests__/wetterTabDaten.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '..', '..', '..', '..', '..', '..');
const SHARED = resolve(HIER, '..', '..');
const HU = join(HIER, '..', 'HubUebersicht.svelte');
const basis = pathToFileURL(FRONTEND + '/').href;
register(pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href, basis);
register(pathToFileURL(join(FRONTEND, 'test-app-environment-stub-hooks.mjs')).href, basis);
register(pathToFileURL(join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, basis);
register(pathToFileURL(join(SHARED, 'versand-tab', '__tests__', 'clientRunenHook.mjs')).href, pathToFileURL(HIER + '/').href);

type Json = any; // eslint-disable-line @typescript-eslint/no-explicit-any
const CLIENT_LAUFZEIT: string = 'svelte/internal/client';
const $: Json = await import(CLIENT_LAUFZEIT);
const m: Json = await import(pathToFileURL(join(HIER, '..', 'hubUebersichtModell.ts')).href);
const am: Json = await import(pathToFileURL(join(SHARED, 'wetter-tab', 'ampelModell.ts')).href);
const lader: Json = await import(pathToFileURL(join(SHARED, 'wetter-tab', 'compareMetricCatalogLoader.ts')).href);
const { erstelleBriefingHistoryLader }: Json = await import(pathToFileURL(join(SHARED, 'briefingHistoryLader.svelte.ts')).href);
const { erstelleNaechstesBriefingLader }: Json = await import(pathToFileURL(join(SHARED, 'versand-tab', 'naechstesBriefingLader.svelte.ts')).href);
const { locale }: Json = await import(pathToFileURL(join(FRONTEND, 'src', 'lib', 'i18n', 'index.ts')).href);
locale.set('de');

const REF: Json = fixture('wertebereiche_karte_referenz_2988.json');
const VORLAGEN: Json = am.vorlagenAusTemplates(live().templates);
const ALT: Json = await (async () => {
	const zurueck = vergleichsKatalogFetch();
	try {
		return am.altSchluesselAusKatalog(await lader.loadCompareSelectionEntries());
	} finally {
		zurueck();
	}
})();

const GERUEST = { id: 'cp-2988-s4', name: 'Karte', location_ids: [], schedule: 'daily', empfaenger: [] };
const karte = (teil: Json, vorlagen: Json = VORLAGEN, alt: Json = ALT): Json =>
	m.deriveVergleichKennzahlen({ ...GERUEST, ...teil }, 'active', null, [], vorlagen, alt).wertebereicheKarte;

describe('AC-17 (#2988 S4): Karte „Wetter" zählt wie vor dem Umbau', () => {
	test('messaufbau_referenz_und_katalog', () => {
		assert.ok(REF.faelle.length >= 10, 'Referenz verloren');
		assert.ok(Object.keys(ALT).length > 0, 'Messaufbau: Vergleichs-Katalog leer');
		assert.ok(new Set(REF.faelle.map((f: Json) => f.kurz)).size >= 5, 'Referenz unterscheidet die Fälle nicht');
	});
	for (const f of REF.faelle as Json[]) {
		test(`zahl_gleich_referenz_${f.name}`, () => {
			const k = karte(f.preset);
			assert.equal(k.beschreibungKurz, f.kurz);
			assert.equal(k.beschreibungLang, f.lang);
		});
	}

	test('ampel_greift_bei_geladenem_katalog_nie', () => {
		// Jede Vorlage, eine ungültige und keine Ampel: die Zahl hängt allein an der Auswahl.
		const ids = am.vergleichsKatalogIds(ALT).slice(0, 4);
		const ampeln: Json[] = [null, ...Object.keys(VORLAGEN).map((template) => ({ template })), { template: 'wandern', metrics: { gust: { enabled: 'ja' } } }];
		for (const teil of [{ active_metrics: ids }, {}]) {
			const zahlen = new Set(ampeln.map((ampel) => karte({ display_config: { ...teil, ampel } }).beschreibungKurz));
			assert.equal(zahlen.size, 1, `${JSON.stringify(teil)}: ${JSON.stringify([...zahlen])}`);
		}
	});

	test('strich_bis_katalog_und_vorlagen_geladen', () => {
		const teil = REF.faelle[0].preset;
		for (const [vorlagen, alt] of [[VORLAGEN, null], [VORLAGEN, {}], [null, ALT], [{}, ALT], [null, null]] as Json[]) {
			const k = karte(teil, vorlagen, alt);
			assert.equal(k.beschreibungKurz, '—', `Vorlagen ${vorlagen && Object.keys(vorlagen).length}, Katalog ${alt && Object.keys(alt).length}`);
			assert.equal(k.beschreibungLang, '—');
		}
	});
});

// ── Netz: der echte Baustein HubUebersicht im Ortsvergleich ──────────────────

const echtesFetch = globalThis.fetch;
const wurzeln: Array<() => void> = [];
afterEach(() => {
	globalThis.fetch = echtesFetch;
	while (wurzeln.length) wurzeln.pop()?.();
});

function netz() {
	const aufrufe: string[] = [];
	const antwort = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
	globalThis.fetch = (async (eingabe: unknown, opt?: RequestInit) => {
		const url = String(eingabe);
		aufrufe.push(`${opt?.method ?? 'GET'} ${url}`);
		if (url === '/api/templates') return antwort(200, live().templates);
		if (url.startsWith('/api/compare/metrics')) return antwort(200, liveVergleichsKatalog());
		if (url.includes('/briefing-history')) return antwort(200, []);
		if (url.startsWith('/api/next-briefings')) return antwort(200, { trips: {}, compare: {} });
		return antwort(404, { error: 'not found' });
	}) as typeof fetch;
	return aufrufe;
}

async function setzen() {
	$.flush();
	for (let i = 0; i < 10; i++) await new Promise((r) => setTimeout(r, 0));
	$.flush();
}

function inWurzel(echt: (...a: Json[]) => Json) {
	return (...args: Json[]) => {
		let l: Json;
		wurzeln.push($.effect_root(() => {
			l = echt(...args);
		}));
		return l;
	};
}

function neuAuswerten(ast: Knoten, quelle: string, u: Knoten, name: string): unknown {
	for (const stmt of (ast.instance?.content?.body as Knoten[]) ?? []) {
		if (stmt.type !== 'VariableDeclaration') continue;
		for (const d of stmt.declarations as Knoten[]) {
			if (d.id?.type === 'Identifier' && d.id.name === name && d.init) return (u[name] = werte(ohneTypen(quelle, d.init), u));
		}
	}
	throw new Error(`Deklaration „${name}" nicht gefunden`);
}

async function vergleichsUebersicht(preset: Json) {
	const hu = await umgebungFuer(
		HU,
		{
			context: 'vergleich', trip: undefined, preset, status: undefined, orte: [], saveController: undefined, onJump: undefined, children: undefined,
			erstelleBriefingHistoryLader: inWurzel(erstelleBriefingHistoryLader),
			erstelleNaechstesBriefingLader: inWurzel(erstelleNaechstesBriefingLader)
		},
		{ jsAlsTs: true }
	);
	assert.ok(hu.u.modell != null, 'Messaufbau: Herleitung „modell" fehlt');
	const rueckrufe: Array<() => unknown> = [];
	hu.u.onMount = (fn: () => unknown) => rueckrufe.push(fn);
	hu.u.window = { matchMedia: () => ({ matches: false, addEventListener() {}, removeEventListener() {} }) };
	for (const stmt of (hu.ast.instance?.content?.body as Knoten[]) ?? []) {
		const c = stmt.type === 'ExpressionStatement' ? (stmt.expression as Knoten) : null;
		if (c?.type === 'CallExpression' && c.callee?.type === 'Identifier' && c.callee.name === 'onMount') werte(ohneTypen(hu.quelle, c), hu.u);
	}
	return {
		mounten: async () => {
			for (const fn of rueckrufe) fn();
			await setzen();
		},
		karte: (): Json => (neuAuswerten(hu.ast, hu.quelle, hu.u, 'modell') as Json).wertebereicheKarte
	};
}

describe('AC-17 (#2988 S4): die Vergleichs-Übersicht fragt die Auflösung nie an', () => {
	for (const f of (REF.faelle as Json[]).filter((x) => ['drei_metriken', 'nie_eingestellt', 'liste_mit_ampel_abweichungen'].includes(x.name))) {
		test(`kein_aufloesungs_aufruf_${f.name}`, async () => {
			const aufrufe = netz();
			const hu = await vergleichsUebersicht({ ...GERUEST, ...f.preset, profil: 'wandern' });
			assert.equal(hu.karte().beschreibungKurz, '—', 'Messaufbau: vor dem Mount ist nichts geladen');
			await hu.mounten();
			assert.ok(aufrufe.includes('GET /api/templates'), `Messaufbau: Abrufe ${JSON.stringify(aufrufe)}`);
			assert.deepEqual(aufrufe.filter((a) => a.includes('/api/ampel/aufloesung')), [], `Abrufe: ${JSON.stringify(aufrufe)}`);
			assert.deepEqual(aufrufe.filter((a) => !a.startsWith('GET ')), [], `kein Schreib- oder POST-Aufruf: ${JSON.stringify(aufrufe)}`);
			assert.equal(hu.karte().beschreibungKurz, f.kurz);
		});
	}
});
