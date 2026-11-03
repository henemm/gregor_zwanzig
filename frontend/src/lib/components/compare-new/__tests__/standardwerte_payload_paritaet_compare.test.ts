// TDD RED — Onboarding S3 (Issue #2521), AC-7 + AC-8: „Mit Standardwerten
// speichern" im Ortsvergleich belegt die Wertebereiche genau so vor wie ein
// unveraenderter Besuch des Wertebereiche-Reiters — und ueberschreibt nie, was
// der Nutzer dort schon geaendert hat.
// Spec: docs/specs/modules/onboarding_standardwerte_hilfe.md
//
// VERGLEICHSMASSSTAB (nicht tautologisch): Was der ECHTE `CorridorEditor.svelte`
// (context="vergleich", Prop-Buendel `corridorPropsAus(feldsatz)` wie in
// CompareNewEditor) beim Mount ueber `syncToWizard` in den Feldsatz
// schreibt — sein Lade-`$effect` wird gegen das echte Instanz-Skript ausgefuehrt
// (svelteInstanzPruefstand.ts). Dieser Test ruft `buildComparePrefillRows` /
// `buildCompareCorridorSavePayload` NIE selbst auf.
//
// STANDARDWERTE-WEG: der Klick-Handler der ECHTEN `<StandardwerteSpeichernKnopf>`-
// Einbettung in CompareNewEditor.svelte, ausgewertet gegen dessen Instanz-Skript.
//
// Umgebaut fuer Issue #2727 (Epic #2345, DoD-1) — Spec
// docs/specs/modules/feat_2727_compare_wizardstate_abloesen.md, AC-8/AC-22: der Editor haelt
// seinen Zustand selbst (kein Context, keine Klasse mit `saveNewPreset`). Gemessen wird deshalb
// der tatsaechlich gesendete Create-Request (`POST /api/compare/presets`, Netzgrenze fetch); der
// Referenzwert des Reiter-Besuchs wird ueber DIESELBE Payload-Funktion
// (`buildNewComparePresetPayload`) in dasselbe Format gebracht, damit beide Seiten vergleichbar
// sind. Name/Orte/Profil reisen ueber `stateOverride`; Nutzer-Aenderungen im Wertebereiche-Reiter
// (AC-8) ueber die Rueckrufe des Prop-Buendels, das der Editor selbst an `<CorridorEditor>` haengt.
// Heute rot: ohne Context hat der Editor keinen Zustand (VERTRAG FEHLT).
//
// Netzgrenze: `globalThis.fetch`. GET /api/compare/metrics = LIVE-Katalog aus dem
// Python-Kern (Muster compareMetricCatalogParity.test.ts).
//
// Mutationen, die rot werden muessen (Spec): „Profil-Rueckfall 'wandern' statt
// Prefill-Profil", „Vorbelegung uebersprungen" (AC-7), „Vorbelegung immer
// anwenden" (AC-8).
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/compare-new/__tests__/standardwerte_payload_paritaet_compare.test.ts

import { test, describe, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { neuerFeldsatz } from '../../shared/__tests__/compareFeldsatzPruefstand.ts';
import { buendelAus, MATCH_MEDIA, VERTRAG_FEHLT_EDITOR } from '../../shared/__tests__/compareNeuEditorPruefstand.ts';
import { effekteVon, type Knoten } from '../../shared/__tests__/svelteInstanzPruefstand.ts';
import {
	COMPARE_EDITOR,
	editorUmgebung,
	mountenUndWarten,
	derivedNeu,
	knopfEinbettungen,
	knopfAttribut,
	ruhe
} from '../../shared/__tests__/standardwerteEditorPruefstand.ts';
import { corridorPropsAus } from '../../compare/corridorPropsAus.ts';
import { buildNewComparePresetPayload } from '../../compare/compareEditorSave.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const CORRIDOR_EDITOR = join(HIER, '..', '..', 'shared', 'corridor-editor', 'CorridorEditor.svelte');
const REPO_ROOT = resolve(HIER, ...Array(6).fill('..'));
const PY =
	'import sys, json\n' +
	"sys.path.insert(0, 'src')\n" +
	'from output.renderers.compare_metric_catalog import get_compare_metric_catalog\n' +
	"print(json.dumps({'metrics': get_compare_metric_catalog()}))\n";
const KATALOG = JSON.parse(
	execFileSync('uv', ['run', 'python3', '-c', PY], { cwd: REPO_ROOT, encoding: 'utf-8' }).trim()
);

const presetPosts: Knoten[] = [];
let originalFetch: typeof globalThis.fetch;
before(() => {
	originalFetch = globalThis.fetch;
	globalThis.fetch = (async (input: unknown, init?: { method?: string; body?: unknown }) => {
		const url = String(input);
		if (url.includes('/api/compare/presets') && (init?.method ?? 'GET').toUpperCase() === 'POST') {
			presetPosts.push(JSON.parse(String(init?.body)) as Knoten);
			return new Response(JSON.stringify({ id: 'cmp-std' }), { status: 201, headers: { 'content-type': 'application/json' } });
		}
		const body = url.includes('/api/compare/metrics') ? JSON.stringify(KATALOG) : '[]';
		return new Response(body, { status: 200, headers: { 'content-type': 'application/json' } });
	}) as typeof globalThis.fetch;
});
after(() => {
	globalThis.fetch = originalFetch;
});

const FELDER = ['corridors', 'idealRanges', 'activeMetricKeys', 'metricAlertLevels'] as const;
type Wertebereiche = Record<(typeof FELDER)[number], unknown>;
const klon = <T>(v: T): T => JSON.parse(JSON.stringify(v));
const auszug = (wiz: Knoten): Wertebereiche =>
	klon(Object.fromEntries(FELDER.map((f) => [f, wiz[f]])) as Wertebereiche);

/** Die Wertebereiche-Anteile eines Create-Körpers (Format des POST). */
function wertebereicheImKoerper(b: Knoten): Knoten {
	const dc = (b.display_config as Knoten) ?? {};
	return klon({
		corridors: b.corridors,
		ideal_ranges: dc.ideal_ranges ?? {},
		active_metrics: dc.active_metrics ?? null,
		metric_alert_levels: dc.metric_alert_levels ?? {}
	});
}

/** Referenz im POST-Format: dieselbe Payload-Funktion wie der Editor. */
function alsKoerper(w: Wertebereiche): Knoten {
	return wertebereicheImKoerper(buildNewComparePresetPayload({ ...neuerFeldsatz(), ...klon(w) } as never));
}

/** Wertebereiche nach UNVERAENDERTEM Besuch des Reiters (echter CorridorEditor). */
async function nachReiterBesuch(activityProfile: string | null): Promise<Wertebereiche> {
	const wiz = neuerFeldsatz({ name: 'Ref', pickedIds: ['loc0', 'loc1'], activityProfile });
	const ohneWert = Object.fromEntries(
		['trip', 'onTripUpdate', 'saveController', 'preset', 'enqueueHubWrite', 'onCompareUpdate'].map((k) => [k, undefined])
	);
	const e = await editorUmgebung(CORRIDOR_EDITOR, {
		...ohneWert,
		context: 'vergleich',
		showInfobox: true,
		...corridorPropsAus(wiz)
	});
	const effekte = effekteVon(e.ast, e.quelle, e.u, 'loadCompareMetricCatalog');
	assert.ok(effekte.length >= 1, 'Messaufbau kaputt: Lade-$effect des CorridorEditor nicht gefunden');
	for (const fn of effekte) fn();
	await ruhe();
	const w = auszug(wiz);
	assert.ok(Array.isArray(w.corridors) && (w.corridors as unknown[]).length > 0, 'Messaufbau kaputt: Reiter-Besuch hat nichts vorbelegt');
	return w;
}

/** Anlege-Editor ohne Context; Name/Orte/Profil ueber stateOverride. */
async function anlegeEditor(eingaben: Knoten, besucht: { metriken?: boolean; ideals?: boolean } = {}) {
	const e = await editorUmgebung(COMPARE_EDITOR, {
		stateOverride: {
			activeTab: besucht.ideals ? 'wertebereiche' : 'vergleich',
			isMobileViewport: false,
			metrikenVisited: !!besucht.metriken,
			idealsVisited: !!besucht.ideals,
			alarmeVisited: false,
			versandVisited: false,
			...eingaben
		},
		window: MATCH_MEDIA
	});
	return e;
}

/** Create-Koerper, den der Standardwerte-Klick sendet. */
async function nachStandardwerteKlick(
	eingaben: Knoten,
	besucht: { metriken?: boolean; ideals?: boolean } = {},
	nutzer?: Wertebereiche
): Promise<{ gesendet: Knoten[] }> {
	presetPosts.length = 0;
	const e = await anlegeEditor({ name: 'Std', pickedIds: ['loc0', 'loc1'], ...eingaben }, besucht);
	assert.equal(e.u.nameOk, true, VERTRAG_FEHLT_EDITOR);
	if (nutzer) {
		const b = buendelAus(e, 'CorridorEditor');
		(b.onCorridorsChange as (v: unknown) => void)(klon(nutzer.corridors));
		(b.onIdealRangesChange as (v: unknown) => void)(klon(nutzer.idealRanges));
		(b.onActiveMetricKeysChange as (v: unknown) => void)(klon(nutzer.activeMetricKeys));
		(b.onMetricAlertLevelsChange as (v: unknown) => void)(klon(nutzer.metricAlertLevels));
	}
	await mountenUndWarten(e);
	derivedNeu(e);
	const knoepfe = knopfEinbettungen(e.ast);
	assert.ok(knoepfe.length >= 1, 'CompareNewEditor bettet <StandardwerteSpeichernKnopf> nicht ein');
	assert.equal(Boolean(knopfAttribut(knoepfe[0], e, 'enabled')), true, 'Standardwerte-Knopf ist trotz Name, 2 Orten und geladenem Katalog nicht aktiv');
	await (knopfAttribut(knoepfe[0], e, 'onclick') as () => unknown)();
	await ruhe();
	return { gesendet: presetPosts.map(wertebereicheImKoerper) };
}

describe('AC-7: Standardwerte == unveraenderter Wertebereiche-Besuch (vorbelegt, nicht leer)', () => {
	test('Positivkontrolle: Profil-Vorbelegung ALLGEMEIN (kein Profil) unterscheidet sich von „wandern"', async () => {
		assert.notDeepEqual(await nachReiterBesuch(null), await nachReiterBesuch('wandern'));
	});

	test('ohne gewaehltes Profil: Wertebereiche, aktive Metriken und Alarmstufen gleich dem Reiter-Besuch', async () => {
		const ref = await nachReiterBesuch(null);
		const { gesendet } = await nachStandardwerteKlick({ activityProfile: null });
		assert.equal(gesendet.length, 1, `erwartet genau ein Speichern, gesehen ${gesendet.length}`);
		assert.deepEqual(gesendet[0], alsKoerper(ref));
	});

	test('mit Profil „wandern": gleich dem Reiter-Besuch mit demselben Profil', async () => {
		const ref = await nachReiterBesuch('wandern');
		const { gesendet } = await nachStandardwerteKlick({ activityProfile: 'wandern' });
		assert.equal(gesendet.length, 1);
		assert.deepEqual(gesendet[0], alsKoerper(ref));
	});

	test('nicht leer: der Standardwerte-Weg speichert Wertebereiche', async () => {
		const { gesendet } = await nachStandardwerteKlick({ activityProfile: null });
		assert.equal(gesendet.length, 1);
		assert.ok((gesendet[0].corridors as unknown[]).length > 0, 'Vorbelegung uebersprungen: corridors leer');
		assert.ok(Object.keys(gesendet[0].ideal_ranges as object).length > 0, 'Vorbelegung uebersprungen: ideal_ranges leer');
	});
});

describe('AC-8: besuchter, geaenderter Wertebereich bleibt erhalten', () => {
	test('Nutzer hat im Wertebereiche-Reiter einen Bereich geaendert: Standardwerte ueberschreiben ihn nicht', async () => {
		const ref = await nachReiterBesuch(null);
		const corridors = klon(ref.corridors) as Array<{ metric: string; range: [number | null, number | null]; notify: boolean; mark: boolean }>;
		corridors[0] = { ...corridors[0], range: [corridors[0].range[0], 999] };
		const nutzer: Wertebereiche = {
			corridors,
			idealRanges: { ...(ref.idealRanges as object), [corridors[0].metric]: { max: 999 } },
			activeMetricKeys: ref.activeMetricKeys,
			metricAlertLevels: ref.metricAlertLevels
		};
		const { gesendet } = await nachStandardwerteKlick({ activityProfile: null }, { metriken: true, ideals: true }, nutzer);
		assert.equal(gesendet.length, 1);
		assert.deepEqual(gesendet[0], alsKoerper(nutzer), 'Profil-Vorbelegung hat die Nutzerwerte ueberschrieben');
	});
});

// ── Adversary F002: Klick bei gesperrtem Gate (Katalog GELADEN, nur 1 Ort) ────
// Der Katalog ist da — damit greift allein der Gate-Guard des Klick-Handlers,
// nicht der Katalog-Guard.
describe('F002: Ortsvergleich — Klick bei gesperrtem Gate speichert nichts', () => {
	test('nur 1 Ort, Katalog geladen: Klick-Handler loest keinen POST aus und belegt nicht vor', async () => {
		presetPosts.length = 0;
		const e = await anlegeEditor({ name: 'Std', pickedIds: ['loc0'], activityProfile: null });
		assert.equal(e.u.nameOk, true, VERTRAG_FEHLT_EDITOR);
		await mountenUndWarten(e);
		derivedNeu(e);
		assert.ok(Array.isArray(e.u.standardwerteKatalog), 'Messaufbau: Vergleichs-Katalog nicht geladen');
		const knoepfe = knopfEinbettungen(e.ast);
		assert.ok(knoepfe.length >= 1);
		assert.equal(Boolean(knopfAttribut(knoepfe[0], e, 'enabled')), false, 'Messaufbau: Gate muss gesperrt sein');
		await (knopfAttribut(knoepfe[0], e, 'onclick') as () => unknown)();
		await ruhe();
		assert.equal(presetPosts.length, 0, 'Klick-Handler ignoriert das gesperrte Standardwerte-Gate');
		assert.deepEqual(buendelAus(e, 'CorridorEditor').corridors ?? [], [], 'Klick bei gesperrtem Gate hat trotzdem vorbelegt');
	});
});
