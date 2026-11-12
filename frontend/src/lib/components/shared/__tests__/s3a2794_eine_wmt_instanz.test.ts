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
import { umgebungFuer, werte, effekteVon } from './svelteInstanzPruefstand.ts';

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

		// Teil-PR 3 (AC-38): der Reiter wetter traegt statt der WMT mit bereich=wetter genau EINEN
		// WetterTab (eigener Speicherer); kein WMT-Traeger mehr unter wetter (sonst zwei Speicherer).
		test(`s3a2794_t2_hub_${kind}_reiter_wetter_zeigt_genau_einen_wettertab`, () => {
			const { e, quelle, ast } = traeger(datei);
			const w = e.filter((x) => reiterVon(x).includes('wetter'));
			assert.deepEqual(w.map((x) => beschreibe(x, quelle)), [], 'Reiter wetter: noch ein WMT-Träger');
			const wt = einbettungenMitWeichen(ast, quelle, ['WetterTab']).filter((x) => reiterVon(x).includes('wetter'));
			assert.equal(wt.length, 1, 'Reiter wetter ohne (genau einen) WetterTab');
			assert.equal(attribut(wt[0].knoten, quelle, 'context')?.literal, ctx, 'WetterTab: falscher context');
		});

		test(`s3a2794_t2_hub_${kind}_reiter_zustellung_bettet_zustellungtab_mit_context_${ctx}`, () => {
			const { e, quelle } = traeger(datei);
			const z = e.filter((x) => x.name === 'ZustellungTab');
			assert.equal(z.length, 1, `erwartet genau eine ZustellungTab-Einbettung, gefunden ${z.length}`);
			assert.deepEqual(reiterVon(z[0]), ['zustellung'], `${beschreibe(z[0], quelle)} hängt nicht am Reiter zustellung`);
			assert.equal(attribut(z[0].knoten, quelle, 'context')?.literal, ctx, 'ZustellungTab: falscher context');
		});

		// Teil-PR 3: die Grenzen zeigt (und bearbeitet) der WetterTab selbst; die Wertebereiche-Ansicht
		// ist im Hub nicht mehr gemountet (sonst zweiter Speicherer, AC-38) — und nirgends ausserhalb wetter.
		test(`s3a2794_t2_hub_${kind}_keine_wertebereiche_ansicht_mehr_im_hub`, () => {
			const { ast, quelle } = svelteAst(datei);
			const c = einbettungenMitWeichen(ast, quelle, ['CorridorEditor', 'CorridorEditorMobile']);
			assert.deepEqual(c.map((x) => beschreibe(x, quelle)), [], 'Hub: Wertebereiche-Ansicht noch gemountet');
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
	// Teil-PR 3: das Panel kennt keinen Bereich wetter mehr (der Reiter Wetter ist der WetterTab) —
	// die Zusicherung „Versand erscheint nie im Reiter wetter" wandert an die Schnittstelle: die Prop
	// `bereich` laesst nur 'zustellung' | 'alles' zu, der Versand-Abschnitt (#versand) bleibt Sprungziel.
	test('s3a2794_panel_versand_abschnitt_nie_im_bereich_wetter', () => {
		const { ast, quelle } = svelteAst(DATEI.panel);
		assert.equal(elementeMitId(ast, quelle, 'section', 'versand').length, 1, 'Panel: kein <section id="versand">');
		const literale: string[] = [];
		(function lauf(n: unknown): void {
			if (n === null || typeof n !== 'object') return;
			if (Array.isArray(n)) return n.forEach(lauf);
			const k = n as Knoten;
			if (k.type === 'TSPropertySignature' && k.key?.name === 'bereich') {
				(function typ(t: Knoten | undefined): void {
					if (!t) return;
					if (t.type === 'TSLiteralType') literale.push(String(t.literal.value));
					for (const u of (t.types ?? []) as Knoten[]) typ(u);
					typ(t.typeAnnotation);
				})(k.typeAnnotation);
			}
			for (const [f, v] of Object.entries(k)) if (f !== 'parent' && f !== 'loc' && f !== 'metadata') lauf(v);
		})(ast.instance?.content);
		assert.deepEqual(literale.sort(), ['alles', 'zustellung'], `Panel: bereich-Prop erlaubt ${JSON.stringify(literale)}`);
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

	// Teil-PR 3 (AC-38): die dauerhafte Instanz traegt fest den Bereich zustellung (Auswahl, Ampel,
	// Tagesfenster meldet allein der WetterTab) — nie bereich=wetter, in keinem Schritt.
	test('s3a2794_t2_trip_neu_bereich_fest_zustellung', () => {
		const { e, quelle } = traeger(DATEI.tripNeu);
		assert.ok(e.length > 0, 'kein WMT-Träger');
		for (const x of e) assert.equal(attribut(x.knoten, quelle, 'bereich')?.literal, 'zustellung', `${beschreibe(x, quelle)}: bereich ≠ 'zustellung'`);
	});

	test('s3a2794_t2_trip_neu_wmt_sichtbar_nur_in_zustellung_wettertab_nur_in_wetter', async () => {
		const { e, quelle, ast } = traeger(DATEI.tripNeu);
		assert.ok(e.length > 0, 'kein WMT-Träger');
		for (const x of e) {
			const d = displayAusdruck(x, quelle);
			assert.ok(d, `${beschreibe(x, quelle)}: keine style:display-Hülle (Muster #932)`);
			assert.equal(await werteImSchritt(d!, 'zustellung'), '', 'WMT im Schritt zustellung nicht sichtbar');
			for (const s of ['wetter', 'route', 'etappen', 'wegpunkte']) assert.equal(await werteImSchritt(d!, s), 'none', `WMT sichtbar im Schritt ${s}`);
		}
		const wt = einbettungenMitWeichen(ast, quelle, ['WetterTab']);
		assert.equal(wt.length, 2, 'WetterTab: erwartet Desktop + Mobil');
		for (const x of wt) {
			assert.ok(!haengtAnActiveTabWeiche(x), `${beschreibe(x, quelle)}: WetterTab nicht dauerhaft (Remount verliert den Anlege-Stand)`);
			const d = displayAusdruck(x, quelle);
			assert.ok(d, `${beschreibe(x, quelle)}: keine style:display-Hülle`);
			assert.equal(await werteImSchritt(d!, 'wetter'), '', 'WetterTab im Schritt wetter nicht sichtbar');
			for (const s of ['zustellung', 'route', 'etappen', 'wegpunkte']) assert.equal(await werteImSchritt(d!, s), 'none', `WetterTab sichtbar im Schritt ${s}`);
		}
	});

	// Teil-PR 3 (§6 d, Anlege-Vorbelegung) hielt den CorridorEditor unsichtbar dauerhaft gemountet;
	// seit Teil-PR 4a (AC-31/AC-43) laeuft die Vorbelegung als Effekt im Skript — es gibt keine
	// Wertebereiche-Ansicht mehr im Trip-Anlegen; die Grenzen bedient der WetterTab (genau ein Bedienort).
	test('s3a2794_t4_trip_neu_keine_wertebereiche_ansicht_mehr', () => {
		const { ast, quelle } = svelteAst(DATEI.tripNeu);
		const c = einbettungenMitWeichen(ast, quelle, ['CorridorEditor', 'CorridorEditorMobile']);
		assert.deepEqual(c.map((x) => beschreibe(x, quelle)), [], 'Trip-Anlegen: Wertebereiche-Ansicht noch eingebettet');
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
// gemessen am POST, den der ECHTE Editor nach seinem Vorbelegungs-Effekt (seit #2794 Teil-PR 4a
// statt der Meldung eines versteckten CorridorEditors) abschickt (Muster
// standardwerte_wartet_auf_wertebereiche_vorbelegung.test.ts), fuer „Speichern" UND
// „Mit Standardwerten speichern".
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
			routeExtraDefs: [], // Zusatz-Katalog geladen (leer: nur die fest verdrahteten Startwerte)
			api: { post: async (url: string, body: Knoten) => (posts.push({ url, body }), { id: 'neu-1' }), get: async () => ({}) }
		});
		// Der ECHTE Vorbelegungs-Effekt des Editors (einziger Effekt, der den Lauf nennt).
		const effekte = effekteVon(e.ast, e.quelle, e.u, 'vorbelegungsLauf');
		assert.equal(effekte.length, 1, `Messaufbau: ${effekte.length} Vorbelegungs-Effekte im Trip-Anlegen (erwartet genau 1)`);
		effekte[0]();
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

	test('s3a2794_t2_vergleich_neu_schritt_zustellung_zeigt_bereich_zustellung', () => {
		const { e, quelle } = traeger(DATEI.vergleichNeu);
		const s = e.filter((x) => reiterVon(x).includes('zustellung'));
		assert.ok(s.length >= 1, 'Schritt zustellung ohne Metrik-Oberfläche');
		for (const x of s) assert.equal(bereichLiteral(x, quelle), 'zustellung', `${beschreibe(x, quelle)}: bereich`);
	});

	// Teil-PR 3 (AC-38): der Schritt wetter zeigt den WetterTab (context vergleich) und keinen
	// WMT-Traeger mehr (sonst zwei Schreiber in denselben Feldsatz).
	test('s3a2794_t2_vergleich_neu_schritt_wetter_zeigt_wettertab', () => {
		const { e, quelle, ast } = traeger(DATEI.vergleichNeu);
		assert.deepEqual(e.filter((x) => reiterVon(x).includes('wetter')).map((x) => beschreibe(x, quelle)), [], 'Schritt wetter: noch ein WMT-Träger');
		const wt = einbettungenMitWeichen(ast, quelle, ['WetterTab']);
		assert.ok(wt.length >= 1, 'Schritt wetter ohne WetterTab');
		for (const x of wt) {
			assert.deepEqual(reiterVon(x), ['wetter'], `${beschreibe(x, quelle)}: nicht (nur) im Schritt wetter`);
			assert.equal(attribut(x.knoten, quelle, 'context')?.literal, 'vergleich', `${beschreibe(x, quelle)}: context`);
		}
	});

	test('s3a2794_t2_vergleich_neu_alarme_im_schritt_zustellung', () => {
		const { ast, quelle } = svelteAst(DATEI.vergleichNeu);
		const direkt = einbettungenMitWeichen(ast, quelle, ['AlarmeTab']).filter((x) => reiterVon(x).includes('zustellung'));
		const ueberBaustein = einbettungenMitWeichen(ast, quelle, ['ZustellungTab']).filter((x) => reiterVon(x).includes('zustellung'));
		assert.ok(direkt.length + ueberBaustein.length >= 1, 'Alarm-Einstellungen im Schritt zustellung fehlen');
	});
});
