// TDD RED — Issue #2276 Scheibe S5 (Epic #2345), AC-11: der Versand-PUT trägt
// die VOLLSTÄNDIGE Preset-Nutzlast (Voll-Spread über
// `buildComparePresetSavePayload`) — einschließlich der drei Legacy-Restfelder
// `alert_cooldown_minutes`/`alert_quiet_from`/`alert_quiet_to`, die kein
// Kontrollelement des Versand-Reiters mutiert.
//
// Spec: docs/specs/modules/rework_2276_s5_versand.md — AC-11, Design Punkt 5+6
//
// WARUM die drei toten Felder BLEIBEN müssen: der Go-Handler dekodiert ein PUT
// ins volle Modell (ein Patch-DTO kommt erst mit #2285). Ein Versand-PUT ohne
// diese Felder NULLT sie bei einem Bestands-Preset auf den Server-Default —
// Datenverlust an Alarm-Zustellungsfeldern, ausgelöst durch einen Vorgang, der
// mit Alarm-Zustellung fachlich nichts zu tun hat (Klasse BUG-DATALOSS-GR221).
//
// Mutations-Gegenprobe (Spec AC-11): die drei Felder aus `baueVersandNutzlast`
// entfernen ⇒ sie fehlen im Body ⇒ rot. Ebenso rot wird der Test, wenn die
// Nutzlast wieder auf eine Teil-Nutzlast zurückfällt (Region, Korridore,
// Metrik-Auswahl, Kanal-Schwellen).
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/__tests__/versand_nutzlast_verliert_keine_daten.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { baueVersandNutzlast, versandSnapshotAus } from '../versandVergleichSpeicherung.ts';
import { dc, hydrierterWiz, makePreset } from './versandVergleichPruefstand.ts';

const PRESET_ID = 'cp-2276-s5-nutzlast';

function nutzlast(aenderung: Record<string, unknown> = {}) {
	const preset = makePreset(PRESET_ID);
	const wiz = { ...hydrierterWiz(preset), ...aenderung };
	return { preset, ...baueVersandNutzlast(preset, versandSnapshotAus(wiz)) };
}

describe('AC-11: die drei Legacy-Restfelder überleben den Versand-PUT', () => {
	test('alert_cooldown_minutes/alert_quiet_from/alert_quiet_to stehen unverändert im Body', () => {
		const { body } = nutzlast({ morningTime: '07:15' });

		assert.equal(body.alert_cooldown_minutes, 45, 'ein fehlendes Feld würde den Cooldown serverseitig nullen');
		assert.equal(body.alert_quiet_from, '22:00', 'Stille Stunden (von) dürfen nicht verloren gehen');
		assert.equal(body.alert_quiet_to, '07:00', 'Stille Stunden (bis) dürfen nicht verloren gehen');
	});

	test('auch bei einer reinen Kanal-Änderung bleiben sie erhalten', () => {
		const { body } = nutzlast({ sendSms: true });

		assert.equal(body.send_sms, true, 'Vorbedingung: die Änderung steht im Body');
		assert.equal(body.alert_cooldown_minutes, 45);
		assert.equal(body.alert_quiet_from, '22:00');
		assert.equal(body.alert_quiet_to, '07:00');
	});
});

describe('AC-11: alle übrigen Einstellungen round-trippen unverändert (Voll-Spread)', () => {
	test('Top-Level-Bestandsfelder bleiben, wie sie waren', () => {
		const { preset, body, url } = nutzlast({ morningTime: '07:15' });

		assert.equal(url, `/api/compare/presets/${PRESET_ID}`);
		assert.equal(body.name, preset.name);
		assert.deepEqual(body.location_ids, preset.location_ids);
		assert.equal(body.profil, preset.profil);
		assert.equal(body.schedule, preset.schedule);
		assert.deepEqual(body.empfaenger, preset.empfaenger);
		assert.equal(body.hour_from, preset.hour_from);
		assert.equal(body.hour_to, preset.hour_to);
		assert.equal(body.forecast_hours, preset.forecast_hours);
		assert.deepEqual(body.corridors, preset.corridors);
		assert.deepEqual(body.alert_channel_thresholds, preset.alert_channel_thresholds);
		assert.deepEqual(body.official_warnings, preset.official_warnings);
		assert.equal(body.radar_alert_enabled, preset.radar_alert_enabled);
		assert.equal(body.official_alerts_enabled, preset.official_alerts_enabled);
		assert.equal(body.hourly_enabled, preset.hourly_enabled);
		assert.equal(body.outlook_enabled, preset.outlook_enabled);
		assert.equal(body.day_window_start_hour, preset.day_window_start_hour);
		assert.equal(body.day_window_end_hour, preset.day_window_end_hour);
	});

	test('display_config round-trippt vollständig — Region, Wertebereiche, Metriken, Kurzstil', () => {
		const { preset, body } = nutzlast({ morningTime: '07:15' });
		const vorher = (preset.display_config ?? {}) as Record<string, unknown>;
		const nachher = dc(body);

		assert.equal(nachher.region, vorher.region, 'die Region darf beim Versand-Speichern nicht leer werden');
		assert.deepEqual(nachher.ideal_ranges, vorher.ideal_ranges);
		assert.deepEqual(nachher.active_metrics, vorher.active_metrics);
		assert.deepEqual(nachher.metric_alert_levels, vorher.metric_alert_levels);
		assert.equal(nachher.telegram_style, vorher.telegram_style);
		assert.deepEqual(nachher.hourly_metrics, vorher.hourly_metrics);
		assert.deepEqual(nachher.outlook_metrics, vorher.outlook_metrics);
		assert.deepEqual(nachher.outlook_metric_formats, vorher.outlook_metric_formats);
	});

	test('die Versand-Felder selbst kommen aus dem aktuellen Stand, nicht aus dem Preset', () => {
		const { body } = nutzlast({ morningTime: '07:15', sendSms: true, endDate: null });

		assert.equal(body.morning_time, '07:15:00', 'HH:MM aus der Oberfläche wird als HH:MM:SS persistiert');
		assert.equal(body.send_sms, true);
		assert.equal(body.end_date, '', '„Bis auf Weiteres" persistiert den Lösch-Sentinel');
		assert.equal(body.evening_time, '18:00:00', 'unangetastete Versand-Felder tragen den Bestandswert');
		assert.equal(body.morning_enabled, true);
		assert.equal(body.evening_enabled, false);
	});
});
