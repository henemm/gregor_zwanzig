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
import { tailUnlocked } from '../../shared/anlegeLockEngine.ts';
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
			metric_alert_levels: { wind_kmh: 'hoch' },
			active_metrics: ['wind_kmh', 'temp_max_c'],
			ideal_ranges: { wind_kmh: { min: 0, max: 20 } },
			channel_active_metrics: { telegram: ['wind_kmh'] }
		},
		alert_channels: { email: false, telegram: true, sms: false, premium_sms: true },
		alert_channel_thresholds: { telegram: 'hoch' },
		official_warnings: { enabled: true },
		official_alert_triggers_enabled: false,
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
		outlookMetricKeys: s.outlookMetricKeys,
		idealRanges: s.idealRanges,
		activeMetricKeys: s.activeMetricKeys,
		metricAlertLevels: s.metricAlertLevels
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
	// Vorderteil wie in CompareNewEditor.svelte: Orte frei ab Namen, Metriken ab Name + >=2 Orten.
	const offen: Set<string> = tailUnlocked(
		{ metriken: 'metriken', wertebereiche: 'idealwerte', alarme: 'alarme', versand: 'versand' },
		{
			metrikenFrei: !!s.name.trim() && s.pickedIds.length >= 2,
			metrikenVisited: false,
			wertebereicheVisited: false,
			alarmeVisited: false,
			versandVisited: false
		}
	);
	if (s.name.trim()) offen.add('orte');
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

// ── AC-1 (Adversary F001): Felder, deren Vorlagenwert vom Standard abweicht ──

test('AC-1 Alarm-Kanaele (alert_channels) werden uebernommen', () => {
	assert.deepEqual(belegt(vorlage()).channels, {
		email: false,
		telegram: true,
		sms: false,
		premium_sms: true
	});
});
test('AC-1 Kanal-Schwellen (alert_channel_thresholds) werden uebernommen', () => {
	assert.deepEqual(belegt(vorlage()).channelThresholds, { telegram: 'hoch' });
});
test('AC-1 amtliche Warnungen (official_warnings.enabled) werden uebernommen', () => {
	assert.equal(belegt(vorlage()).officialWarningsEnabled, true);
});
test('AC-1 official_alert_triggers_enabled=false wird uebernommen', () => {
	assert.equal(belegt(vorlage()).officialAlertTriggersEnabled, false);
});
test('AC-1 aktive Metriken werden uebernommen, fehlend bleibt null', () => {
	assert.deepEqual(belegt(vorlage()).activeMetricKeys, ['wind_kmh', 'temp_max_c']);
	const p = vorlage();
	delete (p.display_config as Record<string, unknown>).active_metrics;
	assert.strictEqual(belegt(p).activeMetricKeys, null);
});
test('AC-1 Idealwerte (ideal_ranges) werden uebernommen', () => {
	assert.deepEqual(belegt(vorlage()).idealRanges, { wind_kmh: { min: 0, max: 20 } });
});
test('AC-1 Kanal-Metriken (channel_active_metrics) werden uebernommen', () => {
	assert.deepEqual(belegt(vorlage()).channelActiveMetricKeys, {
		email: null,
		telegram: ['wind_kmh'],
		sms: null
	});
});
test('AC-9 outlook_metric_formats: fehlend bleibt null, {} bleibt {}', () => {
	const fehlt = vorlage();
	delete (fehlt.display_config as Record<string, unknown>).outlook_metric_formats;
	assert.strictEqual(belegt(fehlt).outlookMetricFormats, null);
	const leer = vorlage();
	(leer.display_config as Record<string, unknown>).outlook_metric_formats = {};
	assert.deepEqual(belegt(leer).outlookMetricFormats, {});
});

// ── Adversary F002: minimale Vorlage => keine erfundenen Werte ──────────────

test('F002 minimale Vorlage (nur name + location_ids): Standardwerte bleiben', () => {
	const s = belegt({ name: 'Mini', location_ids: ['a', 'x'] } as unknown as ComparePreset);
	const frisch = new CompareWizardState();
	assert.equal(s.name, 'Mini (Kopie)');
	assert.deepEqual(s.pickedIds, ['a']);
	assert.equal(s.region, '');
	assert.strictEqual(s.activeMetricKeys, null);
	assert.strictEqual(s.hourlyMetricKeys, null);
	assert.strictEqual(s.outlookMetricKeys, null);
	assert.strictEqual(s.outlookMetricFormats, null);
	assert.strictEqual(s.endDate, null);
	assert.equal(s.officialAlertsEnabled, frisch.officialAlertsEnabled);
	assert.equal(s.radarAlertEnabled, frisch.radarAlertEnabled);
	assert.equal(s.officialAlertTriggersEnabled, frisch.officialAlertTriggersEnabled);
	assert.equal(s.telegramStyle, frisch.telegramStyle);
	assert.equal(s.schedule, frisch.schedule);
	assert.equal(s.weekday, frisch.weekday);
	assert.deepEqual(s.metricAlertLevels, {});
	assert.deepEqual(s.channelThresholds, {});
	assert.deepEqual(s.idealRanges, {});
	assert.deepEqual(s.corridors, []);
	assert.equal(s.isEditMode, false);
});

// ── AC-3 (Adversary F004): echter Create-Request ueber saveNewPreset() ───────
// Ersatz-fetch nur an der Netzgrenze; den Request baut das ECHTE saveNewPreset()
// aus ALLEN Zustandsfeldern (kein handverlesener Feldsatz).

test('AC-3 Create-Request traegt Vorlagenwerte, aber keine Identitaet und kein If-Match', async () => {
	const p = vorlage({ etag: 'W/"orig-etag"' } as unknown as Partial<ComparePreset>);
	const s = belegt(p);
	const aufrufe: { url: string; init: RequestInit }[] = [];
	const echtesFetch = globalThis.fetch;
	globalThis.fetch = (async (url: string, init: RequestInit) => {
		aufrufe.push({ url: String(url), init });
		return new Response(JSON.stringify({ id: 'cmp-neu' }), {
			status: 201,
			headers: { 'Content-Type': 'application/json' }
		});
	}) as typeof fetch;
	try {
		await s.saveNewPreset();
	} finally {
		globalThis.fetch = echtesFetch;
	}
	assert.equal(s.saveStatus, 'ok', `saveError: ${s.saveError}`);
	assert.equal(aufrufe.length, 1);
	const { url, init } = aufrufe[0];
	assert.equal(url, '/api/compare/presets');
	assert.equal(init.method, 'POST');
	const kopf = init.headers as Record<string, string>;
	assert.ok(!('If-Match' in kopf), 'Create-Request darf kein If-Match tragen');
	const roh = String(init.body);
	const body = JSON.parse(roh) as Record<string, unknown>;
	for (const verboten of ['id', 'etag', 'letzter_versand', 'paused_at', 'created_at', 'archived_at']) {
		assert.ok(!(verboten in body), `Create-Request darf "${verboten}" nicht tragen`);
	}
	assert.ok(!roh.includes('cmp-original'), 'Vorlagen-ID darf nirgends im Request stehen');
	assert.ok(!roh.includes('orig-etag'), 'Vorlagen-ETag darf nirgends im Request stehen');
	assert.equal(body.name, 'Korsika Nord (Kopie)');
	assert.deepEqual(body.location_ids, ['a', 'b', 'c']);
	assert.equal(body.official_alert_triggers_enabled, false);
	assert.deepEqual(body.alert_channels, {
		email: false,
		telegram: true,
		sms: false,
		premium_sms: true
	});
	const dc = body.display_config as Record<string, unknown>;
	assert.equal(dc.region, 'Korsika');
	const kanal = dc.channel_active_metrics as Record<string, unknown> | undefined;
	assert.ok(kanal && 'telegram' in kanal, 'Telegram-Kanalauswahl der Vorlage muss im Request stehen');
});
