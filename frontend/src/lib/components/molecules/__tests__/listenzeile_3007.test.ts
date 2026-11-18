// TDD RED — Issue #3007 (Epic #2913): Listen der Reiter Etappen und Orte nach Mockup Fassung 3.
// Spec: docs/specs/modules/feat_3007_etappen_orte_listen.md — AC-1 bis AC-6, AC-8, AC-10 bis AC-13,
// AC-15 bis AC-18, AC-22 (SSR-Anteil). Soll: mockup-hub-fassung3.html viewEtappen Z. 577-587,
// viewOrte Z. 588-591, `.lrow` Z. 140-143.
//
// Geprüft wird dort, wo es WIRKT: der neue Baustein `molecules/Listenzeile.svelte` UND die ECHTEN
// Reiter (`compare/CompareTabs.svelte` Orte, `edit/EditStagesPanelNew.svelte` + `trip-detail/TripTabs.svelte`
// Etappen), serverseitig gerendert. Kein Mock; Zustände per startzustandHook (anderer $state-Startwert).
//
// ── VERTRAG für den Developer (von RED festgelegt) ──────────────────────────────────────
// `molecules/Listenzeile.svelte`, Props: titel: string, zweitzeile?: string, meta?: string, testid?: string,
//   onclick?: () => void (macht die Zeile klickbar), offen?: boolean (→ aria-expanded), griff?: Snippet
//   (Ziehgriff links), children?: Snippet (Aktion rechts). Export in molecules/index.ts.
//   Gerendert wird GENAU EIN Element [data-slot="einstellungszeile"] (die Einstellungszeile, kein zweites
//   .lrow), das zusätzlich das Attribut `data-listenzeile` trägt und die testid bekommt.
//   Titel = <b> in der Textspalte, Zweitzeile = <small data-slot="einstellungszeile-hinweis">,
//   Meta = Element [data-slot="listenzeile-meta"] im Bereich [data-slot="einstellungszeile-bedienung"] VOR
//   der Aktion. Ohne Zweitzeile/Meta: kein leeres <small> bzw. kein Meta-Element.
//   Klickbar (onclick gesetzt): role="button", tabindex="0", aria-expanded="true|false"; sonst keins davon.
// Orte (CompareTabs): Container [data-abschnitt="liste"] genau einmal je Zustand; je Ort eine Listenzeile
//   mit testid `hub-orte-row` (data-loc-id bleibt), Titel = Name, Zweitzeile „Gruppe · Höhe m“ ohne
//   verwaistes „·“; Aktion = Btn variant quiet size sm, testid `hub-orte-remove`, Text aus dem Katalog
//   (DE „entfernen“); Ziehgriff (`drag-handle`) im griff-Slot mit aria-label aus dem Katalog, ohne Text.
//   Kein Rang-Badge, kein .hub-section-hint, keine Wechselfarbe (.alt), kein ✕.
// Etappen (EditStagesPanelNew, neue Prop `listeZuerst`, TripTabs setzt sie): Desktop zeigt nur
//   [data-abschnitt="liste"] mit je Etappe einer klickbaren Listenzeile testid `etappen-liste-zeile`:
//   Titel „E{n} · <erster Wegpunkt> → <letzter Wegpunkt>“ (Pausentag: „E{n} · <Name>“), Zweitzeile
//   „x km · ↑y m“ (computeHeaderStats, Zahlen locale-formatiert wie TripHeader), Meta „Gehzeit h:mm“
//   (Katalog; Dauer aus computeArrivalTimes/activityToSpeed). Grundzustand: alle aria-expanded="false",
//   kein Etappen-Band, keine Reiterfläche, kein Karten-/Profil-Editor. Ohne `listeZuerst` und im
//   Mobil-Zweig unverändert. Kein „Tempo ändern“.
// ─────────────────────────────────────────────────────────────────────────────────────
//
//   cd frontend && npm test -- src/lib/components/molecules/__tests__/listenzeile_3007.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../../..');
const KOMP = path.resolve(HERE, '../..');
const reg = (p: string) => register(pathToFileURL(p).href, pathToFileURL(FRONTEND + '/').href);
reg(path.join(FRONTEND, 'src/routes/account/__tests__/app-navigation-stub-hooks.mjs'));
reg(path.join(KOMP, 'shared/__tests__/svelteTsModulHook.mjs'));
reg(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs'));
reg(path.join(KOMP, 'organisms/__tests__/startzustandHook.mjs'));

const { render } = await import('svelte/server');
const { createRawSnippet } = await import('svelte');
const { locale } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/index.ts')).href);
const { baum, alle, text: rohText } = await import('../../shared/hub-kopf/__tests__/htmlBaum.ts');
const { computeHeaderStats } = await import(pathToFileURL(path.join(KOMP, 'email-preview/headerStats.ts')).href);
const { computeArrivalTimes, activityToSpeed } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/utils/naismith.ts')).href);
type Knoten = import('../../shared/hub-kopf/__tests__/htmlBaum.ts').Knoten;

afterEach(() => locale.set('de'));

type Lang = 'de' | 'en';
const SPRACHEN: Lang[] = ['de', 'en'];

function katalog(lang: Lang): Record<string, string> {
	const dir = path.join(FRONTEND, 'src/lib/i18n/messages', lang);
	const out: Record<string, string> = {};
	for (const f of readdirSync(dir).filter((n) => n.endsWith('.json'))) Object.assign(out, JSON.parse(readFileSync(path.join(dir, f), 'utf8')));
	return out;
}
const DE = katalog('de');
const EN = katalog('en');
const enPassend = (deText: string, enIst: string) => Object.keys(DE).some((k) => DE[k] === deText && EN[k] === enIst);

const entity = (s: string) => s.replace(/&amp;/g, '&').replace(/&nbsp;/g, ' ').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'");
const text = (k: Knoten) => entity(rohText(k)).replace(/\s+/g, ' ').trim();
async function lade(file: string, start: [string, string][] = []): Promise<any> {
	const q = start.length ? `?start=${encodeURIComponent(JSON.stringify(start))}` : '';
	return (await import(pathToFileURL(file).href + q)).default;
}
function mitSprache<R>(lang: Lang, f: () => R): R {
	locale.set(lang);
	try {
		return f();
	} finally {
		locale.set('de');
	}
}
const mitTestid = (b: Knoten, id: string) => alle(b, (n) => n.attrs['data-testid'] === id);
const mitSlot = (b: Knoten, s: string) => alle(b, (n) => n.attrs['data-slot'] === s);
const listen = (b: Knoten) => alle(b, (n) => n.attrs['data-abschnitt'] === 'liste');
const istListenzeile = (n: Knoten) => n.attrs['data-slot'] === 'einstellungszeile' && 'data-listenzeile' in n.attrs;

function einzigeListe(b: Knoten, was: string): Knoten {
	const l = listen(b);
	assert.equal(l.length, 1, `${was}: ${l.length} Marker data-abschnitt="liste" statt genau einem`);
	return l[0];
}
/** Listenzeile zerlegen: Titel (<b>), Zweitzeile (<small>), Meta, Bedienbereich. */
function zeile(z: Knoten, was: string) {
	assert.ok(istListenzeile(z), `${was}: Element ist keine Listenzeile (data-slot="einstellungszeile" + data-listenzeile fehlen)`);
	const b = alle(z, (n) => n.tag === 'b');
	assert.equal(b.length, 1, `${was}: ${b.length} <b>-Titel statt einem`);
	const small = mitSlot(z, 'einstellungszeile-hinweis');
	const meta = mitSlot(z, 'listenzeile-meta');
	const [bed] = mitSlot(z, 'einstellungszeile-bedienung');
	return { titel: text(b[0]), titelKnoten: b[0], zweit: small.map(text), meta: meta.map(text), metaKnoten: meta, bed };
}

// ═══ AC-1 / AC-2: Baustein ═════════════════════════════════════════════════════════════
const LISTENZEILE = path.join(KOMP, 'molecules', 'Listenzeile.svelte');
async function listenzeile(): Promise<any> {
	assert.ok(existsSync(LISTENZEILE), 'TDD RED: molecules/Listenzeile.svelte fehlt');
	return lade(LISTENZEILE);
}
const aktion = () => createRawSnippet(() => ({ render: () => '<button type="button" data-testid="probe-aktion">los</button>' }));

describe('#3007 AC-1/AC-2: Baustein Listenzeile', () => {
	test('AC-1: Titel und Zweitzeile links, Meta vor Aktion rechts, auf der Einstellungszeile', async () => {
		const L = await listenzeile();
		const b = baum(render(L, { props: { titel: 'E1 · A → B', zweitzeile: '7,8 km · ↑520 m', meta: 'Gehzeit 3:10', testid: 'probe', children: aktion() } }).body);
		const ez = mitSlot(b, 'einstellungszeile');
		assert.equal(ez.length, 1, `genau eine Einstellungszeile erwartet, gefunden ${ez.length}`);
		const z = zeile(ez[0], 'Listenzeile');
		assert.equal(ez[0].attrs['data-testid'], 'probe', 'testid nicht an der Zeile');
		assert.equal(z.titel, 'E1 · A → B');
		assert.deepEqual(z.zweit, ['7,8 km · ↑520 m']);
		assert.deepEqual(z.meta, ['Gehzeit 3:10']);
		assert.ok(z.titelKnoten.nr < mitSlot(ez[0], 'einstellungszeile-hinweis')[0].nr, 'Zweitzeile steht vor dem Titel');
		const [knopf] = mitTestid(ez[0], 'probe-aktion');
		assert.ok(z.bed && knopf, 'Bedienbereich oder Aktion fehlt');
		assert.ok(z.metaKnoten[0].eltern && alle(z.bed, (n) => n === z.metaKnoten[0]).length === 1, 'Meta steht nicht im rechten Bedienbereich');
		assert.ok(z.metaKnoten[0].nr < knopf.nr, 'Meta steht nicht vor der Aktion');
	});
	test('AC-1: ohne Zweitzeile und Meta kein leerer Platzhalter', async () => {
		const L = await listenzeile();
		const b = baum(render(L, { props: { titel: 'Nur Titel' } }).body);
		const [ez] = mitSlot(b, 'einstellungszeile');
		assert.ok(ez, 'Einstellungszeile fehlt');
		const z = zeile(ez, 'Listenzeile ohne Zusatz');
		assert.deepEqual(z.zweit, [], 'leere Zweitzeile gerendert');
		assert.deepEqual(z.meta, [], 'leeres Meta gerendert');
	});
	test('AC-2: klickbar → role=button, tabindex=0, aria-expanded folgt `offen`; sonst nichts davon', async () => {
		const L = await listenzeile();
		for (const offen of [false, true]) {
			const [ez] = mitSlot(baum(render(L, { props: { titel: 'K', onclick: () => {}, offen } }).body), 'einstellungszeile');
			assert.ok(ez, 'Einstellungszeile fehlt');
			assert.equal(ez.attrs.role, 'button', 'klickbare Zeile ohne role="button"');
			assert.equal(ez.attrs.tabindex, '0', 'klickbare Zeile nicht fokussierbar');
			assert.equal(ez.attrs['aria-expanded'], String(offen), 'aria-expanded folgt nicht `offen`');
		}
		const [still] = mitSlot(baum(render(L, { props: { titel: 'S' } }).body), 'einstellungszeile');
		for (const a of ['role', 'tabindex', 'aria-expanded']) assert.ok(!(a in still.attrs), `nicht klickbare Zeile trägt ${a}`);
	});
	test('AC-2: Einstellungszeile ohne Option unverändert (kein role/tabindex/aria-expanded, kein data-listenzeile)', async () => {
		const E = await lade(path.join(KOMP, 'molecules', 'Einstellungszeile.svelte'));
		const [ez] = mitSlot(baum(render(E, { props: { titel: 'T', hinweis: 'H' } }).body), 'einstellungszeile');
		for (const a of ['role', 'tabindex', 'aria-expanded', 'data-listenzeile']) assert.ok(!(a in ez.attrs), `Einstellungszeile trägt ungefragt ${a}`);
	});
	test('Baustein ist aus molecules/index.ts exportiert', () => {
		const idx = readFileSync(path.join(KOMP, 'molecules', 'index.ts'), 'utf8'); // doc-compliance-test
		assert.match(idx, /Listenzeile\b[\s\S]*?from\s+['"]\.\/Listenzeile\.svelte['"]/, 'Export Listenzeile fehlt');
	});
});

// ═══ Orte (Teilschritt 1) ═══════════════════════════════════════════════════════════════
const VERGLEICH_HUB = path.join(KOMP, 'compare', 'CompareTabs.svelte');
const ENTSPERRT: [string, string][] = [
	['let versandHydrated = $state(false);', 'let versandHydrated = $state(true);'],
	['let alarmeHydrated = $state(false);', 'let alarmeHydrated = $state(true);'],
	['let wetterMetrikenHydrated = $state(false);', 'let wetterMetrikenHydrated = $state(true);'],
	['let layoutHydrated = $state(false);', 'let layoutHydrated = $state(true);']
];
const ORTE = [
	{ id: 'l1', name: 'Münster', group: 'Stadt', elevation_m: 60, lat: 51.96, lon: 7.63 },
	{ id: 'l2', name: 'Telgte', group: 'Ems', elevation_m: 52, lat: 51.98, lon: 7.78 },
	{ id: 'l3', name: 'Nur Gruppe', group: 'Teutoburger Wald', lat: 52.2, lon: 7.8 },
	{ id: 'l4', name: 'Nur Höhe', elevation_m: 235, lat: 52.21, lon: 7.81 },
	{ id: 'l5', name: 'Ohne beides', lat: 52.22, lon: 7.82 }
];
const ZWEIT_SOLL: Record<string, string[]> = { l1: ['Stadt · 60 m'], l2: ['Ems · 52 m'], l3: ['Teutoburger Wald'], l4: ['235 m'], l5: [] };
async function orteReiter(lang: Lang, orte = ORTE, entsperrt = true): Promise<Knoten> {
	const C = await lade(VERGLEICH_HUB, entsperrt ? ENTSPERRT : []);
	const preset = { id: 'p1', name: 'Vergleich', location_ids: orte.map((o) => o.id), display_config: {} };
	const b = mitSprache(lang, () => baum(render(C, { props: { initialTab: 'orte', preset, locations: orte } }).body));
	const [panel] = mitTestid(b, 'compare-detail-panel-orte');
	assert.ok(panel, 'Messaufbau: Orte-Reiter nicht gerendert');
	return panel;
}

describe('#3007 Orte: Liste nach Mockup (AC-3 bis AC-6, AC-8, AC-17, AC-18, AC-22)', () => {
	for (const lang of SPRACHEN) {
		test(`AC-4/AC-5 (${lang}): Name als Titel, „Gruppe · Höhe m“ ohne verwaistes „·“`, async () => {
			const panel = await orteReiter(lang);
			const liste = einzigeListe(panel, `Orte ${lang}`);
			const zeilen = mitTestid(liste, 'hub-orte-row');
			assert.equal(zeilen.length, ORTE.length, `Orte ${lang}: ${zeilen.length} Zeilen statt ${ORTE.length}`);
			zeilen.forEach((zk, i) => {
				const o = ORTE[i];
				assert.equal(zk.attrs['data-loc-id'], o.id, `Zeile ${i + 1}: Reihenfolge/data-loc-id`);
				const z = zeile(zk, `Ort ${o.name}`);
				assert.equal(z.titel, o.name, `Ort ${o.id}: Titel`);
				assert.deepEqual(z.zweit, ZWEIT_SOLL[o.id], `Ort ${o.id}: Zweitzeile`);
			});
		});
		test(`AC-6 (${lang}): Textknopf „entfernen“ (quiet, sm), kein ✕, kein Rang, kein Hinweis, keine Wechselfarbe`, async () => {
			const panel = await orteReiter(lang);
			const liste = einzigeListe(panel, `Orte ${lang}`);
			const zeilen = mitTestid(liste, 'hub-orte-row');
			assert.equal(zeilen.length, ORTE.length, 'Messaufbau: Zeilenzahl');
			for (const zk of zeilen) {
				const knopf = mitTestid(zk, 'hub-orte-remove');
				assert.equal(knopf.length, 1, 'hub-orte-remove fehlt oder doppelt');
				const k = knopf[0];
				assert.equal(k.tag, 'button');
				assert.equal(k.attrs['data-variant'], 'quiet', 'entfernen ist kein ruhiger Knopf (Btn quiet)');
				assert.equal(k.attrs['data-size'], 'sm', 'entfernen ist kein kleiner Knopf (Btn sm)');
				const t = text(k);
				if (lang === 'de') assert.equal(t, 'entfernen');
				else assert.ok(t !== 'entfernen' && enPassend('entfernen', t), `EN-Knopf „${t}“ nicht aus dem Katalog`);
				assert.ok(!('alt' in zk.attrs) && !/\balt\b/.test(zk.attrs.class ?? ''), 'Wechselfarbe (.alt) noch gesetzt');
				const zText = text(zk);
				assert.ok(!/(^|\s)\d{2}(\s|$)/.test(zText.replace(/\d+ m\b/g, '')), `Rang-Badge noch sichtbar: „${zText}“`);
			}
			assert.ok(!text(panel).includes('✕'), '✕ steht noch im Reiter');
			assert.equal(alle(panel, (n) => /\bhub-section-hint\b/.test(n.attrs.class ?? '')).length, 0, 'Reihenfolge-Hinweis noch da');
			for (const k of ['vergleich.hub.reihenfolge_hinweis', 'vergleich.hub.ziehen_sortieren']) {
				const v = (lang === 'de' ? DE : EN)[k];
				if (v) assert.ok(!text(panel).includes(v), `Hinweis „${v}“ noch sichtbar`);
			}
		});
		test(`AC-8 (${lang}): Ziehgriff je Zeile textlos mit aria-label aus dem Katalog`, async () => {
			const panel = await orteReiter(lang);
			const zeilen = mitTestid(einzigeListe(panel, `Orte ${lang}`), 'hub-orte-row');
			assert.equal(zeilen.length, ORTE.length, 'Messaufbau: Zeilenzahl');
			const kat = lang === 'de' ? DE : EN;
			for (const zk of zeilen) {
				const g = mitTestid(zk, 'drag-handle');
				assert.equal(g.length, 1, 'Ziehgriff fehlt in der Listenzeile');
				assert.equal(text(g[0]), '', 'Ziehgriff hat sichtbaren Text');
				const label = g[0].attrs['aria-label'] ?? '';
				assert.ok(Object.values(kat).includes(label), `aria-label „${label}“ stammt nicht aus dem ${lang}-Katalog`);
			}
		});
	}
	test('AC-17: Orte-Liste trägt den Marker in jedem Zustand genau einmal (gefüllt, leer, gesperrt)', async () => {
		einzigeListe(await orteReiter('de'), 'Orte gefüllt');
		einzigeListe(await orteReiter('de', []), 'Orte leer');
		einzigeListe(await orteReiter('de', ORTE, false), 'Orte Hydrations-Sperre');
	});
	test('AC-3: CompareLocationRow ist entfernt oder ungenutzt', () => {
		const src = readFileSync(VERGLEICH_HUB, 'utf8'); // doc-compliance-test
		assert.ok(!/CompareLocationRow/.test(src), 'CompareTabs nutzt noch CompareLocationRow');
	});
});

// ═══ Etappen (Teilschritt 2) ════════════════════════════════════════════════════════════
const ESP = path.join(KOMP, 'edit', 'EditStagesPanelNew.svelte');
const TRIP_HUB = path.join(KOMP, 'trip-detail', 'TripTabs.svelte');
const wp = (id: string, name: string, lat: number, lon: number, elevation_m: number) => ({ id, name, lat, lon, elevation_m });
const ETAPPEN = [
	{ id: 's1', name: 'Tag 1', date: '2026-08-01', start_time: '08:00', waypoints: [wp('a', "Port d'Andratx", 39.54, 2.39, 10), wp('b', 'Sa Trapa', 39.58, 2.40, 380), wp('c', 'Estellencs', 39.65, 2.48, 150)] },
	{ id: 's2', name: 'Pausentag', date: '2026-08-02', waypoints: [] },
	{ id: 's3', name: 'Tag 3', date: '2026-08-03', start_time: '07:30', waypoints: [wp('d', 'Estellencs', 39.65, 2.48, 150), wp('e', 'Esporles', 39.67, 2.58, 200)] }
];
const MOBIL_START: [string, string][] = [['let isMobileViewport = $state(false);', 'let isMobileViewport = $state(true);']];

function zahl(lang: Lang, v: number, nachkomma: number): string {
	return new Intl.NumberFormat(lang === 'en' ? 'en-GB' : 'de-DE', { minimumFractionDigits: nachkomma, maximumFractionDigits: nachkomma }).format(v);
}
/** Unabhängig berechnete Gehzeit h:mm: letzte minus erste Ankunft der vorhandenen Rechnung. */
function gehzeit(stage: any): string {
	const arr: string[] = computeArrivalTimes(stage, stage.start_time, activityToSpeed(undefined));
	const min = (s: string) => Number(s.slice(0, 2)) * 60 + Number(s.slice(3));
	let d = min(arr[arr.length - 1]) - min(arr[0]);
	if (d < 0) d += 24 * 60;
	return `${Math.floor(d / 60)}:${String(d % 60).padStart(2, '0')}`;
}
/** Meta-Soll aus dem Katalog: Schlüssel mit DE-Wert „Gehzeit {…}“. */
function gehzeitText(lang: Lang, dauer: string): string {
	const keys = Object.keys(DE).filter((k) => /^Gehzeit \{\w+\}$/.test(DE[k]));
	assert.equal(keys.length, 1, `Katalog: ${keys.length} Schlüssel mit DE-Wert „Gehzeit {…}“ statt genau einem`);
	const v = (lang === 'de' ? DE : EN)[keys[0]];
	assert.ok(v && /\{\w+\}/.test(v), `Katalog ${lang}: Gehzeit-Schlüssel ${keys[0]} ohne Platzhalter`);
	return v.replace(/\{\w+\}/, dauer);
}
async function etappenListe(lang: Lang, props: Record<string, unknown> = {}, start: [string, string][] = []): Promise<Knoten> {
	const P = await lade(ESP, start);
	return mitSprache(lang, () => baum(render(P, { props: { stages: ETAPPEN, tripId: 't1', listeZuerst: true, ...props } }).body));
}

describe('#3007 Etappen: Liste im Hub (AC-10 bis AC-13, AC-15 bis AC-18)', () => {
	for (const lang of SPRACHEN) {
		test(`AC-10/AC-11/AC-12 (${lang}): „E{n} · Start → Ziel“, Kennzahlen, Gehzeit; Pausentag ohne Zahlen`, async () => {
			const b = await etappenListe(lang);
			const zeilen = mitTestid(einzigeListe(b, `Etappen ${lang}`), 'etappen-liste-zeile');
			assert.equal(zeilen.length, ETAPPEN.length, `Etappen ${lang}: ${zeilen.length} Zeilen statt ${ETAPPEN.length}`);
			const [z1, z2, z3] = zeilen.map((zk, i) => zeile(zk, `Etappe ${i + 1}`));
			assert.equal(z1.titel, "E1 · Port d'Andratx → Estellencs");
			assert.equal(z3.titel, 'E3 · Estellencs → Esporles');
			for (const [z, s] of [[z1, ETAPPEN[0]], [z3, ETAPPEN[2]]] as const) {
				const st = computeHeaderStats(s);
				assert.deepEqual(z.zweit, [`${zahl(lang, st.distanceKm, 1)} km · ↑${zahl(lang, Math.round(st.ascentM), 0)} m`], `${s.id}: Kennzahlen`);
				assert.deepEqual(z.meta, [gehzeitText(lang, gehzeit(s))], `${s.id}: Gehzeit`);
			}
			assert.equal(z2.titel, 'E2 · Pausentag', 'Pausentag: Titel');
			assert.deepEqual(z2.zweit, [], 'Pausentag zeigt Kennzahlen');
			assert.deepEqual(z2.meta, [], 'Pausentag zeigt Gehzeit');
			if (lang === 'en') assert.ok(!z1.meta[0].startsWith('Gehzeit'), 'EN zeigt deutsches „Gehzeit“');
		});
		test(`AC-13/AC-16 (${lang}): Grundzustand nur Liste — zu, kein Band, keine Fläche, kein Tempo-Knopf`, async () => {
			const b = await etappenListe(lang);
			const zeilen = mitTestid(einzigeListe(b, `Etappen ${lang}`), 'etappen-liste-zeile');
			assert.equal(zeilen.length, ETAPPEN.length, 'Messaufbau: Zeilenzahl');
			for (const zk of zeilen) {
				assert.equal(zk.attrs.role, 'button', 'Etappenzeile nicht klickbar');
				assert.equal(zk.attrs.tabindex, '0', 'Etappenzeile nicht fokussierbar');
				assert.equal(zk.attrs['aria-expanded'], 'false', 'Etappenzeile im Grundzustand offen');
			}
			for (const id of ['etappen-strip-wrapper', 'etappen-reiterflaeche']) assert.equal(mitTestid(b, id).length, 0, `${id} im Grundzustand sichtbar`);
			const t = text(b);
			assert.ok(!t.includes('Tempo ändern') && !/change pace/i.test(t), '„Tempo ändern“ steht im Reiter');
		});
	}
	test('AC-15: ohne listeZuerst (Anlegen-Editor) unverändert — Band da, keine Liste', async () => {
		const P = await lade(ESP);
		const b = baum(render(P, { props: { stages: ETAPPEN, tripId: 't1' } }).body);
		assert.equal(mitTestid(b, 'etappen-strip-wrapper').length, 1, 'Anlegen-Editor: Etappen-Band fehlt');
		assert.equal(listen(b).length, 0, 'Anlegen-Editor zeigt die Hub-Liste');
		assert.equal(mitTestid(b, 'etappen-liste-zeile').length, 0, 'Anlegen-Editor zeigt Listenzeilen');
	});
	test('AC-15: Mobil-Zweig mit listeZuerst unverändert (mobile-stages-list, stage-cardm-row)', async () => {
		const b = await etappenListe('de', {}, MOBIL_START);
		assert.equal(mitTestid(b, 'mobile-stages-list').length, 1, 'Mobil: mobile-stages-list fehlt');
		assert.equal(mitTestid(b, 'etappen-liste-zeile').length, 0, 'Mobil: Hub-Listenzeilen statt Mobil-Karten');
	});
	test('AC-3/AC-17: TripTabs schaltet den Hub-Modus ein — Liste genau einmal, gleicher Baustein wie Orte', async () => {
		const T = await lade(TRIP_HUB, [["let activeTab = $state<string>('uebersicht');", "let activeTab = $state<string>('etappen');"]]);
		const trip = { id: 't1', name: 'Trip', stages: ETAPPEN };
		const b = baum(render(T, { props: { initialTab: 'etappen', trip } }).body);
		const [panel] = mitTestid(b, 'trip-detail-panel-etappen');
		assert.ok(panel, 'Messaufbau: Etappen-Reiter nicht gerendert');
		const zeilen = mitTestid(einzigeListe(panel, 'TripTabs Etappen'), 'etappen-liste-zeile');
		assert.equal(zeilen.length, ETAPPEN.length, 'TripTabs: Hub-Liste nicht eingeschaltet');
		assert.ok(zeilen.every(istListenzeile), 'Etappenzeilen nutzen nicht den Baustein Listenzeile');
		assert.equal(mitTestid(panel, 'etappen-strip-wrapper').length, 0, 'TripTabs: Etappen-Band im Grundzustand');
		const orte = mitTestid(await orteReiter('de'), 'hub-orte-row');
		assert.ok(orte.length > 0 && orte.every(istListenzeile), 'Ortszeilen nutzen nicht den Baustein Listenzeile');
	});
});
