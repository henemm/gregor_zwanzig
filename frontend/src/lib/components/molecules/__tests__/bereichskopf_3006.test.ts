// TDD RED — Issue #3006 (Epic #2913): Bereichsköpfe je Reiter der Einstellungen (Trip + Orts-Vergleich).
// Spec: docs/specs/modules/feat_3006_bereichskoepfe.md — AC-1 bis AC-9, AC-11 bis AC-18.
// Soll: docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html Z. 69–71 (.sectionh), 442, 556, 579, 590, 594.
//
// Geprüft wird dort, wo es WIRKT: der neue Baustein `molecules/Bereichskopf.svelte` UND die ECHTEN Hubs
// `trip-detail/TripTabs.svelte` und `compare/CompareTabs.svelte`, serverseitig gerendert (svelte/server).
// Reiter und Lade-/Sperr-Zustände, die erst nach onMount/$effect entstehen, setzt startzustandHook.mjs
// über einen anderen `$state`-Startwert — das Markup bleibt das der Produktivdatei. Die Optik (AC-2)
// rechnet cssKaskade.ts aus app.css + kompiliertem Komponenten-CSS nach (Tokens aufgelöst). Kein Mock.
//
// ── VERTRAG für den Developer (von RED festgelegt) ──────────────────────────────────────
// Baustein `molecules/Bereichskopf.svelte`, Props: titel: string, erklaerung: string, testid: string
//   (Präfix), aktion?: Snippet. Root trägt data-abschnitt="abschnittskopf"; direkte Kinder in dieser
//   Reihenfolge: <h2 data-testid="<präfix>-titel">, <p data-testid="<präfix>-erklaer">, optional ein
//   Aktions-Wrapper (nur mit Snippet). Export in molecules/index.ts.
// Kopftexte kommen aus dem Katalog (Schlüsselnamen frei, DE+EN je Schlüssel); geprüft wird über die Werte.
// Testid-Präfixe: `wetter-tab`, `zustellung` (bestehend); Etappen/Orte/Übersicht frei.
// Orte: Knopf `hub-orte-add` im Kopf (Btn, Handler toggleAddPanel), keine SectionH „Verglichene Orte“,
//   kein zweiter `hub-orte-add` in der Card.
// Jeder Reiter: genau EIN Marker `abschnittskopf`, in jedem Zustand (Laden, Fehler, Hydrations-Sperre).
// ─────────────────────────────────────────────────────────────────────────────────────
//
//   cd frontend && npm test -- src/lib/components/molecules/__tests__/bereichskopf_3006.test.ts

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
const { ladeQuellen, stil, herkunft, token, px, DESKTOP, HANDY } = await import('../../shared/hub-kopf/__tests__/cssKaskade.ts');
type Knoten = import('../../shared/hub-kopf/__tests__/htmlBaum.ts').Knoten;
type Kontext = import('../../shared/hub-kopf/__tests__/cssKaskade.ts').Kontext;

afterEach(() => locale.set('de'));

type Lang = 'de' | 'en';
const SPRACHEN: Lang[] = ['de', 'en'];

// ── Katalog (alle Dateien einer Sprache) ─────────────────────────────────────────────
function katalog(lang: Lang): Record<string, string> {
	const dir = path.join(FRONTEND, 'src/lib/i18n/messages', lang);
	const out: Record<string, string> = {};
	for (const f of readdirSync(dir).filter((n) => n.endsWith('.json'))) Object.assign(out, JSON.parse(readFileSync(path.join(dir, f), 'utf8')));
	return out;
}
const DE = katalog('de');
const EN = katalog('en');

// ── Soll-Texte (Mockup Fassung 3, DE) ────────────────────────────────────────────────
const SOLL = {
	uebersicht: { titel: 'Übersicht', satz: 'Unverändert: Stand, letzte Briefings, nächster Versand.' },
	etappen: { titel: 'Etappen & Wegpunkte', satz: 'Das Tempo bestimmt die Gehzeiten und damit, welche Stunden je Wegpunkt bewertet werden.' },
	wetter: { titel: DE['wetter.kopf.titel'], satz: DE['wetter.kopf.erklaerung'] },
	zustellung: { titel: DE['zustellung.kopf.titel'], satz: DE['zustellung.kopf.erklaer'] },
	orte: { titel: 'Orte', satz: 'Ein Ort ergibt ein Orts-Briefing. Ab zwei Orten kommt die Vergleichstabelle dazu, ohne Rangfolge.' }
} as const;
const KNOPF_DE = '+ Ort hinzufügen';

/** EN-Soll zu einem DE-Text: der Rendertext muss der EN-Wert eines Schlüssels sein, dessen DE-Wert der DE-Text ist. */
function enPassend(deText: string, enIst: string): boolean {
	return Object.keys(DE).some((k) => DE[k] === deText && EN[k] === enIst);
}

// ── Render-Helfer ─────────────────────────────────────────────────────────────────────
const entity = (s: string) => s.replace(/&amp;/g, '&').replace(/&nbsp;/g, ' ').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'");
const text = (k: Knoten) => entity(rohText(k));
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
const koepfe = (b: Knoten) => alle(b, (n) => n.attrs['data-abschnitt'] === 'abschnittskopf');
const mitTestid = (b: Knoten, id: string) => alle(b, (n) => n.attrs['data-testid'] === id);

function einzigerKopf(b: Knoten, was: string): Knoten {
	const k = koepfe(b);
	assert.equal(k.length, 1, `${was}: ${k.length} Marker data-abschnitt="abschnittskopf" statt genau einem`);
	return k[0];
}
/** Kopf zerlegen: direkte Kinder (h2, p, optional Aktion). */
function teile(kopf: Knoten, was: string): { titel: string; satz: string; kinder: Knoten[] } {
	const kinder = kopf.kinder;
	assert.ok(kinder.length >= 2, `${was}: Kopf hat ${kinder.length} direkte Kinder, erwartet Überschrift und Erklärsatz`);
	assert.equal(kinder[0].tag, 'h2', `${was}: erstes direktes Kind ist <${kinder[0].tag}> statt <h2>`);
	assert.equal(kinder[1].tag, 'p', `${was}: zweites direktes Kind ist <${kinder[1].tag}> statt <p>`);
	return { titel: text(kinder[0]), satz: text(kinder[1]), kinder };
}

const BEREICHSKOPF = path.join(KOMP, 'molecules', 'Bereichskopf.svelte');
async function bereichskopf(): Promise<any> {
	assert.ok(existsSync(BEREICHSKOPF), 'TDD RED: molecules/Bereichskopf.svelte fehlt');
	return lade(BEREICHSKOPF);
}

// Hubs ------------------------------------------------------------------------------
const TRIP_HUB = path.join(KOMP, 'trip-detail', 'TripTabs.svelte');
const VERGLEICH_HUB = path.join(KOMP, 'compare', 'CompareTabs.svelte');
const ZT = path.join(KOMP, 'shared', 'zustellung-tab', 'ZustellungTab.svelte');
const WTI = path.join(KOMP, 'organisms', 'wetter-tab', 'WetterTabInhalt.svelte');
const TRIP = { id: 't1', name: 'Trip', stages: [] };
const LOCS = [
	{ id: 'l1', name: 'Ort A', lat: 47.1, lon: 11.1 },
	{ id: 'l2', name: 'Ort B', lat: 47.2, lon: 11.2 }
];
const PRESET = { id: 'p1', name: 'Vergleich', location_ids: ['l1', 'l2'], display_config: {} };
const TRIP_TAB_START = "let activeTab = $state<string>('uebersicht');";
const ENTSPERRT: [string, string][] = [
	['let versandHydrated = $state(false);', 'let versandHydrated = $state(true);'],
	['let alarmeHydrated = $state(false);', 'let alarmeHydrated = $state(true);'],
	['let wetterMetrikenHydrated = $state(false);', 'let wetterMetrikenHydrated = $state(true);'],
	['let layoutHydrated = $state(false);', 'let layoutHydrated = $state(true);']
];

// `ohneTrip`: Zustand „Trip lädt noch“ — TripTabs bekommt `trip` nicht gesetzt (Prop `trip?: Trip`).
// Bewusst ein Schalter statt eines Default-Parameters, denn ein übergebenes `undefined` würde
// den Default (`TRIP`) auslösen und den Ladezustand nie rendern (#3006 Adversary F001).
async function tripReiter(tab: string, lang: Lang, ohneTrip = false): Promise<Knoten> {
	const T = await lade(TRIP_HUB, [[TRIP_TAB_START, `let activeTab = $state<string>('${tab}');`]]);
	const props: Record<string, unknown> = { initialTab: tab };
	if (!ohneTrip) props.trip = TRIP;
	const b = mitSprache(lang, () => baum(render(T, { props }).body));
	const panel = mitTestid(b, `trip-detail-panel-${tab}`);
	assert.equal(panel.length, 1, `Messaufbau: Trip-Reiter ${tab} nicht aktiv gerendert`);
	return panel[0];
}
async function vergleichReiter(tab: string, lang: Lang, entsperrt = true): Promise<Knoten> {
	const C = await lade(VERGLEICH_HUB, entsperrt ? ENTSPERRT : []);
	const b = mitSprache(lang, () => baum(render(C, { props: { initialTab: tab, preset: PRESET, locations: LOCS } }).body));
	const panel = mitTestid(b, `compare-detail-panel-${tab}`);
	assert.equal(panel.length, 1, `Messaufbau: Orte-Reiter ${tab} nicht aktiv gerendert`);
	return panel[0];
}

function pruefeKopf(panel: Knoten, reiter: keyof typeof SOLL, lang: Lang, was: string): { titel: string; satz: string; kinder: Knoten[] } {
	const kopf = einzigerKopf(panel, was);
	const t = teile(kopf, was);
	const soll = SOLL[reiter];
	if (lang === 'de') {
		assert.equal(t.titel, soll.titel, `${was}: Titel`);
		assert.equal(t.satz, soll.satz, `${was}: Erklärsatz`);
	} else {
		assert.notEqual(t.titel, '', `${was}: EN-Titel leer`);
		assert.ok(enPassend(soll.titel, t.titel), `${was}: EN-Titel „${t.titel}“ ist nicht der EN-Wert eines Katalogschlüssels mit DE „${soll.titel}“`);
		assert.ok(enPassend(soll.satz, t.satz), `${was}: EN-Satz „${t.satz}“ ist nicht der EN-Wert eines Katalogschlüssels mit DE „${soll.satz}“`);
		assert.notEqual(t.satz, soll.satz, `${was}: EN zeigt den deutschen Erklärsatz`);
	}
	return t;
}

// ═══ AC-1 / AC-3: Struktur des Bausteins ══════════════════════════════════════════════
describe('#3006 AC-1/AC-3: Baustein Bereichskopf — Struktur', () => {
	test('AC-1: Marker-Container, direkte Kinder h2 dann p, Testids mit Präfix, kein leerer Aktions-Wrapper', async () => {
		const B = await bereichskopf();
		const b = baum(render(B, { props: { titel: 'Titel X', erklaerung: 'Satz Y', testid: 'probe' } }).body);
		const kopf = einzigerKopf(b, 'Bereichskopf');
		assert.equal(kopf.kinder.length, 2, `ohne Aktion genau zwei direkte Kinder, gefunden ${kopf.kinder.map((k) => k.tag).join(',')}`);
		const t = teile(kopf, 'Bereichskopf');
		assert.equal(t.titel, 'Titel X');
		assert.equal(t.satz, 'Satz Y');
		assert.equal(t.kinder[0].attrs['data-testid'], 'probe-titel');
		assert.equal(t.kinder[1].attrs['data-testid'], 'probe-erklaer');
	});
	test('AC-3: mit Aktions-Snippet steht die Aktion als drittes direktes Kind', async () => {
		const B = await bereichskopf();
		const aktion = createRawSnippet(() => ({ render: () => '<button type="button" data-testid="probe-aktion">Los</button>' }));
		const b = baum(render(B, { props: { titel: 'T', erklaerung: 'S', testid: 'probe', aktion } }).body);
		const kopf = einzigerKopf(b, 'Bereichskopf mit Aktion');
		assert.equal(kopf.kinder.length, 3, `mit Aktion drei direkte Kinder, gefunden ${kopf.kinder.length}`);
		const knopf = mitTestid(kopf.kinder[2], 'probe-aktion');
		assert.equal(knopf.length, 1, 'Aktion steht nicht im dritten direkten Kind');
	});
	test('Baustein ist aus molecules/index.ts exportiert', () => {
		const idx = readFileSync(path.join(KOMP, 'molecules', 'index.ts'), 'utf8'); // doc-compliance-test
		assert.match(idx, /Bereichskopf\b[\s\S]*?from\s+['"]\.\/Bereichskopf\.svelte['"]/, 'Export Bereichskopf fehlt in molecules/index.ts');
	});
});

// ═══ AC-2 / AC-3: Optik wie Mockup ═════════════════════════════════════════════════════
describe('#3006 AC-2/AC-3: Baustein Bereichskopf — Maße und Tokens (Kaskade)', async () => {
	const Q = await ladeQuellen(FRONTEND);
	const s = (k: Knoten, p: string, ctx: Kontext) => stil(Q, k, p, ctx);
	const tok = (n: string, ctx: Kontext) => token(Q, n, ctx.theme);
	for (const [breite, ctx] of [['Desktop 1280', DESKTOP], ['Handy 390', HANDY]] as Array<[string, Kontext]>) {
		test(`AC-2 (${breite}): h2 22px/600, Satz 13px --g-ink-3 ≤ 68ch, Linie 1px --g-rule-soft, Padding 12px`, async () => {
			const B = await bereichskopf();
			const b = baum(render(B, { props: { titel: 'T', erklaerung: 'S', testid: 'probe' } }).body);
			const kopf = einzigerKopf(b, 'Bereichskopf');
			const [h2, p] = kopf.kinder;
			assert.equal(s(kopf, 'border-bottom-style', ctx), 'solid', `Linie: ${herkunft(Q, kopf, 'border-bottom-style', ctx)}`);
			assert.equal(px(s(kopf, 'border-bottom-width', ctx)), 1, `Linienbreite: ${herkunft(Q, kopf, 'border-bottom-width', ctx)}`);
			assert.equal(s(kopf, 'border-bottom-color', ctx), tok('--g-rule-soft', ctx), `Linienfarbe: ${herkunft(Q, kopf, 'border-bottom-color', ctx)}`);
			assert.equal(px(s(kopf, 'padding-bottom', ctx)), 12, `padding-bottom: ${herkunft(Q, kopf, 'padding-bottom', ctx)}`);
			assert.equal(px(s(h2, 'font-size', ctx)), 22, `h2 font-size: ${herkunft(Q, h2, 'font-size', ctx)}`);
			assert.equal(s(h2, 'font-weight', ctx), '600', `h2 font-weight: ${herkunft(Q, h2, 'font-weight', ctx)}`);
			assert.equal(px(s(h2, 'margin-top', ctx)), 0, 'h2 margin-top');
			assert.equal(px(s(p, 'font-size', ctx)), 13, `Satz font-size: ${herkunft(Q, p, 'font-size', ctx)}`);
			assert.equal(s(p, 'color', ctx), tok('--g-ink-3', ctx), `Satz color: ${herkunft(Q, p, 'color', ctx)}`);
			assert.equal(s(p, 'max-width', ctx), '68ch', `Satz max-width: ${herkunft(Q, p, 'max-width', ctx)}`);
		});
	}
	test('AC-2: Stilblock nutzt nur Tokens (keine Roh-px für Schriftgrößen, keine Hex-Farben)', () => {
		assert.ok(existsSync(BEREICHSKOPF), 'TDD RED: molecules/Bereichskopf.svelte fehlt');
		const css = (readFileSync(BEREICHSKOPF, 'utf8').match(/<style[^>]*>([\s\S]*?)<\/style>/) ?? ['', ''])[1]; // doc-compliance-test
		assert.doesNotMatch(css, /#[0-9a-fA-F]{3,8}\b/, 'Hex-Farbe im Stilblock');
		assert.doesNotMatch(css, /font-size:\s*\d/, 'Roh-Schriftgröße statt Token');
	});
});

// ═══ AC-4 bis AC-9, AC-11 bis AC-13: Kopf je Reiter, DE/EN ═══════════════════════════════
describe('#3006 AC-4–AC-13: Kopf je Reiter aus dem Katalog (DE/EN)', () => {
	for (const lang of SPRACHEN) {
		test(`AC-4 (${lang}): Trip-Übersicht`, async () => {
			pruefeKopf(await tripReiter('uebersicht', lang), 'uebersicht', lang, `Trip/Übersicht ${lang}`);
		});
		test(`AC-5 (${lang}): Trip-Etappen — geladen und noch ladend`, async () => {
			pruefeKopf(await tripReiter('etappen', lang), 'etappen', lang, `Trip/Etappen ${lang}`);
			const mit = await tripReiter('etappen', lang);
		const ohne = await tripReiter('etappen', lang, true);
		// Messaufbau: ohne Trip fehlt der Etappen-Inhalt wirklich (das Panel hat weniger direkte Kinder).
		assert.ok(
			ohne.kinder.length < mit.kinder.length,
			`Messaufbau: ohne Trip wird trotzdem Etappen-Inhalt gerendert (${ohne.kinder.length} vs. ${mit.kinder.length} Kinder)`
		);
		pruefeKopf(ohne, 'etappen', lang, `Trip/Etappen ohne Trip ${lang}`);
		});
		test(`AC-6 (${lang}): Trip-Wetter`, async () => {
			const t = pruefeKopf(await tripReiter('wetter', lang), 'wetter', lang, `Trip/Wetter ${lang}`);
			assert.equal(t.kinder[0].attrs['data-testid'], 'wetter-tab-titel');
			assert.equal(t.kinder[1].attrs['data-testid'], 'wetter-tab-erklaer');
		});
		test(`AC-7 (${lang}): Trip-Zustellung`, async () => {
			const t = pruefeKopf(await tripReiter('zustellung', lang), 'zustellung', lang, `Trip/Zustellung ${lang}`);
			assert.equal(t.kinder[0].attrs['data-testid'], 'zustellung-titel');
			assert.equal(t.kinder[1].attrs['data-testid'], 'zustellung-erklaer');
		});
		test(`AC-8 (${lang}): Orte-Übersicht gleich Trip-Übersicht`, async () => {
			const o = pruefeKopf(await vergleichReiter('uebersicht', lang), 'uebersicht', lang, `Orte/Übersicht ${lang}`);
			const t = teile(einzigerKopf(await tripReiter('uebersicht', lang), 'Trip'), 'Trip');
			assert.deepEqual([o.titel, o.satz], [t.titel, t.satz], 'Orte- und Trip-Übersicht weichen ab');
		});
		test(`AC-9 (${lang}): Orte-Reiter — Kopf mit Knopf, keine „Verglichene Orte“, kein Card-Knopf`, async () => {
			const panel = await vergleichReiter('orte', lang);
			const o = pruefeKopf(panel, 'orte', lang, `Orte/Orte ${lang}`);
			assert.equal(o.kinder.length, 3, 'Orte-Kopf: Knopf fehlt als drittes direktes Kind');
			const knopfImKopf = mitTestid(o.kinder[2], 'hub-orte-add');
			assert.equal(knopfImKopf.length, 1, 'hub-orte-add steht nicht im Kopf');
			assert.equal(mitTestid(panel, 'hub-orte-add').length, 1, 'hub-orte-add kommt mehrfach vor (Card-Knopf nicht entfernt)');
			const knopfText = text(knopfImKopf[0]);
			if (lang === 'de') assert.equal(knopfText, KNOPF_DE);
			else assert.ok(enPassend(KNOPF_DE, knopfText) && knopfText !== KNOPF_DE, `EN-Knopf „${knopfText}“ nicht aus dem Katalog`);
			const verglichen = lang === 'de' ? DE['vergleich.hub.verglichene_orte'] : EN['vergleich.hub.verglichene_orte'];
			assert.ok(!text(panel).includes(verglichen), `Überschrift „${verglichen}“ steht noch im Reiter`);
		});
		test(`AC-11 (${lang}): Orte-Wetter gleich Trip-Wetter`, async () => {
			const o = pruefeKopf(await vergleichReiter('wetter', lang), 'wetter', lang, `Orte/Wetter ${lang}`);
			const t = teile(einzigerKopf(await tripReiter('wetter', lang), 'Trip'), 'Trip');
			assert.deepEqual([o.titel, o.satz], [t.titel, t.satz]);
		});
		test(`AC-12 (${lang}): Orte-Zustellung gleich Trip-Zustellung`, async () => {
			const o = pruefeKopf(await vergleichReiter('zustellung', lang), 'zustellung', lang, `Orte/Zustellung ${lang}`);
			const t = teile(einzigerKopf(await tripReiter('zustellung', lang), 'Trip'), 'Trip');
			assert.deepEqual([o.titel, o.satz], [t.titel, t.satz]);
		});
	}
	test('AC-13: jeder Katalogschlüssel mit einem Kopftext existiert in DE und EN', () => {
		const texte = [...Object.values(SOLL).flatMap((v) => [v.titel, v.satz]), KNOPF_DE];
		for (const t of texte) {
			const keys = Object.keys(DE).filter((k) => DE[k] === t);
			assert.ok(keys.length > 0, `Kopftext „${t}“ steht nicht im DE-Katalog`);
			assert.ok(keys.some((k) => typeof EN[k] === 'string' && EN[k] !== '' && EN[k] !== t), `Kopftext „${t}“: kein Schlüssel mit eigener EN-Übersetzung`);
		}
	});
});

// ═══ AC-14 bis AC-16: Zustände, genau ein Marker ════════════════════════════════════════
const START_LAEDT = "$state<'laedt' | 'fehler' | 'bereit'>('laedt')";
describe('#3006 AC-14–AC-16: Kopf in jedem Zustand, genau einmal', () => {
	for (const phase of ['laedt', 'fehler', 'bereit'] as const) {
		test(`AC-14: Wetter im Zustand ${phase} — Kopf genau einmal, Text wie normal`, async () => {
			const W = await lade(WTI, phase === 'laedt' ? [] : [[START_LAEDT, START_LAEDT.replace("('laedt')", `('${phase}')`)]]);
			const b = baum(render(W, { props: { context: 'route', trip: TRIP } }).body);
			pruefeKopf(b, 'wetter', 'de', `Wetter/${phase}`);
		});
	}
	for (const geladen of [false, true]) {
		test(`AC-14: Zustellung (Profil ${geladen ? 'geladen' : 'lädt'}) — Kopf genau einmal über den Baustein`, async () => {
			const Z = await lade(ZT, geladen ? [['let profilGeladen = $state(false);', 'let profilGeladen = $state(true);']] : []);
			const b = baum(render(Z, { props: { context: 'route', trip: TRIP } }).body);
			pruefeKopf(b, 'zustellung', 'de', `Zustellung/${geladen}`);
		});
	}
	for (const tab of ['wetter', 'zustellung'] as const) {
		for (const entsperrt of [false, true]) {
			test(`AC-15: Orte-${tab} ${entsperrt ? 'nach dem Laden' : 'während der Hydrations-Sperre'} — genau ein Kopf`, async () => {
				pruefeKopf(await vergleichReiter(tab, 'de', entsperrt), tab, 'de', `Orte/${tab}/${entsperrt ? 'frei' : 'gesperrt'}`);
			});
		}
	}
	test('AC-16: alle acht Reiter — je genau ein Marker', async () => {
		for (const tab of ['uebersicht', 'etappen', 'wetter', 'zustellung']) einzigerKopf(await tripReiter(tab, 'de'), `Trip/${tab}`);
		for (const tab of ['uebersicht', 'orte', 'wetter', 'zustellung']) {
			einzigerKopf(await vergleichReiter(tab, 'de'), `Orte/${tab}`);
			einzigerKopf(await vergleichReiter(tab, 'de', false), `Orte/${tab} gesperrt`);
		}
	});
});

// ═══ AC-17 / AC-18: Testids bleiben, alte Kopien weg ════════════════════════════════════
describe('#3006 AC-17/AC-18: Testids bleiben, Kopf-Kopien entfernt', () => {
	test('AC-17: wetter-tab-*, zustellung-*, hub-orte-add vorhanden', async () => {
		const w = await tripReiter('wetter', 'de');
		const z = await tripReiter('zustellung', 'de');
		const o = await vergleichReiter('orte', 'de');
		for (const [b, id] of [[w, 'wetter-tab-titel'], [w, 'wetter-tab-erklaer'], [z, 'zustellung-titel'], [z, 'zustellung-erklaer'], [o, 'hub-orte-add']] as Array<[Knoten, string]>) {
			assert.equal(mitTestid(b, id).length, 1, `Testid ${id} fehlt oder doppelt`);
		}
	});
	test('AC-18: ZustellungKopf.svelte entfernt, kein wt-kopf mehr, beide Reiter nutzen den Baustein', () => {
		// doc-compliance-test
		assert.ok(!existsSync(path.join(KOMP, 'organisms', 'zustellung-tab', 'ZustellungKopf.svelte')), 'ZustellungKopf.svelte existiert noch');
		const wti = readFileSync(WTI, 'utf8');
		assert.doesNotMatch(wti, /wt-kopf/, 'WetterTabInhalt trägt noch den Eigenkopf wt-kopf');
		assert.match(wti, /<Bereichskopf\b/, 'WetterTabInhalt nutzt den Baustein nicht');
		assert.match(readFileSync(ZT, 'utf8'), /<Bereichskopf\b/, 'ZustellungTab nutzt den Baustein nicht');
	});
});
