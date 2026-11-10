// Fix-Loop 1 Issue #2794 S3a Teil-PR 3, Adversary-Finding F003 (AC-38, AC-30):
// Der Vergleichs-Speicherer des Reiters Wetter (`SPEICHERER.vergleich`,
// wetterTabSpeicherung.ts) — gemessen dort, wo er WIRKT: echter Controller
// (SaveStatus), echte Hub-Schreibschlange (`createPutQueue`), echtes `api` (ETag/If-Match)
// gegen den Go-Merge-Pruefserver (Merge wie `mergeConfigMap`, 412 bei veraltetem ETag).
// Kein Mock: die Optionen sind die, die WetterTab.svelte uebergibt.
//
// Zusicherungen:
//   (a) der PUT laeuft IN der Hub-Schreibschlange (wartet hinter einem laufenden Hub-Schreiber),
//   (b) die Serverantwort wird an die Seite uebernommen,
//   (c) bei 412 laedt der Reiter das Abo neu (GET), reicht es an `neuGeladen` und die Seite,
//       und wirft den Fehler weiter, damit der Controller „Nochmal speichern" (conflict) zeigt —
//       die fremde Aenderung bleibt auf dem Server stehen,
//   (d) der Rumpf traegt nur die Eigenfelder; `display_config` genau `ampel` + `active_metrics`.
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/f003_vergleich_speicherer_hub_schlange.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../../api.ts';
import { clearEtagRegistry } from '../../../../etagRegistry.ts';
import { createPutQueue } from '../../../compare/compareHubPersistenz.ts';
import { createController } from '../../__tests__/versandVergleichPruefstand.ts';
import { createGoMergeServer, vollerVergleich, type GoMergeServer } from '../../__tests__/goMergeServerPruefstand.ts';
import { live } from './wetterTabDaten.ts';
import { vorlagenAusTemplates } from '../ampelModell.ts';
import { mitAlarmAb, standAusAbo, type AboSicht, type WetterStand } from '../wetterZustand.ts';
import { SPEICHERER } from '../wetterTabSpeicherung.ts';

const ID = 'cp-2794-f003';
const PFAD = `/api/compare/presets/${ID}`;
const ERLAUBT_TOP = ['display_config', 'official_alerts_enabled', 'official_warnings', 'radar_alert_enabled', 'day_window_start_hour', 'day_window_end_hour'];

/** Voller Vergleich (jedes Feld unterscheidbar belegt), Auswahl im Speicherformat des Reiters. */
function abo(): Record<string, unknown> {
	const v = vollerVergleich(ID);
	const dc = v.display_config as Record<string, unknown>;
	dc.active_metrics = [
		{ metric_id: 'temperature', aggregation: 'max' },
		{ metric_id: 'wind', aggregation: 'max' },
		{ metric_id: 'gust', aggregation: 'max' }
	];
	dc.ampel = { template: 'allgemein' };
	return v;
}

let server: GoMergeServer;
const vorlagen = vorlagenAusTemplates(live().templates);

beforeEach(async () => {
	clearEtagRegistry();
	server = createGoMergeServer({ [ID]: abo() });
	server.install();
	await api.get(PFAD); // ETag bekannt, wie nach dem Laden der Seite
});
afterEach(() => server.restore());

const puts = () => server.mitschnitt.filter((e) => e.method === 'PUT');
const tick = () => new Promise((r) => setTimeout(r, 10));

/** Reiter Wetter im Vergleichs-Hub: dieselben Optionen wie WetterTab.svelte. */
function reiter() {
	let seite = abo() as AboSicht;
	let stand: WetterStand = standAusAbo('vergleich', seite, vorlagen);
	const ctl = createController(ID);
	const queue = createPutQueue();
	const uebernommen: unknown[] = [];
	const neuGeladen: AboSicht[] = [];
	const sp = SPEICHERER.vergleich({
		client: api,
		stand: () => stand,
		vorlagen: () => vorlagen,
		abo: () => seite,
		saveController: ctl,
		enqueueHubWrite: (fn) => queue.enqueue(fn),
		uebernehmen: (a) => {
			uebernommen.push(a);
			seite = a as AboSicht;
		},
		neuGeladen: (a) => neuGeladen.push(a)
	});
	return {
		ctl,
		queue,
		uebernommen,
		neuGeladen,
		aendern(neu: (s: WetterStand) => WetterStand) {
			stand = neu(stand);
			sp.melden();
		}
	};
}

const boeenRot = (s: WetterStand) => mitAlarmAb(s, 'gust', 'red');

describe('F003/AC-38: Vergleichs-Speicherer des Reiters Wetter', () => {
	test('(a) der PUT wartet in der Hub-Schreibschlange hinter einem laufenden Hub-Schreiber', async () => {
		const r = reiter();
		let freigeben!: () => void;
		const blocker = r.queue.enqueue(() => new Promise<void>((res) => (freigeben = res)));
		r.aendern(boeenRot);
		const fertig = r.ctl.flush();
		await tick();
		assert.equal(puts().length, 0, 'der Reiter schreibt am Hub-Schreiber vorbei (parallel statt in der Schlange)');
		freigeben();
		await blocker;
		await fertig;
		assert.equal(puts().length, 1, 'nach Freigabe genau EIN PUT');
		assert.equal(puts()[0].status, 200);
	});

	test('(b) die Serverantwort (gemergter Gesamtdatensatz) wird an die Seite uebernommen', async () => {
		const r = reiter();
		r.aendern(boeenRot);
		await r.ctl.flush();
		assert.equal(r.uebernommen.length, 1, 'Serverantwort nicht uebernommen');
		assert.deepEqual(r.uebernommen[0], server.stand(ID));
		assert.equal(r.ctl.state, 'idle');
	});

	test('(c) 412: Abo neu laden, an Reiter und Seite reichen, Fehler weiterwerfen ⇒ „Nochmal speichern"; fremde Aenderung bleibt', async () => {
		const r = reiter();
		const fremd = { template: 'wandern', metrics: { wind: { alarm_ab: 'red' } } };
		server.fremdSchreiben(ID, { name: 'Fremd', display_config: { ampel: fremd } });
		r.aendern(boeenRot);
		await r.ctl.flush();

		assert.equal(puts().length, 1);
		assert.equal(puts()[0].status, 412, 'Messaufbau: der veraltete Stand muss abgelehnt werden');
		const gets = server.mitschnitt.filter((e) => e.method === 'GET');
		assert.equal(gets.length, 2, 'nach dem 412 laedt der Reiter das Abo nicht neu');
		assert.equal(r.neuGeladen.length, 1, 'der Reiter bekommt das neu geladene Abo nicht');
		assert.deepEqual((r.neuGeladen[0].display_config as Record<string, unknown>).ampel, fremd);
		assert.deepEqual(r.uebernommen.at(-1), server.stand(ID), 'die Seite bekommt das neu geladene Abo nicht');
		assert.equal(r.ctl.state, 'conflict', 'der 412 wird verschluckt — der Controller zeigt keinen Konflikt');
		assert.deepEqual((server.stand(ID).display_config as Record<string, unknown>).ampel, fremd, 'fremde Aenderung still ueberschrieben');
	});

	// Fix-Loop 2, F-A4 (D8): der Speicherer ist unter dem Besitzer-Schluessel konfliktfaehig —
	// zwei gescheiterte Vorgaenge desselben Reiters sind EIN Eintrag, „Nochmal speichern" sendet
	// genau einen PUT (den neuesten Stand), nicht zwei.
	test('(e) zwei 412 hintereinander ⇒ „Nochmal speichern" sendet genau EINEN PUT mit dem neuesten Stand', async () => {
		const r = reiter();
		server.fremdSchreiben(ID, { name: 'Fremd 1' });
		r.aendern(boeenRot);
		await r.ctl.flush();
		server.fremdSchreiben(ID, { name: 'Fremd 2' });
		r.aendern((s) => mitAlarmAb(s, 'wind', 'red'));
		await r.ctl.flush();
		assert.deepEqual(puts().map((p) => p.status), [412, 412], 'Messaufbau: beide Vorgaenge muessen am Konflikt scheitern');
		assert.equal(r.ctl.state, 'conflict');

		await r.ctl.retryConflict();
		const retry = puts().slice(2);
		assert.equal(retry.length, 1, `„Nochmal speichern" sendet ${retry.length} PUTs statt einem (kein Besitzer-Schluessel?)`);
		assert.equal(retry[0].status, 200);
		const ampel = ((retry[0].anfrage as Record<string, unknown>).display_config as Record<string, unknown>).ampel as { metrics: Record<string, { alarm_ab?: string }> };
		assert.equal(ampel.metrics.wind?.alarm_ab, 'red', 'der Retry sendet nicht den neuesten Stand');
		assert.equal(r.ctl.state, 'idle');
	});

	test('(d) Rumpf: nur Eigenfelder, display_config genau ampel + active_metrics', async () => {
		const r = reiter();
		r.aendern(boeenRot);
		await r.ctl.flush();
		const rumpf = puts()[0].anfrage as Record<string, unknown>;
		for (const k of Object.keys(rumpf)) assert.ok(ERLAUBT_TOP.includes(k), `Fremdfeld ${k} im Rumpf`);
		assert.deepEqual(Object.keys(rumpf.display_config as object).sort(), ['active_metrics', 'ampel']);
		assert.equal(((rumpf.display_config as Record<string, unknown>).ampel as { metrics: Record<string, { alarm_ab?: string }> }).metrics.gust.alarm_ab, 'red');
		const stand = server.stand(ID).display_config as Record<string, unknown>;
		assert.equal(stand.telegram_style, 'rich', 'Fremdschluessel der display_config verloren');
		assert.deepEqual(stand.metric_alert_levels, { wind_max_kmh: 'standard', snow_depth_cm: 'sensibel' });
	});
});
