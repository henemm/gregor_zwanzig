// TDD RED — Issue #1743 (Spec feat_1743_reiter_aufraeumen): Versand-Spruenge landen unter
// Wetter-Metriken am Anker `#versand`; Vorschau-Sprunglinks entfallen.
//
//   AC-6  „Zeitplan bearbeiten →" (Trip-Uebersicht) oeffnet `?tab=wetter-metriken#versand`.
//   AC-23 Cockpit-Schnellaktionen: jede `?tab=`-Kennung loest ohne Legacy auf; Versand-Aktionen
//         zielen auf `?tab=wetter-metriken#versand`; keine Vorschau-Schnellaktion.
//   AC-24 „Setup abschliessen" (Ortsvergleich-Detailseite) oeffnet `?tab=wetter-metriken#versand`.
//   AC-25 Versand-Spruenge im Vergleichs-Hub („Bearbeiten →", Mobil-Zeile) ebenso.
//   AC-28 Weder „Vorschau oeffnen" (HubOverview) noch „Vorschau pruefen →" (Cockpit, CompareTabs).
//
// Messweise: der Knopf wird im Template-AST ueber seine BESCHRIFTUNG gefunden (nicht ueber
// Variablennamen), sein ECHTER onclick-Ausdruck wird im Instanz-Skript der Komponente
// ausgewertet (`umgebungFuer`/`werte`) und ausgeloest. Bei Trip und Vergleichs-Hub laufen die
// aufgezeichneten Sprung-Argumente anschliessend durch den ECHTEN `handleValueChange` des Hubs —
// gemessen wird die Adresse, die der Hub schreibt (Trip: `goto`, Vergleich: `history.replaceState`).
// Damit legt der Test die Signatur von `onJump` nicht fest, nur die Wirkung.
// HubOverview wird zusaetzlich serverseitig gerendert (svelte/server) — gemessen am HTML.
//
// Grenze: das Scrollen zum Abschnitt und dessen Sichtbarkeit sind nur im Browser messbar
// (Playwright in /50).
//
// Pfadregel #1409: Pruefling relativ zu DIESER Datei.
//
// Ausfuehren (aus frontend/):
//   node --import ./test-lib-loader.mjs --experimental-strip-types --experimental-test-module-mocks \
//     --test src/lib/components/shared/__tests__/versand_sprung_auf_wetter_metriken.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { umgebungFuer, werte, ohneTypen, findeKomponenten, attributAusdruck, type Knoten } from './svelteInstanzPruefstand.ts';
import { vollerVergleich } from './goMergeServerPruefstand.ts';
import { resolveTab } from '../subscriptionTabs.ts';
import { trFor, type MessageKey } from '../../../i18n/index.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '../../../../..');
const SRC = join(FRONTEND, 'src');
const HUB_OVERVIEW = join(SRC, 'lib/components/trip-detail/HubOverview.svelte');
const TRIP_HUB = join(SRC, 'lib/components/trip-detail/TripTabs.svelte');
const VERGLEICH_HUB = join(SRC, 'lib/components/compare/CompareTabs.svelte');
const HUB_UEBERSICHT = join(SRC, 'lib/components/shared/hub-uebersicht/HubUebersicht.svelte');
const VERGLEICH_SEITE = join(SRC, 'routes/compare/[id]/+page.svelte');
const HOME = join(SRC, 'routes/+page.svelte');

register(pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
register(pathToFileURL(join(FRONTEND, 'test-app-environment-stub-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
register(pathToFileURL(join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);

const TRIP: Knoten = {
	id: 't-1',
	name: 'Testtrip',
	stages: [{ id: 's1', name: 'E1', date: '2026-10-23', waypoints: [] }],
	report_config: {},
	display_config: {}
};

// ── Browser-Attrappen (nur Aufzeichnung, die Entscheidung trifft der echte Code) ──

let schreibungen: string[] = [];
const globaleAlt = { window: (globalThis as Knoten).window, history: (globalThis as Knoten).history };
afterEach(() => {
	(globalThis as Knoten).window = globaleAlt.window;
	(globalThis as Knoten).history = globaleAlt.history;
});

function adresszeile(pfad: string, tab: string): void {
	schreibungen = [];
	const location: Knoten = { href: `http://localhost${pfad}?tab=${tab}`, search: `?tab=${tab}`, pathname: pfad, hash: '' };
	(globalThis as Knoten).window = {
		location,
		matchMedia: () => ({ matches: false, addEventListener() {}, removeEventListener() {} })
	};
	(globalThis as Knoten).history = {
		state: null,
		replaceState: (_s: unknown, _t: string, url: string | URL) => schreibungen.push(String(url)),
		pushState: (_s: unknown, _t: string, url: string | URL) => schreibungen.push(String(url))
	};
}
const gotoAufzeichnung = (url: string) => {
	schreibungen.push(String(url));
	return Promise.resolve();
};

// ── AST-Helfer ───────────────────────────────────────────────────────────────

function besuche(knoten: unknown, f: (n: Knoten) => void): void {
	if (knoten === null || typeof knoten !== 'object') return;
	if (Array.isArray(knoten)) {
		knoten.forEach((k) => besuche(k, f));
		return;
	}
	const n = knoten as Knoten;
	f(n);
	for (const key of Object.keys(n)) if (key !== 'parent' && key !== 'loc') besuche(n[key], f);
}

/** Sichtbarer Text eines Knopfs (alle Text-Knoten seines Fragments). */
function text(n: Knoten): string {
	let t = '';
	besuche(n.fragment, (k) => {
		if (k.type === 'Text') t += k.data;
		// Issue #2658 (i18n F9): `{$t('schluessel')}` traegt den deutschen Katalogwert.
		const e = k.type === 'ExpressionTag' ? (k.expression as Knoten) : null;
		if (e?.type === 'CallExpression' && e.callee?.name === '$t' && e.arguments?.[0]?.type === 'Literal') t += trFor('de', e.arguments[0].value);
	});
	return t.replace(/\s+/g, ' ').trim();
}

/** Alle Knoepfe (Element `button` oder Komponente `Btn`), deren Text `teil` enthaelt. */
function knoepfeMitText(ast: Knoten, teil: string): Knoten[] {
	const treffer: Knoten[] = [];
	besuche(ast.fragment, (n) => {
		const istKnopf =
			(n.type === 'RegularElement' && n.name === 'button') || (n.type === 'Component' && n.name === 'Btn');
		if (istKnopf && text(n).includes(teil)) treffer.push(n);
	});
	return treffer;
}

/** Der onclick-Ausdruck eines Knopfs als ausfuehrbarer Quelltext (TS-Annotationen entfernt). */
function onclick(knopf: Knoten, quelle: string): string {
	const a = ((knopf.attributes ?? []) as Knoten[]).find((x) => x.type === 'Attribute' && x.name === 'onclick');
	assert.ok(a && a.value?.type === 'ExpressionTag', `Knopf „${text(knopf)}" hat keinen onclick-Ausdruck`);
	return ohneTypen(quelle, a.value.expression);
}

/** Statischer Wert eines Attributs; Ausdrucksteile werden durch `X` ersetzt. */
function attributText(n: Knoten, name: string): string | null {
	const a = ((n.attributes ?? []) as Knoten[]).find((x) => x.type === 'Attribute' && x.name === name);
	if (!a) return null;
	const teile = Array.isArray(a.value) ? a.value : [a.value];
	return teile.map((t: Knoten) => (t?.type === 'Text' ? t.data : 'X')).join('');
}

/** Angezeigte (deutsche) Beschriftung: statischer Text oder `$t('key')` ueber den Katalog (#2652). */
function beschriftung(n: Knoten, name: string): string {
	const a = ((n.attributes ?? []) as Knoten[]).find((x) => x.type === 'Attribute' && x.name === name);
	const wert = Array.isArray(a?.value) ? a.value[0] : a?.value;
	const e = wert?.type === 'ExpressionTag' ? wert.expression : null;
	if (e?.type === 'CallExpression' && e.callee?.name === '$t') return trFor('de', e.arguments[0].value as MessageKey);
	return attributText(n, name) ?? '';
}

const ziel = (url: string) => new URL(url, 'http://localhost/x');

// ── AC-6: Trip-Uebersicht „Zeitplan bearbeiten →" ───────────────────────────────

describe('#1743 AC-6: „Zeitplan bearbeiten →" der Trip-Uebersicht oeffnet ?tab=wetter-metriken#versand', () => {
	test('Knopf ausloesen → Sprung durch den echten TripTabs-Handler → Adresse ?tab=wetter-metriken#versand', async () => {
		const spruenge: unknown[][] = [];
		const ov = await umgebungFuer(HUB_OVERVIEW, { trip: TRIP, onJump: (...a: unknown[]) => spruenge.push(a) }, { jsAlsTs: true });
		const knoepfe = knoepfeMitText(ov.ast, 'Zeitplan bearbeiten');
		assert.equal(knoepfe.length, 1, 'genau ein „Zeitplan bearbeiten"-Knopf erwartet');
		(werte(onclick(knoepfe[0], ov.quelle), ov.u) as () => void)();
		assert.equal(spruenge.length, 1, `genau ein Sprung erwartet: ${JSON.stringify(spruenge)}`);

		adresszeile('/trips/t-1', 'uebersicht');
		const hub = await umgebungFuer(
			TRIP_HUB,
			{ initialTab: 'uebersicht', goto: gotoAufzeichnung, page: { url: new URL('http://localhost/trips/t-1?tab=uebersicht') }, badges: {}, trip: TRIP },
			{ jsAlsTs: true }
		);
		hub.u.activeTab = 'uebersicht';
		await (hub.u.handleValueChange as (...a: unknown[]) => Promise<void>)(...spruenge[0]);
		assert.equal(hub.u.activeTab, 'wetter-metriken', `aktiver Reiter nach dem Sprung ${JSON.stringify(spruenge[0])}`);
		assert.equal(schreibungen.length, 1, JSON.stringify(schreibungen));
		assert.equal(ziel(schreibungen[0]).searchParams.get('tab'), 'wetter-metriken', schreibungen[0]);
		assert.equal(ziel(schreibungen[0]).hash, '#versand', `Adresse ${schreibungen[0]} springt nicht zum Versand-Abschnitt`);
	});
});

// ── AC-25: Versand-Spruenge im Vergleichs-Hub ───────────────────────────────────

// #2682: die Übersicht ist der geteilte Baustein HubUebersicht (context="vergleich"), den CompareTabs
// mit `onJump={handleValueChange}` einbindet. Gemessen wird wie beim Trip (AC-6) in zwei Schritten:
// der ECHTE onclick des Knopfs im Baustein (Sprung-Argumente aufgezeichnet), dann der ECHTE
// `handleValueChange` von CompareTabs mit genau diesen Argumenten — geprueft wird die geschriebene Adresse.
describe('#1743 AC-25: Versand-Spruenge im Ortsvergleich-Hub landen auf ?tab=wetter-metriken#versand', () => {
	async function vergleichsHub() {
		adresszeile('/compare/c-1', 'uebersicht');
		return umgebungFuer(
			VERGLEICH_HUB,
			{
				initialTab: 'uebersicht',
				preset: vollerVergleich('c-1'),
				locations: [],
				orteCount: 3,
				goto: gotoAufzeichnung,
				page: { url: new URL('http://localhost/compare/c-1?tab=uebersicht') }
			},
			{ jsAlsTs: true }
		);
	}

	test('CompareTabs reicht seinen echten Reiterwechsel als onJump an den Baustein', async () => {
		const hub = await vergleichsHub();
		const e = findeKomponenten(hub.ast, 'HubUebersicht');
		assert.equal(e.length, 1, 'CompareTabs bindet HubUebersicht nicht genau einmal ein');
		assert.equal(attributAusdruck(e[0], hub.quelle, 'onJump'), 'handleValueChange');
	});

	test('„Bearbeiten →" (Briefing-Zeitplan) der Versand-Karte schreibt wetter-metriken#versand', async () => {
		const spruenge: unknown[][] = [];
		const hu = await umgebungFuer(
			HUB_UEBERSICHT,
			{ ...OHNE_PROPS, context: 'vergleich', preset: vollerVergleich('c-1'), orte: [], onJump: (...a: unknown[]) => spruenge.push(a) },
			{ jsAlsTs: true }
		);
		// Knopf mit testid des Versand-Sprungs (Desktop) — gefunden ueber den AUSGEWERTETEN testid-Ausdruck.
		const versandKnoepfe = sprungKnoepfe(hu).filter((s) => s.testid === 'compare-hub-versand-edit');
		assert.equal(versandKnoepfe.length, 1, 'Vorbedingung: Knopf compare-hub-versand-edit vorhanden');
		(versandKnoepfe[0].ausloesen as () => void)();
		assert.equal(spruenge.length, 1, JSON.stringify(spruenge));

		const hub = await vergleichsHub();
		hub.u.activeTab = 'uebersicht';
		schreibungen = [];
		await (hub.u.handleValueChange as (...a: unknown[]) => Promise<void>)(...spruenge[0]);
		assert.equal(hub.u.activeTab, 'wetter-metriken');
		assert.equal(schreibungen.length, 1, JSON.stringify(schreibungen));
		assert.equal(ziel(schreibungen[0]).searchParams.get('tab'), 'wetter-metriken', schreibungen[0]);
		assert.equal(ziel(schreibungen[0]).hash, '#versand', schreibungen[0]);
	});

	test('jeder Reiter-Sprungknopf der Übersicht (Desktop und Mobil-Zeilen) schreibt eine Kennung ohne Legacy-Umweg', async () => {
		const spruenge: unknown[][] = [];
		const hu = await umgebungFuer(
			HUB_UEBERSICHT,
			{
				...OHNE_PROPS,
				context: 'vergleich',
				preset: vollerVergleich('c-1'),
				orte: [{ rank: 1, loc: { id: 'l1', name: 'A' } }],
				onJump: (...a: unknown[]) => spruenge.push(a)
			},
			{ jsAlsTs: true }
		);
		const springer = sprungKnoepfe(hu);
		assert.ok(springer.length >= 6, `Messaufbau: Sprungknoepfe nicht gefunden (${springer.length})`);
		const hub = await vergleichsHub();
		for (const k of springer) {
			spruenge.length = 0;
			(k.ausloesen as () => void)();
			assert.equal(spruenge.length, 1, `Knopf „${k.text}" springt nicht genau einmal`);
			hub.u.activeTab = 'uebersicht';
			schreibungen = [];
			await (hub.u.handleValueChange as (...a: unknown[]) => Promise<void>)(...spruenge[0]);
			assert.ok(schreibungen.length > 0, `Knopf „${k.text}": keine Adresse geschrieben`);
			for (const s of schreibungen) {
				const tab = ziel(s).searchParams.get('tab');
				assert.equal(resolveTab('vergleich', tab).legacy, false, `Knopf „${k.text}" → ${s}: Legacy-Kennung`);
				assert.equal(resolveTab('vergleich', tab).known, true, `Knopf „${k.text}" → ${s}: unbekannte Kennung`);
			}
		}
	});
});

/** Nicht gesetzte Props des Bausteins (die Saat muss jeden Bezeichner kennen). */
const OHNE_PROPS = { trip: undefined, status: undefined, saveController: undefined, children: undefined };

/** Alle Knoepfe des Bausteins, deren onclick `springe(...)` ruft — je {#each}-Eintrag einmal
 *  ausgewertet (die Schleifenvariable wird an den echten Eintrag gebunden). */
function sprungKnoepfe(hu: { ast: Knoten; quelle: string; u: Knoten }): Array<{ text: string; testid: unknown; ausloesen: unknown }> {
	const treffer: Array<{ text: string; testid: unknown; ausloesen: unknown }> = [];
	function lauf(n: unknown, umgebung: Knoten): void {
		if (n === null || typeof n !== 'object') return;
		if (Array.isArray(n)) return void n.forEach((k) => lauf(k, umgebung));
		const k = n as Knoten;
		if (k.type === 'EachBlock') {
			const eintraege = werte(ohneTypen(hu.quelle, k.expression), umgebung) as unknown[];
			eintraege.forEach((e, i) => {
				const u2 = Object.assign(Object.create(umgebung), { [k.context.name]: e });
				if (k.index) u2[k.index] = i;
				lauf(k.body, u2);
			});
			return;
		}
		// {#if}-Zweige: beide werden besucht (mobil UND Desktop).
		const a = k.type === 'RegularElement' && k.name === 'button'
			? ((k.attributes ?? []) as Knoten[]).find((x) => x.type === 'Attribute' && x.name === 'onclick')
			: undefined;
		if (a && a.value?.type === 'ExpressionTag' && hu.quelle.slice(a.value.expression.start, a.value.expression.end).includes('springe')) {
			const t = ((k.attributes ?? []) as Knoten[]).find((x) => x.type === 'Attribute' && x.name === 'data-testid');
			treffer.push({
				text: text(k),
				testid: t?.value?.type === 'ExpressionTag' ? werte(ohneTypen(hu.quelle, t.value.expression), umgebung) : attributText(k, 'data-testid'),
				ausloesen: werte(onclick(k, hu.quelle), umgebung)
			});
		}
		for (const key of Object.keys(k)) if (key !== 'parent' && key !== 'loc') lauf(k[key], umgebung);
	}
	lauf(hu.ast.fragment, hu.u);
	return treffer;
}

// ── AC-24: „Setup abschliessen" ──────────────────────────────────────────────

describe('#1743 AC-24: „Setup abschliessen" der Ortsvergleich-Detailseite oeffnet ?tab=wetter-metriken#versand', () => {
	test('Knopf ausloesen → Ziel ?tab=wetter-metriken#versand (ohne Legacy-Umweg)', async () => {
		adresszeile('/compare/c-1', 'uebersicht');
		const seite = await umgebungFuer(VERGLEICH_SEITE, { goto: gotoAufzeichnung }, { jsAlsTs: true });
		const knoepfe = knoepfeMitText(seite.ast, 'Setup abschließen');
		assert.equal(knoepfe.length, 1, 'genau ein „Setup abschließen"-Knopf erwartet');
		const vorher = (globalThis as Knoten).window.location.href;
		await (werte(onclick(knoepfe[0], seite.quelle), seite.u) as () => unknown)();
		const nachher = (globalThis as Knoten).window.location.href;
		const zielUrl = nachher !== vorher ? String(nachher) : schreibungen.at(-1);
		assert.ok(zielUrl, 'der Knopf hat kein Ziel angesteuert');
		assert.equal(ziel(zielUrl).searchParams.get('tab'), 'wetter-metriken', zielUrl);
		assert.equal(ziel(zielUrl).hash, '#versand', zielUrl);
		assert.equal(resolveTab('vergleich', ziel(zielUrl).searchParams.get('tab')).legacy, false);
	});
});

// ── AC-23 / AC-28: Cockpit-Schnellaktionen ──────────────────────────────────

describe('#1743 AC-23 / AC-28: Cockpit-Schnellaktionen — nur neue Kennungen, Versand per Anker, keine Vorschau', async () => {
	const { ast } = await umgebungFuer(HOME, {}, { jsAlsTs: true });
	const aktionen: Array<{ label: string; href: string }> = [];
	besuche(ast.fragment, (n) => {
		if (n.type === 'Component' && n.name === 'QuickAction')
			aktionen.push({ label: beschriftung(n, 'label'), href: attributText(n, 'href') ?? '' });
	});

	test('Messaufbau: Schnellaktionen fuer Trip und Vergleich gefunden', () => {
		assert.ok(aktionen.some((a) => a.href.startsWith('/trips/')), JSON.stringify(aktionen));
		assert.ok(aktionen.some((a) => a.href.startsWith('/compare/')), JSON.stringify(aktionen));
	});

	test('AC-28: keine Schnellaktion „Vorschau prüfen"', () => {
		const vorschau = aktionen.filter((a) => /Vorschau/.test(a.label));
		assert.deepEqual(vorschau, [], 'die Vorschau-Schnellaktion entfaellt ersatzlos');
	});

	test('AC-23: jede ?tab=-Kennung loest ohne Legacy auf', () => {
		for (const a of aktionen) {
			if (!a.href.includes('?tab=')) continue;
			const kind = a.href.startsWith('/trips/') ? 'trip' : 'vergleich';
			const tab = ziel(a.href).searchParams.get('tab');
			assert.equal(resolveTab(kind, tab).legacy, false, `${a.label}: ${a.href} laeuft ueber den Legacy-Umweg`);
			assert.equal(resolveTab(kind, tab).known, true, `${a.label}: ${a.href} ist keine bekannte Kennung`);
		}
	});

	test('AC-23: „Briefing-Zeitplan" (Trip und Vergleich) zielt auf ?tab=wetter-metriken#versand', () => {
		const zeitplan = aktionen.filter((a) => a.label === 'Briefing-Zeitplan');
		assert.equal(zeitplan.length, 2, `Trip- und Vergleich-Schnellaktion erwartet: ${JSON.stringify(zeitplan)}`);
		for (const a of zeitplan) {
			assert.equal(ziel(a.href).searchParams.get('tab'), 'wetter-metriken', a.href);
			assert.equal(ziel(a.href).hash, '#versand', a.href);
		}
	});
});

// ── AC-28: Uebersicht und Vergleichs-Hub ohne Vorschau-Sprung ─────────────────

describe('#1743 AC-28: HubOverview (gerendert) und CompareTabs ohne Vorschau-Sprung', () => {
	test('HubOverview: gerendertes HTML ohne „Vorschau öffnen", „Zeitplan bearbeiten" bleibt', async () => {
		const { render } = await import('svelte/server');
		const C = (await import(pathToFileURL(HUB_OVERVIEW).href)).default;
		const html = render(C, { props: { trip: TRIP } }).body.replace(/<!--.*?-->/g, '');
		assert.ok(html.includes('Zeitplan bearbeiten'), 'Messaufbau: Zeitplan-Sprung muss bleiben');
		assert.ok(!html.includes('Vorschau öffnen'), 'HubOverview zeigt noch „Vorschau öffnen"');
	});

	test('CompareTabs: kein Knopf „Vorschau prüfen →"', async () => {
		const { ast } = await umgebungFuer(VERGLEICH_HUB, { preset: vollerVergleich('c-1'), locations: [], orteCount: 3 }, { jsAlsTs: true });
		assert.deepEqual(knoepfeMitText(ast, 'Vorschau prüfen').map(text), []);
	});

	test('#2682 HubUebersicht (Übersicht beider Hubs): kein Knopf „Vorschau prüfen →"/„Vorschau öffnen"', async () => {
		const { ast } = await umgebungFuer(HUB_UEBERSICHT, { ...OHNE_PROPS, context: 'vergleich', preset: vollerVergleich('c-1'), orte: [] }, { jsAlsTs: true });
		assert.deepEqual(knoepfeMitText(ast, 'Vorschau').map(text), []);
	});
});
