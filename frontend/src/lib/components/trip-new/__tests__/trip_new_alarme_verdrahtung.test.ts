// Verdrahtung des Alarme-Reiters auf der Anlege-Seite `/trips/new` —
// gemessen an der Stelle, an der sie WIRKT: in `TripNewEditor.svelte`.
//
// Spec: docs/specs/modules/fix_2277_s1_alarme_tab_route.md (AC-2, AC-3, AC-5)
// Anlass: Adversary-Findings F001–F003 (#2277 S1, Fix-Loop 1). Reducer und
// Payload-Builder sind in `tripNewLogic.test.ts` bewacht, der Guard im
// AlarmeTab in `alarme_tab_create_mode_guard.test.ts` — aber keiner dieser
// Tests merkt, wenn der Editor `createMode` nicht setzt, `alarm` nicht an den
// Builder reicht oder einen Rueckruf falsch verdrahtet.
//
// Messweg: der Pruefstand `svelteInstanzPruefstand.ts` wertet das ECHTE
// Instanz-Skript des Editors aus (Importe, Funktionen, Deklarationen) und liest
// die Attribute der ECHTEN `<AlarmeTab>`-Einbettungen aus dem AST. Gesaet werden
// nur Bindungen, die der Pruefstand strukturell nicht herstellt: `untrack` (aus
// `svelte`, kein `$lib`-Import), `stateOverride` (aus `$props()`-Destrukturierung)
// und ein Spion fuer `api.post`.
//
// F002 bewusst BEHAVIORAL statt per AST-Suche nach der Property `alarm` im
// State-Literal: der Spion faengt den tatsaechlich gesendeten POST-Koerper.
// Damit faellt jede Form der Unterbrechung auf (Property weg, falscher
// Bezeichner, Builder-Aufruf mit anderem Objekt, ueberschriebener Wert) — eine
// AST-Suche saehe nur die eine Schreibweise, die sie kennt.

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
	umgebungFuer,
	findeKomponenten,
	attributAusdruck,
	attributNamen,
	type Knoten
} from '../../shared/__tests__/svelteInstanzPruefstand.ts';

const EDITOR = join(dirname(fileURLToPath(import.meta.url)), '..', 'TripNewEditor.svelte');

async function editor() {
	const gesendet: Array<{ url: string; payload: Knoten }> = [];
	const { ast, quelle, u } = await umgebungFuer(EDITOR, {
		stateOverride: undefined,
		untrack: (fn: () => unknown) => fn(),
		api: {
			post: async (url: string, payload: Knoten) => {
				gesendet.push({ url, payload });
				return { id: 'neu-1' };
			}
		}
	});
	assert.ok(u.alarm && typeof u.alarm === 'object', 'Messaufbau kaputt: `alarm` nicht ausgewertet.');
	return { ast, quelle, u, gesendet };
}

describe('F001/AC-2/AC-3: jede AlarmeTab-Einbettung im Anlege-Editor', () => {
	test('traegt createMode={true} und keine Selbst-Speicher-Props', async () => {
		const { ast, quelle } = await editor();
		const treffer = findeKomponenten(ast, 'AlarmeTab');
		assert.strictEqual(treffer.length, 2, 'Erwartet: genau 2 Einbettungen (Desktop + Mobil).');
		for (const [i, e] of treffer.entries()) {
			assert.strictEqual(
				attributAusdruck(e, quelle, 'createMode'),
				'true',
				`F001: Einbettung ${i + 1} setzt createMode nicht auf true — der Selbst-Speicher-` +
					'Effekt des AlarmeTab wuerde vor „Speichern" auf /api/trips/__new__ schreiben.'
			);
			const namen = attributNamen(e);
			for (const verboten of [
				'sendTelegram',
				'sendSms',
				'sendPremiumSms',
				'channelThresholds',
				'metricAlertLevels'
			]) {
				assert.ok(!namen.includes(verboten), `AC-3: Einbettung ${i + 1} setzt \`${verboten}\`.`);
			}
		}
	});

	test('verbindet jeden Rueckruf mit dem passenden Editor-Handler', async () => {
		const { ast, quelle } = await editor();
		const erwartet: Record<string, string> = {
			onChannelToggle: 'handleAlarmChannelToggle',
			onThresholdChange: 'handleAlarmThresholdChange',
			onMetricLevelChange: 'handleAlarmMetricLevelChange',
			onOfficialWarningsChange: 'handleAlarmOfficialWarningsChange',
			onCooldownChange: 'handleAlarmCooldownChange',
			onQuietHoursChange: 'handleAlarmQuietHoursChange',
			officialWarningsEnabled: 'alarm.officialWarningsEnabled',
			cooldownMinutes: 'alarm.cooldownMinutes',
			quietFrom: 'alarm.quietFrom',
			quietTo: 'alarm.quietTo'
		};
		const treffer = findeKomponenten(ast, 'AlarmeTab');
		assert.strictEqual(treffer.length, 2);
		for (const [i, e] of treffer.entries()) {
			for (const [prop, ausdruck] of Object.entries(erwartet)) {
				assert.strictEqual(
					attributAusdruck(e, quelle, prop),
					ausdruck,
					`F003: Einbettung ${i + 1}: \`${prop}\` ist nicht mit \`${ausdruck}\` verbunden.`
				);
			}
		}
	});
});

describe('F003/AC-5: die sechs Alarm-Handler schreiben in den Anlege-Zustand', () => {
	test('Kanal umschalten: nur der genannte Kanal kippt', async () => {
		const { u } = await editor();
		const vorher = { ...u.alarm.channels };
		u.handleAlarmChannelToggle('premium_sms');
		assert.deepStrictEqual(u.alarm.channels, { ...vorher, premium_sms: !vorher.premium_sms });
	});

	test('Kanal-Schwelle: nur die genannte Schwelle wechselt', async () => {
		const { u } = await editor();
		const vorher = { ...u.alarm.channelThresholds };
		u.handleAlarmThresholdChange('sms', 'HIGH');
		assert.deepStrictEqual(u.alarm.channelThresholds, { ...vorher, sms: 'HIGH' });
	});

	test('Metrik-Stufe: landet unter der Metrik', async () => {
		const { u } = await editor();
		u.handleAlarmMetricLevelChange('wind_gust', 'sensibel');
		assert.deepStrictEqual(u.alarm.metricLevels, { wind_gust: 'sensibel' });
	});

	test('Amtliche Warnungen: an und wieder aus', async () => {
		const { u } = await editor();
		u.handleAlarmOfficialWarningsChange(true);
		assert.strictEqual(u.alarm.officialWarningsEnabled, true);
		u.handleAlarmOfficialWarningsChange(false);
		assert.strictEqual(u.alarm.officialWarningsEnabled, false);
	});

	test('Cooldown: Minutenwert wird uebernommen', async () => {
		const { u } = await editor();
		u.handleAlarmCooldownChange(90);
		assert.strictEqual(u.alarm.cooldownMinutes, 90);
	});

	test('Stille Stunden: von/bis werden nicht vertauscht', async () => {
		const { u } = await editor();
		u.handleAlarmQuietHoursChange('22:00', '07:00');
		assert.strictEqual(u.alarm.quietFrom, '22:00');
		assert.strictEqual(u.alarm.quietTo, '07:00');
	});
});

describe('F002: buildAndSave schickt den geaenderten Alarm-Zustand mit', () => {
	test('POST /api/trips traegt die Eingaben aus dem Alarme-Reiter', async () => {
		const { u, gesendet } = await editor();
		u.handleAlarmOfficialWarningsChange(true);
		u.handleAlarmChannelToggle('email');
		u.handleAlarmThresholdChange('sms', 'HIGH');
		u.handleAlarmCooldownChange(90);
		u.handleAlarmQuietHoursChange('22:00', '07:00');
		u.handleAlarmMetricLevelChange('wind_gust', 'sensibel');
		// `ready` haengt am GPX-Upload (etDone) — fuer die Messung des Speicherwegs
		// ohne Belang, darum direkt freigeschaltet.
		u.ready = true;

		const id = await u.buildAndSave();

		assert.strictEqual(id, 'neu-1', `buildAndSave scheiterte: ${u.saveError}`);
		assert.strictEqual(gesendet.length, 1);
		assert.strictEqual(gesendet[0].url, '/api/trips');
		const p = gesendet[0].payload;
		assert.deepStrictEqual(p.official_warnings, { enabled: true });
		assert.strictEqual(p.alert_channels.email, true);
		assert.strictEqual(p.alert_channel_thresholds.sms, 'HIGH');
		assert.strictEqual(p.alert_cooldown_minutes, 90);
		assert.strictEqual(p.alert_quiet_from, '22:00');
		assert.strictEqual(p.alert_quiet_to, '07:00');
		assert.deepStrictEqual(p.display_config.metric_alert_levels, { wind_gust: 'sensibel' });
	});
});
