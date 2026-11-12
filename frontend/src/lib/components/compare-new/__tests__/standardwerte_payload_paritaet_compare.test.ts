// TDD RED — Onboarding S3 (Issue #2521), AC-7 + AC-8: „Mit Standardwerten
// speichern" im Ortsvergleich belegt die Wertebereiche genau so vor wie ein
// unveraenderter Besuch des Wertebereiche-Reiters — und ueberschreibt nie, was
// der Nutzer dort schon geaendert hat.
// Spec: docs/specs/modules/onboarding_standardwerte_hilfe.md
//
// VERGLEICHSMASSSTAB: Was der ECHTE CompareNewEditor beim Betreten des Schritts
// Wetter in den Feldsatz schreibt — sein Vorbelegungs-`$effect` wird gegen das
// echte Instanz-Skript ausgefuehrt (svelteInstanzPruefstand.ts). Bis #2794 S3a
// Teil-PR 4a war das der Lade-Effekt eines unsichtbar gemounteten
// `CorridorEditor.svelte`; die Oberflaeche ist entfernt, die Vorbelegung ist ein
// Effekt im Editor (shared/wetter-tab/anlegeVorbelegung.ts, AC-44). Dieser Test
// ruft `buildComparePrefillRows` / `buildCompareCorridorSavePayload` NIE selbst auf.
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
// sind. Name/Orte/Profil reisen ueber `stateOverride`; ein bereits geaenderter Wertebereich
// (AC-8) steht im Feldsatz des Editors, bevor der Schritt Wetter betreten wird.
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
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { neuerFeldsatz } from '../../shared/__tests__/compareFeldsatzPruefstand.ts';
import { MATCH_MEDIA, VERTRAG_FEHLT_EDITOR } from '../../shared/__tests__/compareNeuEditorPruefstand.ts';
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
import { buildNewComparePresetPayload } from '../../compare/compareEditorSave.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
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

/** Der ECHTE Vorbelegungs-Effekt des Anlege-Editors (AST-Auswahl ueber die importierte Funktion). */
function vorbelegungsEffekt(e: { ast: Knoten; quelle: string; u: Knoten }): () => void {
	const effekte = effekteVon(e.ast, e.quelle, e.u, 'vergleichVorbelegung');
	assert.equal(effekte.length, 1, `Messaufbau kaputt: ${effekte.length} Vorbelegungs-Effekte im CompareNewEditor (erwartet genau 1)`);
	return effekte[0];
}

/** Wertebereiche nach UNVERAENDERTEM Besuch des Schritts Wetter (echter Editor-Effekt). */
async function nachReiterBesuch(activityProfile: string | null): Promise<Wertebereiche> {
	const e = await editorUmgebung(COMPARE_EDITOR, {
		stateOverride: {
			activeTab: 'wetter',
			isMobileViewport: false,
			metrikenVisited: true,
			name: 'Ref',
			pickedIds: ['loc0', 'loc1'],
			activityProfile
		},
		window: MATCH_MEDIA
	});
	await mountenUndWarten(e); // laedt den Vergleichs-Katalog (onMount)
	assert.ok(Array.isArray(e.u.standardwerteKatalog), 'Messaufbau kaputt: Vergleichs-Katalog nicht geladen');
	vorbelegungsEffekt(e)();
	await ruhe();
	const w = auszug(e.u.wiz as Knoten);
	assert.ok(Array.isArray(w.corridors) && (w.corridors as unknown[]).length > 0, 'Messaufbau kaputt: Schritt-Besuch hat nichts vorbelegt');
	return w;
}

/** Anlege-Editor ohne Context; Name/Orte/Profil ueber stateOverride. */
async function anlegeEditor(eingaben: Knoten, besucht: { metriken?: boolean; ideals?: boolean } = {}) {
	const e = await editorUmgebung(COMPARE_EDITOR, {
		stateOverride: {
			activeTab: besucht.ideals ? 'wetter' : 'vergleich',
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
		// Bereits geaenderte Wertebereiche stehen im Feldsatz, bevor der Schritt Wetter
		// (wieder) betreten wird — der Vorbelegungs-Effekt darf sie nicht ueberschreiben (AC-44).
		const wiz = e.u.wiz as Knoten;
		for (const f of FELDER) wiz[f] = klon(nutzer[f]);
	}
	await mountenUndWarten(e);
	// Nach dem Katalog-Laden laeuft der Vorbelegungs-Effekt (im Schritt Wetter) erneut.
	vorbelegungsEffekt(e)();
	await ruhe();
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

// ── #2794 Teil-PR 4a, Fix-Loop 1 ─────────────────────────────────────────────
describe('F003: Vorbelegung nur im Schritt Wetter, mit dem dann aktuellen Profil', () => {
	test('Katalog geladen, Schritt Vergleich ⇒ nichts vorbelegt; Wechsel auf Wetter ⇒ vorbelegt mit dem jetzt gewaehlten Profil', async () => {
		const ref = await nachReiterBesuch('wandern');
		assert.notDeepEqual(ref, await nachReiterBesuch(null), 'Messaufbau: „wandern" muss anders vorbelegen als ohne Profil');
		const e = await anlegeEditor({ name: 'F003', pickedIds: ['loc0', 'loc1'], activityProfile: null });
		const leer = auszug(e.u.wiz as Knoten);
		await mountenUndWarten(e); // laedt den Katalog und laesst alle Effekte im Schritt „vergleich" laufen
		assert.ok(Array.isArray(e.u.standardwerteKatalog), 'Messaufbau: Vergleichs-Katalog nicht geladen');
		const effekt = vorbelegungsEffekt(e);
		effekt();
		await ruhe();
		assert.deepEqual(auszug(e.u.wiz as Knoten), leer, 'F003 FAIL: ausserhalb des Schritts Wetter vorbelegt');
		(e.u.wiz as Knoten).activityProfile = 'wandern';
		e.u.activeTab = 'wetter';
		effekt();
		await ruhe();
		assert.deepEqual(auszug(e.u.wiz as Knoten), ref, 'F003 FAIL: nicht mit dem beim Betreten gewaehlten Profil vorbelegt');
	});
});

describe('F001: Standardwerte nach besuchtem Schritt Wetter belegen nicht vor', () => {
	test('Schritt besucht, Wertebereiche leer ⇒ der Standardwerte-POST traegt keine Vorbelegung (Verhalten wie vor 4a)', async () => {
		const { gesendet } = await nachStandardwerteKlick({ activityProfile: null }, { metriken: true });
		assert.equal(gesendet.length, 1, `erwartet genau ein Speichern, gesehen ${gesendet.length}`);
		assert.deepEqual(gesendet[0].corridors ?? [], [], 'F001 FAIL: trotz besuchtem Schritt vorbelegt (corridors)');
		assert.deepEqual(gesendet[0].ideal_ranges, {}, 'F001 FAIL: trotz besuchtem Schritt vorbelegt (ideal_ranges)');
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
		assert.deepEqual((e.u.wiz as Knoten).corridors ?? [], [], 'Klick bei gesperrtem Gate hat trotzdem vorbelegt');
	});
});
