// TDD RED — Issue #1258 Scheibe S5: Compare-Hub 7. Tab "Alarme" —
// Bridge-Erweiterung fuer den eingebetteten AlarmeTab (context="vergleich")
// (AC-19, AC-29).
//
// Spec: docs/specs/modules/issue_1258_alarme_tab_official_warnings.md
//   Abschnitt 11, AC-19 (Hub-Tab), AC-29 (Erst-Oeffnungs-Hydration ohne
//   Default-Clobber).
// Context: docs/context/feat-1258-s5-hub-alarme.md § Entscheidungen H1-H5.
//
// Ist: `compareHubWizardBridge.ts` kennt drei fertige Snapshot-Pfade
// (Corridor/Idealwerte S6, Versand S7) — aber KEINEN fuer den Alarme-Tab.
// `HubEdit`/`buildHubPutPayload` kennen `metricAlertLevels`/Cooldown/Quiet,
// aber NICHT `officialAlertsEnabled`, `officialWarnings`, `radarAlertEnabled`
// (S4-Known-Gap, s. Context Zeile 32). `hydrateAlarmFieldsFromPreset` und
// `flushPendingAlarmSave` existieren noch NICHT — die named imports
// schlagen heute fehl (RED), bis Phase 6 die Bridge erweitert.
//
// API-Design (von dieser RED-Phase festgelegt, S6/S7-Praezedenz):
//   - hydrateAlarmFieldsFromPreset(state, preset): mutiert `state` DIREKT
//     (analog dem lazy alarme-Effekt in CompareTabs.svelte, H3) mit ALLEN
//     Alarm-relevanten Feldern — officialAlertsEnabled, officialWarningsEnabled
//     (aus official_warnings.enabled, Fallback analog AlarmeTab.svelte:83f
//     `official_warnings?.enabled ?? official_alert_triggers_enabled !== false`),
//     radarAlertEnabled, metricAlertLevels, alertCooldownMinutes,
//     alertQuietFrom/To UND corridors (H4: notifyCount braucht corridors auch
//     wenn Alarme der ERSTE geoeffnete Tab ist, bevor der idealwerte-Effekt
//     je gelaufen ist — deshalb 2-Parameter-Signatur statt Plain-Return wie
//     bei hydrateVersandFieldsFromPreset).
//   - AlarmSnapshot + flushPendingAlarmSave(preset, current, before): analog
//     flushPendingVersandSave — null bei unveraendertem Snapshot (Waechter
//     gegen unnoetige PUTs, #1234-Kontext), sonst fertiger PUT-Payload via
//     buildHubPutPayload. official_warnings im Payload NIEMALS mit `sources`
//     (S4-F001-Lehre, Context Zeile 32).
//   - buildHubPutPayload(preset, edit): HubEdit um officialAlertsEnabled,
//     officialWarnings, radarAlertEnabled erweitert (S4-Known-Gap schliessen).
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/compare_hub_alarme_bridge.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import type { ComparePreset } from '../../../types.ts';
import {
	hydrateAlarmFieldsFromPreset,
	flushPendingAlarmSave,
	buildHubPutPayload,
	rollbackAlarmSnapshot,
	type AlarmSnapshot
} from '../compareHubWizardBridge.ts';

function makePreset(overrides: Partial<ComparePreset> = {}): ComparePreset {
	return {
		id: 'cmp-77',
		name: 'Skigebiete Arlberg',
		location_ids: ['loc-a', 'loc-b'],
		schedule: 'daily',
		profil: 'wintersport',
		hour_from: 6,
		hour_to: 9,
		empfaenger: ['urlauber@example.com'],
		created_at: '2026-01-01T00:00:00Z',
		official_alerts_enabled: true,
		official_warnings: { enabled: true, sources: ['vigilance', 'meteoalarm'] },
		radar_alert_enabled: true,
		alert_cooldown_minutes: 45,
		alert_quiet_from: '22:00',
		alert_quiet_to: '07:00',
		corridors: [{ metric: 'snow_depth_cm', range: [20, null], notify: true, mark: true, prio: 'hoch' }],
		display_config: {
			region: 'Vorarlberg',
			metric_alert_levels: { snow_depth_cm: 'warn', wind_gust: 'mark' }
		},
		...overrides
	};
}

describe('AC-29: hydrateAlarmFieldsFromPreset — Erst-Oeffnungs-Hydration OHNE hydrateWizardStateFromPreset/hydrateVersandFieldsFromPreset', () => {
	test('mutiert einen frischen state-Stub mit ALLEN Alarm-Feldern (official/radar/metricAlertLevels/cooldown/quiet UND corridors)', () => {
		const preset = makePreset();
		// Frischer state-Stub — bewusst KEIN vorheriger Aufruf von
		// hydrateWizardStateFromPreset/hydrateVersandFieldsFromPreset (H3
		// Erst-Oeffnungs-Szenario: Alarme ist der erste geoeffnete Tab).
		const state: Record<string, unknown> = {};

		hydrateAlarmFieldsFromPreset(state, preset);

		assert.strictEqual(state.officialAlertsEnabled, true);
		assert.strictEqual(state.officialWarningsEnabled, true);
		assert.strictEqual(state.radarAlertEnabled, true);
		assert.deepStrictEqual(state.metricAlertLevels, preset.display_config!.metric_alert_levels);
		assert.strictEqual(state.alertCooldownMinutes, 45);
		assert.strictEqual(state.alertQuietFrom, '22:00');
		assert.strictEqual(state.alertQuietTo, '07:00');
		assert.deepStrictEqual(
			state.corridors,
			preset.corridors,
			'corridors muessen mit-hydriert werden (H4: notifyCount braucht corridors auch ohne vorherigen idealwerte-Effekt)'
		);
	});

	test('officialWarningsEnabled-Fallback (analog AlarmeTab.svelte:83f): fehlt official_warnings UND official_alert_triggers_enabled, greift Default AN (true)', () => {
		const preset = makePreset({ official_warnings: undefined, official_alert_triggers_enabled: undefined });
		const state: Record<string, unknown> = {};

		hydrateAlarmFieldsFromPreset(state, preset);

		assert.strictEqual(
			state.officialWarningsEnabled,
			true,
			'ohne official_warnings UND ohne official_alert_triggers_enabled=false muss der Baustein-Fallback true liefern (Default an)'
		);
	});

	test('officialWarningsEnabled-Fallback: official_alert_triggers_enabled===false ohne official_warnings -> false', () => {
		const preset = makePreset({ official_warnings: undefined, official_alert_triggers_enabled: false });
		const state: Record<string, unknown> = {};

		hydrateAlarmFieldsFromPreset(state, preset);

		assert.strictEqual(state.officialWarningsEnabled, false);
	});

	test('officialAlertsEnabled/radarAlertEnabled-Defaults, wenn im Preset nicht gesetzt (analog Baustein-Route-Defaults true/false)', () => {
		const preset = makePreset({ official_alerts_enabled: undefined, radar_alert_enabled: undefined });
		const state: Record<string, unknown> = {};

		hydrateAlarmFieldsFromPreset(state, preset);

		assert.strictEqual(state.officialAlertsEnabled, true, 'officialAlertsEnabled-Default ist AN (Baustein-Route-Zweig)');
		assert.strictEqual(state.radarAlertEnabled, false, 'radarAlertEnabled-Default ist AUS');
	});
});

describe('AC-29 No-Op-Guard: flushPendingAlarmSave', () => {
	function makeAlarmSnapshot(overrides: Partial<AlarmSnapshot> = {}): AlarmSnapshot {
		return {
			officialAlertsEnabled: true,
			officialWarningsEnabled: true,
			radarAlertEnabled: false,
			metricAlertLevels: { snow_depth_cm: 'warn' },
			alertCooldownMinutes: 30,
			alertQuietFrom: '22:00',
			alertQuietTo: '07:00',
			...overrides
		};
	}

	test('identischer Snapshot -> kein PUT (null), egal ob before explizit oder via current selbst als Baseline', () => {
		const preset = makePreset();
		const snap = makeAlarmSnapshot();
		assert.strictEqual(
			flushPendingAlarmSave(preset, snap, makeAlarmSnapshot()),
			null,
			'unveraenderter Alarm-Snapshot darf keinen PUT ausloesen (#1234-Kontext)'
		);
		assert.strictEqual(
			flushPendingAlarmSave(preset, snap, null),
			null,
			'ohne vorherigen persistierten Stand ist der aktuelle Snapshot selbst die Baseline'
		);
	});

	test('geaenderter Snapshot (radarAlertEnabled-Toggle) -> Body enthaelt radar_alert_enabled=true', () => {
		const preset = makePreset({ radar_alert_enabled: false });
		const before = makeAlarmSnapshot({ radarAlertEnabled: false });
		const current = makeAlarmSnapshot({ radarAlertEnabled: true });

		const result = flushPendingAlarmSave(preset, current, before);

		assert.ok(result, 'geaenderter Snapshot muss einen PUT-Payload liefern');
		assert.strictEqual(result!.url, '/api/compare/presets/cmp-77');
		assert.strictEqual(result!.body.radar_alert_enabled, true);
	});

	test('Read-Modify-Write (#1257-Kontext): Nicht-Alarm-Felder (corridors, empfaenger, schedule) bleiben unveraendert aus dem Preset', () => {
		const preset = makePreset();
		const result = flushPendingAlarmSave(
			preset,
			makeAlarmSnapshot({ alertCooldownMinutes: 60 }),
			makeAlarmSnapshot()
		);

		assert.ok(result);
		assert.deepStrictEqual(result!.body.corridors, preset.corridors);
		assert.deepStrictEqual(result!.body.empfaenger, preset.empfaenger);
		assert.strictEqual(result!.body.schedule, preset.schedule);
	});
});

describe('AC-19/F001-Lehre: Payload-Verbot — official_warnings im Alarm-Flush enthaelt NIEMALS sources', () => {
	function makeAlarmSnapshot(overrides: Partial<AlarmSnapshot> = {}): AlarmSnapshot {
		return {
			officialAlertsEnabled: true,
			officialWarningsEnabled: true,
			radarAlertEnabled: false,
			metricAlertLevels: {},
			alertCooldownMinutes: 30,
			alertQuietFrom: '22:00',
			alertQuietTo: '07:00',
			...overrides
		};
	}

	test('geaenderter officialWarningsEnabled-Snapshot -> Body official_warnings NUR {enabled}, sources fehlt trotz vorhandenem Preset-Bestand', () => {
		const preset = makePreset({
			official_warnings: { enabled: true, sources: ['vigilance', 'meteoalarm'] }
		});
		const before = makeAlarmSnapshot({ officialWarningsEnabled: true });
		const current = makeAlarmSnapshot({ officialWarningsEnabled: false });

		const result = flushPendingAlarmSave(preset, current, before);

		assert.ok(result);
		assert.deepStrictEqual(
			result!.body.official_warnings,
			{ enabled: false },
			'enabled muss auf false wechseln; sources darf NIEMALS im Body erscheinen (F001-Clobber-Schutz, Context Zeile 32)'
		);
		assert.ok(
			!Object.prototype.hasOwnProperty.call(result!.body.official_warnings ?? {}, 'sources'),
			'official_warnings darf keinen sources-Key tragen, auch wenn preset.official_warnings.sources gesetzt war'
		);
	});
});

describe('S5 Fix-Loop 1 (F001, Adversary CRITICAL): rollbackAlarmSnapshot ist diff-basiert, kein Pauschal-Rollback', () => {
	function makeAlarmSnapshot(overrides: Partial<AlarmSnapshot> = {}): AlarmSnapshot {
		return {
			officialAlertsEnabled: true,
			officialWarningsEnabled: true,
			radarAlertEnabled: false,
			metricAlertLevels: {},
			alertCooldownMinutes: 30,
			alertQuietFrom: '22:00',
			alertQuietTo: '07:00',
			...overrides
		};
	}

	test('Adversary-Szenario: in-flight Alarme-PUT schlaegt fehl, waehrend der Versand-Tab parallel alertCooldownMinutes aendert -> der fremde Edit ueberlebt, der eigene Alarme-Edit wird zurueckgerollt', () => {
		const before = makeAlarmSnapshot({ officialWarningsEnabled: true, alertCooldownMinutes: 30 });
		// `attempted` = der Snapshot, den DIESER gescheiterte Commit gesendet hat
		// (officialWarningsEnabled 30 wurde noch NICHT geaendert, nur der
		// nutzer-editierte Toggle).
		const attempted = makeAlarmSnapshot({ officialWarningsEnabled: false, alertCooldownMinutes: 30 });
		// state = der AKTUELLE wizardState-Stand zum Zeitpunkt des Fehlschlags:
		// der Nutzer hat WAEHREND des in-flight PUTs im Versand-Tab den Cooldown
		// bereits auf 60 geaendert (geteiltes Feld, H3).
		const state: Record<string, unknown> = {
			...makeAlarmSnapshot({ officialWarningsEnabled: false, alertCooldownMinutes: 60 })
		};

		rollbackAlarmSnapshot(state, before, attempted);

		assert.strictEqual(
			state.officialWarningsEnabled,
			true,
			'eigener, gescheiterter Alarme-Edit muss zurueckgerollt werden (UI wieder deckungsgleich mit Server)'
		);
		assert.strictEqual(
			state.alertCooldownMinutes,
			60,
			'BUG F001: der parallele Versand-Tab-Edit (60) darf NICHT vom Alarme-Rollback auf den alten Wert (30) ueberschrieben werden'
		);
	});

	test('ohne Fremd-Edit rollt ein geteiltes Feld normal zurueck (aktuell === attempted)', () => {
		const before = makeAlarmSnapshot({ alertCooldownMinutes: 30 });
		const attempted = makeAlarmSnapshot({ alertCooldownMinutes: 45 });
		const state: Record<string, unknown> = { ...makeAlarmSnapshot({ alertCooldownMinutes: 45 }) };

		rollbackAlarmSnapshot(state, before, attempted);

		assert.strictEqual(state.alertCooldownMinutes, 30, 'ohne Fremd-Edit muss der Standard-Rollback greifen');
	});

	test('metricAlertLevels (Objekt-Feld): Fremd-Edit ueberlebt, Wertvergleich JSON-stabil (kein Referenzvergleich)', () => {
		const before = makeAlarmSnapshot({ metricAlertLevels: { snow_depth_cm: 'warn' } });
		const attempted = makeAlarmSnapshot({ metricAlertLevels: { snow_depth_cm: 'mark' } });
		const state: Record<string, unknown> = {
			...makeAlarmSnapshot({ metricAlertLevels: { snow_depth_cm: 'mark', wind_gust: 'warn' } })
		};

		rollbackAlarmSnapshot(state, before, attempted);

		assert.deepStrictEqual(
			state.metricAlertLevels,
			{ snow_depth_cm: 'mark', wind_gust: 'warn' },
			'Idealwerte-Tab hat metricAlertLevels zwischenzeitlich erweitert — Alarme-Rollback darf das nicht verwerfen'
		);
	});
});

describe('S4-Known-Gap schliessen: buildHubPutPayload kennt officialAlertsEnabled/officialWarnings/radarAlertEnabled', () => {
	test('Teil-Edit mit allen drei bislang unbekannten Alarm-Feldern mappt korrekt auf die PUT-Keys (bei gegenteiligem Preset-Bestand)', () => {
		const preset = makePreset({
			official_alerts_enabled: false,
			official_warnings: { enabled: false },
			radar_alert_enabled: false
		});

		const { body } = buildHubPutPayload(preset, {
			officialAlertsEnabled: true,
			officialWarnings: { enabled: true },
			radarAlertEnabled: true
		});

		assert.strictEqual(body.official_alerts_enabled, true, 'officialAlertsEnabled muss auf official_alerts_enabled gemappt werden');
		assert.deepStrictEqual(
			body.official_warnings,
			{ enabled: true },
			'officialWarnings.enabled muss auf official_warnings.enabled gemappt werden, ohne sources'
		);
		assert.strictEqual(body.radar_alert_enabled, true, 'radarAlertEnabled muss auf radar_alert_enabled gemappt werden');
	});

	test('ohne die drei Edit-Felder bleibt der Preset-Bestand unveraendert (Round-Trip)', () => {
		const preset = makePreset({
			official_alerts_enabled: false,
			official_warnings: { enabled: false, sources: ['vigilance'] },
			radar_alert_enabled: true
		});

		const { body } = buildHubPutPayload(preset, { corridors: preset.corridors });

		assert.strictEqual(body.official_alerts_enabled, false);
		assert.deepStrictEqual(body.official_warnings, { enabled: false, sources: ['vigilance'] });
		assert.strictEqual(body.radar_alert_enabled, true);
	});
});

// Issue #1260 (Adversary F001): ECHTER Verhaltensnachweis fuer den neu
// verdrahteten Hub-Alarme-Kurzstil-Pfad — ruft die realen Bridge-Funktionen mit
// einem Preset-Objekt auf und beweist, dass telegram_style aus dem Preset
// hydriert UND ein reiner Toggle-Klick in den PUT-Payload (display_config.
// telegram_style) wandert. KEIN Mock, KEIN Datei-Grep — direkte Aufrufe der
// exportierten Funktionen mit Assertion auf das tatsaechliche Ergebnis.
describe('#1260 Hub-Alarme Kurzstil-Toggle: Hydration + PUT-Persistenz (F001)', () => {
	function makeAlarmSnapshot(overrides: Partial<AlarmSnapshot> = {}): AlarmSnapshot {
		return {
			officialAlertsEnabled: true,
			officialWarningsEnabled: true,
			radarAlertEnabled: false,
			metricAlertLevels: {},
			alertCooldownMinutes: 30,
			alertQuietFrom: '22:00',
			alertQuietTo: '07:00',
			telegramStyle: 'rich',
			...overrides
		};
	}

	test('Hydration: display_config.telegram_style="kurzform" wird nach state.telegramStyle uebernommen', () => {
		const preset = makePreset({
			display_config: { region: 'Vorarlberg', telegram_style: 'kurzform' }
		});
		const state: Record<string, unknown> = {};

		hydrateAlarmFieldsFromPreset(state, preset);

		assert.strictEqual(
			state.telegramStyle,
			'kurzform',
			'ohne diese Hydration bliebe der Kurzstil-Toggle im Hub-Alarme-Tab unsichtbar (F001)'
		);
	});

	test('Hydration-Default: fehlt telegram_style im Preset, greift "rich"', () => {
		const preset = makePreset({ display_config: { region: 'Vorarlberg' } });
		const state: Record<string, unknown> = {};

		hydrateAlarmFieldsFromPreset(state, preset);

		assert.strictEqual(state.telegramStyle, 'rich', 'Default ist der reiche Bubble-Stil');
	});

	test('reiner Toggle-Klick (rich -> kurzform) loest PUT aus und setzt display_config.telegram_style', () => {
		const preset = makePreset({
			display_config: { region: 'Vorarlberg', telegram_style: 'rich' }
		});
		const before = makeAlarmSnapshot({ telegramStyle: 'rich' });
		const current = makeAlarmSnapshot({ telegramStyle: 'kurzform' });

		const result = flushPendingAlarmSave(preset, current, before);

		assert.ok(result, 'ein reiner Kurzstil-Toggle-Klick muss einen PUT-Payload liefern (nicht null)');
		const dc = result!.body.display_config as Record<string, unknown>;
		assert.strictEqual(
			dc.telegram_style,
			'kurzform',
			'der neue Kurzstil-Wert muss in display_config.telegram_style landen (F001-Kernbeweis)'
		);
	});

	test('RMW: der Toggle-PUT bewahrt andere display_config-Keys (metric_alert_levels)', () => {
		const preset = makePreset({
			display_config: {
				region: 'Vorarlberg',
				telegram_style: 'rich',
				metric_alert_levels: { snow_depth_cm: 'warn' }
			}
		});
		const result = flushPendingAlarmSave(
			preset,
			makeAlarmSnapshot({ telegramStyle: 'kurzform', metricAlertLevels: { snow_depth_cm: 'warn' } }),
			makeAlarmSnapshot({ telegramStyle: 'rich', metricAlertLevels: { snow_depth_cm: 'warn' } })
		);

		assert.ok(result);
		const dc = result!.body.display_config as Record<string, unknown>;
		assert.strictEqual(dc.telegram_style, 'kurzform');
		assert.deepStrictEqual(
			dc.metric_alert_levels,
			{ snow_depth_cm: 'warn' },
			'RMW: telegram_style-Aenderung darf metric_alert_levels nicht verlieren (#102/#1257-Kontext)'
		);
	});
});
