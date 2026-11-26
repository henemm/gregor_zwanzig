// Issue #2277 Scheibe S2c — /compare/new?from=<id>: Vorbelegung des Anlege-Zustands
// aus einem bestehenden Ortsvergleich (Vorlage).
// Spec: docs/specs/modules/feat_2277_s2c_compare_from_vorlage.md (AC-1..AC-5, AC-8, AC-9)
//
// Umgebaut fuer Issue #2727 (Epic #2345, DoD-1) — Spec
// docs/specs/modules/feat_2727_compare_wizardstate_abloesen.md, AC-7 und AC-22:
// die Vorlage mutiert kein Zustandsobjekt mehr, sondern die REINE Funktion
// `feldsatzAusVorlage(preset, locations)` gibt den Feldsatz zurueck, den der Editor
// einmalig beim Start ueber den Standard-Feldsatz legt
// (`{ ...compareFeldsatzStandard(), ...feldsatzAusVorlage(p, orte) }`).
// Alle bisherigen Zusicherungen bleiben, gemessen am Rueckgabewert. `weekday` und
// `isEditMode` gehoeren nicht in den Vorlagen-Feldsatz; `weekday` reist auch nicht im Payload.
// Der echte Create-Request mit Vorlage (fetch, If-Match, Identitaet) ist in
// shared/__tests__/compare_new_editor_postet_einmal.test.ts am Editor gemessen.
//
// Technik (kein Mock-Theater): ECHTE Funktionen `feldsatzAusVorlage`,
// `compareFeldsatzStandard`, `buildNewComparePresetPayload` — kein gespiegeltes Soll.
//
// Warum heute rot: `feldsatzAusVorlage` und `compareFeldsatzStandard` fehlen (Namensraum-
// Importe, damit die Datei laedt; jeder Test scheitert mit „VERTRAG FEHLT").
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/compare-new/__tests__/compareNewVorlage.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import type { ComparePreset, Location } from '../../../types.ts';
import { tailUnlocked } from '../../shared/anlegeLockEngine.ts';
import { buildNewComparePresetPayload } from '../../compare/compareEditorSave.ts';
import * as vorlageModul from '../compareNewVorlage.ts';
import { neuerFeldsatz } from '../../shared/__tests__/compareFeldsatzPruefstand.ts';
import { aufgeloestVon } from '../../shared/wetter-tab/__tests__/wetterTabDaten.ts';

type Feldsatz = Record<string, any>;

function feldsatzAusVorlage(preset: ComparePreset, locations: Location[], vorlageId: string | null = null): Feldsatz {
	const fn = (vorlageModul as Record<string, unknown>).feldsatzAusVorlage;
	if (typeof fn !== 'function') {
		throw new Error(
			'VERTRAG FEHLT (#2727): compare-new/compareNewVorlage.ts exportiert keine reine Funktion ' +
				'`feldsatzAusVorlage(preset, locations)`.'
		);
	}
	return (fn as (p: ComparePreset, l: Location[], id: string | null) => Feldsatz)(preset, locations, vorlageId);
}

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

/** Was der Editor beim Start haelt: Standard-Feldsatz, darueber der Vorlagen-Feldsatz. */
function belegt(preset: ComparePreset, locations: Location[] = ORTE, vorlageId: string | null = null): Feldsatz {
	return { ...neuerFeldsatz(), ...feldsatzAusVorlage(preset, locations, vorlageId) };
}
/** #3399 S2: wie die Seite — Vorlagen-ID der Quelle aus dem ECHTEN resolve_entwurf (Python). */
const mitServerVorlage = (preset: ComparePreset): Feldsatz =>
	belegt(preset, ORTE, aufgeloestVon(preset as never).vorlage_id);

// ── AC-1: jedes Feld vorbelegt (je Feld ein Fall) ────────────────────────────

test('AC-1 Region wird uebernommen', () => {
	assert.equal(belegt(vorlage()).region, 'Korsika');
});
// #3198 (S4b-3, AC-5): das Profil steuert das Anlegen nicht mehr; uebernommen wird die
// Vorlage der Quelle (ampel.template -> profil -> allgemein).
test('AC-5 (#3198) Profil der Quelle wird nicht uebernommen, ihre Vorlage schon', () => {
	const f = mitServerVorlage(vorlage());
	assert.equal(f.activityProfile, null);
	assert.equal((f as Record<string, unknown>).vorlageId, 'wandern');
});
test('AC-5 (#3198) ampel.template der Quelle hat Vorrang vor dem Profil', () => {
	const f = mitServerVorlage(vorlage({ display_config: { region: 'Korsika', ampel: { template: 'wintersport' } } } as never));
	assert.equal((f as Record<string, unknown>).vorlageId, 'wintersport');
});
test('AC-5 (#3198) Quelle ohne Vorlage und Profil ⇒ „allgemein“', () => {
	assert.equal((mitServerVorlage(vorlage({ profil: undefined } as never)) as Record<string, unknown>).vorlageId, 'allgemein');
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
test('AC-1 Zeitplan: weekly wird uebernommen', () => {
	assert.equal(belegt(vorlage()).schedule, 'weekly');
});
test('#2727 AC-7: weekday steht weder im Vorlagen-Feldsatz noch im Create-Payload', () => {
	const teil = feldsatzAusVorlage(vorlage(), ORTE);
	assert.ok(!('weekday' in teil), `weekday im Feldsatz: ${JSON.stringify(teil.weekday)}`);
	const payload = buildNewComparePresetPayload(belegt(vorlage()) as never);
	assert.ok(!('weekday' in payload), 'weekday darf im Create-Payload nicht reisen');
});
test('#2727 AC-7: reine Funktion — Vorlage und Orte bleiben unveraendert, jeder Aufruf neu', () => {
	const p = vorlage();
	const vorher = JSON.stringify(p);
	const orte = [...ORTE];
	const a = feldsatzAusVorlage(p, orte);
	const b = feldsatzAusVorlage(p, orte);
	assert.equal(JSON.stringify(p), vorher, 'feldsatzAusVorlage veraendert die Vorlage');
	assert.equal(orte.length, ORTE.length);
	assert.notStrictEqual(a, b);
	assert.notStrictEqual(a.pickedIds, b.pickedIds);
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
test('AC-1 Stundenverlauf-Schalter wird uebernommen', () => {
	assert.equal(belegt(vorlage()).hourlyEnabled, false);
});
// Issue #3298: Stundenverlauf-/Ausblick-Auswahl, Ausblick-Schalter und Formate sind Altfelder
// (ADR-0124); die Vorlage traegt sie nicht mehr in den Feldsatz.
test('#3298 Altfelder der Vorlage landen nicht im Feldsatz', () => {
	const s = belegt(vorlage()) as unknown as Record<string, unknown>;
	for (const k of ['outlookEnabled', 'hourlyMetricKeys', 'outlookMetricKeys', 'outlookMetricFormats', 'hourlyMetricFormats']) {
		assert.ok(!(k in s), `${k} im Feldsatz aus Vorlage`);
	}
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

test('AC-3 isEditMode bleibt false (Anlege-Modus) und steht nicht im Vorlagen-Feldsatz', () => {
	assert.equal(belegt(vorlage()).isEditMode, false);
	assert.ok(!('isEditMode' in feldsatzAusVorlage(vorlage(), ORTE)), 'isEditMode im Vorlagen-Feldsatz');
});
test('AC-3 Create-Payload enthaelt keine id, keinen letzter_versand, keinen Pausenstatus', () => {
	const payload = buildNewComparePresetPayload(belegt(vorlage()) as never);
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
		{ metriken: 'wetter-metriken', wertebereiche: 'wertebereiche', alarme: 'alarme' },
		{
			metrikenFrei: !!s.name.trim() && s.pickedIds.length >= 2,
			metrikenVisited: false,
			wertebereicheVisited: false,
			alarmeVisited: false
		}
	);
	if (s.name.trim()) offen.add('orte');
	assert.ok(offen.has('orte'), 'Orte-Reiter muss offen sein, um Orte nachzuwaehlen');
	assert.ok(!offen.has('wetter-metriken'), 'Metriken-Reiter muss bei <2 Orten gesperrt bleiben');
});
test('AC-5 keine Platzhalter-IDs: null vorhandene Orte => pickedIds leer', () => {
	assert.deepEqual(belegt(vorlage(), []).pickedIds, []);
});

// ── AC-8: ohne Vorlage identisch zum Standard ────────────────────────────────

test('AC-8 ohne Vorlage entspricht der Zustand dem Standard (kein Suffix)', () => {
	const frisch = neuerFeldsatz();
	assert.equal(frisch.name, '');
	assert.deepEqual(frisch.pickedIds, []);
	assert.equal(frisch.isEditMode, false);
});

// ── AC-9: Sentinel-Semantik ──────────────────────────────────────────────────

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
// Issue #3298: die Lese-Naht der Kanal-Metriken ist entfernt — ein Altwert der Vorlage
// aendert den Feldsatz nicht, die Kanaele folgen der Grundauswahl (Standard).
test('#3298 Kanal-Metriken der Vorlage (Altschluessel) werden nicht gelesen', () => {
	assert.deepEqual(belegt(vorlage()).channelActiveMetricKeys, neuerFeldsatz().channelActiveMetricKeys);
});

// ── Adversary F002: minimale Vorlage => keine erfundenen Werte ──────────────

test('F002 minimale Vorlage (nur name + location_ids): Standardwerte bleiben', () => {
	const s = belegt({ name: 'Mini', location_ids: ['a', 'x'] } as unknown as ComparePreset);
	const frisch = neuerFeldsatz();
	assert.equal(s.name, 'Mini (Kopie)');
	assert.deepEqual(s.pickedIds, ['a']);
	assert.equal(s.region, '');
	assert.strictEqual(s.activeMetricKeys, null);
	assert.strictEqual(s.endDate, null);
	assert.equal(s.officialAlertsEnabled, frisch.officialAlertsEnabled);
	assert.equal(s.radarAlertEnabled, frisch.radarAlertEnabled);
	assert.equal(s.officialAlertTriggersEnabled, frisch.officialAlertTriggersEnabled);
	assert.equal(s.telegramStyle, frisch.telegramStyle);
	assert.equal(s.schedule, frisch.schedule);
	assert.ok(!('weekday' in s), 'weekday gehoert nicht in den Feldsatz');
	assert.deepEqual(s.metricAlertLevels, {});
	assert.deepEqual(s.channelThresholds, {});
	assert.deepEqual(s.idealRanges, {});
	assert.deepEqual(s.corridors, []);
	assert.equal(s.isEditMode, false);
});

// ── AC-3 (Adversary F004): Create-Payload aus dem vollstaendigen Feldsatz ──────
// Der echte Request (fetch, If-Match) laeuft seit #2727 durch den Editor und ist in
// shared/__tests__/compare_new_editor_postet_einmal.test.ts gemessen. Hier: der Payload, der
// aus ALLEN Feldern (Standard + Vorlage, kein handverlesener Satz) entsteht.

test('AC-3 Create-Payload aus dem vollen Feldsatz traegt Vorlagenwerte, aber keine Identitaet', () => {
	const p = vorlage({ etag: 'W/"orig-etag"' } as unknown as Partial<ComparePreset>);
	const f = belegt(p);
	const body = buildNewComparePresetPayload({ ...f, alertChannels: f.channels } as never);
	const roh = JSON.stringify(body);
	for (const verboten of ['id', 'etag', 'letzter_versand', 'paused_at', 'created_at', 'archived_at', 'weekday']) {
		assert.ok(!(verboten in body), `Create-Payload darf "${verboten}" nicht tragen`);
	}
	assert.ok(!roh.includes('cmp-original'), 'Vorlagen-ID darf nirgends im Payload stehen');
	assert.ok(!roh.includes('orig-etag'), 'Vorlagen-ETag darf nirgends im Payload stehen');
	assert.equal(body.name, 'Korsika Nord (Kopie)');
	assert.deepEqual(body.location_ids, ['a', 'b', 'c']);
	assert.equal(body.official_alert_triggers_enabled, false);
	assert.deepEqual(body.alert_channels, { email: false, telegram: true, sms: false, premium_sms: true });
	const dc = body.display_config as Record<string, unknown>;
	assert.equal(dc.region, 'Korsika');
	// Issue #3276 (Spec-AC-38, AC-1): `channel_active_metrics` ist Altschluessel — vorher musste die
	// Telegram-Kanalauswahl der Vorlage im Payload stehen, jetzt sendet die Neuanlage keinen der
	// sechs Altschluessel (auch nicht aus einer Vorlage).
	for (const alt of ['channel_layouts', 'outlook_metrics', 'outlook_metric_formats', 'channel_active_metrics', 'hourly_metrics', 'hourly_metric_formats']) {
		assert.ok(!(alt in dc), `#3276: ${alt} aus der Vorlage im Create-Payload`);
	}
});
