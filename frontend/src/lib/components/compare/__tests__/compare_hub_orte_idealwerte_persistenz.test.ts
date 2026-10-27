// TDD RED — Issue #2276 Scheibe S6f (Epic #2345): Bridge-Umzug. Dieser Teil
// der ehemaligen `compare_hub_wizard_bridge.test.ts` (Issue #1256 Scheibe 6/7,
// AC-33/AC-34, Edge Case Z.1020, Issue #2276 S3/#1703 S8) testet
// `buildHubPutPayload`/`snapshotForRollback`/`buildToggleActivePutPayload`,
// jetzt aus `../compareHubPersistenz.ts`.
//
// Spec: docs/specs/modules/rework_2276_s6f_bridge_umzug.md — AC-1 (Test-Plan:
//   `compare_hub_wizard_bridge.test.ts` SPLIT + RENAME)
// Vorgaenger-Spec (Funktions-API/Zusicherungen unveraendert):
//   docs/specs/modules/issue_1256_compare_ui_rewire.md § Scheibe 6/7
//
// `compareHubPersistenz.ts` existiert noch NICHT — der Import schlaegt heute
// fehl (RED), bis S6f das Modul anlegt (Umzug byte-identisch aus der
// aufgeloesten Compare-Hub-Klebeschicht).
//
// Reine Verhaltenstests (echter Funktionsaufruf, KEIN Mock, KEINE
// Datei-Inhalt-Pruefung, KEIN DOM-Rendering — Projekt-Idiom analog
// channel_names_label.test.ts).
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/compare_hub_orte_idealwerte_persistenz.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import type { ComparePreset } from '../../../types.ts';
import { snapshotForRollback, buildToggleActivePutPayload } from '../compareHubPersistenz.ts';
import { buildComparePresetPartialPayload } from '../compareEditorSave.ts';
// Issue #2276 S3: Diff-/Payload-Entscheidung des Wertebereiche-Reiters ist aus
// der Bridge in das geteilte Speichermodul umgezogen — Zusicherungen unveraendert.
import {
	flushPendingCorridorSave,
	type CorridorSnapshot
} from '../../shared/corridor-editor/wertebereicheVergleichSpeicherung.ts';
// Issue #1703 Scheibe 8 (Bearbeiten-Pfad) — s. letztes describe dieser Datei.
import type { CompareChannelActiveMetrics } from '../../shared/weather-metrics-tab/compareChannelMetricLayouts.ts';
import { toCompareSelectionEntries } from '../../shared/weather-metrics-tab/compareMetricSelection.ts';
import {
	flushPendingWeatherMetricsSave,
	hydrateChannelActiveMetricsFromPreset,
	type WeatherMetricsSnapshot
} from '../../shared/weather-metrics-tab/weatherMetricsCompareSave.ts';

// Fixture nach dem echten DTO (compareEditorSave.ts:71-162, routes/compare/[id]/edit/+page.svelte:19-86):
// location_ids/schedule/profil/display_config (region, ideal_ranges, active_metrics,
// metric_alert_levels) + Top-Level `corridors` (Issue #1231 Slice 4). channel_layouts
// ist seit #1351 (AC-6) kein Compare-Feld mehr — ein realistisches Preset führt es nicht.
function makePreset(overrides: Partial<ComparePreset> = {}): ComparePreset {
	return {
		id: 'cmp-42',
		name: 'Skigebiete Tirol',
		location_ids: ['loc-1', 'loc-2', 'loc-3'],
		schedule: 'daily',
		weekday: 0,
		profil: 'wintersport',
		hour_from: 6,
		hour_to: 9,
		empfaenger: ['urlauber@example.com'],
		forecast_hours: 48,
		letzter_versand: undefined,
		top_ort_letzter_versand: null,
		created_at: '2026-01-01T00:00:00Z',
		corridors: [{ metric: 'snow_depth_cm', range: [20, null], notify: true, mark: true, prio: 'hoch' }],
		display_config: {
			region: 'Tirol',
			ideal_ranges: { snow_depth_cm: { min: 20, max: null } },
			active_metrics: ['snow_depth_cm', 'wind_gust'],
			metric_alert_levels: { snow_depth_cm: 'warn', wind_gust: 'mark' }
		},
		...overrides
	};
}

describe('AC-33/AC-34 + #1257/#1234-Kontext (seit #2375): Orte-/Korridor-Edit senden nur Eigenfelder', () => {
	test('Korridor-Edit (flushPendingCorridorSave): kein location_ids/name/schedule im Body', () => {
		const preset = makePreset();
		const dc = preset.display_config as Record<string, unknown>;
		const before: CorridorSnapshot = {
			corridors: preset.corridors!,
			idealRanges: dc.ideal_ranges as CorridorSnapshot['idealRanges'],
			activeMetricKeys: ['snow_depth_cm', 'wind_gust'],
			metricAlertLevels: dc.metric_alert_levels as Record<string, string>
		};
		const newCorridors = [
			{ metric: 'snow_depth_cm', range: [30, null] as [number | null, number | null], notify: true, mark: true, prio: 'hoch' as const }
		];
		const result = flushPendingCorridorSave(preset, { ...before, corridors: newCorridors }, before);
		assert.notStrictEqual(result, null);
		const body = result!.body as unknown as Record<string, unknown>;
		assert.deepStrictEqual(body.corridors, newCorridors, 'corridors muss die editierte neue Zeile widerspiegeln');
		for (const fremd of ['location_ids', 'name', 'schedule', 'profil']) {
			assert.ok(!(fremd in body), `Fremdfeld ${fremd} darf nicht im Korridor-PUT stehen`);
		}
	});

	test('Orte-Edit (Reorder/Entfernen): Body ist exakt { location_ids } — display_config bleibt unangetastet', () => {
		const preset = makePreset();
		const newPickedIds = ['loc-3', 'loc-1', 'loc-2'];
		const { body } = buildComparePresetPartialPayload(preset.id, { location_ids: newPickedIds });
		assert.deepStrictEqual(body, { location_ids: newPickedIds });
	});
});

describe('Fix-Loop 1 (F002, Adversary HIGH): flushPendingCorridorSave — reine Diff-/Payload-Entscheidung, entkoppelt vom ausloesenden DOM-Event', () => {
	function makeSnapshot(overrides: Partial<CorridorSnapshot> = {}): CorridorSnapshot {
		return {
			corridors: [{ metric: 'snow_depth_cm', range: [20, null], notify: true, mark: true, prio: 'hoch' }],
			idealRanges: { snow_depth_cm: { min: 20, max: null } },
			activeMetricKeys: ['snow_depth_cm', 'wind_gust'],
			metricAlertLevels: { snow_depth_cm: 'warn', wind_gust: 'mark' },
			...overrides
		};
	}

	test('unveraenderter ws-Zustand + flush → kein PUT (null), egal welches Ereignis den Flush ausgeloest hat', () => {
		const preset = makePreset();
		const before = makeSnapshot();
		const current = makeSnapshot();
		const result = flushPendingCorridorSave(preset, current, before);
		assert.strictEqual(result, null, 'unveraenderter Snapshot darf keinen PUT ausloesen (Waechter gegen unnoetige PUTs, #1234-Kontext)');
	});

	test('geaenderter ws-Zustand (Band-Drag verschiebt min) + flush → genau EIN PUT-Payload mit dem neuen Wert', () => {
		const preset = makePreset();
		const before = makeSnapshot();
		const current = makeSnapshot({
			corridors: [{ metric: 'snow_depth_cm', range: [45, null], notify: true, mark: true, prio: 'hoch' }]
		});
		const result = flushPendingCorridorSave(preset, current, before);
		assert.notStrictEqual(result, null, 'geaenderter Snapshot muss einen PUT-Payload liefern');
		assert.deepStrictEqual(
			result!.body.corridors,
			current.corridors,
			'PUT-Payload muss den neuen (verschobenen) Wert widerspiegeln, nicht den alten'
		);
		assert.deepStrictEqual(
			result!.body.display_config!.metric_alert_levels,
			preset.display_config!.metric_alert_levels,
			'Nachbarfelder (#1257-Kontext) duerfen bei einem reinen Band-Drag nicht verloren gehen'
		);
	});

	test('kein bisher persistierter Stand (before=null, erster Flush) + unveraendert seit Hydration → kein PUT', () => {
		const preset = makePreset();
		const current = makeSnapshot();
		const result = flushPendingCorridorSave(preset, current, null);
		assert.strictEqual(result, null, 'ohne vorherigen persistierten Stand ist der aktuelle Snapshot selbst die Baseline (analog erstelleWertebereicheVergleichSpeicherung)');
	});

	test('Regressions-Beweis F002: der ALTE, wrapper-gebundene Mechanismus haette diesen Fall verpasst — der neue Fenster-Handler ruft dieselbe Funktion unabhaengig vom Ereignisziel auf', () => {
		// Simuliert einen Pointerup AUSSERHALB des `.hub-corridor-wrap`-Subtrees:
		// kein DOM-Event, keine Bubbling-Kette noetig — flushPendingCorridorSave
		// ist reine Zustands-Diff-Logik und kennt kein DOM-Ziel ueberhaupt.
		// Genau das macht sie fuer den Fenster-Handler (CompareTabs.svelte
		// `handleWindowPointerUp`) korrekt wiederverwendbar.
		const preset = makePreset();
		const before = makeSnapshot();
		const current = makeSnapshot({ metricAlertLevels: { snow_depth_cm: 'warn', wind_gust: 'off' } });
		const result = flushPendingCorridorSave(preset, current, before);
		assert.notStrictEqual(result, null, 'ein geaenderter Snapshot muss unabhaengig vom (nicht vorhandenen) DOM-Kontext einen Payload liefern');
	});
});

describe('Fix-Loop 2 (F005, Adversary CRITICAL): Cross-Tab-Sequenz — Baseline nach jedem PUT auffrischen verhindert Lost-Update', () => {
	// Reproduziert exakt den Adversary-Fund (repro_cross_tab_staleness.mjs /
	// repro_cross_tab_reverse.mjs, Runde 3): CompareTabs.svelte haelt jetzt EINE
	// mutable `currentPreset`-Baseline, die nach jedem erfolgreichen S6-PUT aus
	// dem Response-Body (hier durch den gesendeten Payload approximiert — der
	// PUT-Handler, internal/handler/compare_preset.go:390, liefert exakt das
	// gespeicherte Objekt zurueck) aufgefrischt wird. Beide Speicherpfade
	// (Orte via buildHubPutPayload, Idealwerte via flushPendingCorridorSave)
	// lesen ausschliesslich aus dieser aufgefrischten Baseline.

	function makeCorridorSnapshot(preset: ComparePreset): CorridorSnapshot {
		const dc = preset.display_config as Record<string, unknown>;
		return {
			corridors: preset.corridors!,
			idealRanges: dc.ideal_ranges as CorridorSnapshot['idealRanges'],
			activeMetricKeys: dc.active_metrics as string[],
			metricAlertLevels: dc.metric_alert_levels as Record<string, string>
		};
	}

	test('Orte-Edit ZUERST, dann Idealwerte-Edit: zweiter PUT-Payload enthaelt BEIDE Aenderungen', () => {
		// Seit #2375: die Basis bleibt ABSICHTLICH auf dem Lade-Stand — die
		// Nutzlasten sind disjunkt, ein veralteter Stand kann nichts zurueckschreiben.
		const baseline = makePreset();

		// Edit A: Nutzer sortiert im Orte-Tab um -> nur { location_ids }.
		const newIds = ['loc-3', 'loc-1', 'loc-2'];
		const payload1 = buildComparePresetPartialPayload(baseline.id, { location_ids: newIds });
		assert.deepStrictEqual(payload1.body, { location_ids: newIds });

		// Edit B: Nutzer wechselt in den Idealwerte-Tab, verschiebt ein Band (min 20 -> 45).
		const before = makeCorridorSnapshot(baseline);
		const current: CorridorSnapshot = {
			...before,
			corridors: [{ metric: 'snow_depth_cm', range: [45, null], notify: true, mark: true, prio: 'hoch' }]
		};
		const payload2 = flushPendingCorridorSave(baseline, current, before);

		assert.notStrictEqual(payload2, null, 'geaenderter Corridor-Snapshot muss einen PUT-Payload liefern');
		assert.ok(
			!('location_ids' in (payload2!.body as unknown as Record<string, unknown>)),
			'Payload 2 (Idealwerte) darf die Orte-Liste nicht senden — sonst wuerde der Lade-Stand die Orte-Reihenfolge aus Edit A zuruecksetzen'
		);
		assert.deepStrictEqual(
			payload2!.body.corridors,
			current.corridors,
			'Payload 2 muss die neue Idealwerte-Aenderung aus Edit B enthalten'
		);
	});

	test('Idealwerte-Edit ZUERST (inkl. metric_alert_levels), dann Orte-Edit: zweiter PUT-Payload enthaelt BEIDE Aenderungen (umgekehrte Richtung)', () => {
		const baseline = makePreset();

		// Edit A: Nutzer setzt im Idealwerte-Tab eine Alarmstufe (#1257/#1234-relevant) und verschiebt ein Band.
		const before = makeCorridorSnapshot(baseline);
		const current: CorridorSnapshot = {
			...before,
			corridors: [{ metric: 'snow_depth_cm', range: [45, null], notify: true, mark: true, prio: 'hoch' }],
			metricAlertLevels: { snow_depth_cm: 'mark', wind_gust: 'mark' }
		};
		const payload1 = flushPendingCorridorSave(baseline, current, before);
		assert.notStrictEqual(payload1, null);

		// Edit B: Nutzer wechselt in den Orte-Tab und entfernt einen Ort — die Basis
		// ist bewusst veraltet; der Orte-Body darf davon nichts enthalten.
		const newIds = ['loc-1', 'loc-2'];
		const payload2 = buildComparePresetPartialPayload(baseline.id, { location_ids: newIds });

		assert.deepStrictEqual(payload2.body, { location_ids: newIds },
			'Payload 2 (Orte) darf weder Korridore noch metric_alert_levels der (veralteten) Basis zurueckschreiben'
		);
	});
});

// Issue #2276 S3: der Block „F006 shouldFlushOnWindowPointerUp" entfiel mit dem
// fensterweiten pointerup-Auffang (CompareTabs.svelte) — es gibt nur noch EINEN
// Speicherweg (CorridorEditor -> wertebereicheVergleichSpeicherung.ts).

describe('Fix-Loop 3 (F007, Adversary CRITICAL): buildToggleActivePutPayload — dritter PUT-Pfad (Pausieren/Aktivieren) muss die frische Baseline nutzen, nicht die eingefrorene preset-Prop', () => {
	test('S6-Edit (Orte-Reorder) -> Toggle: Toggle-Payload enthaelt die frischen location_ids/corridors/metric_alert_levels UND das getoggelte schedule-Feld', () => {
		// Reproduziert exakt den Adversary-Fund (Runde 4, Angriffspunkt 1c): erst
		// ein S6-Edit im Orte-Tab (PUT 1 -> Response wird zur neuen Baseline,
		// identisch zum CompareTabs.svelte-Muster `currentPreset = await
		// api.put(...)`), danach ein Klick auf Pausieren/Aktivieren im
		// Uebersicht-Tab (PUT 2). Vor dem Fix spread'te handleToggleActive die
		// urspruengliche, eingefrorene `preset`-Prop -> der bereits persistierte
		// Orte-Edit (UND metric_alert_levels/corridors) waeren im Toggle-PUT
		// wieder auf den Lade-Zeitpunkt-Stand zurueckgefallen.
		// Seit #2375: der Toggle-Body traegt NUR den Status — die (hier bewusst
		// veraltete) Basis kann weder Orte noch Korridore noch Alarmstufen
		// zurueckschreiben.
		const baseline = makePreset();
		const togglePayload = buildToggleActivePutPayload(baseline, 'daily', 'daily');

		assert.deepStrictEqual(togglePayload.body, { schedule: 'daily', previous_schedule: 'daily' });
		assert.strictEqual(togglePayload.url, `/api/compare/presets/${baseline.id}`);
	});

	test('S6-Edit (Idealwerte, inkl. metric_alert_levels) -> Toggle: Toggle-Payload enthaelt die frische Baseline (umgekehrte Reihenfolge)', () => {
		// Seit #2375: Pausieren traegt nur { schedule, previous_schedule } — auch bei
		// veralteter Basis kann es keine Bandverschiebung/Alarmstufe zuruecksetzen.
		const baseline = makePreset();
		const togglePayload = buildToggleActivePutPayload(baseline, 'manual', 'daily');

		assert.deepStrictEqual(togglePayload.body, { schedule: 'manual', previous_schedule: 'daily' });
	});
});

describe('Edge Case Spec Z.1020: snapshotForRollback liefert einen echten Deep-Copy-Prae-Zustand', () => {
	test('Mutation des Arbeitszustands NACH dem Snapshot veraendert den Snapshot nicht', () => {
		const workingState = { corridors: [{ metric: 'snow_depth_cm', range: [20, null] as [number | null, number | null], notify: true, mark: false }] };
		const snapshot = snapshotForRollback(workingState);

		workingState.corridors[0].range[0] = 999;
		workingState.corridors.push({ metric: 'wind_gust', range: [null, null], notify: false, mark: false });

		assert.deepStrictEqual(
			snapshot,
			{ corridors: [{ metric: 'snow_depth_cm', range: [20, null], notify: true, mark: false }] },
			'der Snapshot muss den Zustand VOR der Mutation zeigen (Deep-Copy, keine geteilten Referenzen)'
		);
	});
});

// Issue #1703 Scheibe 8 — BEARBEITEN-Pfad (Hauptpfad: bestehenden Ortsvergleich
// aendern). Der Wetter-Metriken-Reiter reicht `channelActiveMetricKeys` an
// `buildComparePresetSavePayload` weiter; bewacht waren bisher nur die reinen
// Leaf-Funktionen (compareChannelMetricLayouts.test.ts) und der ANLEGE-Pfad
// (compare_wizard_save_new_preset_channels.test.ts) — derselbe Fehlertyp
// "Pruefort != Wirkort" wie #1745 F001, nur schwerer wiegend. Gemessen wird der
// Body, den der Commit-Handler des Hub-Reiters "Wetter-Metriken"
// (CompareTabs.svelte::handleWetterMetrikenCommit) an `api.put()` gibt.
describe('#1703 S8 (Bearbeiten-Pfad): Kanal-Overrides der Uebersichtstabelle landen im PUT-Body und ueberleben den Rundlauf', () => {
	const OVERRIDES: CompareChannelActiveMetrics = { email: null, telegram: ['temp_max_c'], sms: [] };
	const KEIN_OVERRIDE: CompareChannelActiveMetrics = { email: null, telegram: null, sms: null };

	// Laedt die Katalogantwort wie der Editor beim Oeffnen (fuellt dabei den
	// Umkehr-Index, den die Schreibuebersetzung als Default nutzt).
	const loadCatalog = () =>
		toCompareSelectionEntries({
			metrics: [
				{ key: 'temp_max_c', label: 'Temperatur', metric_id: 'temperature', aggregation: 'max' },
				{ key: 'wind_max_kmh', label: 'Wind', metric_id: 'wind', aggregation: 'max' }
			]
		} as unknown as Parameters<typeof toCompareSelectionEntries>[0]);

	const snapshot = (channelActiveMetricKeys: CompareChannelActiveMetrics): WeatherMetricsSnapshot => ({
		activeMetricKeys: ['temp_max_c', 'wind_max_kmh'],
		channelActiveMetricKeys,
		officialAlertsEnabled: true,
		dayWindowStartHour: 4,
		dayWindowEndHour: 19
	});

	// Der PUT, den ein reiner Kanal-Edit (Grundauswahl unveraendert) ausloest.
	function putOfChannelEdit() {
		const payload = flushPendingWeatherMetricsSave(makePreset(), snapshot(OVERRIDES), snapshot(KEIN_OVERRIDE));
		assert.ok(payload, 'ein reiner Kanal-Edit (Grundauswahl unveraendert) MUSS einen PUT ergeben — sonst waeren die Kanal-Reiter beim Bearbeiten eine Attrappe');
		return payload!;
	}

	test('Bearbeiten mit Kanal-Overrides: telegram im Speicherformat, sms explizit leer, nie editiertes email gar nicht', () => {
		loadCatalog();
		const payload = putOfChannelEdit();
		assert.strictEqual(payload.url, '/api/compare/presets/cmp-42');
		const dc = payload.body.display_config as Record<string, unknown>;
		assert.ok(dc.channel_active_metrics, 'display_config.channel_active_metrics fehlt im PUT-Body — der Bearbeiten-Pfad reicht channelActiveMetricKeys nicht weiter, ' +
			`die Kanal-Reiter waeren beim Aendern eines bestehenden Vergleichs wirkungslos. display_config: ${JSON.stringify(dc)}`);
		const channels = dc.channel_active_metrics as Record<string, unknown[]>;
		assert.deepStrictEqual(channels.telegram, [{ metric_id: 'temperature', aggregation: 'max' }],
			`erwartet den telegram-Override im Speicherformat (Groesse + Auswertung), erhalten: ${JSON.stringify(channels.telegram)}`);
		assert.ok(Object.prototype.hasOwnProperty.call(channels, 'sms'),
			`bewusste Leerauswahl muss als expliziter Eintrag mitreisen (weggelassen = alter Serverstand bleibt stehen), erhalten: ${JSON.stringify(channels)}`);
		assert.deepStrictEqual(channels.sms, [], 'SMS-Leerauswahl muss als [] gesendet werden');
		assert.ok(!Object.prototype.hasOwnProperty.call(channels, 'email'),
			`nie editierter Kanal darf NICHT als Leerauswahl gesendet werden ("fehlend != leer"), erhalten: ${JSON.stringify(channels.email)}`);
	});

	test('Rundlauf speichern -> laden: die Hydration baut aus dem gespeicherten Stand denselben Kanal-Zustand wieder auf', () => {
		const catalog = loadCatalog();
		assert.deepStrictEqual(hydrateChannelActiveMetricsFromPreset(putOfChannelEdit().body, catalog), OVERRIDES,
			'der gespeicherte Kanal-Stand muss unveraendert zurueckkommen — sonst zeigt der Kanal-Reiter nach dem Neuladen wieder die Grundauswahl');
	});
});
