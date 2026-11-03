// TDD RED — #1895 S3b1, Speicherweg Ortsvergleich (AC-42, 47, 55, 56, 57). Feldname überall
// `alertMetricChannels` (AlarmSnapshot, Hydration, alarmePropsAus, CompareEditorEdits,
// NewComparePresetFields); Diff-Basis von baueAlarmNutzlast = preset.alert_metric_channels.
// AC-56: Rollback setzt seit dem Snapshot neue Einträge explizit auf null (Go-Merge je Schlüssel).
// AC-57 ist heute GRÜN — bewusst als Mutations-Fixture für die Nachbar-Schreiber.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import type { ComparePreset } from '../../../types.ts';
import { alarmSnapshotAus, baueAlarmNutzlast, flushPendingAlarmSave, rollbackAlarmSnapshot } from '../alarmeVergleichSpeicherung.ts';
import { hydrateAlarmFieldsFromPreset } from '../../compare/compareHubHydration.ts';
import { alarmePropsAus } from '../../compare/alarmePropsAus.ts';
import { buildComparePresetSavePayload, buildNewComparePresetPayload } from '../../compare/compareEditorSave.ts';
import { baueVersandNutzlast, hydrateVersandFieldsFromPreset } from '../versandVergleichSpeicherung.ts';
import { baueWertebereichNutzlast, corridorSnapshotAus } from '../corridor-editor/wertebereicheVergleichSpeicherung.ts';
import { goMerge } from './goMergeServerPruefstand.ts';

const TG = { email: false, telegram: true, sms: false, premium_sms: false };
const MAIL = { email: true, telegram: false, sms: false, premium_sms: false };
const ALT = { email: true, telegram: true, sms: false, premium_sms: false };

function preset(amc: Record<string, unknown>): ComparePreset {
	return {
		id: 'cmp-1', name: 'V', location_ids: ['a', 'b', 'c'], display_config: {},
		alert_channels: MAIL, official_warnings: { enabled: false }, alert_metric_channels: amc
	} as unknown as ComparePreset;
}
/** Hydrierter Zustand wie im Hub, dann der Kanal-Map-Stand überschrieben. */
function zustand(p: ComparePreset, amc?: Record<string, unknown>): Record<string, unknown> {
	const z: Record<string, unknown> = {};
	hydrateAlarmFieldsFromPreset(z, p, []);
	if (amc) z.alertMetricChannels = amc;
	return z;
}
const amcVon = (body: unknown) => (body as Record<string, unknown>).alert_metric_channels;

test('AC-55: Hydration aus dem Preset und Wertprop über alarmePropsAus', () => {
	const p = preset({ gust: TG, snowfall_limit: MAIL });
	const z = zustand(p);
	assert.deepStrictEqual(z.alertMetricChannels, { gust: TG, snowfall_limit: MAIL });
	const props = alarmePropsAus(z) as Record<string, unknown>;
	assert.deepStrictEqual(props.alertMetricChannels, { gust: TG, snowfall_limit: MAIL });
	(props.onAlarmFeldSetzen as (f: string, w: unknown) => void)('alertMetricChannels', { gust: null });
	assert.deepStrictEqual(z.alertMetricChannels, { gust: null }, 'Änderung über onAlarmFeldSetzen');
});

test('AC-47/AC-42: Alarm-PUT sendet nur den Diff; snowfall_limit bleibt nach dem Merge erhalten', () => {
	const p = preset({ gust: TG, snowfall_limit: MAIL });
	const vorher = alarmSnapshotAus(zustand(p));
	const jetzt = alarmSnapshotAus(zustand(p, { gust: TG, snowfall_limit: MAIL, thunder: TG }));
	const nutzlast = flushPendingAlarmSave(p, jetzt, vorher);
	assert.ok(nutzlast, 'eine Kanalwahl muss als Änderung erkannt werden (Snapshot trägt das Feld)');
	assert.deepStrictEqual(amcVon(nutzlast!.body), { thunder: TG }, 'nur der geänderte Eintrag (ALARM_TOP + Diff)');
	const gespeichert = goMerge(p as never, nutzlast!.body as never);
	assert.deepStrictEqual(gespeichert.alert_metric_channels, { gust: TG, snowfall_limit: MAIL, thunder: TG });
	assert.ok(!('alert_metric_channels' in (baueAlarmNutzlast(p, vorher).body as object)), 'ohne Änderung: Feld fehlt');
});

test('AC-56: Rollback sendet für den seit dem Snapshot neuen Eintrag gust explizit null und stellt thunder vollständig wieder her', () => {
	const vorher = alarmSnapshotAus(zustand(preset({ thunder: ALT })));
	const versucht = alarmSnapshotAus(zustand(preset({ thunder: ALT }), { thunder: TG, gust: TG }));
	const z = zustand(preset({ thunder: ALT }), { thunder: TG, gust: TG });
	rollbackAlarmSnapshot(z, vorher, versucht);
	assert.deepStrictEqual(z.alertMetricChannels, { thunder: ALT, gust: null });
	// Server hat den Versuch (unbemerkt) übernommen ⇒ der nächste PUT muss gust aktiv zurücksetzen.
	const server = preset({ thunder: TG, gust: TG });
	assert.deepStrictEqual(amcVon(baueAlarmNutzlast(server, alarmSnapshotAus(z)).body), { thunder: ALT, gust: null });
});

test('AC-55: Edit- und Create-Payload tragen alert_metric_channels', () => {
	const edit = buildComparePresetSavePayload(preset({}), {
		name: 'V', activityProfile: null, pickedIds: ['a', 'b', 'c'], region: '', idealRanges: {},
		alertMetricChannels: { thunder: TG }
	} as never);
	assert.deepStrictEqual(amcVon(edit), { thunder: TG }, 'Edit');
	const neu = buildNewComparePresetPayload({
		name: 'Neu', pickedIds: ['a', 'b', 'c'], activityProfile: null, schedule: 'daily_morning',
		officialAlertsEnabled: true, radarAlertEnabled: false, hourlyEnabled: true, officialAlertTriggersEnabled: false,
		sendTelegram: false, sendSms: false, sendPremiumSms: false, officialWarningsEnabled: false,
		morningEnabled: true, morningTime: '07:00', eveningEnabled: false, eveningTime: '18:00', endDate: null,
		dayWindowStartHour: 4, dayWindowEndHour: 19, corridors: [], region: '', idealRanges: {},
		activeMetricKeys: null, hourlyMetricKeys: null, metricAlertLevels: {}, telegramStyle: 'rich',
		alertMetricChannels: { thunder: TG }
	} as never);
	assert.deepStrictEqual(amcVon(neu), { thunder: TG }, 'Create');
});

test('AC-57 (grün, Mutations-Fixture): Versand- und Wertebereiche-Teil-PUT lassen den Bestand unverändert', () => {
	const p = preset({ gust: TG, snowfall_limit: MAIL });
	const versand = baueVersandNutzlast(p, hydrateVersandFieldsFromPreset(p)).body;
	const wb = baueWertebereichNutzlast(p, corridorSnapshotAus({ corridors: [], idealRanges: {}, metricAlertLevels: {} })).body;
	for (const [name, body] of [['Versand', versand], ['Wertebereiche', wb]] as const) {
		const amc = amcVon(body);
		assert.ok(amc === undefined || JSON.stringify(amc) === JSON.stringify(p.alert_metric_channels), `${name} verändert das Feld`);
		assert.deepStrictEqual(goMerge(p as never, body as never).alert_metric_channels, { gust: TG, snowfall_limit: MAIL }, name);
	}
});
