// TDD RED — Fix #1544/#1545, Falle 4 (Kontext-Dokument): AC-6, der
// Datenverlust-Waechter. `buildAlarmeDeliveryPayload` sendet
// `metric_alert_levels` beim Speichern als VOLLSTAENDIGEN Ersatz
// (alarmeDeliveryPayload.ts:117-121), der Go-Merge ist flach
// (internal/handler/config_merge.go:11-22). Die neue, gefilterte
// Zeilen-Ableitung (`deriveActiveAlertMetricsForTrip`, s.
// trip_active_alert_metrics_derivation.test.ts) darf deshalb NUR in
// `activeMetrics` (Zeilen-Sichtbarkeit) einfliessen, NIE in `metricLevels`
// (Speicher-Quelle) -- sonst verliert eine deaktivierte Groesse beim
// naechsten Speichern ihre zuvor gesetzte Stufe unwiderruflich.
// Spec: docs/specs/modules/fix_1544_1545_trip_alarm_zeilen_ableitung.md
//   Implementation Details Punkt 4, Acceptance Criteria AC-6.
//
// Zwei Ebenen, weil eine reine Payload-Pruefung die eigentliche
// Fehlerquelle NICHT sieht (`buildAlarmeDeliveryPayload` selbst aendert sich
// in dieser Scheibe nicht -- der Fehler entstuende beim Umverdrahten von
// `AlarmeScheduleTab.svelte`):
//
//  1. Datenfluss-Nachweis: die neue Ableitung (gefiltert) UND der bestehende
//     Passthrough (ungefiltert) nebeneinander in eine Payload gefuehrt --
//     die deaktivierte Groesse bleibt im gesendeten Dict.
//  2. Verdrahtungs-Wächter (AST, Vorbild
//     shared/__tests__/alarme_tab_catalog_prop_structure.test.ts): in
//     `AlarmeScheduleTab.svelte` duerfen `activeMetrics` und `metricLevels`
//     NICHT aus derselben Quelle rechnen -- das ist der Punkt, an dem die
//     Mutations-Gegenprobe aus der Spec ("die Trennung activeMetrics/
//     metricLevels gezielt aufheben") tatsaechlich rot werden muss.
//
// RED heute: `deriveActiveAlertMetricsForTrip` fehlt (Ebene 1) UND
// `AlarmeScheduleTab.svelte` berechnet `activeMetrics` noch als
// `Object.keys(metricLevels)` -- am Register vorbei UND von `metricLevels`
// abhaengig (Ebene 2, verletzt die geforderte Trennung schon heute).
//
// Pfadregel #1409: alle Importe/Pfade relativ zu DIESER Datei.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/alarme-tab/__tests__/alarme_delivery_payload_preserves_inactive_levels.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { register } from 'node:module';
import { dirname, join, resolve as resolvePath } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { parse } from 'svelte/compiler';

import { buildAlarmeDeliveryPayload } from '../alarmeDeliveryPayload.ts';
import type { AlertMetric, MetricEntry, WeatherConfigMetric } from '../../../../types.ts';
import type { MetricCatalog } from '../../../trip-detail/metricsEditor.ts';

const here = dirname(fileURLToPath(import.meta.url));
const ALARME_SCHEDULE_TAB = join(here, '..', '..', '..', 'trip-detail', 'AlarmeScheduleTab.svelte');

type DeriveTripFn = (
	metrics: WeatherConfigMetric[] | undefined,
	catalog: MetricCatalog
) => AlertMetric[];

async function loadDeriveActiveAlertMetricsForTrip(): Promise<DeriveTripFn> {
	try {
		const mod = await import('../tripAlertMetricsFromCatalog.ts');
		const fn = (mod as Record<string, unknown>).deriveActiveAlertMetricsForTrip;
		if (typeof fn !== 'function') {
			assert.fail(
				'`deriveActiveAlertMetricsForTrip` ist in ' +
					'shared/alarme-tab/tripAlertMetricsFromCatalog.ts nicht exportiert (#1544/#1545).'
			);
		}
		return fn as DeriveTripFn;
	} catch (err) {
		assert.fail(
			'Die trip-weite Ableitung fehlt noch: erwartet wird ' +
				'`shared/alarme-tab/tripAlertMetricsFromCatalog.ts` mit ' +
				`\`deriveActiveAlertMetricsForTrip(metrics, catalog)\` (#1544/#1545). Ursache: ${String(err)}`
		);
	}
}

const CATALOG: MetricCatalog = {
	temperature: [
		{
			id: 'temperature',
			label: 'Temperatur',
			unit: '°C',
			category: 'temperature',
			default_enabled: true,
			has_friendly_format: false,
			change_alert_metric: 'temperature_change',
			aggregations: [
				{ id: 'min', label: 'Minimum', alert_metric: 'temperature_min' },
				{ id: 'max', label: 'Maximum', alert_metric: 'temperature_max' },
				{ id: 'avg', label: 'Mittel', alert_metric: null }
			]
		} as unknown as MetricEntry
	],
	wind: [
		{
			id: 'gust',
			label: 'Böen',
			unit: 'km/h',
			category: 'wind',
			default_enabled: true,
			has_friendly_format: false,
			change_alert_metric: null,
			aggregations: [{ id: 'max', label: 'Maximum', alert_metric: 'wind_gust' }]
		} as unknown as MetricEntry
	]
};

describe('#1544/#1545 AC-6 Ebene 1: gesendete Payload behaelt die Stufe der deaktivierten Groesse', () => {
	test('Böen deaktiviert -> Zeile verschwindet, gespeicherter Wert bleibt im Payload', async () => {
		const derive = await loadDeriveActiveAlertMetricsForTrip();

		// Bestand: der Nutzer hatte "Böen" (wind_gust) frueher auf "sensibel"
		// gesetzt, deaktiviert die Groesse jetzt aber im Wetter-Reiter.
		const persistierteStufen: Record<string, string> = {
			wind_gust: 'sensibel',
			temperature_max: 'standard'
		};
		const metrics: WeatherConfigMetric[] = [
			{ metric_id: 'gust', enabled: false },
			{ metric_id: 'temperature', enabled: true }
		];

		const zeilen = derive(metrics, CATALOG);
		assert.ok(
			!zeilen.includes('wind_gust'),
			'Vorbedingung: die deaktivierte Groesse zeigt keine Zeile mehr.'
		);

		// `metricLevels` bleibt der UNGEFILTERTE Passthrough -- exakt das
		// heutige Verhalten von AlarmeScheduleTab.svelte:36-38
		// (`trip.display_config?.metric_alert_levels ?? {}`), das diese Etappe
		// NICHT aendern darf.
		const payload = buildAlarmeDeliveryPayload({
			officialWarningsEnabled: false,
			channels: { email: true, telegram: false, sms: false },
			metricLevels: persistierteStufen
		}) as { display_config?: { metric_alert_levels?: Record<string, string> } };

		assert.equal(
			payload.display_config?.metric_alert_levels?.wind_gust,
			'sensibel',
			'Die Stufe der deaktivierten Groesse "Böen" fehlt im gesendeten Payload ' +
				`-- Datenverlust (AC-6). Erhalten: ${JSON.stringify(payload.display_config)}`
		);
	});
});

// ── Ebene 2: Verdrahtungs-Waechter ──────────────────────────────────────────
// AST statt Dateiinhalt-Grep (Vorbild:
// shared/__tests__/alarme_tab_catalog_prop_structure.test.ts).

function parseFile(path: string): any {
	return parse(readFileSync(path, 'utf-8'), { modern: true });
}

function identifiers(subtree: unknown): Set<string> {
	const found = new Set<string>();
	function visit(node: unknown): void {
		if (node === null || typeof node !== 'object') return;
		if (Array.isArray(node)) {
			node.forEach(visit);
			return;
		}
		const n = node as Record<string, any>;
		if (n.type === 'Identifier' && typeof n.name === 'string') found.add(n.name);
		for (const key of Object.keys(n)) {
			if (key === 'parent') continue;
			visit(n[key]);
		}
	}
	visit(subtree);
	return found;
}

/** Der `$derived(...)`-Initialisierer einer benannten Instanz-Variable. */
function derivedInit(ast: any, name: string): any {
	const decl = (ast.instance?.content?.body ?? [])
		.filter((n: any) => n.type === 'VariableDeclaration')
		.flatMap((n: any) => n.declarations)
		.find((d: any) => d.id?.type === 'Identifier' && d.id.name === name);
	assert.ok(decl, `Keine Variable \`${name}\` im Instance-Script von AlarmeScheduleTab.svelte gefunden.`);
	assert.equal(decl.init?.type, 'CallExpression');
	assert.equal(decl.init.callee?.name, '$derived');
	return decl.init.arguments[0];
}

describe('#1544/#1545 AC-6 Ebene 2: `activeMetrics` und `metricLevels` rechnen unabhaengig', () => {
	test('`activeMetrics` ruft die neue Register-Ableitung auf, nicht mehr `Object.keys(metricLevels)`', () => {
		const namen = identifiers(derivedInit(parseFile(ALARME_SCHEDULE_TAB), 'activeMetrics'));
		assert.ok(
			namen.has('deriveActiveAlertMetricsForTrip'),
			'`activeMetrics` in AlarmeScheduleTab.svelte ruft die neue, register-' +
				'gestuetzte Ableitung `deriveActiveAlertMetricsForTrip` nicht auf ' +
				'(Fehlerklasse 1, "Der Fehler": Object.keys(metricLevels)).'
		);
	});

	test('`activeMetrics` haengt NICHT (mehr) an `metricLevels`', () => {
		const namen = identifiers(derivedInit(parseFile(ALARME_SCHEDULE_TAB), 'activeMetrics'));
		assert.equal(
			namen.has('metricLevels'),
			false,
			'`activeMetrics` liest weiterhin `metricLevels` -- das ist exakt der ' +
				'heutige Fehler (Zeilen nur fuer bereits persistierte Schluessel, ' +
				'Fehlerklasse 1, unsichtbare Scharfschaltung).'
		);
	});

	test('`metricLevels` bleibt der ungefilterte Passthrough -- kein Bezug zu `activeMetrics`', () => {
		const namen = identifiers(derivedInit(parseFile(ALARME_SCHEDULE_TAB), 'metricLevels'));
		for (const verboten of ['activeMetrics', 'deriveActiveAlertMetricsForTrip']) {
			assert.equal(
				namen.has(verboten),
				false,
				`\`metricLevels\` bezieht sich auf \`${verboten}\` -- damit teilen sich ` +
					'Zeilen-Sichtbarkeit und Speicher-Quelle dieselbe gefilterte ' +
					'Basis. Ein spaeteres Speichern wuerde dann die Stufe jeder ' +
					'gerade nicht angezeigten Groesse unwiderruflich loeschen (AC-6, ' +
					'Falle 4 aus dem Kontext-Dokument).'
			);
		}
	});
});

// ── Ebene 3: LAUFZEIT-Wirkung statt Schreibweise ────────────────────────────
// Adversary Fix-Loop, F001: Ebene 2 prueft nur die literalen Bezeichner im
// `$derived`-Initialisierer. Koppelt man `metricLevels` funktional identisch an
// die gefilterte Menge, aber ueber eine umbenannte Zwischenvariable, bleibt
// Ebene 2 gruen und der Datenverlust traete trotzdem ein -- geprueft war, wo
// der Code STEHT, nicht wo er WIRKT.
//
// Hier laeuft die echte Kette: Trip-Zustand -> ECHTES serverseitiges Rendern
// von AlarmeScheduleTab.svelte (svelte/server + test-svelte-ssr-hooks.mjs,
// Vorbild versand-tab/__tests__/channel_checkbox_dedupe_render.test.ts) ->
// LAUFZEITWERT der `metricLevels`-Prop -> echter AlarmeTab (sein Markup zeigt
// `routeMetricLevels`) -> echte `buildAlarmeDeliveryPayload`. Kein
// Mock-Theater: ersetzt ist allein die SENKE (das Kind des Containers), um an
// die vom unveraenderten Produktivcode erzeugten Werte zu kommen.
//
// Grenze (ehrlich): `$effect` laeuft unter SSR nicht, ein DOM-Shim fehlt (kein
// jsdom/happy-dom in package.json) -- der Save-Effekt selbst ist nicht
// ausloesbar. Die letzte Fuge (`routeMetricLevels` -> `buildAlarmeSaveFn`) ist
// eine Zeile und durch shared/__tests__/alarme_save_single_writer.test.ts
// abgedeckt; alles davor ist hier gemessen.

const FRONTEND = resolvePath(here, '../../../../../..');
register(
	pathToFileURL(join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

(globalThis as any).__gzAlarmeTabProps = [];
// Nur der Import AUS AlarmeScheduleTab.svelte heraus wird umgelenkt --
// derselbe Import weiter unten in dieser Datei liefert die echte Komponente.
register(
	'data:text/javascript,' +
		encodeURIComponent(`
export async function resolve(specifier, context, nextResolve) {
  if ((context.parentURL ?? '').endsWith('/AlarmeScheduleTab.svelte')
      && specifier.endsWith('shared/AlarmeTab.svelte')) {
    return { url: 'gz-stub:alarme-tab', shortCircuit: true };
  }
  return nextResolve(specifier, context);
}
export async function load(url, context, nextLoad) {
  if (url === 'gz-stub:alarme-tab') {
    return { format: 'module', shortCircuit: true,
      source: 'export default function(_p, props) { globalThis.__gzAlarmeTabProps.push(props); }' };
  }
  return nextLoad(url, context);
}`)
);

const { render } = await import('svelte/server');
const AlarmeScheduleTab = (
	await import(pathToFileURL(join(FRONTEND, 'src/lib/components/trip-detail/AlarmeScheduleTab.svelte')).href)
).default;
const AlarmeTab = (
	await import(pathToFileURL(join(FRONTEND, 'src/lib/components/shared/AlarmeTab.svelte')).href)
).default;

/** Trip-Zustand des Bugs: "Böen" traegt eine gespeicherte Stufe UND ist im
 *  Wetter-Reiter deaktiviert. */
const TRIP_MIT_DEAKTIVIERTER_BOE = {
	id: 'trip-ac6',
	display_config: {
		metric_alert_levels: { wind_gust: 'sensibel', temperature_max: 'standard' },
		metrics: [
			{ metric_id: 'gust', enabled: false },
			{ metric_id: 'temperature', enabled: true }
		]
	}
};

describe('#1544/#1545 AC-6 Ebene 3: die Kette bis zur gesendeten Nutzlast, zur Laufzeit gemessen', () => {
	test('Böen deaktiviert: Zeile weg, Stufe bleibt im Payload — unabhaengig von jeder Schreibweise', () => {
		(globalThis as any).__gzAlarmeTabProps = [];
		// `.body` lesen ist Pflicht: svelte/server rendert erst beim Zugriff.
		const containerHtml = render(AlarmeScheduleTab, {
			props: { trip: TRIP_MIT_DEAKTIVIERTER_BOE, metricsCatalog: CATALOG }
		}).body;
		assert.match(containerHtml, /alarme-schedule-tab/);
		const props = (globalThis as any).__gzAlarmeTabProps;
		assert.equal(props.length, 1, 'AlarmeScheduleTab hat den AlarmeTab nicht genau einmal gerendert.');
		const { activeMetrics, metricLevels } = props[0] as {
			activeMetrics: AlertMetric[];
			metricLevels: Record<string, string>;
		};

		assert.ok(
			!activeMetrics.includes('wind_gust' as AlertMetric),
			`Vorbedingung: die deaktivierte Groesse zeigt keine Zeile mehr. Erhalten: ${JSON.stringify(activeMetrics)}`
		);

		// Der Kern: die SPEICHER-Quelle darf NICHT mitgefiltert sein. Gemessen am
		// Laufzeitwert -- eine umbenannte Zwischenvariable rettet hier nichts.
		assert.equal(
			metricLevels?.wind_gust,
			'sensibel',
			'Die `metricLevels`-Prop, die AlarmeScheduleTab zur Laufzeit liefert, hat ' +
				'die Stufe der deaktivierten Groesse verloren. Beim naechsten Speichern ' +
				'ersetzt sie `metric_alert_levels` vollstaendig (Go-Merge ist flach) -- ' +
				`unwiderruflicher Datenverlust (AC-6). Erhalten: ${JSON.stringify(metricLevels)}`
		);

		// Fuge 2, ebenfalls zur Laufzeit: der ECHTE AlarmeTab uebernimmt diesen
		// Wert in `routeMetricLevels` (im Markup an `data-level` ablesbar) -- hier
		// mit erzwungen sichtbarer Zeile, damit der Wert ueberhaupt gerendert wird.
		const html = render(AlarmeTab, {
			props: {
				context: 'route',
				trip: TRIP_MIT_DEAKTIVIERTER_BOE,
				activeMetrics: ['wind_gust'],
				metricLevels,
				existingChannels: { email: true, telegram: false, sms: false }
			}
		}).body;
		assert.match(
			html,
			/data-testid="alert-metric-row-wind_gust"[^>]*data-level="sensibel"/,
			'Der echte AlarmeTab uebernimmt die durchgereichte Stufe nicht in seinen ' +
				'`routeMetricLevels`-Zustand -- damit ginge sie im konsolidierten Save verloren.'
		);

		// Fuge 3: dieselben Werte durch die ECHTE Payload-Funktion.
		const payload = buildAlarmeDeliveryPayload({
			officialWarningsEnabled: false,
			channels: { email: true, telegram: false, sms: false },
			metricLevels
		}) as { display_config?: { metric_alert_levels?: Record<string, string> } };
		assert.equal(
			payload.display_config?.metric_alert_levels?.wind_gust,
			'sensibel',
			'Die tatsaechlich gesendete Nutzlast hat die Stufe der deaktivierten ' +
				`Groesse verloren (AC-6). Erhalten: ${JSON.stringify(payload.display_config)}`
		);
	});
});
