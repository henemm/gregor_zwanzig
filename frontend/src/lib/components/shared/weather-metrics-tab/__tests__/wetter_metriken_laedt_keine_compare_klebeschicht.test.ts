// TDD RED — Issue #2276 Scheibe S4 (Epic #2345), AC-9: der geteilte
// `WeatherMetricsTab.svelte` lädt im vergleich-Kontext zur Laufzeit KEIN
// Modul aus `compare/compareHubWizardBridge.ts` mehr — seine kombinierte
// Vergleichs-Speicherung kommt aus
// `shared/weather-metrics-tab/weatherMetricsCompareSave.ts`. Ein
// Laufzeit-Import von `buildComparePresetSavePayload` aus
// `compare/compareEditorSave.ts` bleibt ausdrücklich zulässig.
//
// Spec: docs/specs/modules/rework_2276_s4_wetter_metriken.md — AC-9
//
// Nachweis über den tatsächlichen Ladegraphen, KEIN Dateiinhalt-/Grep-Check
// (Muster S2/S3: alarme_tab_laedt_keine_compare_klebeschicht.test.ts,
// corridor_editor_laedt_keine_compare_klebeschicht.test.ts): ein
// Auflösungs-Haken protokolliert jede Modul-URL, die beim Import + SSR-Render
// im `vergleich`-Kontext geladen wird. `import type` verschwindet beim
// Übersetzen und bleibt zulässig.
//
// RED HEUTE: WeatherMetricsTab.svelte importiert
// `weatherMetricsCompareSave.ts` heute NICHT (die kombinierte Orchestrierung
// wird heute noch in CompareTabs.svelte erzeugt, nicht im Tab selbst).
//
// Mutations-Gegenprobe (Spec): einen Laufzeit-Re-Import von
// `buildHubPutPayload` aus der alten Bridge einfügen ⇒ die Bridge erscheint
// im Ladegraphen ⇒ rot.
//
// Pfadregel #1409: Prüfling relativ zu DIESER Datei auflösen.
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/weather-metrics-tab/__tests__/wetter_metriken_laedt_keine_compare_klebeschicht.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register, registerHooks } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> weather-metrics-tab -> shared -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../../..');

/** Jede URL, die ab hier aufgelöst wird (Ladegraph des Prüflings). */
const geladen = new Set<string>();
registerHooks({
	resolve(specifier, context, nextResolve) {
		const ergebnis = nextResolve(specifier, context);
		geladen.add(ergebnis.url);
		return ergebnis;
	}
});

register(
	pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const { render } = await import('svelte/server');
const WeatherMetricsTab = (
	await import(pathToFileURL(path.join(FRONTEND, 'src/lib/components/shared/WeatherMetricsTab.svelte')).href)
).default;

const PRESET = {
	id: 'cp-2276-s4-graph',
	name: 'Ortsvergleich Graph',
	location_ids: ['loc-a', 'loc-b', 'loc-c'],
	schedule: 'daily',
	profil: 'wandern',
	hour_from: 6,
	hour_to: 9,
	empfaenger: [],
	created_at: '2026-01-01T00:00:00Z',
	hourly_enabled: true,
	outlook_enabled: true,
	day_window_start_hour: 4,
	day_window_end_hour: 19,
	display_config: {
		active_metrics: ['wind_max_kmh'],
		channel_active_metrics: {},
		hourly_metrics: ['wind_max_kmh'],
		outlook_metrics: ['wind_max_kmh'],
		outlook_metric_formats: {}
	}
};

function wizStub(): Record<string, unknown> {
	return {
		activityProfile: 'wandern',
		activeMetricKeys: ['wind_max_kmh'],
		channelActiveMetricKeys: { email: null, telegram: null, sms: null },
		officialAlertsEnabled: true,
		hourlyMetricKeys: ['wind_max_kmh'],
		hourlyEnabled: true,
		outlookMetricKeys: ['wind_max_kmh'],
		outlookMetricFormats: {},
		outlookEnabled: true,
		dayWindowStartHour: 4,
		dayWindowEndHour: 19
	};
}

/** Minimaler Speicher-Controller — nur für den Mount; SSR führt keine Speicherung aus. */
const controllerStub = {
	state: 'idle',
	hasPending: false,
	schedule() {},
	flush: async () => {},
	cancel() {},
	markPristine() {},
	setDirty() {}
};

const BRIDGE = '/src/lib/components/compare/compareHubWizardBridge.ts';
const NEUES_MODUL = '/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts';

function renderVergleich(): string {
	const { body } = render(WeatherMetricsTab as never, {
		props: {
			context: 'vergleich',
			wiz: wizStub(),
			saveController: controllerStub,
			preset: PRESET,
			enqueueHubWrite: <T>(fn: () => Promise<T>) => fn(),
			onCompareUpdate: () => {}
		} as never
	});
	return body;
}

describe('AC-9: WeatherMetricsTab lädt zur Laufzeit keine Compare-Klebeschicht', () => {
	test('Render im vergleich-Kontext mit den neuen Speicher-Props', () => {
		const body = renderVergleich();
		assert.ok(
			body.includes('weather-metrics-tab-vergleich') || body.includes('weather-metrics-vergleich'),
			'Vorbedingung: der Organismus muss im vergleich-Kontext rendern'
		);

		const liste = [...geladen];
		assert.ok(
			liste.some((u) => u.endsWith('/src/lib/components/shared/weather-metrics-tab/compareMetricOrder.ts')),
			'Vorbedingung: der Protokoll-Haken muss die Laufzeit-Importe von WeatherMetricsTab sehen — sonst beweist „Bridge fehlt" nichts'
		);
		assert.ok(
			liste.some((u) => u.endsWith(NEUES_MODUL)),
			'WeatherMetricsTab muss seine kombinierte Vergleichs-Speicherung aus weatherMetricsCompareSave.ts laden'
		);
		assert.deepEqual(
			liste.filter((u) => u.endsWith(BRIDGE)),
			[],
			'WeatherMetricsTab (oder ein von ihm geladenes Modul) lädt compare/compareHubWizardBridge.ts zur Laufzeit'
		);
	});
});
