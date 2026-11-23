// TDD RED — Issue #1299/#1287 (Scheibe C2 von Epic #1301): Persist-Bridge fuer
// den Hub-Layout-Tab (Stundenverlauf-Metriken + "Stundenverlauf ein/aus").
//
// Spec: docs/specs/modules/compare_hub_hourly_metrics.md § AC-2, AC-3, AC-5
//
// Reine Verhaltenstests auf der (noch nicht existierenden) Pure-Function
// `flushPendingLayoutSave` — analog `flushPendingVersandSave`/
// `flushPendingCorridorSave` in der damaligen Compare-Hub-Klebeschicht (inzwischen aufgeloest, Issue #2276 S6f). Echte
// `ComparePreset`-Objekte, KEIN Mock. `flushPendingLayoutSave` ruft intern
// `buildHubPutPayload` → `buildComparePresetSavePayload` auf (Read-Modify-
// Write-Kern), damit ist AC-3 (Datenerhalt) automatisch mitgeprueft, sobald
// die Funktion existiert und `HubEdit` die Stundenverlauf-Felder durchreicht.
//
// RED-Erwartung (vor Implementierung):
//   `flushPendingLayoutSave` und der Typ `LayoutSnapshot` existieren in der
//   damaligen Compare-Hub-Klebeschicht (inzwischen aufgeloest, Issue #2276
//   S6f) noch NICHT — der Import selbst schlaegt fehl
//   (Node meldet "does not provide an export named ..."), das gesamte File
//   kann nicht laufen. Das IST der RED-Beweis fuer AC-2/AC-3/AC-5.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/compare_hub_layout_save.test.ts

// Issue #3276 (Spec-AC-38, AC-2): `hourly_metrics` ist Altschluessel. `flushPendingLayoutSave`
// schreibt es nicht mehr und wertet Aenderungen daran nicht mehr als Aenderung; gesendet werden
// nur noch die Schalter `hourly_enabled`/`outlook_enabled`. Die Tests unten sind entsprechend
// umgestellt (Listen-Aenderung -> kein PUT; Datenerhalt: kein display_config im Rumpf).

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { flushPendingLayoutSave, type LayoutSnapshot } from '../../shared/weather-metrics-tab/weatherMetricsCompareSave.ts';
import type { ComparePreset } from '../../../types.ts';

/** Preset-Fixture mit allen fuenf AC-3-relevanten Feldern befuellt, PLUS
 * einer initialen `hourly_metrics`-Auswahl (fuer den AC-5-Loeschbeweis). */
function makePresetWithFullDisplayConfig(): ComparePreset {
	return {
		id: 'preset-c2-hub-layout',
		name: 'Ortsvergleich Stubaier Alpen',
		location_ids: ['loc-a', 'loc-b', 'loc-c'],
		schedule: 'daily',
		previous_schedule: 'daily',
		weekday: 2,
		profil: 'wandern',
		hour_from: 6,
		hour_to: 20,
		empfaenger: ['a@example.com'],
		forecast_hours: 72,
		created_at: '2026-07-01T08:00:00Z',
		hourly_enabled: true,
		display_config: {
			region: 'Stubaier Alpen',
			top_n: 7,
			// Issue #1351 (AC-6): channel_layouts faellt beim Speichern immer weg —
			// metric_alert_levels dient hier als Beispiel-Feld fuer den
			// AC-3-Datenerhalt-Beweis (unbeteiligte Felder bleiben unangetastet).
			metric_alert_levels: { wind_max_kmh: 'sensibel' },
			hourly_metrics: ['temp_c']
		}
	} as ComparePreset;
}

describe('C2 AC-2: flushPendingLayoutSave — geänderter Snapshot → PUT-Payload', () => {
	test('#3276: geänderte hourlyMetricKeys loesen keinen PUT mehr aus (Altschluessel)', () => {
		const preset = makePresetWithFullDisplayConfig();
		const before: LayoutSnapshot = { hourlyMetricKeys: ['temp_c'], hourlyEnabled: true, outlookMetricKeys: null, outlookEnabled: false };
		const current: LayoutSnapshot = { hourlyMetricKeys: ['temp_c', 'wind_kmh'], hourlyEnabled: true, outlookMetricKeys: null, outlookEnabled: false };

		assert.equal(flushPendingLayoutSave(preset, current, before), null);
	});

	test('geänderter hourlyEnabled-Schalter landet als hourly_enabled im Body', () => {
		// GIVEN: ein Preset mit hourly_enabled=true, letzter Snapshot ebenfalls true
		// WHEN: der Nutzer den Stundenverlauf-Schalter ausschaltet
		// THEN: der PUT-Payload setzt hourly_enabled auf false
		// RED heute: Import schlaegt fehl.
		const preset = makePresetWithFullDisplayConfig();
		const before: LayoutSnapshot = { hourlyMetricKeys: ['temp_c'], hourlyEnabled: true, outlookMetricKeys: null, outlookEnabled: false };
		const current: LayoutSnapshot = { hourlyMetricKeys: ['temp_c'], hourlyEnabled: false, outlookMetricKeys: null, outlookEnabled: false };

		const payload = flushPendingLayoutSave(preset, current, before);

		assert.ok(payload, 'flushPendingLayoutSave darf bei geaendertem Snapshot nicht null liefern');
		assert.equal(payload!.body.hourly_enabled, false);
	});

	// Issue #1361: eine reine Umsortierung loeste einen PUT mit der neuen Reihenfolge aus.
	// #3276: die Reihenfolge des Stundenverlaufs stellt der Nutzer in „Was steht wo" ein;
	// `hourly_metrics` wird nicht mehr geschrieben, eine Umsortierung loest keinen PUT aus.
	test('#3276: umsortierter Snapshot → kein PUT (Reihenfolge nur noch in „Was steht wo")', () => {
		const preset = makePresetWithFullDisplayConfig();
		const before: LayoutSnapshot = { hourlyMetricKeys: ['temp_c', 'wind_kmh'], hourlyEnabled: true, outlookMetricKeys: null, outlookEnabled: false };
		const current: LayoutSnapshot = { hourlyMetricKeys: ['wind_kmh', 'temp_c'], hourlyEnabled: true, outlookMetricKeys: null, outlookEnabled: false };

		assert.equal(flushPendingLayoutSave(preset, current, before), null);
	});

	test('wirklich identischer Snapshot (gleiche Reihenfolge, gleiche Werte) → null (No-Op-Guard bleibt bestehen)', () => {
		// GIVEN: current und before sind bitgleich (auch in der Reihenfolge)
		// WHEN: flushPendingLayoutSave aufgerufen wird
		// THEN: weiterhin null — die #1299-Regel bleibt fuer ECHTE Identitaet
		// richtig, nur "umsortiert" zaehlt seit #1361 nicht mehr als identisch.
		const preset = makePresetWithFullDisplayConfig();
		const before: LayoutSnapshot = { hourlyMetricKeys: ['temp_c', 'wind_kmh'], hourlyEnabled: true, outlookMetricKeys: null, outlookEnabled: false };
		const current: LayoutSnapshot = { hourlyMetricKeys: ['temp_c', 'wind_kmh'], hourlyEnabled: true, outlookMetricKeys: null, outlookEnabled: false };

		const payload = flushPendingLayoutSave(preset, current, before);

		assert.equal(payload, null, 'bitgleicher Snapshot (auch Reihenfolge gleich) muss weiterhin No-Op sein');
	});
});

// C2 AC-5 (leere hourlyMetricKeys als [] persistieren, Bug #1299/C2) entfaellt mit #3276:
// `hourly_metrics` wird weder als Liste noch als [] geschrieben (Spec #3276: nie leer senden).
describe('C2 AC-5 / #3276: leere hourlyMetricKeys werden NICHT als [] gesendet', () => {
	test('current.hourlyMetricKeys = [] (mit Schalter-Aenderung) → kein display_config im PUT', () => {
		const preset = makePresetWithFullDisplayConfig();
		const before: LayoutSnapshot = { hourlyMetricKeys: ['temp_c'], hourlyEnabled: true, outlookMetricKeys: null, outlookEnabled: false };
		const current: LayoutSnapshot = { hourlyMetricKeys: [], hourlyEnabled: false, outlookMetricKeys: null, outlookEnabled: false };

		const payload = flushPendingLayoutSave(preset, current, before);

		assert.ok(payload, 'die Schalter-Aenderung muss gespeichert werden');
		assert.equal(payload!.body.display_config, undefined, 'display_config (hourly_metrics: []) im PUT');
	});
});

describe('C2 AC-3 (PFLICHT Datenerhalt): top_n/metric_alert_levels/forecast_hours/hour_from/hour_to bleiben unangetastet', () => {
	test('fünf Bestandsfelder sind nach einer Stundenverlauf-Änderung byteidentisch zum Ausgangs-Preset', () => {
		// GIVEN: ein Preset mit gesetzten top_n, channel_layouts (display_config)
		//        sowie forecast_hours, hour_from, hour_to (top-level)
		// WHEN: eine Stundenverlauf-Aenderung ueber flushPendingLayoutSave persistiert wird
		// THEN: alle fuenf Felder sind im PUT-Body wertgleich zum Ausgangs-Preset
		// RED heute: Import schlaegt fehl — dieser Test beweist zusaetzlich, dass die
		// HubEdit-Luecke (hourlyMetricKeys/hourlyEnabled kommen bislang gar nicht bei
		// buildHubPutPayload an) tatsaechlich geschlossen wurde, sobald er gruen wird.
		const preset = makePresetWithFullDisplayConfig();
		const before: LayoutSnapshot = { hourlyMetricKeys: ['temp_c'], hourlyEnabled: true, outlookMetricKeys: null, outlookEnabled: false };
		const current: LayoutSnapshot = { hourlyMetricKeys: ['wind_kmh'], hourlyEnabled: false, outlookMetricKeys: null, outlookEnabled: false };

		const payload = flushPendingLayoutSave(preset, current, before);

		assert.ok(payload, 'flushPendingLayoutSave darf bei geaendertem Snapshot nicht null liefern');
		const body = payload!.body;
		// #3276: der Layout-Rumpf traegt gar kein display_config mehr.
		const displayConfig = (body.display_config ?? {}) as Record<string, unknown>;

		// Seit #2375 bleiben die Bestandsfelder erhalten, weil der Layout-Body sie
		// GAR NICHT sendet (Server-Abgleich laesst fehlende Felder unveraendert) —
		// ein mitgesendeter Wert koennte veraltet sein.
		assert.ok(!('top_n' in displayConfig), 'display_config.top_n darf nicht mitgesendet werden');
		assert.ok(!('metric_alert_levels' in displayConfig), 'display_config.metric_alert_levels darf nicht mitgesendet werden');
		const roh = body as unknown as Record<string, unknown>;
		for (const k of ['forecast_hours', 'hour_from', 'hour_to']) {
			assert.ok(!(k in roh), `${k} darf nicht mitgesendet werden`);
		}
		assert.equal(body.hourly_enabled, false, 'das Eigenfeld kommt an');
		assert.ok(!('hourly_metrics' in displayConfig), '#3276: hourly_metrics ist Altschluessel');
	});
});
