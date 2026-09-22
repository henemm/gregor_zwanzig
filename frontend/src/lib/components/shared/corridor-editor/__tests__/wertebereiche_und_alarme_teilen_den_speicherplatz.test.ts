// TDD RED — Issue #2276 Scheibe S3 (Epic #2345): nach S3 speichern ZWEI Reiter
// des Ortsvergleich-Hubs selbst (Alarme, Wertebereiche) — über DENSELBEN
// Speicher-Controller der Seite, dessen `_pendingFn` genau EIN Platz ist
// (saveStatusStore.svelte.ts `schedule()`). Und beide schreiben dasselbe Feld
// `metricAlertLevels` auf demselben Wizard-Zustand.
//
// Spec: docs/specs/modules/rework_2276_s3_wertebereiche.md
//   AC-3 (Metrik-Entfernen + Alarm-Änderung im selben Hub-Besuch: beide bleiben,
//         unabhängig von der Reihenfolge)
//   AC-4 (Reiterwechsel Wertebereiche → Alarme im Entprell-Fenster verliert nichts)
//
// Prüfstand: EIN Wizard-Zustand, EIN Controller, EINE Hub-Queue, ZWEI echte
// Orchestrierungen (Alarme aus S2, Wertebereiche neu) — genau die Lage im Hub.
//
// Zielschnittstelle, die dieser Test festschreibt (existiert noch NICHT → RED):
//   shared/corridor-editor/wertebereicheVergleichSpeicherung.ts
//     erstelleWertebereicheVergleichSpeicherung(...)            (s. wertebereiche_vergleich_speichert_einmal.test.ts)
//     SELBST_SPEICHERNDE_VERGLEICH_REITER: readonly string[]     — enthält 'alarme' UND 'idealwerte'
//     sichereSelbstSpeichererVorReiterwechsel(aktiverReiter, zielReiter, saveController?): Promise<void>
//       — der GENERISCHE, listenbasierte Flush-Guard (Trip-Muster TripTabs.svelte
//         handleValueChange): verlässt der Nutzer einen Reiter der Liste und steht
//         etwas aus, wird VOR dem Wechsel geflusht. Ersetzt die reiter-spezifische
//         `sichereAlarmeVorReiterwechsel` (S2) in CompareTabs.handleValueChange
//         (Spec Design Punkt 4 — keine zweite Einzelreiter-Funktion).
//
// Zum Wort „aus" in AC-3: seit #1371 setzt das Entfernen einer Zeile im
// vergleich-Zweig KEINE Stufe mehr auf 'off' (buildCompareCorridorSavePayload
// reicht metricAlertLevels unverändert durch); die Metrik ist „aus", weil sie
// aus corridors, active_metrics und ideal_ranges verschwindet. Genau das wird
// geprüft — plus dass die gleichzeitige Alarm-Stufe erhalten bleibt.
//
// Prüfort ≠ Wirkort: dass CompareTabs.handleValueChange den Guard wirklich
// abwartet, misst die E2E-Spec compare-wertebereiche-speichert-selbst.spec.ts.
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/corridor-editor/__tests__/wertebereiche_und_alarme_teilen_den_speicherplatz.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../../api.ts';
import { clearEtagRegistry } from '../../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../../__tests__/fakeTripServer.ts';
import type { ComparePreset } from '../../../../types.ts';
import { createPutQueue } from '../../../compare/compareHubWizardBridge.ts';
import { erstelleAlarmeVergleichSpeicherung } from '../../alarmeVergleichSpeicherung.ts';
import {
	erstelleWertebereicheVergleichSpeicherung,
	SELBST_SPEICHERNDE_VERGLEICH_REITER,
	sichereSelbstSpeichererVorReiterwechsel
} from '../wertebereicheVergleichSpeicherung.ts';
import {
	createController,
	hydrierterWs,
	korridor,
	makePreset,
	wertebereicheBedienung
} from './wertebereicheVergleichPruefstand.ts';

const PRESET_ID = 'cp-2276-s3-slot';

let server: FakeTripServer;

beforeEach(() => {
	clearEtagRegistry();
	// Server-Laufzeit > 0: „vor dem Wechsel" heißt, der PUT ist ABGESCHLOSSEN.
	server = createFakeTripServer({ latencyMs: 15 });
	server.install();
});

afterEach(() => server.restore());

const puts = () => server.calls.filter((c) => c.method === 'PUT');
const gespeichert = () => server.storedBody(PRESET_ID) as Record<string, unknown>;
const dc = (body: Record<string, unknown>) => body.display_config as Record<string, unknown>;

/** Der Hub: ein Wizard-Zustand, ein Controller, eine Queue, zwei Selbst-Speicherer. */
function hub() {
	let basis: ComparePreset = makePreset(PRESET_ID);
	const ws = hydrierterWs(basis);
	const ctl = createController(PRESET_ID);
	const queue = createPutQueue();
	const gemeinsam = {
		client: api,
		preset: () => basis,
		enqueueHubWrite: <T>(fn: () => Promise<T>) => queue.enqueue(fn),
		onCompareUpdate: (p: ComparePreset) => {
			basis = p;
		},
		saveController: ctl
	};
	const wertebereiche = erstelleWertebereicheVergleichSpeicherung({ ...gemeinsam, ws });
	const alarme = erstelleAlarmeVergleichSpeicherung({ ...gemeinsam, zustand: ws });
	const bedienung = wertebereicheBedienung(ws);
	return { ws, ctl, wertebereiche, alarme, bedienung };
}

/** Alarm-Reiter: Empfindlichkeit einer Metrik ändern (wie AlarmeTab.handleMetricLevelChange). */
function alarmStufe(ws: Record<string, unknown>, metric: string, stufe: string): void {
	ws.metricAlertLevels = { ...(ws.metricAlertLevels as Record<string, string>), [metric]: stufe };
}

describe('AC-4: Reiterwechsel Wertebereiche → Alarme im Entprell-Fenster verliert nichts', () => {
	test('Wertebereich ändern, sofort zu „alarme", dort Radar an → BEIDE Änderungen gespeichert, in der richtigen Reihenfolge', async () => {
		const { ws, ctl, wertebereiche, alarme, bedienung } = hub();

		bedienung.patch('wind_max_kmh', { max: 55 });
		wertebereiche.aenderungMelden();
		assert.equal(ctl.hasPending, true, 'Vorbedingung: Wertebereich-Änderung wartet im Entprell-Fenster');

		await sichereSelbstSpeichererVorReiterwechsel('idealwerte', 'alarme', ctl);

		assert.equal(puts().length, 1, 'die Wertebereich-Änderung muss VOR dem Reiterwechsel gesendet sein');
		assert.equal(puts()[0].status, 200, 'der PUT muss abgeschlossen sein, bevor der Wechsel weiterläuft');
		assert.deepEqual(korridor(puts()[0].body, 'wind_max_kmh')?.range, [0, 55]);

		ws.radarAlertEnabled = true;
		alarme.aenderungMelden();
		await ctl.flush();

		assert.equal(puts().length, 2, 'zwei Reiter, zwei Änderungen, zwei PUTs');
		assert.equal((puts()[1].body as Record<string, unknown>).radar_alert_enabled, true);
		const stand = gespeichert();
		assert.deepEqual(
			korridor(stand, 'wind_max_kmh')?.range,
			[0, 55],
			'die Wertebereich-Änderung darf vom Alarm-Speichern nicht überschrieben werden'
		);
		assert.equal(stand.radar_alert_enabled, true, 'die Alarm-Änderung muss gespeichert sein');
		assert.equal(ctl.state, 'idle');
	});

	test('Gegenprobe (warum der Guard nötig ist): OHNE Flush verdrängt der Alarm-Vorgang den Wertebereich-Vorgang vom einen Platz', async () => {
		const { ws, ctl, wertebereiche, alarme, bedienung } = hub();

		bedienung.patch('wind_max_kmh', { max: 55 });
		wertebereiche.aenderungMelden();
		ws.radarAlertEnabled = true;
		alarme.aenderungMelden();
		await ctl.flush();

		assert.equal(puts().length, 1, 'der zweite schedule() überschreibt den ersten — nur ein PUT');
		assert.deepEqual(
			korridor(gespeichert(), 'wind_max_kmh')?.range,
			[0, 40],
			'ohne Guard geht die Wertebereich-Änderung verloren — genau das verhindert der Flush beim Wechsel'
		);
	});

	test('die Liste der Selbst-Speicherer enthält „alarme" UND „idealwerte"', () => {
		assert.ok(SELBST_SPEICHERNDE_VERGLEICH_REITER.includes('idealwerte'), '„idealwerte" fehlt im Flush-Guard');
		assert.ok(SELBST_SPEICHERNDE_VERGLEICH_REITER.includes('alarme'), '„alarme" fehlt im Flush-Guard (S2-Verhalten)');
	});

	test('Richtung Alarme → Wertebereiche: der Guard flusht auch beim Verlassen von „alarme" (S2-Verhalten bleibt)', async () => {
		const { ws, ctl, alarme } = hub();

		ws.radarAlertEnabled = true;
		alarme.aenderungMelden();
		await sichereSelbstSpeichererVorReiterwechsel('alarme', 'idealwerte', ctl);

		assert.equal(puts().length, 1);
		assert.equal(puts()[0].status, 200);
		assert.equal(ctl.hasPending, false);
	});

	test('kein echter Wechsel (gleicher Reiter) → nichts wird vorzeitig gesendet', async () => {
		const { ctl, wertebereiche, bedienung } = hub();
		bedienung.patch('wind_max_kmh', { max: 55 });
		wertebereiche.aenderungMelden();

		await sichereSelbstSpeichererVorReiterwechsel('idealwerte', 'idealwerte', ctl);

		assert.equal(puts().length, 0, 'ohne echten Wechsel bleibt der Debounce unangetastet');
		assert.equal(ctl.hasPending, true);
		ctl.cancel();
	});

	test('ohne Controller (Anlege-Seite) → kein Fehler, kein PUT', async () => {
		await sichereSelbstSpeichererVorReiterwechsel('idealwerte', 'alarme', undefined);
		assert.equal(puts().length, 0);
	});
});

describe('AC-3: Metrik entfernen (Wertebereiche) + Alarm-Stufe ändern (Alarme) im selben Hub-Besuch', () => {
	test('Alarm ZUERST, Wertebereiche ZULETZT gespeichert → Metrik bleibt entfernt UND die neue Alarm-Stufe bleibt', async () => {
		const { ws, ctl, wertebereiche, alarme, bedienung } = hub();

		alarmStufe(ws, 'wind_max_kmh', 'sensibel');
		alarme.aenderungMelden();
		await sichereSelbstSpeichererVorReiterwechsel('alarme', 'idealwerte', ctl);
		assert.equal(puts().length, 1, 'Vorbedingung: Alarm-Stufe gespeichert');

		bedienung.remove('snow_depth_cm');
		wertebereiche.aenderungMelden();
		await ctl.flush();

		const stand = gespeichert();
		assert.equal(korridor(stand, 'snow_depth_cm'), undefined, 'die entfernte Metrik darf keinen Korridor mehr haben');
		assert.deepEqual(
			dc(stand).active_metrics,
			['wind_max_kmh', 'temp_max_c'],
			'die entfernte Metrik muss aus der Auswahl verschwunden sein'
		);
		assert.equal(
			(dc(stand).ideal_ranges as Record<string, unknown>).snow_depth_cm,
			undefined,
			'die entfernte Metrik darf keinen Idealbereich mehr haben'
		);
		assert.equal(
			(dc(stand).metric_alert_levels as Record<string, string>).wind_max_kmh,
			'sensibel',
			'der Wertebereiche-PUT hat die zuvor gespeicherte Alarm-Stufe mit einem veralteten Stand überschrieben'
		);
	});

	test('Wertebereiche ZUERST, Alarm ZULETZT gespeichert → Metrik bleibt entfernt UND die neue Alarm-Stufe bleibt', async () => {
		const { ws, ctl, wertebereiche, alarme, bedienung } = hub();

		bedienung.remove('snow_depth_cm');
		wertebereiche.aenderungMelden();
		await sichereSelbstSpeichererVorReiterwechsel('idealwerte', 'alarme', ctl);
		assert.equal(puts().length, 1, 'Vorbedingung: Entfernen gespeichert');

		alarmStufe(ws, 'wind_max_kmh', 'sensibel');
		alarme.aenderungMelden();
		await ctl.flush();

		const stand = gespeichert();
		assert.equal(korridor(stand, 'snow_depth_cm'), undefined, 'der Alarm-PUT hat die entfernte Metrik zurückgeholt');
		assert.deepEqual(dc(stand).active_metrics, ['wind_max_kmh', 'temp_max_c']);
		assert.equal((dc(stand).metric_alert_levels as Record<string, string>).wind_max_kmh, 'sensibel');
	});

	test('Alarm-Stufe steht noch im Zustand (nicht gespeichert), Wertebereiche speichert → die Stufe wird LIVE mitgenommen, nicht aus der Basis', async () => {
		const { ws, ctl, wertebereiche, bedienung } = hub();

		alarmStufe(ws, 'wind_max_kmh', 'entspannt');
		bedienung.remove('snow_depth_cm');
		wertebereiche.aenderungMelden();
		await ctl.flush();

		assert.equal(puts().length, 1);
		assert.equal(
			(dc(gespeichert()).metric_alert_levels as Record<string, string>).wind_max_kmh,
			'entspannt',
			'metric_alert_levels muss live aus dem Wizard-Zustand kommen, nicht aus einer eingefrorenen Preset-Kopie'
		);
	});
});
