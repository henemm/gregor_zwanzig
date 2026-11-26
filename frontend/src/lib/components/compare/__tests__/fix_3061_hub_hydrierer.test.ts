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
import { hydrateLayoutFieldsFromPreset } from '../../shared/weather-metrics-tab/weatherMetricsCompareSave.ts';
import { deriveActiveAlertMetricsFromCatalog } from '../../shared/alarme-tab/activeAlertMetricsFromCatalog.ts';
import { getCompareDefaultOrder, loadCompareMetricCatalog } from '../../shared/wetter-tab/compareMetricCatalogLoader.ts';
import { endpointFetch } from '../../shared/wetter-tab/__tests__/compareDefaultOrder2989Daten.ts';
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
const FIXTURE = resolve(FRONTEND, '..', 'tests', 'fixtures', 'einstellung_gleich_mail', 'editor_standard.json');

register(pathToFileURL(join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');
const AlarmeTab = (await import(pathToFileURL(join(SHARED, 'AlarmeTab.svelte')).href)).default;
const { locale } = await import(pathToFileURL(join(FRONTEND, 'src/lib/i18n/index.ts')).href);
locale.set('de');

// #2989: die Vorgabemenge „nie eingestellt" ist die Standardfolge `default_order` der
// Katalog-Antwort, befuellt ueber den echten Lader (fetch-Stub an der Netzgrenze).
const zurueck = endpointFetch();
try {
	await loadCompareMetricCatalog();
} finally {
	zurueck();
}
const STANDARD = getCompareDefaultOrder() ?? [];
assert.ok(STANDARD.length > 0, 'Messaufbau: Standardfolge nicht geladen');

const DATEN = JSON.parse(readFileSync(FIXTURE, 'utf-8'));
const KATALOG = toCompareSelectionEntries(DATEN.kataloge.orte_api_compare_metrics);
// Die aufgezeichnete Katalog-Antwort in editor_standard.json ist auf die Ausblick-Felder
// gekuerzt; fuer die Alarm-Tabelle traegt hier die Boeen-Zeile ihr Register-Feld
// `alertMetric` (Wert wie GET /api/compare/metrics, #1435 E1a-1).
const ALARM_KATALOG = KATALOG.map((e) => (e.metric === 'gust_max_kmh' ? { ...e, alertMetric: 'wind_gust' } : e));
const DEFAULT_SPALTEN =['temperature', 'precipitation', 'rain_probability', 'wind', 'gust', 'thunder'];


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
const VOLLAUSWAHL = () => preset({ active_metrics: [...STANDARD] });

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

// Issue #3276: die Ausblick-Einbettung des Vergleichs (OutlookLayoutControls im
// Vergleichs-Zweig von WeatherMetricsTab) ist entfernt — Ausblick stellt der Ortsvergleich
// nur noch in „Was steht wo" ein. Die Hilfen `vergleichGrundauswahl`/`ausblickImEditor`
// entfallen mit ihr; die verbliebene Einbettung ist die des Trips (bis #3297).

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
		assert.deepEqual(a.activeMetricKeys, STANDARD);
		assert.deepEqual(w.activeMetricKeys, STANDARD);
	});
});

// Issue #3276: „Ausblick im Editor = Mail" fuer den Ortsvergleich entfaellt mit der Bedienflaeche
// (AC-1/AC-2 dieses Blocks pruefen den entfernten Ausblick-Block). Bestehen bleibt die
// Reiter-Reihenfolge-Unabhaengigkeit der Hydrierer samt Alarm-Tabelle (AC-3).
describe('#3061 Hydrier-Reihenfolge (Ausblick-Block entfernt, #3276)', () => {
	for (const [name, p] of [['Altbestand', ALTBESTAND], ['Vollauswahl', VOLLAUSWAHL]] as const) {
		test(`AC-3: ${name} -- Reiter-Reihenfolge aendert die Grundauswahl nicht, Alarm-Tabelle hat Metriken`, async () => {
			const alarmZuerst: Record<string, unknown> = {};
			alarmHydrierer(alarmZuerst, p());
			await wetterHydrierer(alarmZuerst, p());
			const wetterZuerst: Record<string, unknown> = {};
			await wetterHydrierer(wetterZuerst, p());
			alarmHydrierer(wetterZuerst, p());
			assert.deepEqual(alarmZuerst.activeMetricKeys, wetterZuerst.activeMetricKeys);
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
	// #3389: die Speicherer-Anteile (Snapshot/Diff-Nutzlast des toten Wetter-Metriken-Speicherers)
	// entfielen; AC-4 prueft jetzt nur noch die Hydration beim Oeffnen.
	test('AC-4: Altbestand oeffnen laesst activeMetricKeys null', async () => {
		const s: Record<string, unknown> = {};
		await wetterHydrierer(s, ALTBESTAND());
		alarmHydrierer(s, ALTBESTAND());
		assert.equal('hourly_enabled' in ALTBESTAND(), false, 'Messaufbau: der Altbestand traegt kein hourly_enabled');
		const layout = hydrateLayoutFieldsFromPreset(ALTBESTAND());
		Object.assign(s, layout);
		// #3276: der Ausblick-Block des Vergleichs ist entfernt; „Oeffnen" mountet ihn nicht mehr.
		assert.equal(s.activeMetricKeys, null, 'activeMetricKeys nach dem Oeffnen nicht mehr „nie eingestellt"');
		assert.deepEqual(layout, { hourlyEnabled: true }, 'Altbestand ohne hourly_enabled: Stundenverlauf an (Standard)');
	});

	// #3297/#3020: AC-5 (Trip-Einbettung von OutlookLayoutControls in WeatherMetricsTab) entfaellt — beide Dateien geloescht.
});
