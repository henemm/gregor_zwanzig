// TDD RED — #1895 S3b1, Speicherweg Ortsvergleich (AC-42, 47, 55, 56, 57). Feldname überall
// `alertMetricChannels` (AlarmSnapshot, Hydration, alarmePropsAus, CompareEditorEdits,
// NewComparePresetFields); Diff-Basis von baueAlarmNutzlast = preset.alert_metric_channels.
// AC-56: Rollback setzt seit dem Snapshot neue Einträge explizit auf null (Go-Merge je Schlüssel).
// AC-57 ist heute GRÜN — bewusst als Mutations-Fixture für die Nachbar-Schreiber.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import type { ComparePreset } from '../../../types.ts';
import { alarmSnapshotAus, baueAlarmNutzlast, erstelleAlarmeVergleichSpeicherung, flushPendingAlarmSave } from '../alarmeVergleichSpeicherung.ts';
import { hydrateAlarmFieldsFromPreset } from '../../compare/compareHubHydration.ts';
import { alarmePropsAus } from '../../compare/alarmePropsAus.ts';
import { buildComparePresetSavePayload, buildNewComparePresetPayload } from '../../compare/compareEditorSave.ts';
import { baueVersandNutzlast, hydrateVersandFieldsFromPreset } from '../versandVergleichSpeicherung.ts';
import { baueWertebereichNutzlast, corridorSnapshotAus } from '../wetter-tab/wertebereicheVergleichSpeicherung.ts';
import { goMerge } from './goMergeServerPruefstand.ts';
import { baueWetterMetrikenNutzlast, wetterMetrikenSnapshotAus } from '../weather-metrics-tab/weatherMetricsCompareSave.ts';
import { hydrierterWs } from '../weather-metrics-tab/__tests__/wetterMetrikenVergleichPruefstand.ts';

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

/** Echter Speicherweg des Hubs (erstelleAlarmeVergleichSpeicherung) über einem hydrierten
 *  Zustand; der Server ist goMerge. `scheitert`: 'nach' = 500 nach dem Merge (Server hat übernommen,
 *  Antwort verloren), 'vor' = 500 ohne Übernahme. Die Hub-Basis folgt nur über onCompareUpdate. */
function hubSpeicherweg(start: ComparePreset) {
	let basis = start;
	let server = start;
	let scheitert: false | 'nach' | 'vor' = false;
	const z = zustand(start);
	const bodies: unknown[] = [];
	const geplant: Array<(init?: RequestInit) => Promise<void>> = [];
	const sp = erstelleAlarmeVergleichSpeicherung({
		client: { put: async <T,>(_u: string, body: unknown) => {
			bodies.push(body);
			if (scheitert === 'vor') throw Object.assign(new Error('5xx'), { status: 500 });
			server = goMerge(server as never, body as never) as unknown as ComparePreset;
			if (scheitert === 'nach') throw Object.assign(new Error('5xx'), { status: 500 });
			return server as unknown as T;
		} } as never,
		zustand: z, preset: () => basis, enqueueHubWrite: (fn) => fn(),
		onCompareUpdate: (a) => { basis = a; },
		saveController: { schedule: (fn: never) => geplant.push(fn), cancel: () => {}, markPristine: () => {}, imWiederholen: false } as never
	});
	return {
		z, bodies, server: () => server,
		async aendern(amc: Record<string, unknown>, fehler: false | 'nach' | 'vor' = false, sonst: Record<string, unknown> = {}) {
			z.alertMetricChannels = amc as never;
			Object.assign(z, sonst);
			scheitert = fehler;
			sp.aenderungMelden();
			await geplant.at(-1)!().catch(() => {});
		}
	};
}

test('AC-56: Rollback nach gescheitertem PUT — der nächste PUT trägt gust explizit null, auch bei Hub-Basis ohne gust', async () => {
	const hub = hubSpeicherweg(preset({ thunder: ALT }));
	await hub.aendern({ thunder: TG, gust: TG }, 'nach'); // Server übernimmt, Antwort geht verloren
	assert.deepStrictEqual(hub.z.alertMetricChannels, { thunder: ALT, gust: null }, 'Rollback im Zustand');
	await hub.aendern(hub.z.alertMetricChannels as Record<string, unknown>); // Rückweg wird gespeichert
	assert.deepStrictEqual(amcVon(hub.bodies.at(-1)), { thunder: ALT, gust: null }, 'Wire-Body nach dem Rollback');
	assert.deepStrictEqual(hub.server().alert_metric_channels, { thunder: ALT, gust: null }, 'Server erbt wieder');
});

test('AC-56: Fehlschlag OHNE Übernahme — dieselbe Wahl erneut gewählt wird gesendet und landet auf dem Server', async () => {
	const hub = hubSpeicherweg(preset({ thunder: ALT }));
	await hub.aendern({ thunder: TG }, 'vor');
	assert.deepStrictEqual(hub.z.alertMetricChannels, { thunder: ALT }, 'Rollback im Zustand');
	await hub.aendern({ thunder: TG });
	assert.deepStrictEqual(amcVon(hub.bodies.at(-1)), { thunder: TG }, 'Wiederholung verpufft an einem Versuch als Basis');
	assert.deepStrictEqual(hub.server().alert_metric_channels, { thunder: TG });
});

test('AC-56 mehrere Fehlschläge in Folge: jeder gescheiterte Versuch zählt, bis ein Erfolg Server und UI angleicht', async () => {
	const hub = hubSpeicherweg(preset({ thunder: ALT }));
	await hub.aendern({ thunder: TG }, 'nach'); // Server übernimmt TG, Antwort verloren
	await hub.aendern({ thunder: ALT }, 'vor', { alertCooldownMinutes: 45 }); // scheitert ohne Übernahme
	await hub.aendern({ thunder: ALT }, false, { alertCooldownMinutes: 50 }); // Erfolg über ein Fremdfeld
	assert.deepStrictEqual(hub.server().alert_metric_channels, hub.z.alertMetricChannels, 'Server ≠ UI nach Erholung');
});

test('AC-56 Rollback schont neuere Wahl: Änderung während der PUT fliegt bleibt nach dem Fehlschlag erhalten', async () => {
	const p = preset({ thunder: ALT });
	const z = zustand(p);
	let scheitern!: (e: unknown) => void;
	const geplant: Array<() => Promise<void>> = [];
	const sp = erstelleAlarmeVergleichSpeicherung({
		client: { put: () => new Promise((_ok, nein) => { scheitern = nein; }) } as never,
		zustand: z, preset: () => p, enqueueHubWrite: (fn) => fn(), onCompareUpdate: () => {},
		saveController: { schedule: (fn: never) => geplant.push(fn), cancel: () => {}, markPristine: () => {}, imWiederholen: false } as never
	});
	z.alertMetricChannels = { thunder: TG };
	sp.aenderungMelden();
	const lauf = geplant[0]().catch(() => {});
	await Promise.resolve();
	z.alertMetricChannels = { thunder: MAIL }; // neuere Wahl, während der PUT fliegt
	scheitern(Object.assign(new Error('5xx'), { status: 500 }));
	await lauf;
	assert.deepStrictEqual(z.alertMetricChannels, { thunder: MAIL }, 'Rollback überschreibt die neuere Wahl');
});

test('AC-47 nach Erholung: ist ein Fehlschlag nachgeholt, sendet ein fremdes Alarmfeld die Kanalwahl nicht mehr mit', async () => {
	const hub = hubSpeicherweg(preset({ thunder: ALT }));
	await hub.aendern({ thunder: TG }, 'vor');
	await hub.aendern({ thunder: ALT }, false, { alertCooldownMinutes: 45 }); // Serverstand unbekannt ⇒ thunder geht mit
	assert.deepStrictEqual(amcVon(hub.bodies.at(-1)), { thunder: ALT });
	await hub.aendern({ thunder: ALT }, false, { alertCooldownMinutes: 50 }); // nach Erfolg ist der Versuch verworfen
	assert.ok(!('alert_metric_channels' in (hub.bodies.at(-1) as object)), 'veralteter Versuch schreibt nach Erfolg weiter mit');
});

test('AC-46 (Ablauf): speichern, Basis zieht nach, zurück zur alten Wahl ⇒ der Rückweg wird gesendet', async () => {
	const hub = hubSpeicherweg(preset({ thunder: MAIL }));
	await hub.aendern({ thunder: TG });
	assert.deepStrictEqual(amcVon(hub.bodies.at(-1)), { thunder: TG });
	await hub.aendern({ thunder: MAIL });
	assert.deepStrictEqual(amcVon(hub.bodies.at(-1)), { thunder: MAIL }, 'Basis nicht nachgezogen ⇒ Rückweg verpufft');
	await hub.aendern({ thunder: null });
	assert.deepStrictEqual(hub.server().alert_metric_channels, { thunder: null }, 'zurück auf „wie Abo"');
});

test('AC-55: Edit- und Create-Payload tragen alert_metric_channels', () => {
	const edit = buildComparePresetSavePayload(preset({}), {
		name: 'V', activityProfile: null, pickedIds: ['a', 'b', 'c'], region: '', idealRanges: {},
		alertMetricChannels: { thunder: TG }
	} as never);
	assert.deepStrictEqual(amcVon(edit.body), { thunder: TG }, 'Edit'); // buildComparePresetSavePayload liefert {url, body}
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

test('AC-57: Versand-, Wertebereiche- und Wetter-Metriken-Teil-PUT senden das Feld gar nicht und lassen den Bestand unverändert', () => {
	const p = preset({ gust: TG, snowfall_limit: MAIL });
	const versand = baueVersandNutzlast(p, hydrateVersandFieldsFromPreset(p)).body;
	const wb = baueWertebereichNutzlast(p, corridorSnapshotAus({ corridors: [], idealRanges: {}, metricAlertLevels: {} })).body;
	const wetter = baueWetterMetrikenNutzlast(p, wetterMetrikenSnapshotAus(hydrierterWs(p) as never)).body;
	for (const [name, body] of [['Versand', versand], ['Wertebereiche', wb], ['Wetter-Metriken', wetter]] as const) {
		// Auch eine unveränderte Vollmap wäre aus einer veralteten Hub-Basis ein Rückschreiber (Race).
		assert.ok(!('alert_metric_channels' in (body as object)), `${name} sendet alert_metric_channels mit`);
		assert.deepStrictEqual(goMerge(p as never, body as never).alert_metric_channels, { gust: TG, snowfall_limit: MAIL }, name);
	}
});
