// Rework #3020 R1, AC-14: „Defaults = Auslieferung“ im Reiter „Zustellung“ beim Anlegen.
// Was der Reiter bei einem neu angelegten Trip bzw. Ortsvergleich als Standard zeigt, ist genau das, was
// der Anlege-POST ausliefert, wenn der Nutzer den Reiter nie beruehrt. Ersatz fuer den mit #3357
// geloeschten versand_tab_defaults_gleich_auslieferung.test.ts (galt dem geloeschten Versand-Reiter).
//
// Spec: docs/specs/modules/rework_3020_pruefungen_wiederherstellen.md (AC-14)
//
// Dieselbe Quelle auf beiden Seiten: der Reiter liest seinen Start aus dem Eintritts-Abo der Anlege-Seite
// (TripNewEditor: `zustellungAnlegeTrip` = Stub-Trip + Alarm-Zustand; CompareNewEditor: `zustellungAbo` aus
// `compareFeldsatzStandard()`); der POST entsteht aus demselben Zustand (`buildCreateTripPayload` mit
// `ergaenzeStandardwerteReportConfig`, bzw. `baueVergleichAnlegeRumpf`). Verglichen wird Reiter-Stand gegen
// den aus dem POST-Rumpf gelesenen Stand UND Feld fuer Feld gegen den Rumpf selbst.
//
//   cd frontend && npm test -- src/lib/components/shared/zustellung-tab/__tests__/rework_3020_defaults_gleich_auslieferung.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { standAusPreset, standAusTrip, KANAELE, type ZustellungStand } from '../zustellungModell.ts';
import { zustellungNutzlast } from '../zustellungSpeicherung.ts';
import { toHHMMSS } from '../../../../utils/time.ts';
import {
	buildCreateTripPayload,
	ergaenzeStandardwerteReportConfig,
	initialCreateTripAlarmState
} from '../../../trip-new/tripNewLogic.ts';
import { baueVergleichAnlegeRumpf, compareFeldsatzStandard } from '../../../compare/compareEditorSave.ts';
import { newEntityAlertChannelDefault } from '../../alarme-tab/alertChannelState.ts';
import type { ComparePreset, Trip } from '../../../../types.ts';

type Rec = Record<string, unknown>;

/** Briefing-Felder des Stands gegen den ausgelieferten Rumpf (Trip: report_config, Orte: top-level). */
function pruefeBriefingFelder(stand: ZustellungStand, quelle: Rec, wo: string): void {
	assert.equal(quelle.morning_enabled, stand.morgenAn, `${wo}: morning_enabled`);
	assert.equal(quelle.evening_enabled, stand.abendAn, `${wo}: evening_enabled`);
	assert.equal(quelle.morning_time, toHHMMSS(stand.morgenZeit), `${wo}: morning_time`);
	assert.equal(quelle.evening_time, toHHMMSS(stand.abendZeit), `${wo}: evening_time`);
	for (const k of KANAELE) assert.equal(quelle[`send_${k}`], stand.briefing[k], `${wo}: send_${k}`);
}

/** Adversary F003: Cooldown und Stille-Stunden sind beim Anlegen nicht im POST, die Auslieferung nimmt
 *  dann ihren eigenen Standard. Der Vergleich „Stand aus dem POST“ ist hier symmetrisch (beide Seiten lesen
 *  denselben Rueckfall aus zustellungModell.ts) und faengt eine Aenderung dieses Rueckfalls nicht. Deshalb
 *  feste Sollwerte der Auslieferung:
 *  - Cooldown ohne Feld: 120 Minuten (`_DEFAULT_COOLDOWN_MINUTES = 120` in src/services/compare_alert.py und
 *    compare_radar_alert.py, `or 120` in src/services/radar_alert_service.py).
 *  - Stille-Stunden ohne Felder: keine Ruhezeit (Schalter aus); schaltet der Nutzer sie ein, ohne die Zeiten
 *    anzufassen, liefert der Reiter die angezeigte Vorbelegung 22:00 bis 06:00 aus. */
const AUSLIEFERUNG_COOLDOWN_MINUTEN = 120;
const STILLE_VORBELEGUNG = { von: '22:00', bis: '06:00' };

function pruefeAlarmFelder(context: 'route' | 'vergleich', stand: ZustellungStand, post: Rec, wo: string): void {
	const cooldown = typeof post.alert_cooldown_minutes === 'number' ? post.alert_cooldown_minutes : AUSLIEFERUNG_COOLDOWN_MINUTEN;
	assert.equal(stand.cooldown, cooldown, `${wo}: der Reiter zeigt einen anderen Cooldown als die Auslieferung`);
	const stilleGeliefert = !!post.alert_quiet_from && !!post.alert_quiet_to;
	assert.equal(stand.stilleAn, stilleGeliefert, `${wo}: Stille-Schalter weicht von der Auslieferung ab`);
	assert.deepEqual({ von: stand.stilleVon, bis: stand.stilleBis }, STILLE_VORBELEGUNG, `${wo}: Vorbelegung der Stille-Stunden`);
	const eingeschaltet = zustellungNutzlast(context, stand, { ...stand, stilleAn: true }).alarme as Rec;
	assert.equal(eingeschaltet.alert_quiet_from, STILLE_VORBELEGUNG.von, `${wo}: eingeschaltet ausgeliefertes alert_quiet_from`);
	assert.equal(eingeschaltet.alert_quiet_to, STILLE_VORBELEGUNG.bis, `${wo}: eingeschaltet ausgeliefertes alert_quiet_to`);
}

describe('Rework #3020 AC-14 (route): Reiter-Standard beim neuen Trip = Anlege-POST', () => {
	test('unberuehrter Reiter: angezeigter Stand gleich dem ausgelieferten', () => {
		// Anlege-Seite: reportConfig startet leer (seed ohne reportConfig), Alarm-Zustand Neuanlage.
		const reportConfig = undefined;
		const alarm = initialCreateTripAlarmState();
		const eintritt = {
			id: '__new__', name: 'Neuer Trip', stages: [], report_config: reportConfig,
			alert_channels: alarm.channels, alert_channel_thresholds: alarm.channelThresholds,
			alert_quiet_from: alarm.quietFrom, alert_quiet_to: alarm.quietTo, alert_cooldown_minutes: alarm.cooldownMinutes
		} as unknown as Trip;
		const angezeigt = standAusTrip(eintritt);

		const post = buildCreateTripPayload({
			name: 'Neuer Trip', startDate: '2026-07-10', stages: [{ name: 'E1', waypoints: [] }] as never,
			weatherMetrics: [], channels: { email: true, telegram: true, sms: false } as never,
			reportConfig: ergaenzeStandardwerteReportConfig(reportConfig), alarm
		} as never) as unknown as Rec;

		const rc = post.report_config as Rec;
		assert.ok(rc, 'der POST traegt report_config');
		pruefeBriefingFelder(angezeigt, rc, 'Trip');
		pruefeAlarmFelder('route', angezeigt, post, 'Trip');
		assert.deepEqual(post.alert_channels, angezeigt.alarme, 'Alarm-Kanaele');
		assert.deepEqual(standAusTrip(post as unknown as Trip), angezeigt, 'Stand aus dem POST = angezeigter Stand');
	});
});

describe('Rework #3020 AC-14 (vergleich): Reiter-Standard beim neuen Ortsvergleich = Anlege-POST', () => {
	test('unberuehrter Reiter: angezeigter Stand gleich dem ausgelieferten', () => {
		const wiz = { ...compareFeldsatzStandard(), name: 'Neuer Vergleich', pickedIds: ['loc-a'] };
		// Eintritts-Abo wie CompareNewEditor.svelte (`zustellungAbo`).
		const eintritt = {
			id: '', name: wiz.name, location_ids: wiz.pickedIds,
			send_email: wiz.sendEmail, send_telegram: wiz.sendTelegram, send_sms: wiz.sendSms, send_premium_sms: wiz.sendPremiumSms,
			morning_enabled: wiz.morningEnabled, morning_time: wiz.morningTime,
			evening_enabled: wiz.eveningEnabled, evening_time: wiz.eveningTime,
			end_date: wiz.endDate ?? undefined,
			alert_channels: wiz.channels ?? newEntityAlertChannelDefault(),
			alert_channel_thresholds: wiz.channelThresholds,
			alert_quiet_from: wiz.alertQuietFrom, alert_quiet_to: wiz.alertQuietTo, alert_cooldown_minutes: wiz.alertCooldownMinutes
		} as unknown as ComparePreset;
		const angezeigt = standAusPreset(eintritt);

		const post = baueVergleichAnlegeRumpf(wiz);

		pruefeBriefingFelder(angezeigt, post, 'Vergleich');
		pruefeAlarmFelder('vergleich', angezeigt, post, 'Vergleich');
		assert.deepEqual(post.alert_channels, angezeigt.alarme, 'Alarm-Kanaele');
		assert.deepEqual(standAusPreset(post as unknown as ComparePreset), angezeigt, 'Stand aus dem POST = angezeigter Stand');
	});
});
