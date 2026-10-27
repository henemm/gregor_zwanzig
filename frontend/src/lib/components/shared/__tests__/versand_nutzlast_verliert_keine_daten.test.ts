// Issue #2276 Scheibe S5 (Epic #2345), AC-11 — UMGEDREHT durch Issue #2375:
// der Versand-PUT trägt NUR die Versand-Eigenfelder. Früher schickte er die
// VOLLSTÄNDIGE Preset-Nutzlast (Voll-Spread) samt der drei Legacy-Restfelder
// `alert_cooldown_minutes`/`alert_quiet_from`/`alert_quiet_to`, weil der Go-
// Handler ein PUT ins volle Modell dekodierte und fehlende Felder nullte. Das
// ist seit dem Feld-Merge des Go-Handlers (`mergeBriefingPatch`) überholt: ein
// fehlendes Feld bleibt unverändert. Ein Voll-Spread der (womöglich
// veralteten) Basis dagegen schrieb Fremdwerte eines anderen Tabs zurück.
//
// Spec: docs/specs/bugfix/compare_konfliktschutz_teilfelder.md
//   Abschnitt 2 (Feld-Besitz: Versand) / AC-7 — keine alert_cooldown_minutes/
//   alert_quiet_*/alert_channels im Versand-Body.
//
// Mutations-Gegenprobe: die drei Legacy-Felder wieder in `baueVersandNutzlast`
// aufnehmen ⇒ sie stehen im Body ⇒ rot. Ebenso rot wird der Test, wenn die
// Nutzlast wieder auf den Voll-Spread zurückfällt (Name, Orte, Korridore,
// Metrik-Auswahl, display_config).
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/__tests__/versand_nutzlast_verliert_keine_daten.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { baueVersandNutzlast, versandSnapshotAus } from '../versandVergleichSpeicherung.ts';
import { hydrierterWiz, makePreset } from './versandVergleichPruefstand.ts';

const PRESET_ID = 'cp-2276-s5-nutzlast';

function nutzlast(aenderung: Record<string, unknown> = {}) {
	const preset = makePreset(PRESET_ID);
	const wiz = { ...hydrierterWiz(preset), ...aenderung };
	const { url, body } = baueVersandNutzlast(preset, versandSnapshotAus(wiz));
	return { preset, url, body: body as unknown as Record<string, unknown> };
}

describe('AC-7 (#2375): die drei Legacy-Restfelder stehen NICHT im Versand-PUT (Besitzer: Alarme)', () => {
	test('weder alert_cooldown_minutes noch alert_quiet_from/-to noch alert_channels', () => {
		const { body } = nutzlast({ morningTime: '07:15' });
		for (const k of ['alert_cooldown_minutes', 'alert_quiet_from', 'alert_quiet_to', 'alert_channels']) {
			assert.ok(!(k in body), `Versand darf ${k} nicht senden — der Alarme-Reiter besitzt das Feld`);
		}
	});

	test('auch bei einer reinen Kanal-Änderung nicht', () => {
		const { body } = nutzlast({ sendSms: true });
		assert.equal(body.send_sms, true, 'Vorbedingung: die Änderung steht im Body');
		for (const k of ['alert_cooldown_minutes', 'alert_quiet_from', 'alert_quiet_to']) {
			assert.ok(!(k in body), `${k} darf nicht mitgesendet werden`);
		}
	});
});

describe('AC-7 (#2375): kein Fremdfeld im Versand-PUT — der Server bewahrt alles andere', () => {
	test('Bestandsfelder anderer Reiter und des Kopfes stehen nicht im Body', () => {
		const { url, body } = nutzlast({ morningTime: '07:15' });

		assert.equal(url, `/api/compare/presets/${PRESET_ID}`);
		for (const k of [
			'id',
			'name',
			'location_ids',
			'profil',
			'schedule',
			'previous_schedule',
			'empfaenger',
			'hour_from',
			'hour_to',
			'forecast_hours',
			'corridors',
			'alert_channel_thresholds',
			'official_warnings',
			'radar_alert_enabled',
			'official_alerts_enabled',
			'hourly_enabled',
			'outlook_enabled',
			'day_window_start_hour',
			'day_window_end_hour',
			'display_config'
		]) {
			assert.ok(!(k in body), `Fremdfeld ${k} darf im Versand-PUT nicht stehen`);
		}
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
