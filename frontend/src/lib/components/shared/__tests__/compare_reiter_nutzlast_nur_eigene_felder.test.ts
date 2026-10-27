// TDD RED — Issue #2375 (löst #2381 mit), Epic #2345: jeder selbst
// speichernde Ortsvergleich-Reiter sendet NUR seine Eigenfelder laut
// Feld-Besitz-Tabelle — kein Voll-Spread der (womöglich veralteten) Basis.
//
// Spec: docs/specs/bugfix/compare_konfliktschutz_teilfelder.md
//   Test 1 / AC-7  — exakter Schlüsselsatz je Reiter (Top-Level + display_config)
//   Test 2 / AC-8  — Leerauswahl/Löschen erreicht den Server: `[]`, `end_date: ""`,
//                    `ideal_ranges: {}` stehen im Body (nicht weggelassen)
//   Test 5 / AC-11 — WÄCHTER: geteilte Schlüssel kommen aus dem Live-Zustand
//   Test 7 / AC-10 — WÄCHTER: die Server-Antwort wird über onCompareUpdate Basis
//
// Gemessen wird der TATSÄCHLICH gesendete PUT-Rumpf: echter Speicherweg
// (`erstelle…Speicherung` + echter Controller + Hub-Queue + echtes `api`)
// gegen einen Ersatz-Server, der wie der Go-Handler mergt und die
// ANFRAGE-Rümpfe mitschneidet (goMergeServerPruefstand.ts).
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/shared/__tests__/compare_reiter_nutzlast_nur_eigene_felder.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import type { ComparePreset } from '../../../types.ts';
import {
	createGoMergeServer,
	EIGENFELDER,
	schluessel,
	vollerVergleich,
	type GoMergeServer
} from './goMergeServerPruefstand.ts';
import { REITER, reiterAufbau, type Reiter } from './compareReiterAufbauPruefstand.ts';

const ID = 'cp-2375-nutzlast';
const PFAD = `/api/compare/presets/${ID}`;

let server: GoMergeServer;

beforeEach(() => {
	clearEtagRegistry();
	server = createGoMergeServer({ [ID]: vollerVergleich(ID) });
	server.install();
});

afterEach(() => server.restore());

function start(): ComparePreset {
	return vollerVergleich(ID) as unknown as ComparePreset;
}

/** Ein Speichervorgang des Reiters; liefert den EINEN gesendeten PUT-Rumpf. */
async function speichereEinmal(reiter: Reiter, aktion: 'aendern' | 'leeren') {
	await api.get(PFAD);
	const a = reiterAufbau(reiter, start());
	// Vorbedingung: kein Eigenfeld des Snapshots ist `undefined` — sonst fiele
	// ein Schlüssel nur wegen einer lückenhaften Hydration aus dem Body.
	for (const [k, v] of Object.entries(a.zustand)) {
		assert.notEqual(v, undefined, `Messaufbau: Zustandsfeld ${k} ist nach der Hydration undefined`);
	}
	a[aktion]();
	a.speicherung.aenderungMelden();
	await a.ctl.flush();
	const ruempfe = server.putRuempfe();
	assert.equal(ruempfe.length, 1, `Messaufbau: genau EIN PUT erwartet, gesehen ${ruempfe.length}`);
	assert.equal(server.mitschnitt.at(-1)?.status, 200, 'Messaufbau: der PUT muss durchgehen');
	return { body: ruempfe[0], aufbau: a };
}

function pruefeSchluesselsatz(reiter: Reiter, body: Record<string, unknown>): void {
	const soll = EIGENFELDER[reiter];
	assert.deepEqual(
		schluessel(body),
		[...soll.top].sort(),
		`${reiter}: der PUT-Rumpf muss GENAU die Eigenfelder tragen (Feld-Besitz-Tabelle) — ` +
			`Fremdfelder überschreiben die Änderung eines anderen Tabs. Gesendet: ${JSON.stringify(schluessel(body))}`
	);
	if (soll.display === null) {
		assert.equal(
			body.display_config,
			undefined,
			`${reiter}: besitzt keinen display_config-Schlüssel und darf display_config nicht senden`
		);
	} else {
		assert.deepEqual(
			schluessel(body.display_config),
			[...soll.display].sort(),
			`${reiter}: display_config muss GENAU die eigenen Schlüssel tragen. ` +
				`Gesendet: ${JSON.stringify(schluessel(body.display_config))}`
		);
	}
}

describe('Test 1 / AC-7: jeder Reiter sendet ausschließlich seine Eigenfelder', () => {
	for (const reiter of REITER) {
		test(`${reiter}: PUT-Rumpf = exakter Eigenfeld-Satz (kein name/location_ids/profil/schedule/id)`, async () => {
			const { body } = await speichereEinmal(reiter, 'aendern');
			pruefeSchluesselsatz(reiter, body);
			for (const fremd of ['id', 'name', 'location_ids', 'profil', 'schedule', 'previous_schedule', 'empfaenger']) {
				assert.ok(!(fremd in body), `${reiter}: Fremdfeld \`${fremd}\` im PUT-Rumpf`);
			}
		});
	}

	test('alarme: weder official_alerts_enabled noch send_* ; official_warnings nur { enabled }', async () => {
		const { body } = await speichereEinmal('alarme', 'aendern');
		assert.ok(!('official_alerts_enabled' in body), 'Alarme besitzt official_alerts_enabled nicht (gehört Wetter-Metriken)');
		for (const k of ['send_telegram', 'send_sms', 'send_premium_sms']) {
			assert.ok(!(k in body), `Alarme darf ${k} nicht senden`);
		}
		assert.deepEqual(
			schluessel(body.official_warnings),
			['enabled'],
			'official_warnings darf nie `sources` tragen'
		);
	});

	test('versand: keine alert_cooldown_minutes/alert_quiet_*/alert_channels', async () => {
		const { body } = await speichereEinmal('versand', 'aendern');
		for (const k of ['alert_cooldown_minutes', 'alert_quiet_from', 'alert_quiet_to', 'alert_channels']) {
			assert.ok(!(k in body), `Versand darf ${k} nicht senden (Besitzer: Alarme)`);
		}
	});
});

describe('Test 2 / AC-8: Leerauswahl und Löschen stehen explizit im Rumpf', () => {
	test('wetterMetriken: alle Metriken abgewählt, Stundenverlauf/Ausblick leer ⇒ je [] im Rumpf, sonst nur Eigenfelder', async () => {
		const { body } = await speichereEinmal('wetterMetriken', 'leeren');
		const dc = body.display_config as Record<string, unknown>;
		assert.deepEqual(dc.active_metrics, [], 'Leerauswahl Metriken muss als [] gesendet werden');
		assert.deepEqual(dc.hourly_metrics, [], 'Leerauswahl Stundenverlauf muss als [] gesendet werden');
		assert.deepEqual(dc.outlook_metrics, [], 'Leerauswahl Ausblick muss als [] gesendet werden');
		pruefeSchluesselsatz('wetterMetriken', body);
	});

	test('wertebereiche: Korridor-Leerung ⇒ corridors: [] UND ideal_ranges: {} im Rumpf', async () => {
		const { body } = await speichereEinmal('wertebereiche', 'leeren');
		assert.deepEqual(body.corridors, [], 'Korridor-Leerung muss als [] gesendet werden');
		const dc = body.display_config as Record<string, unknown>;
		assert.ok('ideal_ranges' in dc, 'ideal_ranges muss auch leer gesendet werden — weggelassen bliebe der alte Wert');
		assert.deepEqual(dc.ideal_ranges, {}, 'geleerte Ideal-Ranges müssen als {} gesendet werden, nicht der Bestand');
		pruefeSchluesselsatz('wertebereiche', body);
	});

	test('versand: „Bis auf Weiteres" ⇒ end_date: "" (nicht null, nicht weggelassen)', async () => {
		const { body } = await speichereEinmal('versand', 'leeren');
		assert.ok('end_date' in body, 'end_date muss gesendet werden');
		assert.equal(body.end_date, '', 'Lösch-Sentinel ist "" (Go, compare_preset.go:338-340), nicht null');
		pruefeSchluesselsatz('versand', body);
	});

	test('wertebereiche: Leerung erreicht den Server — nach dem Merge sind Korridore und Ideal-Ranges leer', async () => {
		await speichereEinmal('wertebereiche', 'leeren');
		const stand = server.stand(ID);
		assert.deepEqual(stand.corridors, []);
		assert.deepEqual(
			(stand.display_config as Record<string, unknown>).ideal_ranges,
			{},
			'nach dem Go-Merge müssen die Ideal-Ranges leer sein'
		);
	});
});

describe('Test 5 / AC-11 (Wächter): geteilte Schlüssel kommen aus dem Live-Zustand', () => {
	test('Wächter: metric_alert_levels — Alarme und Wertebereiche senden den Live-Wert, nicht den der Basis', async () => {
		await api.get(PFAD);
		const alarme = reiterAufbau('alarme', start());
		const werte = reiterAufbau('wertebereiche', start());
		// Live-Zustand geändert (Alarme-Bedienung), Basis bleibt beim Ausgangswert
		const live = { wind_max_kmh: 'sensibel', snow_depth_cm: 'standard' };
		alarme.zustand.metricAlertLevels = { ...live };
		werte.zustand.metricAlertLevels = { ...live };
		alarme.speicherung.aenderungMelden();
		await alarme.ctl.flush();
		// Wertebereiche speichert danach eine eigene Änderung
		werte.aendern();
		werte.speicherung.aenderungMelden();
		await werte.ctl.flush();
		const [a, w] = server.putRuempfe();
		assert.deepEqual((a.display_config as Record<string, unknown>).metric_alert_levels, live);
		assert.deepEqual((w.display_config as Record<string, unknown>).metric_alert_levels, live);
		assert.deepEqual(
			(server.stand(ID).display_config as Record<string, unknown>).metric_alert_levels,
			live,
			'der zuletzt bediente Live-Wert steht auf dem Server'
		);
	});

	test('Wächter: active_metrics — Wertebereiche sendet die im Wetter-Reiter gerade geänderte Auswahl', async () => {
		await api.get(PFAD);
		const werte = reiterAufbau('wertebereiche', start());
		const live = ['wind_max_kmh', 'snow_depth_cm', 'temp_max_c', 'gust_max_kmh'];
		werte.zustand.activeMetricKeys = [...live];
		werte.aendern();
		werte.speicherung.aenderungMelden();
		await werte.ctl.flush();
		const [w] = server.putRuempfe();
		const gesendet = JSON.stringify((w.display_config as Record<string, unknown>).active_metrics);
		assert.ok(gesendet.includes('gust_max_kmh'), `active_metrics muss den Live-Wert tragen, gesendet: ${gesendet}`);
	});
});

describe('Test 7 / AC-10 (Wächter): die gemergte Server-Antwort wird Basis', () => {
	for (const reiter of REITER) {
		test(`Wächter: ${reiter} — nach Erfolg ist die Basis gleich dem Server-Stand`, async () => {
			const { aufbau } = await speichereEinmal(reiter, 'aendern');
			assert.deepEqual(
				aufbau.basis(),
				server.stand(ID),
				'onCompareUpdate muss den gemergten Gesamtdatensatz als Basis übernehmen'
			);
		});
	}
});
