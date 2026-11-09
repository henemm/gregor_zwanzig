// TDD RED — Issue #2794 S3a, Teil-PR 2: nie zwei WeatherMetricsTab-Instanzen zugleich,
// Uebergangsreiter Zustellung, Wertebereiche-Vorbelegung beim Anlegen.
// Spec: docs/specs/modules/feat_2794_s3a_teil2_leiste.md — AC-2.T2, AC-2.T4, §3, §4, §5
//
// Warum: die Zustellungs-Bloecke (Layout je Kanal, Ausblick, Mail-Inhalt, Nacht-Block,
// Stundenverlauf) teilen State und Speicher-Owner mit der Metrik-Auswahl im selben
// WeatherMetricsTab (WMT). Zwei gleichzeitig gemountete WMT-Instanzen ueberschreiben einander
// mit veraltetem Stand (Datenverlust, Analyse-Befund 2). Deshalb: Hub mountet je Reiter, das
// Trip-Anlegen haelt EINE dauerhafte Instanz je Viewport-Zweig, deren `bereich` dem Schritt folgt.
//
// Messweise: AST-Struktur-Waechter nach Repo-Muster (compare_wetter_metriken_wertprops.test.ts,
// trip_new_mail_inhalt_karte_genau_eine_instanz.test.ts) ueber alle WMT-Traeger
// (WeatherMetricsTab, WetterMetrikenVersandPanel, ZustellungTab): unter welcher Weiche steht
// welche Einbettung, schliessen sich je zwei gegenseitig aus. Wo ein Ausdruck vom Schritt
// abhaengt (`bereich`, `style:display`), wird er gegen das ECHTE Instanz-Skript des Editors
// mit vorbelegtem Schritt ausgewertet (svelteInstanzPruefstand.umgebungFuer), nicht gelesen.
// Die Browser-Haelfte (Zahl der WMT-Wurzelknoten nach jedem Wechsel) ist Playwright (/e2e-verify).
//
// RED heute: kein ZustellungTab, keine Kennungen wetter/zustellung, kein Prop `bereich`.
// Regressionswaechter (heute gruen): AC-2.T4 Wartebedingung `wertebereicheVorbelegt`.
//
// Ausfuehren (aus frontend/):
//   npm test -- src/lib/components/shared/__tests__/s3a2794_eine_wmt_instanz.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import {
	svelteAst,
	existiert,
	einbettungenMitWeichen,
	reiterVon,
	haengtAnActiveTabWeiche,
	viewportVon,
	schliessenSichAus,
	attribut,
	displayAusdruck,
	elementeMitId,
	propNamen,
	aufrufe,
	type Einbettung,
	type Knoten
} from './s3a2794Ast.ts';
import { umgebungFuer, werte } from './svelteInstanzPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '../../../../..');
const KOMP = join(HIER, '..', '..');
register(
	pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const DATEI = {
	tripHub: join(KOMP, 'trip-detail', 'TripTabs.svelte'),
	vergleichHub: join(KOMP, 'compare', 'CompareTabs.svelte'),
	tripNeu: join(KOMP, 'trip-new', 'TripNewEditor.svelte'),
	vergleichNeu: join(KOMP, 'compare-new', 'CompareNewEditor.svelte'),
	zustellung: join(KOMP, 'shared', 'zustellung-tab', 'ZustellungTab.svelte'),
	panel: join(KOMP, 'shared', 'WetterMetrikenVersandPanel.svelte'),
	wmt: join(KOMP, 'shared', 'WeatherMetricsTab.svelte')
};

const WMT_TRAEGER = ['WeatherMetricsTab', 'WetterMetrikenVersandPanel', 'ZustellungTab'];

const traeger = (datei: string): { e: Einbettung[]; quelle: string; ast: Knoten } => {
	const { ast, quelle } = svelteAst(datei);
	return { e: einbettungenMitWeichen(ast, quelle, WMT_TRAEGER), quelle, ast };
};

const beschreibe = (e: Einbettung, quelle: string) =>
	`${e.name}@${quelle.slice(0, e.knoten.start).split('\n').length} [${e.weichen.map((w) => `${w.zweig}:${w.test}`).join(' > ')}]`;

function paarweiseExklusiv(e: Einbettung[], quelle: string, wo: string): void {
	for (let i = 0; i < e.length; i++) {
		for (let j = i + 1; j < e.length; j++) {
			assert.ok(
				schliessenSichAus(e[i], e[j]),
				`AC-2.T2 ${wo}: zwei WMT-Träger können zugleich gemountet sein: ${beschreibe(e[i], quelle)} und ${beschreibe(e[j], quelle)}`
			);
		}
	}
}

/** Bereich einer Einbettung: Literal oder (bei Zustellungs-Baustein) implizit 'zustellung'. */
function bereichLiteral(e: Einbettung, quelle: string): string | null {
	if (e.name === 'ZustellungTab') return 'zustellung';
	return attribut(e.knoten, quelle, 'bereich')?.literal ?? null;
}

// ── Hubs ─────────────────────────────────────────────────────────────────────

for (const [kind, datei, ctx] of [
	['trip', DATEI.tripHub, 'route'],
	['vergleich', DATEI.vergleichHub, 'vergleich']
] as const) {
	describe(`AC-2.T2 Hub ${kind}: je Reiter höchstens eine WMT-Instanz`, () => {
		test(`s3a2794_t2_hub_${kind}_wmt_traeger_nur_unter_wetter_oder_zustellung`, () => {
			const { e, quelle } = traeger(datei);
			assert.ok(e.length > 0, 'Messaufbau: kein WMT-Träger im Hub gefunden');
			for (const x of e) {
				const r = reiterVon(x);
				assert.ok(
					r.length > 0 && r.every((t) => t === 'wetter' || t === 'zustellung'),
					`AC-2.T2: ${beschreibe(x, quelle)} hängt nicht (nur) am Reiter wetter/zustellung (Reiter: ${JSON.stringify(r)})`
				);
			}
		});

		test(`s3a2794_t2_hub_${kind}_wmt_traeger_paarweise_exklusiv`, () => {
			const { e, quelle } = traeger(datei);
			paarweiseExklusiv(e, quelle, `Hub ${kind}`);
		});

		test(`s3a2794_t2_hub_${kind}_reiter_wetter_zeigt_wmt_mit_bereich_wetter`, () => {
			const { e, quelle } = traeger(datei);
			const w = e.filter((x) => reiterVon(x).includes('wetter'));
			assert.ok(w.length >= 1, 'Reiter wetter ohne Metrik-Oberfläche');
			for (const x of w) assert.equal(bereichLiteral(x, quelle), 'wetter', `${beschreibe(x, quelle)}: bereich ≠ 'wetter'`);
		});

		test(`s3a2794_t2_hub_${kind}_reiter_zustellung_bettet_zustellungtab_mit_context_${ctx}`, () => {
			const { e, quelle } = traeger(datei);
			const z = e.filter((x) => x.name === 'ZustellungTab');
			assert.equal(z.length, 1, `erwartet genau eine ZustellungTab-Einbettung, gefunden ${z.length}`);
			assert.deepEqual(reiterVon(z[0]), ['zustellung'], `${beschreibe(z[0], quelle)} hängt nicht am Reiter zustellung`);
			assert.equal(attribut(z[0].knoten, quelle, 'context')?.literal, ctx, 'ZustellungTab: falscher context');
		});

		test(`s3a2794_t2_hub_${kind}_reiter_wetter_zeigt_wertebereiche_lesend_darunter`, () => {
			const { ast, quelle } = svelteAst(datei);
			const c = einbettungenMitWeichen(ast, quelle, ['CorridorEditor', 'CorridorEditorMobile']);
			assert.ok(c.length >= 1, 'keine Wertebereiche-Ansicht im Hub');
			for (const x of c) {
				assert.deepEqual(reiterVon(x), ['wetter'], `${beschreibe(x, quelle)}: Wertebereiche-Ansicht nicht unter dem Reiter wetter`);
			}
		});
	});
}

// ── ZustellungTab (neu, shared, context="route"|"vergleich") ──────────────────

describe('§3: shared/zustellung-tab/ZustellungTab.svelte — Übergangsreiter', () => {
	test('s3a2794_zustellung_baustein_existiert_mit_context_prop', () => {
		assert.ok(existiert(DATEI.zustellung), 'shared/zustellung-tab/ZustellungTab.svelte fehlt');
		const { ast } = svelteAst(DATEI.zustellung);
		assert.ok(propNamen(ast).includes('context'), `ZustellungTab: keine Prop context (Props: ${propNamen(ast).join(', ')})`);
	});

	test('s3a2794_zustellung_genau_ein_wmt_traeger_mit_bereich_zustellung', () => {
		assert.ok(existiert(DATEI.zustellung), 'ZustellungTab.svelte fehlt');
		const { e, quelle } = traeger(DATEI.zustellung);
		assert.ok(e.length >= 1, 'ZustellungTab zeigt keine Zustellungs-Blöcke der Metrik-Oberfläche');
		paarweiseExklusiv(e, quelle, 'ZustellungTab');
		for (const x of e) assert.equal(bereichLiteral(x, quelle), 'zustellung', `${beschreibe(x, quelle)}: bereich ≠ 'zustellung'`);
	});

	test('s3a2794_zustellung_enthaelt_section_versand', () => {
		assert.ok(existiert(DATEI.zustellung), 'ZustellungTab.svelte fehlt');
		const { ast, quelle } = svelteAst(DATEI.zustellung);
		const eigen = elementeMitId(ast, quelle, 'section', 'versand').length;
		const panelMitZustellung = einbettungenMitWeichen(ast, quelle, ['WetterMetrikenVersandPanel']).some(
			(x) => attribut(x.knoten, quelle, 'bereich')?.literal === 'zustellung'
		);
		const { ast: pAst, quelle: pQ } = svelteAst(DATEI.panel);
		const panelSection = elementeMitId(pAst, pQ, 'section', 'versand').length > 0;
		assert.ok(
			eigen > 0 || (panelMitZustellung && panelSection),
			'Zustellung: kein <section id="versand"> (Sprungziel #versand) — weder im Baustein noch über das Panel mit bereich=zustellung'
		);
	});

	test('s3a2794_zustellung_enthaelt_alarmetab_vollstaendig', () => {
		assert.ok(existiert(DATEI.zustellung), 'ZustellungTab.svelte fehlt');
		const { ast, quelle } = svelteAst(DATEI.zustellung);
		const a = einbettungenMitWeichen(ast, quelle, ['AlarmeTab', 'AlarmeScheduleTab']);
		assert.ok(a.length >= 1, 'ZustellungTab bettet weder AlarmeTab noch die Hülle AlarmeScheduleTab ein');
	});
});

describe('§2: Panel und WeatherMetricsTab tragen den bereich-Filter', () => {
	test('s3a2794_panel_versand_abschnitt_nur_bei_bereich_zustellung', () => {
		const { ast, quelle } = svelteAst(DATEI.panel);
		const s = elementeMitId(ast, quelle, 'section', 'versand');
		for (const x of s) {
			assert.ok(
				x.weichen.some((w) => /\bbereich\b/.test(w.test)),
				'Panel: <section id="versand"> steht nicht unter einer bereich-Weiche — Versand erschiene auch im Reiter wetter'
			);
		}
	});

	test('s3a2794_panel_reicht_bereich_an_wmt_durch', () => {
		const { ast, quelle } = svelteAst(DATEI.panel);
		const wmt = einbettungenMitWeichen(ast, quelle, ['WeatherMetricsTab']);
		assert.equal(wmt.length, 1, 'Panel: genau eine WeatherMetricsTab-Einbettung erwartet');
		const explizit = attribut(wmt[0].knoten, quelle, 'bereich') !== null;
		const perStreuung =
			(wmt[0].knoten.attributes as Knoten[]).some((a) => a.type === 'SpreadAttribute') && !propNamen(ast).includes('bereich');
		assert.ok(explizit, `Panel: WeatherMetricsTab bekommt kein bereich-Attribut (Streuung ohne eigenes bereich: ${perStreuung})`);
	});

	test('s3a2794_wmt_leitet_abschnitte_aus_context_und_bereich_ab', () => {
		const { ast, quelle } = svelteAst(DATEI.wmt);
		assert.ok(propNamen(ast).includes('bereich'), 'WeatherMetricsTab: keine Prop bereich');
		const a = aufrufe(ast.instance?.content).filter((c) => c.callee?.name === 'weatherMetricsTabSections');
		assert.ok(a.length >= 1, 'WeatherMetricsTab ruft weatherMetricsTabSections nicht auf');
		assert.ok(
			a.some((c) => (c.arguments as Knoten[]).length === 2 && quelle.slice(c.arguments[1].start, c.arguments[1].end) === 'bereich'),
			'WeatherMetricsTab: weatherMetricsTabSections(context, bereich) — bereich wird nicht übergeben'
		);
	});
});

// ── Trip-Anlegen: EINE dauerhafte WMT-Instanz je Viewport-Zweig ───────────────

async function editorUmgebung(activeTab: string): Promise<Knoten> {
	const { u } = await umgebungFuer(
		DATEI.tripNeu,
		{ stateOverride: { activeTab, isMobileViewport: false }, untrack: (fn: () => unknown) => fn() },
		{ jsAlsTs: true }
	);
	return u;
}

async function werteImSchritt(ausdruck: string, schritt: string): Promise<unknown> {
	const u = await editorUmgebung(schritt);
	assert.equal(u.activeTab, schritt, `Prüfstand: stateOverride.activeTab='${schritt}' greift nicht (activeTab=${String(u.activeTab)})`);
	return werte(ausdruck, u);
}

describe('AC-2.T2 Trip-Anlegen (TripNewEditor): eine dauerhafte WMT-Instanz je Viewport-Zweig', () => {
	test('s3a2794_t2_trip_neu_genau_zwei_wmt_traeger_desktop_xor_mobil_dauerhaft', () => {
		const { e, quelle } = traeger(DATEI.tripNeu);
		assert.equal(e.length, 2, `erwartet 2 WMT-Träger (Desktop + Mobil), gefunden: ${e.map((x) => beschreibe(x, quelle)).join(' | ')}`);
		assert.deepEqual(e.map(viewportVon).sort(), ['desktop', 'mobil']);
		for (const x of e) {
			assert.ok(!haengtAnActiveTabWeiche(x), `${beschreibe(x, quelle)}: hängt an einer activeTab-Weiche (Remount verliert Anlege-Zustand, #932)`);
		}
		paarweiseExklusiv(e, quelle, 'TripNewEditor');
	});

	for (const schritt of ['wetter', 'zustellung']) {
		test(`s3a2794_t2_trip_neu_bereich_folgt_dem_schritt_${schritt}`, async () => {
			const { e, quelle } = traeger(DATEI.tripNeu);
			assert.ok(e.length > 0, 'kein WMT-Träger');
			for (const x of e) {
				const b = attribut(x.knoten, quelle, 'bereich');
				assert.ok(b?.ausdruck, `${beschreibe(x, quelle)}: bereich fehlt oder ist fest (${JSON.stringify(b)}) — muss dem Schritt folgen`);
				assert.equal(await werteImSchritt(b!.ausdruck!, schritt), schritt, `${beschreibe(x, quelle)}: bereich im Schritt ${schritt}`);
			}
		});
	}

	test('s3a2794_t2_trip_neu_wmt_sichtbar_nur_in_wetter_und_zustellung', async () => {
		const { e, quelle } = traeger(DATEI.tripNeu);
		assert.ok(e.length > 0, 'kein WMT-Träger');
		for (const x of e) {
			const d = displayAusdruck(x, quelle);
			assert.ok(d, `${beschreibe(x, quelle)}: keine style:display-Hülle (Muster #932)`);
			for (const s of ['wetter', 'zustellung']) assert.equal(await werteImSchritt(d!, s), '', `sichtbar im Schritt ${s}`);
			for (const s of ['route', 'etappen', 'wegpunkte']) assert.equal(await werteImSchritt(d!, s), 'none', `verborgen im Schritt ${s}`);
		}
	});

	test('s3a2794_t4_trip_neu_corridor_editor_dauerhaft_im_schritt_wetter', async () => {
		const { ast, quelle } = svelteAst(DATEI.tripNeu);
		const c = einbettungenMitWeichen(ast, quelle, ['CorridorEditor', 'CorridorEditorMobile']);
		assert.equal(c.length, 2, `CorridorEditor (createMode): erwartet Desktop + Mobil, gefunden ${c.length}`);
		for (const x of c) {
			assert.ok(!haengtAnActiveTabWeiche(x), `${beschreibe(x, quelle)}: nicht dauerhaft gemountet — Vorbelegung liefe nicht`);
			assert.ok(attribut(x.knoten, quelle, 'onVorbelegungFertig'), `${beschreibe(x, quelle)}: onVorbelegungFertig fehlt`);
			const d = displayAusdruck(x, quelle);
			assert.ok(d, `${beschreibe(x, quelle)}: keine style:display-Hülle`);
			assert.equal(await werteImSchritt(d!, 'wetter'), '', 'Wertebereiche-Vorbelegung im Schritt wetter nicht sichtbar');
			for (const s of ['route', 'zustellung']) assert.equal(await werteImSchritt(d!, s), 'none', `Wertebereiche sichtbar im Schritt ${s}`);
		}
	});
});

describe('AC-2.T4 (Regressionswächter): „Mit Standardwerten speichern" wartet auf wertebereicheVorbelegt', () => {
	function defaultsBereitAusdruck(): string {
		const { ast, quelle } = svelteAst(DATEI.tripNeu);
		let gefunden: string | null = null;
		(function lauf(n: unknown): void {
			if (gefunden || n === null || typeof n !== 'object') return;
			if (Array.isArray(n)) return n.forEach(lauf);
			const k = n as Knoten;
			if (k.type === 'Property' && k.key?.name === 'defaultsBereit') {
				gefunden = quelle.slice(k.value.start, k.value.end);
				return;
			}
			for (const [f, v] of Object.entries(k)) if (f !== 'parent' && f !== 'loc' && f !== 'metadata') lauf(v);
		})(ast.instance?.content);
		assert.ok(gefunden, 'TripNewEditor: kein defaultsBereit an canFinishMitStandardwerten');
		return gefunden!;
	}

	test('s3a2794_t4_standardwerte_gesperrt_bis_vorbelegung_fertig', () => {
		const a = defaultsBereitAusdruck();
		const metrik = [{ metric_id: 'temperature' }];
		assert.equal(werte(a, { catalogLoaded: true, wertebereicheVorbelegt: false, weatherMetrics: metrik }), false, 'frei, obwohl die Vorbelegung noch läuft');
		assert.equal(werte(a, { catalogLoaded: true, wertebereicheVorbelegt: true, weatherMetrics: metrik }), true, 'nach Vorbelegung nicht frei');
		assert.equal(werte(a, { catalogLoaded: false, wertebereicheVorbelegt: true, weatherMetrics: metrik }), false, 'frei ohne Katalog');
	});
});

// Fix-Loop 1 (Adversary F005, Mutation M6): die Vorbelegung muss im Anlege-PAYLOAD ankommen —
// gemessen am POST, den der ECHTE Editor nach der Meldung des CorridorEditors im Schritt wetter
// abschickt (Muster standardwerte_wartet_auf_wertebereiche_vorbelegung.test.ts), fuer
// „Speichern" UND „Mit Standardwerten speichern".
describe('AC-2.T4 (F005): das neue Abo enthält die Wertebereiche-Vorbelegung (corridors) im Anlege-Payload', () => {
	const VORBELEGUNG = [{ metric: 'wind_gust', range: [null, 70], notify: true, mark: false }];

	async function editorMitVorbelegung(): Promise<{ e: Knoten; posts: Array<{ url: string; body: Knoten }> }> {
		const { editorUmgebung: eu, derivedNeu, TRIP_EDITOR } = await import('./standardwerteEditorPruefstand.ts');
		const posts: Array<{ url: string; body: Knoten }> = [];
		const e = await eu(TRIP_EDITOR, {
			stateOverride: { activeTab: 'wetter', isMobileViewport: false },
			name: 'Trip X',
			startDate: '2026-07-01',
			stages: [1, 2].map((id) => ({ id, name: `E${id}`, gpx: { file: 'a.gpx', km: 10, asc: 500 }, waypoints: [] })),
			catalogLoaded: true,
			weatherMetrics: [{ metric_id: 'gust', enabled: true }],
			api: { post: async (url: string, body: Knoten) => (posts.push({ url, body }), { id: 'neu-1' }), get: async () => ({}) }
		});
		// Der CorridorEditor, der im Schritt wetter sichtbar ist (Desktop-Zweig), meldet seine Vorbelegung.
		const { ast, quelle } = svelteAst(DATEI.tripNeu);
		const c = einbettungenMitWeichen(ast, quelle, ['CorridorEditor']).find((x) => viewportVon(x) !== 'mobil');
		assert.ok(c, 'Messaufbau: kein Desktop-CorridorEditor im Trip-Anlegen');
		const d = displayAusdruck(c!, quelle);
		assert.equal(d ? werte(d, e.u) : '', '', 'Messaufbau: der CorridorEditor ist im Schritt wetter nicht sichtbar');
		for (const name of ['onCorridorsChange', 'onVorbelegungFertig']) {
			const a = attribut(c!.knoten, quelle, name);
			assert.ok(a?.ausdruck, `F005: CorridorEditor ohne ${name}`);
			const fn = werte(a!.ausdruck!, e.u) as (...x: unknown[]) => unknown;
			if (name === 'onCorridorsChange') fn(VORBELEGUNG);
			else fn();
		}
		derivedNeu(e);
		return { e, posts };
	}

	test('s3a2794_t4_speichern_traegt_corridors_im_payload', async () => {
		const { e, posts } = await editorMitVorbelegung();
		e.u.ready = true; // alle Pflichtschritte erfuellt — Gegenstand ist allein der Payload
		await (e.u.buildAndSave as (m?: boolean) => Promise<unknown>)(false);
		assert.equal(posts.length, 1, 'Messaufbau: „Speichern" hat nicht genau einmal gepostet');
		assert.equal(posts[0].url, '/api/trips');
		assert.deepEqual(posts[0].body.corridors, VORBELEGUNG, 'AC-2.T4 FAIL: der Anlege-POST traegt die Wertebereiche-Vorbelegung (corridors) nicht');
	});

	test('s3a2794_t4_mit_standardwerten_traegt_corridors_im_payload', async () => {
		const { e, posts } = await editorMitVorbelegung();
		assert.equal(e.u.standardwerteFrei, true, 'Messaufbau: „Mit Standardwerten speichern" nach der Vorbelegung nicht frei');
		await (e.u.buildAndSave as (m?: boolean) => Promise<unknown>)(true);
		assert.equal(posts.length, 1, 'Messaufbau: „Mit Standardwerten speichern" hat nicht genau einmal gepostet');
		assert.deepEqual(posts[0].body.corridors, VORBELEGUNG, 'AC-2.T4 FAIL: der Standardwerte-POST traegt die Vorbelegung (corridors) nicht');
	});
});

// ── Vergleich-Anlegen: if-Kette, je Schritt höchstens eine Instanz ────────────

describe('AC-2.T2 Vergleich-Anlegen (CompareNewEditor): Schritte wetter/zustellung, nie zwei Instanzen', () => {
	test('s3a2794_t2_vergleich_neu_wmt_traeger_nur_in_wetter_oder_zustellung_und_exklusiv', () => {
		const { e, quelle } = traeger(DATEI.vergleichNeu);
		assert.ok(e.length > 0, 'kein WMT-Träger');
		for (const x of e) {
			const r = reiterVon(x);
			assert.ok(r.length > 0 && r.every((t) => t === 'wetter' || t === 'zustellung'), `${beschreibe(x, quelle)}: Schritt ${JSON.stringify(r)}`);
		}
		paarweiseExklusiv(e, quelle, 'CompareNewEditor');
	});

	for (const schritt of ['wetter', 'zustellung']) {
		test(`s3a2794_t2_vergleich_neu_schritt_${schritt}_zeigt_bereich_${schritt}`, () => {
			const { e, quelle } = traeger(DATEI.vergleichNeu);
			const s = e.filter((x) => reiterVon(x).includes(schritt));
			assert.ok(s.length >= 1, `Schritt ${schritt} ohne Metrik-Oberfläche`);
			for (const x of s) assert.equal(bereichLiteral(x, quelle), schritt, `${beschreibe(x, quelle)}: bereich`);
		});
	}

	test('s3a2794_t2_vergleich_neu_alarme_im_schritt_zustellung', () => {
		const { ast, quelle } = svelteAst(DATEI.vergleichNeu);
		const direkt = einbettungenMitWeichen(ast, quelle, ['AlarmeTab']).filter((x) => reiterVon(x).includes('zustellung'));
		const ueberBaustein = einbettungenMitWeichen(ast, quelle, ['ZustellungTab']).filter((x) => reiterVon(x).includes('zustellung'));
		assert.ok(direkt.length + ueberBaustein.length >= 1, 'Alarm-Einstellungen im Schritt zustellung fehlen');
	});
});
