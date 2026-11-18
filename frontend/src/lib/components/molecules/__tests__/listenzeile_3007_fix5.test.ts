// Fix-Runde 5 — Issue #3007 (Epic #2913), /60-validate Befunde V-1 (AC-17) und V-2 (AC-14).
// Spec: docs/specs/modules/feat_3007_etappen_orte_listen.md
// Befunde: docs/artifacts/3007-etappen-orte-listen/validate-befunde-runde1.md
//
// Gemessen wird am ECHTEN serverseitig gerenderten Markup (kein Mock). Zustände, die erst nach
// Laden/Klick entstehen, setzt der startzustandHook als STARTWERT eines `$state` der Produktivdatei.
//
//   V-1 (AC-17)  Etappen-Reiter im Hub, solange der Trip lädt (TripTabs ohne `trip`): genau ein
//                Listen-Container `data-abschnitt="liste"` (vorher 0). Orte-Gegenprobe: gefüllt,
//                leer, gesperrt je genau einer.
//   V-2 (AC-14)  Offene Kaskaden-Rückfrage (Datum einer Etappe mit Folge-Etappen geändert, Speichern
//                zurückgestellt) im Hub-Listenmodus: sichtbar, wenn KEINE Etappe aufgeklappt ist
//                (Nutzer hat zugeklappt) und wenn eine ANDERE Etappe aufgeklappt ist; ebenso der
//                Erfolgs-Streifen. Genau ein Banner gleichzeitig. Anlegen-Editor und Mobil-Zweig
//                unverändert genau ein Banner (AC-15).
//
//   cd frontend && npm test -- src/lib/components/molecules/__tests__/listenzeile_3007_fix5.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
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
const { locale } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/index.ts')).href);
const { baum, alle } = await import('../../shared/hub-kopf/__tests__/htmlBaum.ts');
type Knoten = import('../../shared/hub-kopf/__tests__/htmlBaum.ts').Knoten;

afterEach(() => locale.set('de'));

async function lade(file: string, start: [string, string][] = []): Promise<any> {
	const q = start.length ? `?start=${encodeURIComponent(JSON.stringify(start))}` : '';
	return (await import(pathToFileURL(file).href + q)).default;
}
const mitTestid = (b: Knoten, id: string) => alle(b, (n) => n.attrs['data-testid'] === id);
const listen = (b: Knoten) => alle(b, (n) => n.attrs['data-abschnitt'] === 'liste');

const ESP = path.join(KOMP, 'edit', 'EditStagesPanelNew.svelte');
const TRIP_HUB = path.join(KOMP, 'trip-detail', 'TripTabs.svelte');
const VERGLEICH_HUB = path.join(KOMP, 'compare', 'CompareTabs.svelte');

const wp = (id: string, name: string, lat: number, lon: number, elevation_m: number) => ({ id, name, lat, lon, elevation_m });
const ETAPPEN = [
	{ id: 's1', name: 'Tag 1', date: '2026-08-01', start_time: '08:00', waypoints: [wp('a', "Port d'Andratx", 39.54, 2.39, 10), wp('b', 'Sa Trapa', 39.58, 2.40, 380)] },
	{ id: 's2', name: 'Tag 2', date: '2026-08-02', start_time: '08:00', waypoints: [wp('c', 'Estellencs', 39.65, 2.48, 150), wp('d', 'Banyalbufar', 39.69, 2.51, 100)] },
	{ id: 's3', name: 'Tag 3', date: '2026-08-03', start_time: '07:30', waypoints: [wp('e', 'Valldemossa', 39.71, 2.62, 420), wp('f', 'Deià', 39.75, 2.65, 150)] }
];

// ═══ V-1 (AC-17): Etappen-Reiter im Ladezustand ═════════════════════════════════════════
describe('#3007 V-1: Etappen-Reiter im Hub trägt den Listen-Marker auch beim Laden (AC-17)', () => {
	const ETAPPEN_TAB: [string, string][] = [["let activeTab = $state<string>('uebersicht');", "let activeTab = $state<string>('etappen');"]];
	test('Trip lädt noch (kein trip): genau ein data-abschnitt="liste" im Etappen-Reiter', async () => {
		const T = await lade(TRIP_HUB, ETAPPEN_TAB);
		const b = baum(render(T, { props: { initialTab: 'etappen' } }).body);
		const [panel] = mitTestid(b, 'trip-detail-panel-etappen');
		assert.ok(panel, 'Messaufbau: Etappen-Reiter nicht gerendert');
		assert.equal(mitTestid(panel, 'etappen-laden-reiterflaeche').length, 1, 'Messaufbau: Ladezweig nicht getroffen');
		const l = listen(panel);
		assert.equal(l.length, 1, `Laden: ${l.length} Marker data-abschnitt="liste" statt genau einem`);
		assert.equal(mitTestid(l[0], 'etappen-liste-zeile').length, 0, 'Laden: Listen-Container zeigt Zeilen ohne Trip');
	});
	test('Trip geladen: weiterhin genau ein Marker (normal)', async () => {
		const T = await lade(TRIP_HUB, ETAPPEN_TAB);
		const b = baum(render(T, { props: { initialTab: 'etappen', trip: { id: 't1', name: 'Trip', stages: ETAPPEN } } }).body);
		const [panel] = mitTestid(b, 'trip-detail-panel-etappen');
		assert.equal(listen(panel).length, 1);
	});
	test('Trip geladen ohne Etappen (Lücke): genau ein Marker', async () => {
		const T = await lade(TRIP_HUB, ETAPPEN_TAB);
		const b = baum(render(T, { props: { initialTab: 'etappen', trip: { id: 't1', name: 'Trip', stages: [] } } }).body);
		const [panel] = mitTestid(b, 'trip-detail-panel-etappen');
		assert.equal(listen(panel).length, 1);
	});
	test('Orte-Gegenprobe: gefüllt, leer, gesperrt je genau ein Marker', async () => {
		const ENTSPERRT: [string, string][] = [
			['let versandHydrated = $state(false);', 'let versandHydrated = $state(true);'],
			['let alarmeHydrated = $state(false);', 'let alarmeHydrated = $state(true);'],
			['let wetterMetrikenHydrated = $state(false);', 'let wetterMetrikenHydrated = $state(true);'],
			['let layoutHydrated = $state(false);', 'let layoutHydrated = $state(true);']
		];
		const ORTE = [{ id: 'l1', name: 'Münster', group: 'Stadt', elevation_m: 60, lat: 51.96, lon: 7.63 }];
		for (const [orte, start, was] of [[ORTE, ENTSPERRT, 'gefüllt'], [[], ENTSPERRT, 'leer'], [ORTE, [], 'gesperrt']] as const) {
			const C = await lade(VERGLEICH_HUB, start as [string, string][]);
			const preset = { id: 'p1', name: 'Vergleich', location_ids: orte.map((o) => o.id), display_config: {} };
			const b = baum(render(C, { props: { initialTab: 'orte', preset, locations: orte } }).body);
			const [panel] = mitTestid(b, 'compare-detail-panel-orte');
			assert.ok(panel, `Messaufbau Orte ${was}`);
			assert.equal(listen(panel).length, 1, `Orte ${was}: Marker nicht genau einmal`);
		}
	});
});

// ═══ V-2 (AC-14): Kaskaden-Rückfrage bleibt im Listenmodus sichtbar ══════════════════════
/** Datum von Etappe 1 auf den 5.8. geändert, Folge-Etappen 2 und 3 betroffen → Rückfrage offen. */
const KASKADE_OFFEN: [string, string] = [
	'let cascade = $state<CascadeState | null>(null);',
	"let cascade = $state<CascadeState | null>({ stageId: 's1', done: false, baseFirstDate: '2026-08-01', anchorDate: '2026-08-05' });"
];
const KASKADE_ERLEDIGT: [string, string] = [
	'let cascade = $state<CascadeState | null>(null);',
	"let cascade = $state<CascadeState | null>({ stageId: 's1', done: true, baseFirstDate: '2026-08-01', anchorDate: '2026-08-05' });"
];
const OFFEN = (id: string): [string, string][] => [
	['let offeneEtappeId = $state<string | null>(null);', `let offeneEtappeId = $state<string | null>('${id}');`],
	["stages.find((s) => !isPauseStage(s))?.id ?? stages[0]?.id ?? ''", `'${id}'`]
];
const MOBIL: [string, string] = ['let isMobileViewport = $state(false);', 'let isMobileViewport = $state(true);'];

async function panel(start: [string, string][], props: Record<string, unknown> = { listeZuerst: true }): Promise<Knoten> {
	const P = await lade(ESP, start);
	return baum(render(P, { props: { stages: structuredClone(ETAPPEN), tripId: 't1', ...props } }).body);
}

describe('#3007 V-2: offene Kaskaden-Rückfrage im Hub-Listenmodus (AC-14, Fehlerklasse #1389/#1390)', () => {
	test('Rückfrage offen, Etappe zugeklappt (keine offen): Rückfrage sichtbar, genau einmal', async () => {
		const b = await panel([KASKADE_OFFEN]);
		assert.equal(mitTestid(b, 'etappen-aufklapp').length, 0, 'Messaufbau: eine Etappe ist aufgeklappt');
		assert.equal(mitTestid(b, 'cascade-strip').length, 1, 'zugeklappt: offene Rückfrage unsichtbar (Speichern bleibt zurückgestellt)');
	});
	test('Rückfrage offen, ANDERE Etappe aufgeklappt: Rückfrage sichtbar, genau einmal', async () => {
		const b = await panel([KASKADE_OFFEN, ...OFFEN('s3')]);
		assert.equal(mitTestid(b, 'etappen-aufklapp').length, 1, 'Messaufbau: Etappe 3 nicht aufgeklappt');
		assert.equal(mitTestid(b, 'cascade-strip').length, 1, 'andere Etappe offen: Rückfrage nicht genau einmal');
	});
	test('Rückfrage offen, auslösende Etappe aufgeklappt: genau ein Banner (nicht doppelt)', async () => {
		const b = await panel([KASKADE_OFFEN, ...OFFEN('s1')]);
		assert.equal(mitTestid(b, 'etappen-aufklapp').length, 1, 'Messaufbau: Etappe 1 nicht aufgeklappt');
		assert.equal(mitTestid(b, 'cascade-strip').length, 1, 'auslösende Etappe offen: Rückfrage nicht genau einmal');
	});
	test('Erfolgs-Streifen nach dem Durchdatieren bleibt zugeklappt sichtbar, genau einmal', async () => {
		const b = await panel([KASKADE_ERLEDIGT]);
		assert.equal(mitTestid(b, 'cascade-done').length, 1, 'zugeklappt: Erfolgs-Streifen unsichtbar');
		const b2 = await panel([KASKADE_ERLEDIGT, ...OFFEN('s2')]);
		assert.equal(mitTestid(b2, 'cascade-done').length, 1, 'andere Etappe offen: Erfolgs-Streifen nicht genau einmal');
	});
	test('Rückfrage steht im Reiter (Listen-Reiterfläche), über der Liste', async () => {
		const b = await panel([KASKADE_OFFEN]);
		const [flaeche] = mitTestid(b, 'etappen-liste-reiterflaeche');
		assert.ok(flaeche, 'Messaufbau: Listen-Reiterfläche fehlt');
		assert.equal(mitTestid(flaeche, 'cascade-strip').length, 1, 'Rückfrage nicht in der Listen-Reiterfläche');
		const [liste] = listen(flaeche);
		assert.equal(mitTestid(liste, 'cascade-strip').length, 0, 'Rückfrage zwischen den Listenzeilen statt über der Liste');
	});
	// Fix-Runde 6 (Adversary F001): der Pausentag-Zweig des aufgeklappten Editors trägt einen eigenen
	// Banner-Aufruf; im Listenmodus muss er schweigen, sonst steht die Rückfrage doppelt da.
	const MIT_PAUSE = () => {
		const s = structuredClone(ETAPPEN);
		s.splice(2, 0, { id: 'p1', name: 'Pausentag', date: '2026-08-03', waypoints: [] } as any);
		return s;
	};
	test('Rückfrage offen, Pausentag aufgeklappt: Rückfrage genau einmal (nicht doppelt)', async () => {
		const P = await lade(ESP, [KASKADE_OFFEN, ...OFFEN('p1')]);
		const b = baum(render(P, { props: { stages: MIT_PAUSE(), tripId: 't1', listeZuerst: true } }).body);
		assert.equal(mitTestid(b, 'etappen-aufklapp').length, 1, 'Messaufbau: Pausentag nicht aufgeklappt');
		assert.equal(mitTestid(b, 'cascade-strip').length, 1, 'Pausentag offen: Rückfrage nicht genau einmal');
	});
	test('Erfolgs-Streifen, Pausentag aufgeklappt: genau einmal (nicht doppelt)', async () => {
		const P = await lade(ESP, [KASKADE_ERLEDIGT, ...OFFEN('p1')]);
		const b = baum(render(P, { props: { stages: MIT_PAUSE(), tripId: 't1', listeZuerst: true } }).body);
		assert.equal(mitTestid(b, 'etappen-aufklapp').length, 1, 'Messaufbau: Pausentag nicht aufgeklappt');
		assert.equal(mitTestid(b, 'cascade-done').length, 1, 'Pausentag offen: Erfolgs-Streifen nicht genau einmal');
	});
	test('AC-15: Anlegen-Editor (ohne listeZuerst) unverändert — Rückfrage genau einmal im Editor', async () => {
		const b = await panel([KASKADE_OFFEN], {});
		const [editor] = mitTestid(b, 'etappen-reiterflaeche');
		assert.ok(editor, 'Messaufbau: Anlegen-Editor fehlt');
		assert.equal(mitTestid(b, 'cascade-strip').length, 1, 'Anlegen-Editor: Rückfrage nicht genau einmal');
		assert.equal(mitTestid(editor, 'cascade-strip').length, 1, 'Anlegen-Editor: Rückfrage nicht mehr im Editor');
	});
	test('AC-15: Mobil-Zweig mit listeZuerst unverändert — Rückfrage genau einmal in der Mobil-Liste', async () => {
		const b = await panel([KASKADE_OFFEN, MOBIL]);
		const [mobil] = mitTestid(b, 'mobile-stages-list');
		assert.ok(mobil, 'Messaufbau: Mobil-Liste fehlt');
		assert.equal(mitTestid(b, 'cascade-strip').length, 1, 'Mobil: Rückfrage nicht genau einmal');
		assert.equal(mitTestid(mobil, 'cascade-strip').length, 1, 'Mobil: Rückfrage nicht in der Mobil-Liste');
	});
});
