// TDD RED — Issue #1299/#1287 (Scheibe C2 von Epic #1301): Persist-Bridge fuer
// den Hub-Layout-Tab (Stundenverlauf-Metriken + "Stundenverlauf ein/aus").
//
// Spec: docs/specs/modules/compare_hub_hourly_metrics.md § AC-2, AC-3, AC-5
//
// Reine Verhaltenstests auf der (noch nicht existierenden) Pure-Function
// `flushPendingLayoutSave` — analog `flushPendingVersandSave`/
// `flushPendingCorridorSave` in `compareHubWizardBridge.ts`. Echte
// `ComparePreset`-Objekte, KEIN Mock. `flushPendingLayoutSave` ruft intern
// `buildHubPutPayload` → `buildComparePresetSavePayload` auf (Read-Modify-
// Write-Kern), damit ist AC-3 (Datenerhalt) automatisch mitgeprueft, sobald
// die Funktion existiert und `HubEdit` die Stundenverlauf-Felder durchreicht.
//
// RED-Erwartung (vor Implementierung):
//   `flushPendingLayoutSave` und der Typ `LayoutSnapshot` existieren in
//   `compareHubWizardBridge.ts` noch NICHT — der Import selbst schlaegt fehl
//   (Node meldet "does not provide an export named ..."), das gesamte File
//   kann nicht laufen. Das IST der RED-Beweis fuer AC-2/AC-3/AC-5.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/compare_hub_layout_save.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { flushPendingLayoutSave, type LayoutSnapshot } from '../compareHubWizardBridge.ts';
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
			channel_layouts: {
				email: [{ metric_id: 'wind_max_kmh', enabled: true }],
				sms: [{ metric_id: 'temp_max_c', enabled: true }]
			},
			hourly_metrics: ['temp_c']
		}
	} as ComparePreset;
}

describe('C2 AC-2: flushPendingLayoutSave — geänderter Snapshot → PUT-Payload', () => {
	test('geänderte hourlyMetricKeys landen als display_config.hourly_metrics im Body', () => {
		// GIVEN: ein Preset + letzter persistierter Snapshot mit nur "temp_c"
		// WHEN: der Nutzer "wind_kmh" zusaetzlich anhakt (current != before)
		// THEN: der PUT-Payload setzt display_config.hourly_metrics auf beide Keys
		// RED heute: Import schlaegt fehl (flushPendingLayoutSave existiert nicht).
		const preset = makePresetWithFullDisplayConfig();
		const before: LayoutSnapshot = { hourlyMetricKeys: ['temp_c'], hourlyEnabled: true };
		const current: LayoutSnapshot = { hourlyMetricKeys: ['temp_c', 'wind_kmh'], hourlyEnabled: true };

		const payload = flushPendingLayoutSave(preset, current, before);

		assert.ok(payload, 'flushPendingLayoutSave darf bei geaendertem Snapshot nicht null liefern');
		const displayConfig = payload!.body.display_config as Record<string, unknown>;
		assert.deepEqual(displayConfig.hourly_metrics, ['temp_c', 'wind_kmh']);
	});

	test('geänderter hourlyEnabled-Schalter landet als hourly_enabled im Body', () => {
		// GIVEN: ein Preset mit hourly_enabled=true, letzter Snapshot ebenfalls true
		// WHEN: der Nutzer den Stundenverlauf-Schalter ausschaltet
		// THEN: der PUT-Payload setzt hourly_enabled auf false
		// RED heute: Import schlaegt fehl.
		const preset = makePresetWithFullDisplayConfig();
		const before: LayoutSnapshot = { hourlyMetricKeys: ['temp_c'], hourlyEnabled: true };
		const current: LayoutSnapshot = { hourlyMetricKeys: ['temp_c'], hourlyEnabled: false };

		const payload = flushPendingLayoutSave(preset, current, before);

		assert.ok(payload, 'flushPendingLayoutSave darf bei geaendertem Snapshot nicht null liefern');
		assert.equal(payload!.body.hourly_enabled, false);
	});

	test('identischer Snapshot (auch bei umsortiertem hourlyMetricKeys-Array) → null (No-Op-Guard)', () => {
		// GIVEN: current und before enthalten dieselben Keys, nur andere Reihenfolge
		// WHEN: flushPendingLayoutSave aufgerufen wird
		// THEN: kein PUT ausgeloest (null) — Diff-Waechter normalisiert per sort()
		// RED heute: Import schlaegt fehl.
		const preset = makePresetWithFullDisplayConfig();
		const before: LayoutSnapshot = { hourlyMetricKeys: ['temp_c', 'wind_kmh'], hourlyEnabled: true };
		const current: LayoutSnapshot = { hourlyMetricKeys: ['wind_kmh', 'temp_c'], hourlyEnabled: true };

		const payload = flushPendingLayoutSave(preset, current, before);

		assert.equal(payload, null, 'identischer (nur umsortierter) Snapshot muss No-Op sein');
	});
});

describe('C2 AC-5: leere hourlyMetricKeys werden als [] persistiert (Default "alle sichtbar")', () => {
	// Staging-Fund F005 (Bug #1299/C2): der Server-Merge (mergeConfigMap,
	// config_merge.go, #1159-Datenverlust-Schutz) kann Keys nur ueberschreiben,
	// nie loeschen. Ein weggelassener "hourly_metrics"-Key bliebe daher auf dem
	// alten Wert stehen -> "alle abwaehlen" sprang nach Reload nicht zurueck.
	// Fix: [] wird EXPLIZIT persistiert (analog active_metrics, #1191). Die
	// Renderer-Seite (resolve_hourly_metrics) deckt separat ab, dass [] wie
	// "kein Schluessel gesetzt" behandelt wird -> alle 9 Spalten sichtbar:
	// tests/tdd/test_issue_1106_hourly_metrics_config.py::test_empty_list_returns_none.
	test('current.hourlyMetricKeys = [] → display_config.hourly_metrics ist [] (kein geloeschter Schluessel)', () => {
		// GIVEN: ein Preset mit gespeicherter Auswahl ["temp_c"], letzter Snapshot ebenso
		// WHEN: der Nutzer alle Metriken abwaehlt (current.hourlyMetricKeys = [])
		// THEN: der resultierende PUT-Body enthaelt display_config.hourly_metrics als
		//       leeres Array — NICHT als fehlenden Schluessel (der Server-Merge kann
		//       fehlende Keys nicht als "loeschen" interpretieren).
		const preset = makePresetWithFullDisplayConfig();
		const before: LayoutSnapshot = { hourlyMetricKeys: ['temp_c'], hourlyEnabled: true };
		const current: LayoutSnapshot = { hourlyMetricKeys: [], hourlyEnabled: true };

		const payload = flushPendingLayoutSave(preset, current, before);

		assert.ok(payload, 'flushPendingLayoutSave darf bei geaendertem Snapshot nicht null liefern');
		const displayConfig = payload!.body.display_config as Record<string, unknown>;
		assert.deepEqual(
			displayConfig.hourly_metrics,
			[],
			`display_config.hourly_metrics muss nach Leerauswahl [] sein (nicht geloescht), ` +
				`ist aber: ${JSON.stringify(displayConfig.hourly_metrics)}`
		);
	});
});

describe('C2 AC-3 (PFLICHT Datenerhalt): top_n/channel_layouts/forecast_hours/hour_from/hour_to bleiben unangetastet', () => {
	test('fünf Bestandsfelder sind nach einer Stundenverlauf-Änderung byteidentisch zum Ausgangs-Preset', () => {
		// GIVEN: ein Preset mit gesetzten top_n, channel_layouts (display_config)
		//        sowie forecast_hours, hour_from, hour_to (top-level)
		// WHEN: eine Stundenverlauf-Aenderung ueber flushPendingLayoutSave persistiert wird
		// THEN: alle fuenf Felder sind im PUT-Body wertgleich zum Ausgangs-Preset
		// RED heute: Import schlaegt fehl — dieser Test beweist zusaetzlich, dass die
		// HubEdit-Luecke (hourlyMetricKeys/hourlyEnabled kommen bislang gar nicht bei
		// buildHubPutPayload an) tatsaechlich geschlossen wurde, sobald er gruen wird.
		const preset = makePresetWithFullDisplayConfig();
		const before: LayoutSnapshot = { hourlyMetricKeys: ['temp_c'], hourlyEnabled: true };
		const current: LayoutSnapshot = { hourlyMetricKeys: ['wind_kmh'], hourlyEnabled: false };

		const payload = flushPendingLayoutSave(preset, current, before);

		assert.ok(payload, 'flushPendingLayoutSave darf bei geaendertem Snapshot nicht null liefern');
		const body = payload!.body;
		const displayConfig = body.display_config as Record<string, unknown>;

		assert.equal(displayConfig.top_n, 7, 'display_config.top_n darf sich nicht veraendern');
		assert.deepEqual(
			displayConfig.channel_layouts,
			{
				email: [{ metric_id: 'wind_max_kmh', enabled: true }],
				sms: [{ metric_id: 'temp_max_c', enabled: true }]
			},
			'display_config.channel_layouts darf sich nicht veraendern'
		);
		assert.equal(body.forecast_hours, 72, 'forecast_hours darf sich nicht veraendern');
		assert.equal(body.hour_from, 6, 'hour_from darf sich nicht veraendern');
		assert.equal(body.hour_to, 20, 'hour_to darf sich nicht veraendern');
	});
});
