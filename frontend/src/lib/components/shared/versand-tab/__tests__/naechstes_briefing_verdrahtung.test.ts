// Issue #1969 Fix-Loop 1 (Adversary F002) — Verdrahtung „Nächstes Briefing"
// an den Stellen, an denen sie WIRKT: Versand-Reiter (Trip + Vergleich),
// Vergleichs-Hub (CompareTabs) und Trip-Karte (HubOverview).
// Spec: docs/specs/modules/feat_1969_naechstes_briefing.md (AC-16..AC-20, AC-23)
//
// Testart (Kern, kein Netz): svelteInstanzPruefstand wertet das ECHTE
// Instanz-Skript mit gesäten Props aus und liest die Attribut-Ausdrücke der
// ECHTEN Einbettungen (<VTNextBriefing …>). Geprüft wird, mit welcher Quelle
// (context, id, neuLaden = savedAt) jede Komponente den geteilten Lader
// füttert, welcher Pfad daraus abgefragt wird und was dann angezeigt wird.
// WIE der Lader auf diese Quelle reagiert (Neuladen, veraltete Antworten),
// prüft naechstes_briefing_lader_laufzeit.test.ts in der Client-Laufzeit.
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/shared/versand-tab/__tests__/naechstes_briefing_verdrahtung.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { umgebungFuer, findeKomponenten, ohneTypen, werte, type Knoten } from '../../__tests__/svelteInstanzPruefstand.ts';
import { vollerVergleich } from '../../__tests__/goMergeServerPruefstand.ts';

process.env.TZ = 'America/Los_Angeles';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '../../../../../..');
const basis = pathToFileURL(FRONTEND + '/').href;
const VERSAND_TAB = join(HIER, '..', '..', 'VersandTab.svelte');
const BAUSTEIN = join(HIER, '..', 'VTNextBriefing.svelte');
const VERGLEICH_HUB = join(HIER, '..', '..', '..', 'compare', 'CompareTabs.svelte');
const TRIP_KARTE = join(HIER, '..', '..', '..', 'trip-detail', 'HubOverview.svelte');
const UEBERSICHT = join(HIER, '..', '..', 'hub-uebersicht', 'HubUebersicht.svelte');

register(pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href, basis);
register(pathToFileURL(join(FRONTEND, 'test-app-environment-stub-hooks.mjs')).href, basis);
register(pathToFileURL(join(FRONTEND, 'src/lib/components/trip-new/__tests__/ssrRunesHook.mjs')).href, basis);
register(pathToFileURL(join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, basis);
register(pathToFileURL(join(HIER, '..', '..', '__tests__', 'svelteTsModulHook.mjs')).href, basis);

const { render } = await import('svelte/server');
const { ladeNaechstesBriefing } = await import('../nextBriefingLoad.ts');
const VTNextBriefing = (await import(pathToFileURL(BAUSTEIN).href)).default;

const NB = (local_time: string) => ({
	at: `2026-10-22T${local_time}:00+02:00`,
	local_date: '2026-10-22',
	local_time,
	tz: 'Europe/Paris',
	tz_abbr: 'CEST',
	slot: 'morning'
});
const GESPEICHERT = new Date('2026-10-22T05:00:00Z');
const TRIP = { id: 't-1969', name: 'T', stages: [], report_config: { morning_time: '08:00:00', evening_time: '20:00:00' }, display_config: {} };

/** Wert eines Attributs an einer Einbettung (Kurzform `{x}` = Bezeichner). */
function attribut(einbettung: Knoten, quelle: string, name: string, u: Knoten): unknown {
	const a = ((einbettung.attributes ?? []) as Knoten[]).find((x) => x.type === 'Attribute' && x.name === name);
	if (!a) return undefined;
	if (a.value === true) return true;
	if (a.value?.type === 'ExpressionTag') return werte(ohneTypen(quelle, a.value.expression), u);
	const teile = (Array.isArray(a.value) ? a.value : [a.value]) as Knoten[];
	return teile.map((t) => (t.type === 'Text' ? t.data : werte(ohneTypen(quelle, t.expression), u))).join('');
}
function propsVon(einbettung: Knoten, quelle: string, u: Knoten): Record<string, unknown> {
	const p: Record<string, unknown> = {};
	for (const a of (einbettung.attributes ?? []) as Knoten[]) if (a.type === 'Attribute') p[a.name] = attribut(einbettung, quelle, a.name, u);
	return p;
}
/** Wertet die Deklaration `name` des Instanz-Skripts erneut gegen `u` aus. */
function deklaration(ast: Knoten, quelle: string, u: Knoten, name: string): unknown {
	for (const stmt of (ast.instance?.content?.body as Knoten[]) ?? []) {
		if (stmt.type !== 'VariableDeclaration') continue;
		for (const d of stmt.declarations as Knoten[]) {
			if (d.id?.type === 'Identifier' && d.id.name === name) return werte(ohneTypen(quelle, d.init), u);
		}
	}
	throw new Error(`Messaufbau: Deklaration ${name} fehlt`);
}
const text = (html: string) => html.replace(/<!--[\s\S]*?-->/g, '').replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();

/** Quelle, mit der der Baustein bei diesen Props den Lader füttert. */
async function bausteinQuelle(props: Record<string, unknown>) {
	const { u } = await umgebungFuer(
		BAUSTEIN,
		{ nextBriefing: undefined, id: undefined, reloadKey: undefined, context: undefined, ...props },
		{ jsAlsTs: true }
	);
	assert.ok(u.lader && typeof u.lader === 'object', 'Messaufbau: Lader im Baustein nicht auswertbar');
	return u.lader.quelle as { context: string; id?: string; neuLaden?: unknown; extern?: unknown };
}

/** Kette Quelle → Abruf (aufgezeichnet) → Anzeige des Bausteins. */
async function abrufUndAnzeige(q: { context: string; id?: string }, antwort: unknown) {
	const pfade: string[] = [];
	const nb = await ladeNaechstesBriefing(async (p: string) => (pfade.push(p), antwort), q.context as never, q.id!);
	const zeile = text(render(VTNextBriefing, { props: { nextBriefing: nb, context: q.context } }).body);
	return { pfade, zeile };
}

const ANTWORT = { trips: { 't-1969': NB('08:00') }, compare: { 'cp-1969': NB('07:00') } };

describe('(a) VersandTab → VTNextBriefing: Quelle je Kontext', () => {
	async function einbettungen(saat: Record<string, unknown>) {
		const { ast, quelle, u } = await umgebungFuer(
			VERSAND_TAB,
			{ trip: undefined, preset: undefined, saveController: undefined, ...saat },
			{ jsAlsTs: true }
		);
		const e = findeKomponenten(ast, 'VTNextBriefing');
		assert.equal(e.length, 2, 'je Zweig genau eine Einbettung erwartet');
		return { e, quelle, u };
	}

	test('Vergleich: fragt preset_id ab und zeigt .compare[id]', async () => {
		const { e, quelle, u } = await einbettungen({
			context: 'vergleich',
			preset: vollerVergleich('cp-1969'),
			saveController: { savedAt: GESPEICHERT }
		});
		const q = await bausteinQuelle(propsVon(e[1], quelle, u));
		assert.equal(q.context, 'vergleich');
		assert.equal(q.id, 'cp-1969');
		assert.equal(q.neuLaden, GESPEICHERT, 'Neuladen muss am Speicher-Zeitstempel hängen');
		const { pfade, zeile } = await abrufUndAnzeige(q, ANTWORT);
		assert.deepEqual(pfade, ['/api/next-briefings?preset_id=cp-1969']);
		assert.ok(zeile.includes('Nächstes Briefing') && zeile.includes('Do 07:00 (CEST)'), zeile);
	});

	test('Trip: fragt trip_id ab und zeigt .trips[id]', async () => {
		const { e, quelle, u } = await einbettungen({ context: 'route', trip: TRIP, saveController: { savedAt: GESPEICHERT } });
		const q = await bausteinQuelle(propsVon(e[0], quelle, u));
		assert.equal(q.context, 'route');
		assert.equal(q.id, 't-1969');
		assert.equal(q.neuLaden, GESPEICHERT);
		const { pfade, zeile } = await abrufUndAnzeige(q, ANTWORT);
		assert.deepEqual(pfade, ['/api/next-briefings?trip_id=t-1969']);
		assert.ok(zeile.includes('Do 08:00 (CEST)'), zeile);
	});

	test('neues savedAt ⇒ neue Quelle; ungespeicherte Zeitplan-Eingaben ändern die Quelle nicht', async () => {
		const basisSaat = { context: 'vergleich', preset: vollerVergleich('cp-1969') };
		const quelleBei = async (saat: Record<string, unknown>) => {
			const { e, quelle, u } = await einbettungen(saat);
			return bausteinQuelle(propsVon(e[1], quelle, u));
		};
		const a = await quelleBei({ ...basisSaat, saveController: { savedAt: GESPEICHERT }, morningTime: '07:00' });
		const b = await quelleBei({ ...basisSaat, saveController: { savedAt: GESPEICHERT }, morningTime: '09:00' });
		const c = await quelleBei({ ...basisSaat, saveController: { savedAt: new Date('2026-10-22T06:00:00Z') }, morningTime: '09:00' });
		assert.deepEqual(a, b, 'eine ungespeicherte Eingabe darf die Lade-Quelle nicht verändern');
		assert.notEqual(a.neuLaden, c.neuLaden, 'Speichern muss die Lade-Quelle verändern (Neuladen)');
	});

	test('Anlege-Seite (Trip ohne saveController): keine id ⇒ kein Abruf', async () => {
		const { e, quelle, u } = await einbettungen({ context: 'route', trip: TRIP });
		const q = await bausteinQuelle(propsVon(e[0], quelle, u));
		assert.equal(q.id, undefined);
	});
});

// Issue #2682: die Hub-Stat „Nächster Versand" steht im geteilten Übersichts-Baustein
// (shared/hub-uebersicht/HubUebersicht.svelte); CompareTabs reicht `saveController` durch.
// Gemessen wird dieselbe Kette wie vorher, nur am neuen Ort: Lader-Quelle → Abruf → Anzeige.
const UEBERSICHT_LEER = { trip: undefined, preset: undefined, status: undefined, orte: undefined, saveController: undefined, onJump: undefined, children: undefined };
async function vergleichsUebersicht() {
	return umgebungFuer(
		UEBERSICHT,
		{ ...UEBERSICHT_LEER, context: 'vergleich', preset: vollerVergleich('cp-1969'), orte: [], saveController: { savedAt: GESPEICHERT } },
		{ jsAlsTs: true }
	);
}

describe('(c) Vergleichs-Hub: Hub-Stat „Nächster Versand" aus dem Backend-Wert', () => {
	test('CompareTabs reicht saveController an den Übersichts-Baustein (Neuladen nach Speichern)', async () => {
		const { ast, quelle } = await umgebungFuer(
			VERGLEICH_HUB,
			{ preset: vollerVergleich('cp-1969'), locations: [], saveController: { savedAt: GESPEICHERT } },
			{ jsAlsTs: true }
		);
		const e = findeKomponenten(ast, 'HubUebersicht');
		assert.equal(e.length, 1, 'CompareTabs bindet HubUebersicht nicht genau einmal ein');
		const a = ((e[0].attributes ?? []) as Knoten[]).find((x) => x.type === 'Attribute' && x.name === 'saveController');
		assert.ok(a, 'CompareTabs reicht saveController nicht an HubUebersicht');
		assert.equal(a.value?.type === 'ExpressionTag' ? quelle.slice(a.value.expression.start, a.value.expression.end) : null, 'saveController');
	});

	test('Lader-Quelle: vergleich, preset.id, savedAt', async () => {
		const { u } = await vergleichsUebersicht();
		const q = u.naechstesBriefing?.quelle;
		assert.ok(q, 'Messaufbau: Lader im Baustein nicht auswertbar');
		assert.equal(q.context, 'vergleich');
		assert.equal(q.id, 'cp-1969');
		assert.equal(q.neuLaden, GESPEICHERT, 'Hub lädt nach dem Speichern nicht neu');
		const { pfade } = await abrufUndAnzeige(q, ANTWORT);
		assert.deepEqual(pfade, ['/api/next-briefings?preset_id=cp-1969']);
	});

	test('Anzeige-Text folgt dem geladenen Wert', async () => {
		const { ast, quelle, u } = await vergleichsUebersicht();
		const naechster = () =>
			(deklaration(ast, quelle, u, 'modell') as Knoten).kennzahlen.find((k: Knoten) => k.id === 'naechster-versand');
		assert.equal(naechster().lang, '—', 'nicht geladen ⇒ „—"');
		u.naechstesBriefing = { wert: NB('07:00'), quelle: u.naechstesBriefing.quelle };
		assert.equal(naechster().lang, 'Do 07:00 (CEST)');
		assert.equal(naechster().kurz, 'Do 07:00 (CEST)');
	});
});

// ── F007: die Anzeige-STELLEN im Markup des Hubs (nicht nur die Variable) ──
/** Alle Knoten eines Typs im Template (AST, kein Textmuster). */
function knoten(wurzel: unknown, typ: string, aus: Knoten[] = []): Knoten[] {
	if (wurzel === null || typeof wurzel !== 'object') return aus;
	if (Array.isArray(wurzel)) {
		for (const k of wurzel) knoten(k, typ, aus);
		return aus;
	}
	const n = wurzel as Knoten;
	if (n.type === typ) aus.push(n);
	for (const key of Object.keys(n)) if (key !== 'parent' && key !== 'loc') knoten(n[key], typ, aus);
	return aus;
}
const reinerText = (el: Knoten) =>
	((el.fragment?.nodes ?? []) as Knoten[]).map((c) => (c.type === 'Text' ? c.data : '\u0000')).join('').trim();

// #2682: die Etiketten sind Daten des Modells (`{k.label}` je {#each}-Eintrag) — gemessen wird je
// Raster (mobil, Desktop) der Eintrag „Nächster Versand" mit seiner ECHTEN Schleifenbindung.
/** Text-Kinder eines Knotens (Fragment-Ebene, rekursiv, ohne Attribut-Ausdrücke). */
function fragmentAusdruecke(n: Knoten, aus: Knoten[] = []): Knoten[] {
	for (const c of (n.fragment?.nodes ?? n.consequent?.nodes ?? []) as Knoten[]) {
		if (c.type === 'ExpressionTag') aus.push(c);
		else fragmentAusdruecke(c, aus);
	}
	if (n.type === 'IfBlock' && n.alternate) for (const c of n.alternate.nodes as Knoten[]) {
		if (c.type === 'ExpressionTag') aus.push(c);
		else fragmentAusdruecke(c, aus);
	}
	return aus;
}

describe('(c/F007) Vergleichs-Übersicht: jede „Nächster Versand"-Anzeige rendert den geladenen Wert', () => {
	async function hubMitWert() {
		const r = await vergleichsUebersicht();
		r.u.naechstesBriefing = { wert: NB('07:00'), quelle: r.u.naechstesBriefing.quelle };
		r.u.modell = deklaration(r.ast, r.quelle, r.u, 'modell');
		r.u.mobileKennzahlen = deklaration(r.ast, r.quelle, r.u, 'mobileKennzahlen');
		return r;
	}

	test('Stat-Karten (mobil + Desktop): der Wert-Knoten neben dem Etikett zeigt „Do 07:00 (CEST)"', async () => {
		const { ast, quelle, u } = await hubMitWert();
		const schleifen = knoten(ast.fragment, 'EachBlock').filter((e) => /kennzahlen|Kennzahlen/.test(quelle.slice(e.expression.start, e.expression.end)));
		assert.equal(schleifen.length, 2, 'Messaufbau: genau zwei Kennzahlen-Raster (mobil, Desktop) erwartet');
		for (const s of schleifen) {
			const eintraege = werte(ohneTypen(quelle, s.expression), u) as Knoten[];
			const eintrag = eintraege.find((k) => k.label === 'Nächster Versand');
			assert.ok(eintrag, 'Messaufbau: Raster ohne Kennzahl „Nächster Versand"');
			const bindung = Object.assign(Object.create(u), { [s.context.name]: eintrag });
			const etikett = knoten(s.body, 'RegularElement').find((el) =>
				((el.fragment?.nodes ?? []) as Knoten[]).some(
					(c) => c.type === 'ExpressionTag' && werte(ohneTypen(quelle, c.expression), bindung) === 'Nächster Versand'
				)
			);
			assert.ok(etikett, 'Etikett „Nächster Versand" wird nicht gerendert');
			const eltern = [...knoten(s.body, 'RegularElement'), ...knoten(s.body, 'Component')].find((p) =>
				((p.fragment?.nodes ?? []) as Knoten[]).includes(etikett)
			);
			const elemente = ((eltern?.fragment?.nodes ?? []) as Knoten[]).filter((g) => g.type === 'RegularElement');
			const wertKnoten = elemente[elemente.indexOf(etikett!) + 1];
			assert.ok(wertKnoten, 'Wert-Knoten neben dem Etikett fehlt');
			const tags = fragmentAusdruecke(wertKnoten);
			assert.ok(tags.length >= 1, 'Wert-Knoten rendert keinen Ausdruck');
			for (const t of tags) assert.equal(werte(ohneTypen(quelle, t.expression), bindung), 'Do 07:00 (CEST)');
		}
	});

	test('Versand-Zusammenfassung (aktiver Vergleich) nennt den geladenen Termin', async () => {
		const { ast, quelle, u } = await hubMitWert();
		assert.equal(u.modell.kennzahlen[0].lang, 'Läuft automatisch', 'Messaufbau: aktiver Vergleich');
		const tags = knoten(ast.fragment, 'ExpressionTag').filter((t) =>
			/versandKarte\.beschreibungLang/.test(quelle.slice(t.expression.start, t.expression.end))
		);
		assert.equal(tags.length, 1, 'Messaufbau: Zusammenfassung wird genau einmal gerendert');
		const gerendert = String(werte(ohneTypen(quelle, tags[0].expression), u));
		assert.ok(gerendert.includes('nächster Versand Do 07:00 (CEST)'), gerendert);
	});
});

describe('(F008) HubOverview: abgeschalteter Slot wird als inaktiv dargestellt', () => {
	/** Punktfarbe der Zeile mit dem Etikett `label` (Punkt = erstes <span> der Zeile). */
	function punktfarbe(html: string, label: string): string {
		const i = html.indexOf(`>${label}</span>`);
		assert.notEqual(i, -1, `Messaufbau: Zeile ${label} fehlt`);
		const zeile = html.lastIndexOf('<div', i);
		const m = /background:\s*([^;"]+)/.exec(html.slice(zeile, i));
		assert.ok(m, `Messaufbau: Punktfarbe der Zeile ${label} nicht gefunden`);
		return m![1].trim();
	}
	test('Abend aus, Morgen an → Abend-Punkt neutral (--g-rule), Morgen-Punkt aktiv (--g-good)', async () => {
		const HubOverview = (await import(pathToFileURL(TRIP_KARTE).href)).default;
		const trip = { ...TRIP, report_config: { ...TRIP.report_config, enabled: true, morning_enabled: true, evening_enabled: false } };
		const html = render(HubOverview, { props: { trip, nextBriefing: NB('08:00') } }).body.replace(/<!--[\s\S]*?-->/g, '');
		assert.equal(punktfarbe(html, 'Morgen-Briefing'), 'var(--g-good)');
		assert.equal(punktfarbe(html, 'Abend-Briefing'), 'var(--g-rule)');
	});
	test('Morgen aus, Abend an → Morgen-Punkt neutral, Abend-Punkt aktiv', async () => {
		const HubOverview = (await import(pathToFileURL(TRIP_KARTE).href)).default;
		const trip = { ...TRIP, report_config: { ...TRIP.report_config, enabled: true, morning_enabled: false, evening_enabled: true } };
		const html = render(HubOverview, { props: { trip, nextBriefing: NB('20:00') } }).body.replace(/<!--[\s\S]*?-->/g, '');
		assert.equal(punktfarbe(html, 'Morgen-Briefing'), 'var(--g-rule)');
		assert.equal(punktfarbe(html, 'Abend-Briefing'), 'var(--g-good)');
	});
});

describe('(f) HubOverview ohne Prop: lädt selbst und zeigt das Kürzel', () => {
	test('Lader-Quelle: route, trip.id, kein Wert von aussen', async () => {
		const { u } = await umgebungFuer(TRIP_KARTE, { trip: TRIP, nextBriefing: undefined }, { jsAlsTs: true });
		const q = u.naechstesBriefing?.quelle;
		assert.ok(q, 'Messaufbau: Lader in der Karte nicht auswertbar');
		assert.equal(q.context, 'route');
		assert.equal(q.id, 't-1969');
		assert.equal(q.extern, undefined);
		const { pfade } = await abrufUndAnzeige(q, ANTWORT);
		assert.deepEqual(pfade, ['/api/next-briefings?trip_id=t-1969']);
	});

	test('geladener Wert ⇒ Karten-Zeiten tragen das Kürzel', async () => {
		const { ast, quelle, u } = await umgebungFuer(TRIP_KARTE, { trip: TRIP, nextBriefing: undefined }, { jsAlsTs: true });
		assert.equal(deklaration(ast, quelle, u, 'morgenZeit'), '08:00', 'nicht geladen ⇒ ohne Kürzel');
		u.naechstesBriefing = { wert: NB('08:00'), quelle: u.naechstesBriefing.quelle };
		u.briefing = deklaration(ast, quelle, u, 'briefing');
		assert.equal(deklaration(ast, quelle, u, 'morgenZeit'), '08:00 (CEST)');
		assert.equal(deklaration(ast, quelle, u, 'abendZeit'), '20:00 (CEST)');
	});
});
