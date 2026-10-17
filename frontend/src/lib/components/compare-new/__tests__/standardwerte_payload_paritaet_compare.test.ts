// TDD RED — Onboarding S3 (Issue #2521), AC-7 + AC-8: „Mit Standardwerten
// speichern" im Ortsvergleich belegt die Wertebereiche genau so vor wie ein
// unveraenderter Besuch des Wertebereiche-Reiters — und ueberschreibt nie, was
// der Nutzer dort schon geaendert hat.
// Spec: docs/specs/modules/onboarding_standardwerte_hilfe.md
//
// VERGLEICHSMASSSTAB (nicht tautologisch): Was der ECHTE `CorridorEditor.svelte`
// (context="vergleich", Prop-Buendel `corridorPropsAus(wiz)` wie in
// CompareNewEditor) beim Mount ueber `syncToWizard` in den Wizard-Zustand
// schreibt — sein Lade-`$effect` wird gegen das echte Instanz-Skript ausgefuehrt
// (svelteInstanzPruefstand.ts). Dieser Test ruft `buildComparePrefillRows` /
// `buildCompareCorridorSavePayload` NIE selbst auf.
//
// STANDARDWERTE-WEG: der Klick-Handler der ECHTEN `<StandardwerteSpeichernKnopf>`-
// Einbettung in CompareNewEditor.svelte, ausgewertet gegen dessen Instanz-Skript
// mit einem echten CompareWizardState. `wiz.saveNewPreset` ist durch einen
// Schnappschuss ersetzt — gemessen wird der Wizard-Zustand, den der Klick in den
// bestehenden Speicherweg (POST /api/compare/presets) gibt.
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
import { neuerWiz } from '../../shared/__tests__/infoboxSsr.ts';
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

const HIER = dirname(fileURLToPath(import.meta.url));
const CORRIDOR_EDITOR = join(HIER, '..', '..', 'shared', 'corridor-editor', 'CorridorEditor.svelte');
const REPO_ROOT = resolve(HIER, ...Array(7).fill('..'));
const PY =
	'import sys, json\n' +
	"sys.path.insert(0, 'src')\n" +
	'from output.renderers.compare_metric_catalog import get_compare_metric_catalog\n' +
	"print(json.dumps({'metrics': get_compare_metric_catalog()}))\n";
const KATALOG = JSON.parse(
	execFileSync('uv', ['run', 'python3', '-c', PY], { cwd: REPO_ROOT, encoding: 'utf-8' }).trim()
);

let originalFetch: typeof globalThis.fetch;
before(() => {
	originalFetch = globalThis.fetch;
	globalThis.fetch = (async (input: unknown) => {
		const body = String(input).includes('/api/compare/metrics') ? JSON.stringify(KATALOG) : '[]';
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

/** Wertebereiche nach UNVERAENDERTEM Besuch des Reiters (echter CorridorEditor). */
async function nachReiterBesuch(activityProfile: string | null): Promise<Wertebereiche> {
	const wiz = neuerWiz({ name: 'Ref', pickedIds: ['loc0', 'loc1'], activityProfile });
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

/** Wizard-Zustand, den der Standardwerte-Klick an saveNewPreset uebergibt. */
async function nachStandardwerteKlick(
	wizFelder: Knoten,
	besucht: { metriken?: boolean; ideals?: boolean } = {}
): Promise<{ gespeichert: Wertebereiche[] }> {
	const wiz = neuerWiz({ name: 'Std', pickedIds: ['loc0', 'loc1'], ...wizFelder });
	const gespeichert: Wertebereiche[] = [];
	wiz.saveNewPreset = async () => {
		gespeichert.push(auszug(wiz));
	};
	const e = await editorUmgebung(COMPARE_EDITOR, {
		getContext: () => wiz,
		stateOverride: {
			activeTab: besucht.ideals ? 'wertebereiche' : 'vergleich',
			isMobileViewport: false,
			metrikenVisited: !!besucht.metriken,
			idealsVisited: !!besucht.ideals,
			alarmeVisited: false,
			versandVisited: false
		},
		window: { matchMedia: () => ({ matches: false, addEventListener() {}, removeEventListener() {} }) }
	});
	await mountenUndWarten(e);
	derivedNeu(e);
	const knoepfe = knopfEinbettungen(e.ast);
	assert.ok(knoepfe.length >= 1, 'CompareNewEditor bettet <StandardwerteSpeichernKnopf> nicht ein');
	assert.equal(Boolean(knopfAttribut(knoepfe[0], e, 'enabled')), true, 'Standardwerte-Knopf ist trotz Name, 2 Orten und geladenem Katalog nicht aktiv');
	await (knopfAttribut(knoepfe[0], e, 'onclick') as () => unknown)();
	await ruhe();
	return { gespeichert };
}

describe('AC-7: Standardwerte == unveraenderter Wertebereiche-Besuch (vorbelegt, nicht leer)', () => {
	test('Positivkontrolle: Profil-Vorbelegung ALLGEMEIN (kein Profil) unterscheidet sich von „wandern"', async () => {
		assert.notDeepEqual(await nachReiterBesuch(null), await nachReiterBesuch('wandern'));
	});

	test('ohne gewaehltes Profil: Wertebereiche, aktive Metriken und Alarmstufen gleich dem Reiter-Besuch', async () => {
		const ref = await nachReiterBesuch(null);
		const { gespeichert } = await nachStandardwerteKlick({ activityProfile: null });
		assert.equal(gespeichert.length, 1, `erwartet genau ein Speichern, gesehen ${gespeichert.length}`);
		assert.deepEqual(gespeichert[0], ref);
	});

	test('mit Profil „wandern": gleich dem Reiter-Besuch mit demselben Profil', async () => {
		const ref = await nachReiterBesuch('wandern');
		const { gespeichert } = await nachStandardwerteKlick({ activityProfile: 'wandern' });
		assert.equal(gespeichert.length, 1);
		assert.deepEqual(gespeichert[0], ref);
	});

	test('nicht leer: der Standardwerte-Weg speichert Wertebereiche', async () => {
		const { gespeichert } = await nachStandardwerteKlick({ activityProfile: null });
		assert.equal(gespeichert.length, 1);
		assert.ok((gespeichert[0].corridors as unknown[]).length > 0, 'Vorbelegung uebersprungen: corridors leer');
		assert.ok(Object.keys(gespeichert[0].idealRanges as object).length > 0, 'Vorbelegung uebersprungen: ideal_ranges leer');
	});
});

describe('AC-8: besuchter, geaenderter Wertebereich bleibt erhalten', () => {
	test('Nutzer hat im Wertebereiche-Reiter einen Bereich geaendert: Standardwerte ueberschreiben ihn nicht', async () => {
		const ref = await nachReiterBesuch(null);
		const corridors = klon(ref.corridors) as Array<{ metric: string; range: [number | null, number | null]; notify: boolean; mark: boolean }>;
		corridors[0] = { ...corridors[0], range: [corridors[0].range[0], 999] };
		const nutzer = {
			corridors,
			idealRanges: { ...(ref.idealRanges as object), [corridors[0].metric]: { max: 999 } },
			activeMetricKeys: ref.activeMetricKeys,
			metricAlertLevels: ref.metricAlertLevels
		};
		const { gespeichert } = await nachStandardwerteKlick(
			{ activityProfile: null, ...klon(nutzer) },
			{ metriken: true, ideals: true }
		);
		assert.equal(gespeichert.length, 1);
		assert.deepEqual(gespeichert[0], klon(nutzer), 'Profil-Vorbelegung hat die Nutzerwerte ueberschrieben');
	});
});
