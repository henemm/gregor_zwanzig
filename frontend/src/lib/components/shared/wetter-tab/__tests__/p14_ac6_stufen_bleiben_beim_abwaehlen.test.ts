// #3047 Runde 7, Paket p14 — Ersatz fuer #1544/#1545 AC-6 Ebene 2/3 (Spec
// docs/specs/modules/fix_1544_1545_trip_alarm_zeilen_ableitung.md, AC-6 „Kein Datenverlust“).
//
// Ebene 2/3 massen den toten Container AlarmeScheduleTab.svelte (mit p11 entfernt). Der
// LIVE-Weg, auf dem ein Nutzer heute eine Groesse abwaehlt und speichert, ist der Reiter
// Wetter (Speicherer `SPEICHERER.route` / `SPEICHERER.vergleich`). Zusicherung dort, wo sie
// wirkt: Groesse mit gesetzter Stufe abwaehlen -> speichern -> neu oeffnen -> wieder
// aufnehmen -> die Stufe ist dieselbe. „Stufe“ heisst heute zweierlei und beides wird
// geprueft: die Ampel-Abweichung der Zeile (`ampel.metrics.<id>`: „Alarm ab“ und Grenzen,
// ADR-0106) und der Altbestand `display_config.metric_alert_levels` (#2793 S2b: nur lesbar,
// darf nie still verschwinden).
//
// Server-Seite: der Trip-Pfad `/weather-config` mergt `display_config` einstufig
// (`mergeConfigMap`, internal/handler/config_merge.go) — hier als `{...dc, ...rumpf}`
// nachgebildet; dass der echte Go-Handler das fuer GENAU diese Nutzlast-Form mit zwei Nutzern
// tut, belegt internal/handler/p14_ac6_stufen_bleiben_test.go. Der Vergleich laeuft ueber den
// gemeinsamen Go-Merge-Pruefstand (goMergeServerPruefstand.ts).
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/p14_ac6_stufen_bleiben_beim_abwaehlen.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../../api.ts';
import { clearEtagRegistry } from '../../../../etagRegistry.ts';
import { createPutQueue } from '../../../compare/compareHubPersistenz.ts';
import { createController } from '../../__tests__/versandVergleichPruefstand.ts';
import { createGoMergeServer, vollerVergleich, type GoMergeServer } from '../../__tests__/goMergeServerPruefstand.ts';
import { aufgeloestVon, live } from './wetterTabDaten.ts';
import { eigenschaftenAusKatalog, vorlagenAusTemplates } from '../ampelModell.ts';
import { mitMetrik, ohneMetrik, standAusAbo, type AboSicht, type WetterStand } from '../wetterZustand.ts';
import { SPEICHERER } from '../wetterTabSpeicherung.ts';

type Rec = Record<string, unknown>;
const vorlagen = vorlagenAusTemplates(live().templates);
const EIG = eigenschaftenAusKatalog(live().metrics);
const klon = <T>(x: T): T => JSON.parse(JSON.stringify(x));

/** Boeen mit eigener Zeile: Grenzen und „Alarm ab“ weichen von der Vorlage ab. */
const GUST_ZEILE = { upper: { yellow: 45, orange: 65, red: 85 }, alarm_ab: 'red' };
const STUFEN = { wind_gust: 'sensibel', temperature_max: 'standard', wind: 'robust' };

function gustZeile(stand: WetterStand): Rec {
	return (stand.ampel.metrics?.gust ?? {}) as Rec;
}

function pruefeZeileWieVorher(stand: WetterStand, wo: string): void {
	assert.ok(stand.auswahl.includes('gust'), `${wo}: Boeen nicht wieder in der Auswahl`);
	const z = gustZeile(stand);
	assert.equal(z.alarm_ab, 'red', `${wo}: „Alarm ab“ der wieder aufgenommenen Boeen verloren (AC-6). Zeile: ${JSON.stringify(z)}`);
	assert.deepEqual(
		{ yellow: (z.upper as Rec)?.yellow, orange: (z.upper as Rec)?.orange, red: (z.upper as Rec)?.red },
		GUST_ZEILE.upper,
		`${wo}: Grenzen der wieder aufgenommenen Boeen verloren (AC-6)`
	);
}

// ── Trip ──────────────────────────────────────────────────────────────────────────────────

const TRIP_ID = 'trip-p14-ac6';
function tripAbo(): AboSicht {
	return {
		id: TRIP_ID,
		profil: 'wandern',
		report_config: { enabled: true, day_window_start_hour: 6, day_window_end_hour: 18 },
		display_config: {
			preset_name: 'wandern',
			metrics: [
				{ metric_id: 'wind', enabled: true },
				{ metric_id: 'gust', enabled: true },
				{ metric_id: 'temperature', enabled: true }
			],
			ampel: { template: 'wandern', metrics: { gust: klon(GUST_ZEILE) } },
			metric_alert_levels: klon(STUFEN)
		}
	};
}

/** Trip-Server: `/weather-config` mergt einstufig wie mergeConfigMap, `/trips/{id}` top-level. */
function tripServer(start: AboSicht) {
	let doc = klon(start) as Rec;
	const puts: { path: string; body: Rec }[] = [];
	const client = {
		async get<T>(): Promise<T> {
			return klon(doc) as T;
		},
		async put<T>(path: string, body: unknown): Promise<T> {
			const b = klon(body) as Rec;
			puts.push({ path, body: b });
			if (path.endsWith('/weather-config')) doc = { ...doc, display_config: { ...(doc.display_config as Rec), ...b } };
			else doc = { ...doc, ...b, report_config: { ...(doc.report_config as Rec), ...((b.report_config as Rec) ?? {}) } };
			return klon(doc) as T;
		},
		async post<T>(path: string): Promise<T> {
			throw new Error(`unerwartet: POST ${path}`);
		}
	};
	return { client, puts, doc: () => klon(doc) as AboSicht };
}

async function tripSpeichern(server: ReturnType<typeof tripServer>, aendern: (s: WetterStand) => WetterStand): Promise<void> {
	const seite = server.doc();
	let stand = standAusAbo('route', seite, aufgeloestVon(seite), {}, { eig: EIG });
	const ctl = createController(TRIP_ID);
	const sp = SPEICHERER.route({ client: server.client, stand: () => stand, vorlagen: () => vorlagen, abo: () => seite, saveController: ctl });
	stand = aendern(stand);
	const vorher = server.puts.length;
	sp.melden();
	await ctl.flush();
	assert.equal(ctl.error, null, `Messaufbau: Speichern gescheitert (${ctl.state}: ${ctl.error})`);
	assert.equal(server.puts.length - vorher, 2, 'Messaufbau: ein Speichervorgang = zwei PUTs (/weather-config, /trips/{id})');
}

describe('p14 / #1544 AC-6 Trip (Reiter Wetter, echter Speicherer)', () => {
	test('Boeen abwaehlen + speichern: Ampel-Zeile und Altstufen bleiben gespeichert', async () => {
		const server = tripServer(tripAbo());
		const vorher = standAusAbo('route', server.doc(), aufgeloestVon(server.doc()), {}, { eig: EIG });
		pruefeZeileWieVorher(vorher, 'Messaufbau');

		await tripSpeichern(server, (s) => ohneMetrik(s, 'gust'));
		const wetterPut = server.puts.find((p) => p.path.endsWith('/weather-config'));
		assert.ok(wetterPut, 'Messaufbau: kein PUT auf /weather-config');
		const gesendet = wetterPut.body.metric_alert_levels as Rec | undefined;
		assert.ok(
			gesendet === undefined || JSON.stringify(gesendet) === JSON.stringify(STUFEN),
			`Nutzlast ueberschreibt metric_alert_levels (Go-Merge ersetzt den Unterbaum) mit ${JSON.stringify(gesendet)}`
		);

		const dc = server.doc().display_config as Rec;
		assert.deepEqual(dc.metric_alert_levels, STUFEN, 'Altstufen nach dem Abwaehlen verloren (AC-6)');
		const metrics = dc.metrics as { metric_id: string; enabled: boolean }[];
		assert.equal(metrics.find((m) => m.metric_id === 'gust')?.enabled, false, 'Messaufbau: Boeen nicht abgewaehlt');
		const gust = ((dc.ampel as Rec).metrics as Rec).gust as Rec;
		assert.equal(gust?.alarm_ab, 'red', `„Alarm ab“ der abgewaehlten Boeen nicht gespeichert: ${JSON.stringify(gust)}`);
	});

	test('neu oeffnen + Boeen wieder aufnehmen: dieselbe Stufe, auch nach erneutem Speichern', async () => {
		const server = tripServer(tripAbo());
		await tripSpeichern(server, (s) => ohneMetrik(s, 'gust'));

		const wieder = mitMetrik(standAusAbo('route', server.doc(), aufgeloestVon(server.doc()), {}, { eig: EIG }), 'gust');
		pruefeZeileWieVorher(wieder, 'nach Neu-Oeffnen');

		await tripSpeichern(server, (s) => mitMetrik(s, 'gust'));
		pruefeZeileWieVorher(standAusAbo('route', server.doc(), aufgeloestVon(server.doc()), {}, { eig: EIG }), 'nach erneutem Speichern');
		assert.deepEqual((server.doc().display_config as Rec).metric_alert_levels, STUFEN, 'Altstufen nach Wieder-Aufnahme verloren');
	});
});

// ── Orts-Vergleich ────────────────────────────────────────────────────────────────────────

const CP_ID = 'cp-p14-ac6';
function vergleichAbo(): Rec {
	const v = vollerVergleich(CP_ID);
	const dc = v.display_config as Rec;
	dc.active_metrics = [
		{ metric_id: 'wind', aggregation: 'max' },
		{ metric_id: 'gust', aggregation: 'max' },
		{ metric_id: 'temperature', aggregation: 'max' }
	];
	dc.ampel = { template: 'wandern', metrics: { gust: klon(GUST_ZEILE) } };
	dc.metric_alert_levels = klon(STUFEN);
	return v;
}

let server: GoMergeServer | undefined;
afterEach(() => server?.restore());

async function vergleichSpeichern(aendern: (s: WetterStand) => WetterStand): Promise<void> {
	clearEtagRegistry();
	await api.get(`/api/compare/presets/${CP_ID}`);
	const seite = server!.stand(CP_ID) as AboSicht;
	let stand = standAusAbo('vergleich', seite, aufgeloestVon(seite));
	const ctl = createController(CP_ID);
	const queue = createPutQueue();
	const sp = SPEICHERER.vergleich({
		client: api,
		stand: () => stand,
		vorlagen: () => vorlagen,
		abo: () => seite,
		saveController: ctl,
		enqueueHubWrite: (fn) => queue.enqueue(fn),
		uebernehmen: () => {},
		neuGeladen: () => {},
		aggregationFuer: () => 'max'
	} as Parameters<typeof SPEICHERER.vergleich>[0]);
	stand = aendern(stand);
	sp.melden();
	await ctl.flush();
	const puts = server!.mitschnitt.filter((e) => e.method === 'PUT');
	assert.equal(puts.at(-1)?.status, 200, `Messaufbau: PUT gescheitert (${ctl.state})`);
}

describe('p14 / #1544 AC-6 Orts-Vergleich (Reiter Wetter, echter Speicherer, Go-Merge)', () => {
	test('Boeen abwaehlen, speichern, wieder aufnehmen: Stufe und Altstufen bleiben', async () => {
		server = createGoMergeServer({ [CP_ID]: vergleichAbo() });
		server.install();
		pruefeZeileWieVorher(standAusAbo('vergleich', server.stand(CP_ID) as AboSicht, aufgeloestVon(server.stand(CP_ID))), 'Messaufbau');

		await vergleichSpeichern((s) => ohneMetrik(s, 'gust'));
		const dc = server.stand(CP_ID).display_config as Rec;
		assert.ok(
			!(dc.active_metrics as { metric_id: string }[]).some((m) => m.metric_id === 'gust'),
			'Messaufbau: Boeen nicht abgewaehlt'
		);
		assert.deepEqual(dc.metric_alert_levels, STUFEN, 'Altstufen nach dem Abwaehlen verloren (AC-6)');

		const wieder = mitMetrik(standAusAbo('vergleich', server.stand(CP_ID) as AboSicht, aufgeloestVon(server.stand(CP_ID))), 'gust', 'vergleich');
		pruefeZeileWieVorher(wieder, 'nach Neu-Oeffnen');

		await vergleichSpeichern((s) => mitMetrik(s, 'gust', 'vergleich'));
		pruefeZeileWieVorher(standAusAbo('vergleich', server.stand(CP_ID) as AboSicht, aufgeloestVon(server.stand(CP_ID))), 'nach erneutem Speichern');
		assert.deepEqual((server.stand(CP_ID).display_config as Rec).metric_alert_levels, STUFEN);
	});
});
