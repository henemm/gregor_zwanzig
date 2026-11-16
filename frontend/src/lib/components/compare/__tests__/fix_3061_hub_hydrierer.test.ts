// RED — #3061 (Befund F4 aus Epic #3047): „nie eingestellt" muss die Hub-Hydrierung
// ueberleben, sonst ist eine BEWUSST gespeicherte Vollauswahl im Ausblick-Block
// vom Altbestand nicht zu unterscheiden.
//
// Spec: docs/specs/modules/fix_3061_ausblick_alle_groessen.md (AC-1 bis AC-5)
//
// Gemessen an den ECHTEN Hub-Hydrierern:
//   * `hydrateAlarmFieldsFromPreset` (compareHubHydration.ts, Reiter Zustellung/Alarme),
//   * `hydrateWetterMetrikenTab` aus dem Instanz-Skript von CompareTabs.svelte
//     (svelteInstanzPruefstand.ts, Ladefunktion des Katalogs gesaet),
// und am ECHTEN Attribut-Ausdruck `grundauswahl={...}` der beiden
// OutlookLayoutControls-Einbettungen in WeatherMetricsTab.svelte. Der Ausblick
// wird mit svelte/server gerendert und aus dem DOM gelesen. Kein Mock.
//
//   cd frontend && npm test -- src/lib/components/compare/__tests__/fix_3061_hub_hydrierer.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { register, stripTypeScriptTypes } from 'node:module';
import { parse } from 'svelte/compiler';

import type { ComparePreset } from '../../../types.ts';
import { hydrateAlarmFieldsFromPreset } from '../compareHubHydration.ts';
import { alarmePropsAus } from '../alarmePropsAus.ts';
import { toCompareSelectionEntries } from '../../shared/weather-metrics-tab/compareMetricSelection.ts';
import { materializeActiveMetricKeys } from '../../shared/weather-metrics-tab/compareMetricOrder.ts';
import {
	flushPendingWetterMetrikenSave,
	hydrateLayoutFieldsFromPreset,
	wetterMetrikenSnapshotAus
} from '../../shared/weather-metrics-tab/weatherMetricsCompareSave.ts';
import { deriveActiveAlertMetricsFromCatalog } from '../../shared/alarme-tab/activeAlertMetricsFromCatalog.ts';
import { COMPARE_METRIC_KEYS } from '../../shared/wetter-tab/corridorEditorState.ts';
import {
	attributAusdruck,
	findeKomponenten,
	umgebungFuer,
	werte,
	type Knoten
} from '../../shared/__tests__/svelteInstanzPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '../../../../..');
const HUB = join(HIER, '..', 'CompareTabs.svelte');
const SHARED = resolve(HIER, '../../shared');
const TAB = join(SHARED, 'WeatherMetricsTab.svelte');
const FIXTURE = resolve(FRONTEND, '..', 'tests', 'fixtures', 'einstellung_gleich_mail', 'editor_standard.json');

register(pathToFileURL(join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');
const OutlookLayoutControls = (await import(pathToFileURL(join(SHARED, 'OutlookLayoutControls.svelte')).href)).default;
const AlarmeTab = (await import(pathToFileURL(join(SHARED, 'AlarmeTab.svelte')).href)).default;
const { locale } = await import(pathToFileURL(join(FRONTEND, 'src/lib/i18n/index.ts')).href);
locale.set('de');

const DATEN = JSON.parse(readFileSync(FIXTURE, 'utf-8'));
const KATALOG = toCompareSelectionEntries(DATEN.kataloge.orte_api_compare_metrics);
// Die aufgezeichnete Katalog-Antwort in editor_standard.json ist auf die Ausblick-Felder
// gekuerzt; fuer die Alarm-Tabelle traegt hier die Boeen-Zeile ihr Register-Feld
// `alertMetric` (Wert wie GET /api/compare/metrics, #1435 E1a-1).
const ALARM_KATALOG = KATALOG.map((e) => (e.metric === 'gust_max_kmh' ? { ...e, alertMetric: 'wind_gust' } : e));
const DEFAULT_SPALTEN =['temperature', 'precipitation', 'rain_probability', 'wind', 'gust', 'thunder'];

const TAB_QUELLE = readFileSync(TAB, 'utf-8');
const TAB_AST = parse(TAB_QUELLE, { modern: true }) as unknown as Knoten;
const EINBETTUNGEN = findeKomponenten(TAB_AST, 'OutlookLayoutControls');

function preset(displayConfig: Record<string, unknown>): ComparePreset {
	return {
		id: 'cp-3061',
		name: 'Vergleich 3061',
		location_ids: ['loc-a', 'loc-b'],
		schedule: 'daily',
		empfaenger: ['a@example.com'],
		created_at: '2026-11-16T00:00:00Z',
		display_config: displayConfig
	} as unknown as ComparePreset;
}
const ALTBESTAND = () => preset({});
const VOLLAUSWAHL = () => preset({ active_metrics: [...COMPARE_METRIC_KEYS] });

/** Wetter-Metriken-Hydrierer des Hubs (CompareTabs.svelte), auf `wizardState`. */
async function wetterHydrierer(wizardState: Record<string, unknown>, p: ComparePreset): Promise<void> {
	const { u } = await umgebungFuer(HUB, { preset: p, locations: [], wizardState, onScheduleChange: undefined });
	assert.equal(typeof u.hydrateWetterMetrikenTab, 'function', 'Messaufbau: hydrateWetterMetrikenTab nicht herleitbar');
	u.currentPreset = p;
	u.wizardState = wizardState;
	u.loadCompareSelectionEntries = async () => KATALOG;
	await u.hydrateWetterMetrikenTab();
}
function alarmHydrierer(wizardState: Record<string, unknown>, p: ComparePreset): void {
	hydrateAlarmFieldsFromPreset(wizardState as never, p, KATALOG);
}

/** Grundauswahl, die WeatherMetricsTab der Vergleichs-Einbettung reicht. */
function vergleichGrundauswahl(activeMetricKeys: string[] | null): string[] | null {
	const ausdruck = attributAusdruck(EINBETTUNGEN[0], TAB_QUELLE, 'grundauswahl');
	assert.ok(ausdruck, 'Messaufbau: grundauswahl-Attribut der Vergleichs-Einbettung fehlt');
	return werte(stripTypeScriptTypes(ausdruck), {
		activeMetricKeys,
		materializedActiveMetricKeys: materializeActiveMetricKeys(activeMetricKeys ?? null)
	}) as string[] | null;
}

function aktiveFolge(html: string): string[] {
	const zeilen = html.match(/<div[^>]*data-testid="wm2-reihenfolge-row"[^>]*>/g) ?? [];
	return zeilen.map((tag) => /data-metric-id="([^"]+)"/.exec(tag)![1]);
}
function ausblickImEditor(wizardState: Record<string, unknown>, p: ComparePreset): string[] {
	const layout = hydrateLayoutFieldsFromPreset(p, KATALOG);
	const grundauswahl = vergleichGrundauswahl((wizardState.activeMetricKeys as string[] | null | undefined) ?? null);
	const html = render(OutlookLayoutControls as never, {
		props: { metricKeys: layout.outlookMetricKeys, catalog: KATALOG, grundauswahl, onMetricKeys: () => {} }
	} as never).body;
	return aktiveFolge(html);
}

describe('#3061 Hub-Hydrierer behalten „nie eingestellt"', () => {
	test('AC-2: Alarm-Hydrierer laesst activeMetricKeys bei Altbestand null', () => {
		const s: Record<string, unknown> = {};
		alarmHydrierer(s, ALTBESTAND());
		assert.equal(
			s.activeMetricKeys,
			null,
			`Altbestand ohne active_metrics hydriert zu ${JSON.stringify(s.activeMetricKeys)} statt null -- ` +
				'„nie eingestellt" geht verloren und ist von einer gespeicherten Vollauswahl nicht mehr zu unterscheiden.'
		);
	});

	test('AC-2: Wetter-Metriken-Hydrierer (CompareTabs) laesst activeMetricKeys bei Altbestand null', async () => {
		const s: Record<string, unknown> = {};
		await wetterHydrierer(s, ALTBESTAND());
		assert.equal(s.activeMetricKeys, null, `Altbestand hydriert zu ${JSON.stringify(s.activeMetricKeys)} statt null`);
	});

	test('AC-1: gespeicherte Vollauswahl bleibt in beiden Hydrierern die Liste', async () => {
		const a: Record<string, unknown> = {};
		alarmHydrierer(a, VOLLAUSWAHL());
		const w: Record<string, unknown> = {};
		await wetterHydrierer(w, VOLLAUSWAHL());
		assert.deepEqual(a.activeMetricKeys, COMPARE_METRIC_KEYS);
		assert.deepEqual(w.activeMetricKeys, COMPARE_METRIC_KEYS);
	});
});

describe('#3061 Ausblick im Editor = Mail', () => {
	test('AC-1: gespeicherte Vollauswahl ohne outlook_metrics zeigt alle darstellbaren Groessen', () => {
		const s: Record<string, unknown> = {};
		alarmHydrierer(s, VOLLAUSWAHL());
		const ist = ausblickImEditor(s, VOLLAUSWAHL());
		const soll = DATEN.listen.orte_ausblick.zustaende.find(
			(z: { id: string }) => z.id === 'gespeichert_vollauswahl_ohne_ausblick'
		).erwartet;
		assert.deepEqual(ist, soll, `Editor zeigt ${JSON.stringify(ist)}, die Mail zeigt ${JSON.stringify(soll)}`);
	});

	test('AC-2: Altbestand zeigt weiter die festen Vorgabe-Spalten', () => {
		const s: Record<string, unknown> = {};
		alarmHydrierer(s, ALTBESTAND());
		assert.deepEqual(ausblickImEditor(s, ALTBESTAND()), DEFAULT_SPALTEN);
	});

	for (const [name, p] of [['Altbestand', ALTBESTAND], ['Vollauswahl', VOLLAUSWAHL]] as const) {
		test(`AC-3: ${name} -- Reiter-Reihenfolge aendert das Ausblick-Ergebnis nicht, Alarm-Tabelle hat Metriken`, async () => {
			const alarmZuerst: Record<string, unknown> = {};
			alarmHydrierer(alarmZuerst, p());
			await wetterHydrierer(alarmZuerst, p());
			const wetterZuerst: Record<string, unknown> = {};
			await wetterHydrierer(wetterZuerst, p());
			alarmHydrierer(wetterZuerst, p());
			assert.deepEqual(ausblickImEditor(alarmZuerst, p()), ausblickImEditor(wetterZuerst, p()));
			assert.deepEqual(alarmZuerst.activeMetricKeys, wetterZuerst.activeMetricKeys);
			const soll = name === 'Altbestand' ? DEFAULT_SPALTEN : null;
			if (soll) assert.deepEqual(ausblickImEditor(alarmZuerst, p()), soll);
			// #1320: die Empfindlichkeits-Tabelle (CompareTabs `beispielAlarmRegeln`) materialisiert selbst.
			for (const s of [alarmZuerst, wetterZuerst]) {
				const zeilen = deriveActiveAlertMetricsFromCatalog(
					materializeActiveMetricKeys((s.activeMetricKeys as string[] | null | undefined) ?? null),
					ALARM_KATALOG as never
				);
				assert.ok(zeilen.length > 0, 'Alarm-Empfindlichkeits-Tabelle zeigt keine Metriken (#1320)');
			}
		});
	}
});

// Adversary F001 (Fix-Loop): der AC-3-Test oben materialisiert selbst. Hier wird die
// Empfindlichkeits-Tabelle dort gemessen, wo sie WIRKT: am serverseitig gerenderten
// AlarmeTab (context="vergleich", Prop-Buendel des echten `alarmePropsAus` aus dem vom
// echten Hub-Hydrierer befuellten Zustand) und am Beispiel-Alarm des Hubs
// (`beispielAlarmRegeln` aus dem ECHTEN Instanz-Skript von CompareTabs.svelte, gelesen
// ueber den echten Attribut-Ausdruck der ZustellungTab-Einbettung).
describe('#3061 AC-3 am Wirkort: Altbestand (activeMetricKeys=null) zeigt Alarm-Metriken', () => {
	function renderAlarmeTab(wizardState: Record<string, unknown>): string {
		return render(AlarmeTab as never, {
			props: {
				context: 'vergleich',
				...alarmePropsAus(wizardState as never),
				catalog: ALARM_KATALOG,
				profileOverride: { premium_sms_allowed: false }
			}
		} as never).body;
	}

	test('AlarmeTab rendert fuer Altbestand die Tabelle mit Metrik-Zeilen, nicht „keine Metriken"', () => {
		const s: Record<string, unknown> = {};
		alarmHydrierer(s, ALTBESTAND());
		assert.equal(s.activeMetricKeys, null, 'Messaufbau: Altbestand muss null tragen');
		const html = renderAlarmeTab(s);
		assert.ok(!html.includes('data-testid="alarme-no-metrics"'), 'Alarme-Reiter meldet „keine Metriken" (#1320)');
		assert.ok(
			!html.includes('data-testid="alarme-only-unalertable-hint"'),
			'Alarme-Reiter meldet nur nicht alarmfaehige Groessen statt der Tabelle (#1320)'
		);
		assert.ok(html.includes('data-testid="alert-metric-level-table"'), 'Empfindlichkeits-Tabelle fehlt (#1320)');
		const zeilen = [...html.matchAll(/data-testid="alert-metric-row-([a-z_]+)"/g)].map((m) => m[1]);
		assert.deepEqual(zeilen, ['wind_gust'], `Tabellenzeilen ${JSON.stringify(zeilen)} statt der Vorgabemenge`);
	});

	test('AlarmeTab nennt fuer Altbestand die gewaehlten, nicht alarmfaehigen Groessen (dieselbe Materialisierung)', () => {
		const s: Record<string, unknown> = {};
		alarmHydrierer(s, ALTBESTAND());
		const html = renderAlarmeTab(s);
		const m = /data-testid="alarme-unalertable-metrics-hint"[^>]*>([\s\S]*?)<\/p>/.exec(html);
		assert.ok(m, 'Hinweis auf nicht alarmfaehige Groessen der Vorgabemenge fehlt');
		assert.ok(m![1].includes('Sonnenstunden'), `Hinweis nennt nicht die Vorgabemenge: ${m![1]}`);
	});

	test('Hub: Beispiel-Alarm (beispielAlarmRegeln an ZustellungTab) hat fuer Altbestand Regeln', async () => {
		const s: Record<string, unknown> = {};
		alarmHydrierer(s, ALTBESTAND());
		assert.equal(s.activeMetricKeys, null, 'Messaufbau: Altbestand muss null tragen');
		const { ast, quelle, u } = await umgebungFuer(HUB, {
			preset: ALTBESTAND(),
			locations: [],
			wizardState: s,
			onScheduleChange: undefined,
			alarmeCatalog: ALARM_KATALOG,
			alarmeRegister: {}
		});
		const einbettungen = findeKomponenten(ast, 'ZustellungTab');
		assert.equal(einbettungen.length, 1, 'Messaufbau: genau eine ZustellungTab-Einbettung im Hub erwartet');
		const ausdruck = attributAusdruck(einbettungen[0], quelle, 'beispielAlarmRegeln');
		assert.ok(ausdruck, 'Messaufbau: beispielAlarmRegeln-Attribut der ZustellungTab-Einbettung fehlt');
		const regeln = werte(ausdruck!, u) as Array<{ metric: string }> | undefined;
		assert.ok(Array.isArray(regeln), `Messaufbau: ${ausdruck} nicht herleitbar (${typeof regeln})`);
		assert.deepEqual(
			regeln!.map((r) => r.metric),
			['wind_gust'],
			'Beispiel-Alarm im Reiter Zustellung hat fuer Altbestand keine Metrik (#1320)'
		);
	});
});

describe('#3061 Speichern und Trip bleiben unveraendert', () => {
	test('AC-4: Altbestand oeffnen und ohne Aenderung speichern -- kein PUT, kein active_metrics', async () => {
		const s: Record<string, unknown> = {};
		await wetterHydrierer(s, ALTBESTAND());
		alarmHydrierer(s, ALTBESTAND());
		const vorher = wetterMetrikenSnapshotAus(s);
		const nachher = wetterMetrikenSnapshotAus(s);
		assert.equal(flushPendingWetterMetrikenSave(ALTBESTAND(), nachher, vorher), null, 'Scheindifferenz nach reinem Oeffnen');
	});

	test('AC-5: Trip-Einbettung reicht weiter buckets.primary, nie null als Altbestand-Signal', () => {
		assert.equal(EINBETTUNGEN.length, 2, 'Messaufbau: genau zwei Ausblick-Einbettungen (Vergleich, Trip) erwartet');
		const trip = attributAusdruck(EINBETTUNGEN[1], TAB_QUELLE, 'grundauswahl');
		assert.equal(trip, 'buckets.primary', `Trip-Grundauswahl ist ${trip} statt buckets.primary`);
		const liste = ['temperature', 'wind'];
		assert.deepEqual(
			werte(trip!, { buckets: { primary: liste }, activeMetricKeys: null, materializedActiveMetricKeys: COMPARE_METRIC_KEYS }),
			liste
		);
	});
});
