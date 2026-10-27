// TDD RED — Issue #2215 (AC-9, Familien Wetter-Metriken + Briefing-Zeitplan):
// Wenn das Speicher-Gate `skip` entscheidet (Katalog nicht geladen bzw. keine
// Nutzergeste), steht auf dem Bildschirm ein ungespeicherter Stand. Der Editor
// muss das als „offener Zwischenstand" melden (`setUnsavedInput()`), NICHT per
// `setDirty()` — sonst überschreibt ein bereits vorgemerkter Save die Anzeige
// mit „Gespeichert".
//
// Spec: docs/specs/modules/fix_2215_unsaved_input_marker.md
// Wirkort-Prüfstand `svelteInstanzPruefstand.ts`: die ECHTEN Funktionen
// `scheduleAutoSave`/`scheduleReportConfigOnlySave`/`handleSave` (WeatherMetricsTab)
// bzw. der echte report_config-Effekt (BriefingScheduleTab) laufen; der Controller
// zeichnet den gerufenen Meldeweg auf. Nur `context="route"` (Trip) erreicht diese
// Zeilen — im Vergleich speichert der Hub über eine eigene Orchestrierung.
//
// Regression EditStagesPanelNew: `setDirty()` (vorgemerkter Save läuft, danach
// „Gespeichert") bleibt unverändert — Kerntest 6 in
// `src/lib/stores/__tests__/saveStatus_ungespeicherter_zwischenstand.test.ts`.
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/speicher_anzeige_zwischenstand_wetter_und_briefing.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { umgebungFuer, effekteVon, type Knoten } from './svelteInstanzPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const WETTER = join(HIER, '..', 'WeatherMetricsTab.svelte');
const BRIEFING = join(HIER, '..', '..', 'trip-detail', 'BriefingScheduleTab.svelte');

interface Aufrufe {
	schedule: number;
	setDirty: number;
	setUnsavedInput: number;
}

function controller(a: Aufrufe) {
	return {
		schedule: () => a.schedule++,
		setDirty: () => a.setDirty++,
		setUnsavedInput: () => a.setUnsavedInput++,
		cancel: () => {},
		markPristine: () => {}
	};
}

const keine = (): Aufrufe => ({ schedule: 0, setDirty: 0, setUnsavedInput: 0 });

const WERTPROPS = [
	'activeMetricKeys', 'channelActiveMetricKeys', 'officialAlertsEnabled',
	'dayWindowStartHour', 'dayWindowEndHour', 'hourlyMetricKeys', 'hourlyEnabled',
	'outlookMetricKeys', 'outlookMetricFormats', 'outlookEnabled',
	'onVergleichsMetrikenChange', 'onOfficialAlertsEnabledChange',
	'onDayWindowStartHourChange', 'onDayWindowEndHourChange', 'onHourlyMetricKeysChange',
	'onHourlyEnabledChange', 'onOutlookMetricKeysChange', 'onOutlookMetricFormatsChange',
	'onOutlookEnabledChange'
];

function saatWetter(a: Aufrufe): Knoten {
	return {
		context: 'route',
		untrack: (fn: () => unknown) => fn(),
		trip: {
			id: 't-2215',
			display_config: { channels: { email: true, telegram: true, sms: false } },
			report_config: { day_window_start_hour: 6, day_window_end_hour: 20 },
			official_alerts_enabled: true
		},
		createMode: false,
		onChannelsChange: undefined,
		onWeatherMetricsChange: undefined,
		onDayWindowChange: undefined,
		onTripUpdate: undefined,
		...Object.fromEntries(WERTPROPS.map((n) => [n, undefined])),
		preset: undefined,
		onCompareUpdate: undefined,
		enqueueHubWrite: undefined,
		// Gate `skip`: Katalog (noch) nicht geladen, keine Nutzergeste.
		catalogLoaded: false,
		api: { put: async () => ({}) },
		saveController: controller(a)
	};
}

describe('#2215 AC-9: Wetter-Metriken meldet „keine Nutzergeste / Gate skip" als offenen Zwischenstand', () => {
	for (const name of ['scheduleAutoSave', 'scheduleReportConfigOnlySave', 'handleSave']) {
		test(`${name}() bei Gate skip → setUnsavedInput, nicht setDirty`, async () => {
			const a = keine();
			const { u } = await umgebungFuer(WETTER, saatWetter(a));
			assert.equal(typeof u[name], 'function', `Messaufbau kaputt: ${name} nicht herleitbar.`);
			await (u[name] as () => unknown)();
			assert.equal(a.schedule, 0, 'Messaufbau kaputt: Gate war nicht skip (es wurde ein Save geplant).');
			assert.equal(a.setUnsavedInput, 1, `${name}: der Gate-skip-Stand muss setUnsavedInput() melden`);
			assert.equal(a.setDirty, 0, `${name}: setDirty() ließe einen vorgemerkten Save „Gespeichert" melden (#2215)`);
		});
	}
});

describe('#2215 AC-9: Briefing-Zeitplan meldet geänderte Eingabe ohne Nutzergeste als offenen Zwischenstand', () => {
	test('report_config-Effekt: Änderung bei Gate skip → setUnsavedInput, nicht setDirty', async () => {
		const a = keine();
		const saat: Knoten = {
			trip: { id: 't-2215', report_config: { send_time_morning: '07:00:00' } },
			onTripUpdate: undefined,
			saveController: controller(a),
			onJump: undefined,
			api: { put: async () => ({}) }
		};
		const { u, ast, quelle } = (await umgebungFuer(BRIEFING, saat)) as Knoten;
		const effekte = effekteVon(ast, quelle, u, 'reportConfig');
		assert.ok(effekte.length >= 1, 'Messaufbau kaputt: kein report_config-Effekt gefunden.');
		// Eingabe ändert sich inhaltlich, ohne dass eine Nutzergeste erfasst wurde.
		u.reportConfig = { send_time_morning: '08:30:00' };
		for (const effekt of effekte) effekt();
		assert.equal(a.schedule, 0, 'Messaufbau kaputt: Gate war nicht skip.');
		assert.equal(a.setUnsavedInput, 1, 'der Gate-skip-Stand muss setUnsavedInput() melden');
		assert.equal(a.setDirty, 0, 'setDirty() ließe einen vorgemerkten Save „Gespeichert" melden (#2215)');
	});
});
