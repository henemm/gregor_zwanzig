// #3047 Paket D: Editor-Standard = Mail-Standard, FRONTEND-Seite (AC-13, AC-16, AC-21).
//
// SPEC: docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md §5, §7
// Konzept: docs/context/einstellungen_neu.md §5 Punkt 6 und 8
//
// Je Liste laeuft die ECHTE Frontend-Ableitung mit derselben Eingabe wie die
// Python-Seite (tests/tdd/test_einstellung_gleich_mail_editor_standard.py) aus
// tests/fixtures/einstellung_gleich_mail/editor_standard.json und wird gegen die
// dort von Hand gesetzte Folge verglichen:
//   * Ausblick (Trip und Orte) und Orte-Stundenverlauf: die geteilten Komponenten
//     OutlookLayoutControls.svelte / CompareHourlyLayoutControls.svelte werden mit
//     svelte/server gerendert, die aktive Folge wird aus dem DOM gelesen
//     (`wm2-reihenfolge-row`, WeatherV2Reihenfolge).
//   * Ladepfade: dieselben exportierten Helfer, die WeatherMetricsTab.svelte
//     aufruft (computeInitialBuckets :477, channelOverrideFromMetrics :505,
//     normalizeStoredOutlookMetrics :512; hydrate*FromPreset fuer den Vergleich).
//   * Inline-Logik des Reiters (allCatalogIds, channelView, channelListSections,
//     compareChannelPrimary, applyPreset): der ECHTE Funktionsquelltext wird per
//     svelte/compiler aus WeatherMetricsTab.svelte gelesen und mit den echten
//     Modul-Exporten ausgefuehrt (kein Nachbau, kein vi.mock).
//
// Bekannte Abweichungen laufen ueber `rotErwartet` (Gegenstueck zu Vitest
// `it.fails` bzw. pytest xfail strict): der Fall MUSS scheitern, sonst wird er
// rot ("Marker entfernen"). Mit GZ_RUNXFAIL=1 laufen sie als normale Tests
// (RED-Nachweis). Die Behebungspakete (F2/F4) ersetzen `rotErwartet` durch `test`.
//
//   cd frontend && npm test -- src/lib/components/shared/weather-metrics-tab/__tests__/editor_standard_gleich_mail.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register, stripTypeScriptTypes } from 'node:module';
import { readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { parse } from 'svelte/compiler';

import * as metricsEditor from '../../../trip-detail/metricsEditor.ts';
import * as channelLayouts from '../channelMetricLayouts.ts';
import * as savePayload from '../weatherMetricsSavePayload.ts';
import { toCompareSelectionEntries } from '../compareMetricSelection.ts';
import { normalizeStoredOutlookMetrics } from '../compareMetricSelection.ts';
import {
	hydrateChannelActiveMetricsFromPreset,
	hydrateLayoutFieldsFromPreset,
	hydrateWeatherMetricsFromPreset
} from '../weatherMetricsCompareSave.ts';
import { materializeActiveMetricKeys } from '../compareMetricOrder.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> weather-metrics-tab -> shared -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../../..');
const SHARED = path.resolve(HERE, '../..');
const TAB = path.join(SHARED, 'WeatherMetricsTab.svelte');
const FIXTURE = path.resolve(FRONTEND, '..', 'tests', 'fixtures', 'einstellung_gleich_mail', 'editor_standard.json');

register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');
const komp = async (datei: string) => (await import(pathToFileURL(datei).href)).default;
const OutlookLayoutControls = await komp(path.join(SHARED, 'OutlookLayoutControls.svelte'));
const CompareHourlyLayoutControls = await komp(path.join(SHARED, '..', 'compare', 'CompareHourlyLayoutControls.svelte'));
const { locale } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/index.ts')).href);
locale.set('de');

type Zustand = { id: string; eingabe: { display_config: Record<string, unknown> }; erwartet: string[] };
const DATEN = JSON.parse(readFileSync(FIXTURE, 'utf-8'));
const TRIP_KATALOG = DATEN.kataloge.trip_api_metrics as metricsEditor.MetricCatalog;
const ORTE_KATALOG = toCompareSelectionEntries(DATEN.kataloge.orte_api_compare_metrics);
const zustand = (liste: string, id: string): Zustand =>
	DATEN.listen[liste].zustaende.find((z: Zustand) => z.id === id);
const gespeicherte = (liste: string): Zustand[] =>
	DATEN.listen[liste].zustaende.filter((z: Zustand) => z.id.startsWith('gespeichert'));

const RUNXFAIL = process.env.GZ_RUNXFAIL === '1';
/** Erwartet-rot (strict): scheitert der Rumpf NICHT, ist der Test rot. */
function rotErwartet(name: string, befund: string, rumpf: () => void): void {
	if (RUNXFAIL) {
		test(`${name} [${befund}]`, rumpf);
		return;
	}
	test(`${name} [erwartet rot: ${befund}]`, () => {
		let fehler: unknown = null;
		try {
			rumpf();
		} catch (e) {
			fehler = e;
		}
		assert.ok(fehler, `${befund} ist behoben: rotErwartet durch test ersetzen`);
		// Nur ein inhaltlicher Folgen-Unterschied zaehlt als erwartetes Rot, kein
		// Pruefstand-Fehler (ReferenceError o. ae.) -- der waere sonst still gruen.
		assert.equal((fehler as { code?: string }).code, 'ERR_ASSERTION', `Pruefstand-Fehler statt Befund: ${String(fehler)}`);
	});
}

// ── Echte Inline-Funktionen aus WeatherMetricsTab.svelte ──────────────────────
const TAB_QUELLE = readFileSync(TAB, 'utf-8');
const TAB_AST = parse(TAB_QUELLE, { modern: true }) as unknown as {
	instance: { content: { body: Array<{ type: string; id?: { name: string }; start: number; end: number }> } };
};
function funktionsQuelle(name: string): string {
	const knoten = TAB_AST.instance.content.body.find((n) => n.type === 'FunctionDeclaration' && n.id?.name === name);
	assert.ok(knoten, `Funktion ${name} nicht mehr in WeatherMetricsTab.svelte`);
	return stripTypeScriptTypes(TAB_QUELLE.slice(knoten.start, knoten.end));
}
const MODUL_BINDUNGEN = { ...metricsEditor, ...channelLayouts, ...savePayload };
/** Fuehrt die genannten Instanz-Funktionen des Reiters in einem Zustands-Objekt
 *  aus (Komponenten-`$state` = Eigenschaften von `zustand`; Zuweisungen landen dort). */
function tabFunktionen(namen: string[], zustand: Record<string, unknown>): Record<string, (...a: unknown[]) => unknown> {
	// Modul-Importe des Reiters ueber die Prototypkette: Lesen findet sie,
	// Zuweisungen an `$state` landen als eigene Eigenschaft in `zustand`.
	if (Object.getPrototypeOf(zustand) !== MODUL_BINDUNGEN) Object.setPrototypeOf(zustand, MODUL_BINDUNGEN);
	const quelle = namen.map(funktionsQuelle).join('\n');
	const rueckgabe = `return { ${namen.join(', ')} };`;
	// eslint-disable-next-line @typescript-eslint/no-implied-eval
	return new Function('zustand', `with (zustand) { ${quelle}\n${rueckgabe} }`)(zustand);
}

// ── DOM-Lesen der geteilten Reihenfolge-Liste ──────────────────────────────────
function aktiveFolge(html: string): string[] {
	const zeilen = html.match(/<div[^>]*data-testid="wm2-reihenfolge-row"[^>]*>/g) ?? [];
	return zeilen.map((tag) => /data-metric-id="([^"]+)"/.exec(tag)![1]);
}
const nix = () => {};
const rendern = (k: unknown, props: Record<string, unknown>) => render(k as never, { props } as never).body;

// ── Trip: Ladepfad wie initFromTrip() ──────────────────────────────────────────
const TRIP_METRIC_BY_ID: Record<string, { trip_default_enabled?: boolean }> = Object.fromEntries(
	Object.values(TRIP_KATALOG).flat().map((m) => [m.id, m as { trip_default_enabled?: boolean }])
);
function tripEditor(eingabe: Zustand['eingabe']) {
	const dc = eingabe.display_config as Record<string, any>;
	const zustand: Record<string, unknown> = { catalog: TRIP_KATALOG, CATEGORY_ORDER: metricsEditor.CATEGORY_ORDER };
	const { allCatalogIds } = tabFunktionen(['allCatalogIds'], zustand);
	const ids = allCatalogIds() as string[];
	const buckets = metricsEditor.computeInitialBuckets(TRIP_KATALOG, TRIP_METRIC_BY_ID, dc.metrics, ids);
	const channelBuckets: Record<string, unknown> = { email: null, telegram: null, sms: null };
	for (const ch of ['email', 'telegram', 'sms']) {
		const layout = dc.channel_layouts?.[ch];
		if (layout) channelBuckets[ch] = channelLayouts.channelOverrideFromMetrics(layout, ids, {});
	}
	Object.assign(zustand, { buckets, friendlyMap: {}, channelBuckets });
	const { channelListSections } = tabFunktionen(['channelView', 'channelListSections'], zustand);
	return {
		buckets,
		emailListe: (channelListSections('email') as { active: string[] }).active,
		outlookKeys: normalizeStoredOutlookMetrics(dc.outlook_metrics, ORTE_KATALOG)
	};
}
function frontendTripTabellen(eingabe: Zustand['eingabe']): string[] {
	return tripEditor(eingabe).emailListe;
}
function frontendTripAusblick(eingabe: Zustand['eingabe']): string[] {
	const ed = tripEditor(eingabe);
	return aktiveFolge(rendern(OutlookLayoutControls, {
		metricKeys: ed.outlookKeys, catalog: ORTE_KATALOG, grundauswahl: ed.buckets.primary,
		onMetricKeys: nix, showEmailOnlyHint: false
	}));
}

// ── Orte: Hydration wie im Vergleichs-Hub ──────────────────────────────────────
function orteEditor(eingabe: Zustand['eingabe']) {
	const preset = { id: 'pruef-3047', ...eingabe } as never;
	const activeMetricKeys = hydrateWeatherMetricsFromPreset(preset, ORTE_KATALOG);
	const materializedActiveMetricKeys = materializeActiveMetricKeys(activeMetricKeys ?? null);
	const channelActiveMetricKeys = hydrateChannelActiveMetricsFromPreset(preset, ORTE_KATALOG);
	const layout = hydrateLayoutFieldsFromPreset(preset, ORTE_KATALOG);
	const { compareChannelPrimary } = tabFunktionen(['compareChannelPrimary'], {
		channelActiveMetricKeys, materializedActiveMetricKeys
	});
	return { materializedActiveMetricKeys, layout, kanalListe: compareChannelPrimary as (ch: string) => string[] };
}
function frontendOrteVergleichstabelle(eingabe: Zustand['eingabe']): string[] {
	const ed = orteEditor(eingabe);
	// WeatherMetricsTab.svelte:1236-1238 (compareChannelSections fuer den E-Mail-Reiter)
	return channelLayouts.splitChannelMetricsForDisplay(ed.materializedActiveMetricKeys, ed.kanalListe('email')).active;
}
function frontendOrteStundenverlauf(eingabe: Zustand['eingabe']): string[] {
	const ed = orteEditor(eingabe);
	return aktiveFolge(rendern(CompareHourlyLayoutControls, {
		metricKeys: ed.layout.hourlyMetricKeys, onMetricKeys: nix, catalog: ORTE_KATALOG
	}));
}
function frontendOrteAusblick(eingabe: Zustand['eingabe']): string[] {
	const ed = orteEditor(eingabe);
	return aktiveFolge(rendern(OutlookLayoutControls, {
		metricKeys: ed.layout.outlookMetricKeys, catalog: ORTE_KATALOG,
		grundauswahl: ed.materializedActiveMetricKeys, onMetricKeys: nix
	}));
}

function pruefe(seite: (e: Zustand['eingabe']) => string[], liste: string, z: Zustand): void {
	assert.deepEqual(seite(z.eingabe), z.erwartet,
		`Frontend-Seite ${liste}/${z.id}: Editor zeigt eine andere Folge als editor_standard.json erwartet`);
}

describe('#3047 Editor-Standard = Mail-Standard (Frontend-Seite)', () => {
	test('frontend_seite_trip_tabellen_standard', () =>
		pruefe(frontendTripTabellen, 'trip_tabellen', zustand('trip_tabellen', 'nie_eingestellt')));
	// #3047 RED N2
	rotErwartet('frontend_seite_trip_tabellen_altbestand', '#3047 RED N2', () =>
		pruefe(frontendTripTabellen, 'trip_tabellen', zustand('trip_tabellen', 'altbestand_ohne_metrics')));
	for (const z of gespeicherte('trip_tabellen'))
		test(`frontend_seite_trip_tabellen_gespeichert ${z.id}`, () => pruefe(frontendTripTabellen, 'trip_tabellen', z));

	test('frontend_seite_trip_ausblick_standard', () =>
		pruefe(frontendTripAusblick, 'trip_ausblick', zustand('trip_ausblick', 'nie_eingestellt')));
	for (const z of gespeicherte('trip_ausblick'))
		test(`frontend_seite_trip_ausblick_gespeichert ${z.id}`, () => pruefe(frontendTripAusblick, 'trip_ausblick', z));

	test('frontend_seite_orte_vergleichstabelle_standard', () =>
		pruefe(frontendOrteVergleichstabelle, 'orte_vergleichstabelle', zustand('orte_vergleichstabelle', 'nie_eingestellt')));
	for (const z of gespeicherte('orte_vergleichstabelle'))
		test(`frontend_seite_orte_vergleichstabelle_gespeichert ${z.id}`, () =>
			pruefe(frontendOrteVergleichstabelle, 'orte_vergleichstabelle', z));

	// #3047 O2 behoben (F4)
	test('frontend_seite_orte_stundenverlauf_standard', () =>
		pruefe(frontendOrteStundenverlauf, 'orte_stundenverlauf', zustand('orte_stundenverlauf', 'nie_eingestellt')));
	for (const z of gespeicherte('orte_stundenverlauf'))
		test(`frontend_seite_orte_stundenverlauf_gespeichert ${z.id}`, () =>
			pruefe(frontendOrteStundenverlauf, 'orte_stundenverlauf', z));

	// #3047 O4 behoben (F4)
	test('frontend_seite_orte_ausblick_standard', () =>
		pruefe(frontendOrteAusblick, 'orte_ausblick', zustand('orte_ausblick', 'nie_eingestellt')));
	test('frontend_seite_orte_ausblick_standard_mit_grundauswahl', () =>
		pruefe(frontendOrteAusblick, 'orte_ausblick', zustand('orte_ausblick', 'nie_eingestellt_mit_grundauswahl')));
	for (const z of gespeicherte('orte_ausblick'))
		test(`frontend_seite_orte_ausblick_gespeichert ${z.id}`, () => pruefe(frontendOrteAusblick, 'orte_ausblick', z));
});

// ── AC-16: Vorlage anwenden behaelt die Vorlagen-Folge (Befund T4) ─────────────
describe('#3047 AC-16 Vorlage anwenden (Frontend-Seite)', () => {
	// #3047 RED T4
	rotErwartet('frontend_seite_trip_vorlage_reihenfolge', '#3047 RED T4', () => {
		const vorlage = DATEN.listen.trip_vorlage;
		const ed = tripEditor(zustand('trip_tabellen', 'nie_eingestellt').eingabe);
		const zustandTab: Record<string, unknown> = {
			userTouched: false, userPresets: [], templates: [vorlage.vorlage], catalog: TRIP_KATALOG,
			friendlyMap: {}, buckets: ed.buckets, selectedTemplate: '', ampelAngewendet: undefined,
			// applyDiff steuert nur das 2,5-s-Aufleuchten der geaenderten Zeile (UI), nicht den Zustand.
			applyDiff: nix
		};
		const { applyPreset } = tabFunktionen(['applyPreset'], zustandTab);
		applyPreset(vorlage.vorlage.id);
		const gespeichert = metricsEditor.buildWeatherConfigMetrics(
			zustandTab.buckets as metricsEditor.Buckets, zustandTab.friendlyMap as Record<string, boolean>, {}, TRIP_KATALOG
		);
		const folge = gespeichert
			.filter((m) => m.enabled && m.bucket === 'primary')
			.sort((a, b) => a.order - b.order)
			.map((m) => m.metric_id);
		assert.deepEqual(folge, vorlage.erwartet, 'gespeicherte Folge nach Vorlage anwenden');
	});
});
