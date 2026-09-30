// Issue #2277 Scheibe S2c — /compare/new?from=<id>: Vorbelegung des Anlege-Zustands
// aus einem bestehenden Ortsvergleich (Vorlage).
// Spec: docs/specs/modules/feat_2277_s2c_compare_from_vorlage.md (AC-1..AC-5, AC-8, AC-9)
//
// Technik (kein Mock-Theater): der ECHTE CompareWizardState wird instanziiert
// ($state als Passthrough geschimmt, Praezedenz compare_wizard_save_new_preset_channels.test.ts)
// und von der ECHTEN Funktion vorlageInZustand() befuellt. Gemessen wird der Zustand bzw.
// der aus ihm gebaute Create-Payload (buildNewComparePresetPayload) — kein gespiegeltes Soll.
//
// RED-Zustand: compareNewVorlage.ts existiert noch nicht -> Import scheitert.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/compare-new/__tests__/compareNewVorlage.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import type { ComparePreset, Location } from '../../../types.ts';
import { unlockedTabs } from '../compareNewLogic.ts';
import { buildNewComparePresetPayload } from '../../compare/compareEditorSave.ts';

// `$app/navigation` existiert ausserhalb von SvelteKit nicht; CompareWizardState importiert es
// nur lazy in saveNewPreset() — hier nicht aufgerufen, der Hook haelt den Import trotzdem stabil.
const appNavigationStubHook = `
export async function resolve(specifier, context, nextResolve) {
	if (specifier === '$app/navigation') {
		return { url: 'data:text/javascript,export function goto(){}', shortCircuit: true };
	}
	return nextResolve(specifier, context);
}
`;
register(`data:text/javascript,${encodeURIComponent(appNavigationStubHook)}`, import.meta.url);

(globalThis as unknown as { $state: <T>(v: T) => T }).$state = <T>(v: T): T => v;

const { CompareWizardState } = await import('../../compare/compareWizardState.svelte.ts');
const { vorlageInZustand } = await import('../compareNewVorlage.ts');

const loc = (id: string): Location => ({ id, name: id }) as unknown as Location;
const ORTE = [loc('a'), loc('b'), loc('c')];

/** Vollstaendig belegte Vorlage: jedes Feld mit einem vom Standard ABWEICHENDEN Wert. */
function vorlage(over: Partial<ComparePreset> = {}): ComparePreset {
	return {
		id: 'cmp-original',
		name: 'Korsika Nord',
		location_ids: ['a', 'b', 'c'],
		schedule: 'weekly',
		weekday: 3,
		profil: 'wandern',
		hour_from: 6,
		hour_to: 18,
		empfaenger: [],
		forecast_hours: 48,
		letzter_versand: '2026-09-01T07:00:00Z',
		created_at: '2026-08-01T00:00:00Z',
		paused_at: '2026-09-02T00:00:00Z',
		display_config: {
			region: 'Korsika',
			hourly_metrics: ['temp_max_c'],
			outlook_metrics: ['temp_max_c'],
			outlook_metric_formats: { temp_max_c: true },
			telegram_style: 'kurzform',
			metric_alert_levels: { wind_kmh: 'hoch' }
		},
		hourly_enabled: false,
		outlook_enabled: false,
		send_telegram: true,
		send_sms: true,
		send_premium_sms: true,
		morning_enabled: false,
		morning_time: '05:30:00',
		evening_enabled: true,
		evening_time: '19:45:00',
		end_date: '2026-10-15',
		day_window_start_hour: 7,
		day_window_end_hour: 21,
		alert_cooldown_minutes: 90,
		alert_quiet_from: '22:00',
		alert_quiet_to: '06:00',
		official_alerts_enabled: false,
		radar_alert_enabled: true,
		corridors: [{ metric_id: 'wind_kmh', min: 0, max: 30 }] as unknown as ComparePreset['corridors'],
		...over
	} as ComparePreset;
}

function belegt(preset: ComparePreset, locations: Location[] = ORTE) {
	const state = new CompareWizardState();
	vorlageInZustand(preset, locations, state);
	return state;
}

// ── AC-1: jedes Feld vorbelegt (je Feld ein Fall) ────────────────────────────

test('AC-1 Region wird uebernommen', () => {
	assert.equal(belegt(vorlage()).region, 'Korsika');
});
test('AC-1 Aktivitaetsprofil wird uebernommen', () => {
	assert.equal(belegt(vorlage()).activityProfile, 'wandern');
});
test('AC-1 Orte (pickedIds) werden uebernommen', () => {
	assert.deepEqual(belegt(vorlage()).pickedIds, ['a', 'b', 'c']);
});
test('AC-1 Korridore werden uebernommen', () => {
	assert.deepEqual(belegt(vorlage()).corridors, vorlage().corridors);
});
test('AC-1 Alarmstufen je Metrik werden uebernommen', () => {
	assert.deepEqual(belegt(vorlage()).metricAlertLevels, { wind_kmh: 'hoch' });
});
test('AC-1 Zeitplan: weekly + Wochentag werden uebernommen', () => {
	const s = belegt(vorlage());
	assert.equal(s.schedule, 'weekly');
	assert.equal(s.weekday, 3);
});
test('AC-1 Versand-Kanaele (Telegram/SMS/Premium-SMS) werden uebernommen', () => {
	const s = belegt(vorlage());
	assert.equal(s.sendTelegram, true);
	assert.equal(s.sendSms, true);
	assert.equal(s.sendPremiumSms, true);
});
test('AC-1 Zwei-Slot-Zeitplan wird uebernommen (HH:MM)', () => {
	const s = belegt(vorlage());
	assert.equal(s.morningEnabled, false);
	assert.equal(s.morningTime, '05:30');
	assert.equal(s.eveningEnabled, true);
	assert.equal(s.eveningTime, '19:45');
});
test('AC-1 Enddatum wird uebernommen', () => {
	assert.equal(belegt(vorlage()).endDate, '2026-10-15');
});
test('AC-1 Tagesfenster wird uebernommen', () => {
	const s = belegt(vorlage());
	assert.equal(s.dayWindowStartHour, 7);
	assert.equal(s.dayWindowEndHour, 21);
});
test('AC-1 Stundenverlauf: Schalter + Metriken werden uebernommen', () => {
	const s = belegt(vorlage());
	assert.equal(s.hourlyEnabled, false);
	assert.deepEqual(s.hourlyMetricKeys, ['temp_max_c']);
});
test('AC-1 Ausblick: Schalter + Metriken + Formate werden uebernommen', () => {
	const s = belegt(vorlage());
	assert.equal(s.outlookEnabled, false);
	assert.deepEqual(s.outlookMetricKeys, ['temp_max_c']);
	assert.deepEqual(s.outlookMetricFormats, { temp_max_c: true });
});
test('AC-1 Kurzform (telegram_style) wird uebernommen', () => {
	assert.equal(belegt(vorlage()).telegramStyle, 'kurzform');
});
test('AC-1 Alarm-Felder (Cooldown, Ruhezeit, Amtlich, Radar) werden uebernommen', () => {
	const s = belegt(vorlage());
	assert.equal(s.alertCooldownMinutes, 90);
	assert.equal(s.alertQuietFrom, '22:00');
	assert.equal(s.alertQuietTo, '06:00');
	assert.equal(s.officialAlertsEnabled, false);
	assert.equal(s.radarAlertEnabled, true);
});

// ── AC-2: Name ───────────────────────────────────────────────────────────────

test('AC-2 Name lautet "<Name> (Kopie)"', () => {
	assert.equal(belegt(vorlage()).name, 'Korsika Nord (Kopie)');
});

// ── AC-3: keine Identitaet, Anlege-Modus ─────────────────────────────────────

test('AC-3 isEditMode bleibt false (Anlege-Modus)', () => {
	assert.equal(belegt(vorlage()).isEditMode, false);
});
test('AC-3 Create-Payload enthaelt keine id, keinen letzter_versand, keinen Pausenstatus', () => {
	const s = belegt(vorlage());
	const payload = buildNewComparePresetPayload({
		name: s.name,
		pickedIds: s.pickedIds,
		activityProfile: s.activityProfile,
		schedule: s.schedule,
		corridors: s.corridors,
		region: s.region,
		hourlyMetricKeys: s.hourlyMetricKeys,
		outlookMetricKeys: s.outlookMetricKeys
	} as never);
	for (const verboten of ['id', 'letzter_versand', 'paused_at', 'created_at', 'archived_at']) {
		assert.ok(!(verboten in payload), `Create-Payload darf "${verboten}" nicht tragen`);
	}
});

// ── AC-4: geloeschte Orte ────────────────────────────────────────────────────

test('AC-4 geloeschter Ort erscheint nicht in pickedIds', () => {
	const s = belegt(vorlage(), [loc('a'), loc('c')]);
	assert.deepEqual(s.pickedIds, ['a', 'c']);
});

// ── AC-5: <2 Orte => Folge-Reiter bleibt gesperrt ────────────────────────────
// Spec-Wortlaut "Orte-Reiter gesperrt": die Lock-Engine sperrt bei <2 Orten den Reiter NACH
// Orte (metriken); Orte selbst ist ab gesetztem Namen offen (sonst koennte man keinen Ort
// nachwaehlen). Gemessen wird deshalb die reale Lock-Engine.

test('AC-5 bei nur einem vorhandenen Ort bleibt der Reiter nach Orte gesperrt, Orte offen', () => {
	const s = belegt(vorlage(), [loc('a')]);
	assert.deepEqual(s.pickedIds, ['a']);
	const offen = unlockedTabs({
		name: s.name,
		pickedCount: s.pickedIds.length,
		metrikenVisited: false,
		idealsVisited: false,
		alarmeVisited: false,
		versandVisited: false
	} as never);
	assert.ok(offen.has('orte'), 'Orte-Reiter muss offen sein, um Orte nachzuwaehlen');
	assert.ok(!offen.has('metriken'), 'Metriken-Reiter muss bei <2 Orten gesperrt bleiben');
});
test('AC-5 keine Platzhalter-IDs: null vorhandene Orte => pickedIds leer', () => {
	assert.deepEqual(belegt(vorlage(), []).pickedIds, []);
});

// ── AC-8: ohne Vorlage identisch zum Standard ────────────────────────────────

test('AC-8 ohne Aufruf von vorlageInZustand entspricht der Zustand dem Standard (kein Suffix)', () => {
	const frisch = new CompareWizardState();
	assert.equal(frisch.name, '');
	assert.deepEqual(frisch.pickedIds, []);
	assert.equal(frisch.isEditMode, false);
});

// ── AC-9: Sentinel-Semantik ──────────────────────────────────────────────────

test('AC-9 bewusst leeres hourly_metrics [] bleibt []', () => {
	const p = vorlage();
	(p.display_config as Record<string, unknown>).hourly_metrics = [];
	assert.deepEqual(belegt(p).hourlyMetricKeys, []);
});
test('AC-9 fehlendes hourly_metrics bleibt null (nie eingestellt)', () => {
	const p = vorlage();
	delete (p.display_config as Record<string, unknown>).hourly_metrics;
	assert.strictEqual(belegt(p).hourlyMetricKeys, null);
});
test('AC-9 bewusst leere outlook_metrics [] bleibt [], fehlende bleibt null', () => {
	const leer = vorlage();
	(leer.display_config as Record<string, unknown>).outlook_metrics = [];
	assert.deepEqual(belegt(leer).outlookMetricKeys, []);
	const fehlt = vorlage();
	delete (fehlt.display_config as Record<string, unknown>).outlook_metrics;
	assert.strictEqual(belegt(fehlt).outlookMetricKeys, null);
});
test('AC-9 fehlendes end_date => endDate null (nicht "" und nicht undefined)', () => {
	const p = vorlage();
	delete (p as { end_date?: string }).end_date;
	assert.strictEqual(belegt(p).endDate, null);
});
