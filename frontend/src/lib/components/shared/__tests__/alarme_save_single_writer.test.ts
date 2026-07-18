// Bug-Nachweis — Issue #1258 Scheibe S3, Adversary Fix-Loop 1, Finding F001.
//
// Bug (rot vor Fix): AlarmeScheduleTab.svelte hatte zwei EIGENE
// `saveController.schedule()`-Aufrufer (handleMetricLevelChange :47,
// handleChannelToggle :66) neben dem EINEN konsolidierten `$effect` in
// AlarmeTab.svelte. Alle drei Aufrufer teilten sich denselben Ein-Slot-
// Debounce (`saveStatusStore.svelte.ts:67-72`, `_pendingFn` wird bei jedem
// `schedule()` vollstaendig ersetzt) — zwei Aenderungen aus verschiedenen
// Quellen innerhalb des 700ms-Fensters verwarfen die erste Payload
// unwiderruflich, waehrend die UI "Gespeichert ✓" zeigte. Reproduziert vom
// Adversary mit der echten `SaveStatus`-Klasse (SSR-kompiliert).
//
// Fix: Kanaele (`channels`) und Metrik-Level (`metricLevels`) sind Teil der
// EINEN konsolidierten Payload in `buildAlarmeDeliveryPayload` geworden
// (s. AlarmeTab.svelte route-$effect) — AlarmeScheduleTab.svelte hat keine
// eigene Schreibquelle mehr.
//
// Teil (a): statische Architektur-Invarianz — AlarmeScheduleTab.svelte darf
// KEIN eigenes `saveController.schedule(`/`doSave(` mehr enthalten (Muster
// wie legacy_wizard_removed.test.ts).
// Teil (b): Verhaltens-Test gegen die echte `buildAlarmeDeliveryPayload` —
// EINE Payload traegt Kanaele + Cooldown + Metrik-Level + amtliche-Toggles
// GEMEINSAM, und der display_config-RMW-Spread erhaelt fremde Keys.
//
// Spec: docs/specs/modules/issue_1258_alarme_tab_official_warnings.md (AC-12, AC-26)

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

import { buildAlarmeDeliveryPayload } from '../alarme-tab/alarmeDeliveryPayload.ts';

const here = dirname(fileURLToPath(import.meta.url));
const COMPONENTS = join(here, '..', '..'); // frontend/src/lib/components

// ── Teil (a): keine zweite Schreibquelle im Trip-Container ────────────────

test('#1258 S3 F001: AlarmeScheduleTab.svelte enthaelt keinen eigenen saveController.schedule()-Aufruf mehr', () => {
	const src = readFileSync(join(COMPONENTS, 'trip-detail', 'AlarmeScheduleTab.svelte'), 'utf-8');
	assert.ok(
		!src.includes('saveController.schedule('),
		'AlarmeScheduleTab.svelte ruft schedule() noch selbst auf — F001-Race lebt fort ' +
			'(zwei Schreibquellen teilen sich den Ein-Slot-Debounce)'
	);
	assert.ok(
		!src.includes('void doSave('),
		'AlarmeScheduleTab.svelte hat noch einen eigenen doSave()-Fallback-Pfad — ' +
			'Persistenz muss ausschliesslich ueber AlarmeTab.svelte laufen'
	);
});

// ── Teil (b): EINE konsolidierte Payload traegt alle Felder gemeinsam ─────

test('#1258 S3 F001: buildAlarmeDeliveryPayload konsolidiert Kanaele + Cooldown + Metrik-Level + amtliche-Toggles in EINEM Objekt', () => {
	const payload = buildAlarmeDeliveryPayload(
		{
			officialWarningsEnabled: false,
			cooldownMinutes: 30,
			quietFrom: '21:00',
			quietTo: '07:00',
			channels: { email: false, telegram: true, sms: false },
			metricLevels: { wind_gust: 'sensibel' }
		},
		{ ideal_ranges: { temp: [10, 20] }, region: 'gr20' }
	) as Record<string, unknown>;

	// amtliche-Toggles + Cooldown/Quiet — wie bisher.
	assert.deepEqual(payload.official_warnings, { enabled: false });
	assert.equal(payload.alert_cooldown_minutes, 30);

	// Kanaele — NEU Teil derselben Payload (F001-Fix).
	assert.deepEqual(payload.alert_channels, { email: false, telegram: true, sms: false });

	// Metrik-Level — NEU Teil derselben Payload, als RMW-Spread ueber
	// currentDisplayConfig (fremde Keys wie ideal_ranges/region bleiben erhalten,
	// BUG-DATALOSS-Klasse s. CLAUDE.md "Daten-Schema-Reworks").
	assert.deepEqual(payload.display_config, {
		ideal_ranges: { temp: [10, 20] },
		region: 'gr20',
		metric_alert_levels: { wind_gust: 'sensibel' }
	});
});

test('#1258 S3 F001: ohne metricLevels bleibt display_config komplett aus der Payload draussen (kein leerer Overwrite)', () => {
	const payload = buildAlarmeDeliveryPayload({
		officialWarningsEnabled: true,
		channels: { email: true, telegram: false, sms: false }
	}) as Record<string, unknown>;
	assert.equal('display_config' in payload, false);
});

test('#1258 S3 F001: channels ist Pflicht — Nicht-boolean-Kanalwert wirft (Guard analog officialWarningsEnabled)', () => {
	assert.throws(() => {
		buildAlarmeDeliveryPayload({
			officialWarningsEnabled: true,
			channels: { email: true, telegram: 'true' as unknown as boolean, sms: false }
		});
	}, /channels/);
});

test('#1258 S3 F001: zwei rasch aufeinanderfolgende Aenderungen (Kanal, dann Metrik-Level) ergeben je eine Payload mit dem VOLLSTAENDIGEN Zustand — kein Feld geht verloren', () => {
	// Simuliert Aenderung 1: Nutzer togglet einen Kanal.
	const afterChannelToggle = buildAlarmeDeliveryPayload({
		officialWarningsEnabled: false,
		cooldownMinutes: 15,
		channels: { email: true, telegram: true, sms: false },
		metricLevels: { wind_gust: 'standard' }
	}) as Record<string, unknown>;

	// Simuliert Aenderung 2 (innerhalb desselben 700ms-Debounce-Fensters):
	// Nutzer aendert ein Metrik-Level. Weil BEIDE Aenderungen denselben
	// lokalen State in AlarmeTab.svelte treiben, enthaelt die finale Payload
	// (die einzige, die tatsaechlich gesendet wird) beide Aenderungen.
	const afterMetricChange = buildAlarmeDeliveryPayload({
		officialWarningsEnabled: false,
		cooldownMinutes: 15,
		channels: { email: true, telegram: true, sms: false },
		metricLevels: { wind_gust: 'sensibel' }
	}) as Record<string, unknown>;

	assert.deepEqual(afterMetricChange.alert_channels, afterChannelToggle.alert_channels);
	assert.notDeepEqual(afterMetricChange.display_config, afterChannelToggle.display_config);
	assert.deepEqual(
		(afterMetricChange.display_config as Record<string, unknown>).metric_alert_levels,
		{ wind_gust: 'sensibel' }
	);
});
