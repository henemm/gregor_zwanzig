// TDD — Fix-Loop #2276 S6g, Adversary-Finding F001 (MEDIUM,
// docs/artifacts/refactor-2276-s6g-wmt-wertprops/adversary-dialog.md, Runde 2/M10):
// `WeatherMetricsTab.svelte` bindet seit dieser Scheibe im Vergleichs-Zweig eine
// Wertprop `officialAlertsEnabled` (und `outlookMetricKeys`/`outlookMetricFormats`)
// — GLEICHNAMIG zu den route-eigenen State-Variablen, die deshalb den Suffix
// `Route` tragen (`officialAlertsEnabledRoute`/`outlookMetricKeysRoute`/
// `outlookMetricFormatsRoute`). Kein Kern-Test band bisher den tatsaechlichen
// Rueckschreibpfad (PUT-Payload) an die ROUTE-Werte — ein Tippfehler/
// Autocomplete-Fehlgriff, der an einer Schreibstelle `…Route` durch den
// gleichnamigen (im Trip-Kontext IMMER `undefined`) Bezeichner ohne Suffix
// ersetzt, waere unbeobachtet durchgelaufen (TypeScript meldet nichts — beide
// Bezeichner sind an der Stelle typkompatibel, `boolean | undefined`).
//
// Diese Datei fuehrt den ECHTEN Rueckschreibpfad im Kontext `context="route"`
// (Trip-Mount OHNE Vergleichs-Wertprops — exakt wie TripTabs.svelte/
// TripEditView.svelte/TripNewEditor.svelte mounten) aus: die drei echten
// Handler `onOutlookMetricKeys`/`onOutlookMetricFormats`/`onToggleOfficialAlerts`
// loesen `scheduleAutoSave()` aus, die wiederum `baueWetterMetrikenSpeicherung`
// (echter Produktivcode, `tripSpeicherung.ts`) mit einem AUFZEICHNENDEN
// `PutClient` verdrahtet — kein Mock, sondern derselbe Aufzeichnungs-Ansatz wie
// in `wetter_metriken_speichern_beim_entladen.test.ts` begruendet (Zusicherung
// dort messen, wo das Modul entscheidet: an seinen Aufrufen des Clients).
//
// Kein Rendering-Harness fuer Svelte-5-Runen im node:test-Setup (SSR-only,
// kein DOM/`$effect`) — deshalb der Herleitungs-Pruefstand `svelteInstanzPruefstand.ts`
// (Praezedenz: compare_wetter_metriken_wertprops.test.ts AC-3).
//
// Spec: docs/specs/modules/rework_2276_s6g_wetter_metriken_wertprops.md (AC-6)
// Pfadregel #1409: alles relativ zu DIESER Datei aufgeloest.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/shared/__tests__/wetter_metriken_trip_speichert_eigene_ausblick_und_warnungswerte.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { umgebungFuer, type Knoten } from './svelteInstanzPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const TAB = join(HIER, '..', 'WeatherMetricsTab.svelte');

/** Die zehn Vergleichs-Wertprops + neun Rueckrufe — im Trip-Mount NIE gebunden
 *  (TripTabs.svelte/TripEditView.svelte/TripNewEditor.svelte reichen sie nicht
 *  durch). Explizit `undefined` gesaet statt weggelassen: genau der Zustand,
 *  den `officialAlertsEnabled`/`outlookMetricKeys`/`outlookMetricFormats`
 *  (OHNE `Route`-Suffix) im echten Trip-Mount haben. */
const WERTPROPS = [
	'activeMetricKeys', 'channelActiveMetricKeys', 'officialAlertsEnabled',
	'dayWindowStartHour', 'dayWindowEndHour', 'hourlyMetricKeys', 'hourlyEnabled',
	'outlookMetricKeys', 'outlookMetricFormats', 'outlookEnabled',
] as const;
const RUECKRUFE = [
	'onVergleichsMetrikenChange', 'onOfficialAlertsEnabledChange',
	'onDayWindowStartHourChange', 'onDayWindowEndHourChange', 'onHourlyMetricKeysChange',
	'onHourlyEnabledChange', 'onOutlookMetricKeysChange', 'onOutlookMetricFormatsChange',
	'onOutlookEnabledChange',
] as const;

const TRIP_ID = 't-2276-s6g-wmt';
/** Der route-eigene Anfangswert weicht bewusst vom spaeter gesetzten ROUTE-Wert
 *  ab (true -> false) — ein Test, der still den Anfangswert durchreicht statt
 *  den tatsaechlich getoggelten, wuerde sonst faelschlich gruen. */
const TRIP = {
	id: TRIP_ID,
	display_config: { channels: { email: true, telegram: true, sms: false } },
	report_config: { day_window_start_hour: 6, day_window_end_hour: 20 },
	official_alerts_enabled: true,
};

const ROUTE_OFFICIAL_ALERTS = false;
const ROUTE_OUTLOOK_KEYS = ['temp_max_c'];
const ROUTE_OUTLOOK_FORMATS = { temp_max_c: true };

interface PutAufruf { path: string; body: Knoten; }

/** Aufzeichnender Client (kein Mock/keine Annahme-Rueckgabe): haelt jeden
 *  `put`-Aufruf mit SEINER echten Kennung/seinem echten Koerper fest — dieselbe
 *  Begruendung wie `wetter_metriken_speichern_beim_entladen.test.ts`. */
function aufzeichnenderClient(): { client: { put: (path: string, body: unknown) => Promise<Knoten> }; puts: PutAufruf[] } {
	const puts: PutAufruf[] = [];
	const client = {
		put: async (path: string, body: unknown) => {
			puts.push({ path, body: body as Knoten });
			return {} as Knoten;
		},
	};
	return { client, puts };
}

/** Saat fuer den ECHTEN Trip-Mount (context="route", keine Vergleichs-Wertprops). */
function saatRoute(zusatz: Knoten = {}): Knoten {
	return {
		context: 'route',
		untrack: (fn: () => unknown) => fn(),
		trip: TRIP,
		createMode: false,
		onChannelsChange: undefined,
		onWeatherMetricsChange: undefined,
		onDayWindowChange: undefined,
		onTripUpdate: undefined,
		...Object.fromEntries([...WERTPROPS, ...RUECKRUFE].map((n) => [n, undefined])),
		preset: undefined,
		onCompareUpdate: undefined,
		enqueueHubWrite: undefined,
		catalogLoaded: true,
		...zusatz,
	};
}

describe('AC-6 (Trip, context=route): der echte Rueckschreibpfad traegt die ROUTE-Werte, nicht die (im Trip immer leere) Vergleichs-Wertprop', () => {
	test('onOutlookMetricKeys/onOutlookMetricFormats/onToggleOfficialAlerts -> scheduleAutoSave() schickt die ROUTE-Werte in die echten PUT-Bodies', async () => {
		const { client, puts } = aufzeichnenderClient();
		let geplant = null as ((init?: RequestInit) => Promise<void>) | null;
		const saveController = {
			schedule: (fn: (init?: RequestInit) => Promise<void>) => { geplant = fn; },
			setDirty: () => {},
			cancel: () => {},
			markPristine: () => {},
		};

		const { u } = await umgebungFuer(TAB, saatRoute({ api: client, saveController }));

		assert.strictEqual(typeof u.onOutlookMetricKeys, 'function', 'Messaufbau kaputt: onOutlookMetricKeys nicht herleitbar.');
		assert.strictEqual(typeof u.onOutlookMetricFormats, 'function', 'Messaufbau kaputt: onOutlookMetricFormats nicht herleitbar.');
		assert.strictEqual(typeof u.onToggleOfficialAlerts, 'function', 'Messaufbau kaputt: onToggleOfficialAlerts nicht herleitbar.');

		// Echte Handler-Aufrufe, wie sie eine DOM-Geste ausloesen wuerde — nicht
		// direktes Setzen der State-Variablen.
		(u.onOutlookMetricKeys as (k: string[]) => void)(ROUTE_OUTLOOK_KEYS);
		(u.onOutlookMetricFormats as (f: Record<string, boolean>) => void)(ROUTE_OUTLOOK_FORMATS);
		(u.onToggleOfficialAlerts as (e: Event) => void)({
			target: { checked: ROUTE_OFFICIAL_ALERTS },
		} as unknown as Event);

		assert.ok(geplant, 'Messaufbau kaputt: scheduleAutoSave() hat saveController.schedule() nie aufgerufen.');
		await geplant!();

		assert.strictEqual(puts.length, 2, `Erwartet zwei PUTs (weather-config + trip), bekommen: ${JSON.stringify(puts.map((p) => p.path))}`);
		const [wetterPut, tripPut] = puts;

		assert.strictEqual(wetterPut.path, `/api/trips/${TRIP_ID}/weather-config`);
		assert.deepStrictEqual(
			wetterPut.body.outlook_metrics,
			ROUTE_OUTLOOK_KEYS,
			'F001: outlook_metrics in der weather-config-PUT-Payload muss der ROUTE-Wert ' +
				'(outlookMetricKeysRoute) sein, nicht die (im Trip-Mount immer undefined) ' +
				'Vergleichs-Wertprop outlookMetricKeys.'
		);
		assert.deepStrictEqual(
			wetterPut.body.outlook_metric_formats,
			ROUTE_OUTLOOK_FORMATS,
			'F001: outlook_metric_formats in der weather-config-PUT-Payload muss der ROUTE-Wert ' +
				'(outlookMetricFormatsRoute) sein, nicht die Vergleichs-Wertprop outlookMetricFormats.'
		);

		assert.strictEqual(tripPut.path, `/api/trips/${TRIP_ID}`);
		assert.strictEqual(
			tripPut.body.official_alerts_enabled,
			ROUTE_OFFICIAL_ALERTS,
			'F001: official_alerts_enabled in der Trip-PUT-Payload muss der ROUTE-Wert ' +
				'(officialAlertsEnabledRoute) sein, nicht die (im Trip-Mount immer undefined) ' +
				'Vergleichs-Wertprop officialAlertsEnabled.'
		);
	});
});
