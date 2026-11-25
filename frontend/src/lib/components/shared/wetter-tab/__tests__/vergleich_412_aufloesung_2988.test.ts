// #2988 S3, AC-12: 412 im Ortsvergleich – neu laden samt Aufloesung, dann erst an Seite und Reiter geben;
// scheitert die Aufloesung, wie beim gescheiterten Nachladen (kein Neuladen, Konflikt gemeldet).
// Spec: docs/specs/modules/rework_2988_ampel_ableitung.md. Aufbau wie f003_vergleich_speicherer_hub_schlange:
// echter Controller, echte Hub-Schlange, echtes `api` gegen den Go-Merge-Pruefserver; die Aufloesung
// beantwortet echtes Python.

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { api } from '../../../../api.ts';
import { clearEtagRegistry } from '../../../../etagRegistry.ts';
import { createPutQueue } from '../../../compare/compareHubPersistenz.ts';
import { createController } from '../../__tests__/versandVergleichPruefstand.ts';
import { createGoMergeServer, vollerVergleich, type GoMergeServer } from '../../__tests__/goMergeServerPruefstand.ts';
import { AUFLOESUNG, aufgeloestVon, echterPost, funktion, json, modul, oeffne, refVorlagen, tick, tor, type Json } from './laden2988.ts';

const ID = 'cp-2988-412';
const PFAD = `/api/compare/presets/${ID}`;
const FREMD = { template: 'wandern', metrics: { wind: { alarm_ab: 'red' } } };
/** Auswahl = Metriken der Vorlage „allgemein“ (keine Abweichung durch die Auswahl). */
const AUSWAHL = Object.entries(refVorlagen().allgemein.metrics).filter(([, z]) => (z as Json).enabled).map(([id]) => id);
const JSON_KOPF = { 'Content-Type': 'application/json' };

function abo(): Json {
	const v = vollerVergleich(ID) as Json;
	v.display_config.active_metrics = AUSWAHL.map((metric_id) => ({ metric_id, aggregation: 'max' }));
	v.display_config.ampel = { template: 'allgemein' };
	return v;
}

let server: GoMergeServer;
let ablauf: string[];
/** Ersatz fuer GET des Abos nach dem 412 bzw. fuer die Aufloesung; `null` = echt. */
let getErsatz: (() => Promise<Response>) | null;
let postErsatz: ((rumpf: Json) => Promise<Response>) | null;
let aufloesungen: Json[];

beforeEach(async () => {
	clearEtagRegistry();
	ablauf = [];
	getErsatz = null;
	postErsatz = null;
	aufloesungen = [];
	server = createGoMergeServer({ [ID]: abo() });
	server.install();
	(globalThis as Json).fetch = async (input: unknown, init?: RequestInit) => {
		const pfad = new URL(String(input), 'http://gz.invalid').pathname;
		const methode = (init?.method ?? 'GET').toUpperCase();
		if (pfad === AUFLOESUNG) {
			assert.equal(methode, 'POST');
			const rumpf = JSON.parse(String(init?.body));
			ablauf.push('POST Auflösung');
			aufloesungen.push(rumpf);
			if (postErsatz) return postErsatz(rumpf);
			return new Response(JSON.stringify(await echterPost(pfad, rumpf)), { status: 200, headers: JSON_KOPF });
		}
		if (methode === 'GET' && getErsatz) {
			ablauf.push('GET scheitert');
			return getErsatz();
		}
		const antwort = await server.handler(input, init);
		ablauf.push(`${methode} ${antwort.status}`);
		return antwort;
	};
	await api.get(PFAD); // ETag bekannt, wie nach dem Laden der Seite
	ablauf.length = 0;
});
afterEach(() => server.restore());

const puts = () => server.mitschnitt.filter((e) => e.method === 'PUT');
const ampelServer = (): Json => (server.stand(ID) as Json).display_config.ampel;
const fremdSchreiben = () => server.fremdSchreiben(ID, { name: 'Fremd', display_config: { ampel: FREMD } });
const status = (s: number, rumpf: Json = { error: 'kaputt' }) => async () => new Response(JSON.stringify(rumpf), { status: s, headers: JSON_KOPF });

/** Speicherer des Reiters mit denselben Optionen wie WetterTabInhalt (Stand bleibt beim Test). */
async function speicherer() {
	const Z = await modul('wetterZustand.ts');
	const { SPEICHERER } = await modul('wetterTabSpeicherung.ts');
	let seite = abo();
	const start = aufgeloestVon(seite);
	let stand: Json = { vorlageId: start.vorlage_id, ampel: start.ampel, auswahl: AUSWAHL, warnungenAn: true, radarAn: false, tagesfenster: { start: 5, end: 18 } };
	const ctl = createController(ID);
	const queue = createPutQueue();
	const uebernommen: Json[] = [];
	const neuGeladen: Json[][] = [];
	const sp = SPEICHERER.vergleich({
		client: api,
		stand: () => stand,
		vorlagen: () => refVorlagen(),
		abo: () => seite,
		saveController: ctl,
		enqueueHubWrite: (fn: () => Promise<Json>) => queue.enqueue(fn),
		uebernehmen: (a: Json) => {
			ablauf.push('uebernehmen');
			uebernommen.push(a);
			seite = a;
		},
		neuGeladen: (...a: Json[]) => {
			ablauf.push('neuGeladen');
			neuGeladen.push(a);
		}
	});
	return {
		ctl,
		uebernommen,
		neuGeladen,
		/** Boeen „Alarm ab“ setzen und melden. */
		boeen(stufe: string) {
			stand = Z.mitAlarmAb(stand, 'gust', stufe);
			sp.melden();
		},
		wind(stufe: string) {
			stand = Z.mitAlarmAb(stand, 'wind', stufe);
			sp.melden();
		}
	};
}

describe('AC-12 (#2988): 412 im Vergleich – Nachladen, Auflösung, dann erst Seite und Reiter', () => {
	test('reihenfolge_get_aufloesung_uebernehmen_neuGeladen', async () => {
		const r = await speicherer();
		fremdSchreiben();
		r.boeen('red');
		await r.ctl.flush();
		assert.deepEqual(ablauf, ['PUT 412', 'GET 200', 'POST Auflösung', 'uebernehmen', 'neuGeladen']);
		assert.deepEqual(aufloesungen, [{ eintraege: [{ ampel: FREMD, preset_name: null, profil: 'wandern' }] }]);
		assert.deepEqual(r.uebernommen, [server.stand(ID)]);
		assert.equal(r.neuGeladen.length, 1);
		assert.deepEqual(r.neuGeladen[0][0], server.stand(ID));
		assert.deepEqual(r.neuGeladen[0][1], aufgeloestVon(server.stand(ID)), 'neuGeladen bekommt die Auflösung nicht');
		assert.equal(r.neuGeladen[0][1].ampel.metrics.wind.alarm_ab, 'red', 'fremde Änderung fehlt in der Auflösung');
		assert.equal(r.ctl.state, 'conflict');
		assert.deepEqual(ampelServer(), FREMD, 'fremde Änderung überschrieben');
	});
	test('vor_der_antwort_weder_uebernehmen_noch_neuGeladen', async () => {
		const halt = tor();
		postErsatz = async (rumpf) => {
			await halt.versprechen;
			return new Response(JSON.stringify(await echterPost(AUFLOESUNG, rumpf)), { status: 200, headers: JSON_KOPF });
		};
		const r = await speicherer();
		fremdSchreiben();
		r.boeen('red');
		const fertig = r.ctl.flush();
		for (let i = 0; i < 100 && aufloesungen.length === 0 && r.uebernommen.length === 0; i++) await tick();
		await tick(30);
		const zwischen = [...ablauf];
		halt.auf();
		await fertig;
		assert.deepEqual(zwischen, ['PUT 412', 'GET 200', 'POST Auflösung']);
		assert.deepEqual(ablauf.slice(3), ['uebernehmen', 'neuGeladen']);
	});
	test('ohne_412_keine_aufloesung', async () => {
		const r = await speicherer();
		r.boeen('red');
		await r.ctl.flush();
		assert.deepEqual(ablauf, ['PUT 200', 'uebernehmen']);
		assert.equal(r.ctl.state, 'idle');
	});
	test('anderer_fehler_als_412_laedt_nicht_nach', async () => {
		const r = await speicherer();
		const vorher = globalThis.fetch;
		(globalThis as Json).fetch = async (input: unknown, init?: RequestInit) => (init?.method === 'PUT' ? status(500)() : vorher(input as RequestInfo, init));
		r.boeen('red');
		await r.ctl.flush();
		assert.deepEqual(ablauf, []);
		assert.deepEqual(r.uebernommen, []);
	});
});

describe('AC-12 (#2988): Auflösung scheitert nach dem 412 – wie beim gescheiterten Nachladen', () => {
	/** Ablauf aus Sicht von Nutzer und Server: Konflikt, weitere Eingabe, „Nochmal speichern“. */
	async function protokoll(): Promise<Json> {
		const r = await speicherer();
		fremdSchreiben();
		r.boeen('red');
		await r.ctl.flush();
		const nachKonflikt = { state: r.ctl.state, uebernommen: r.uebernommen.length, neuGeladen: r.neuGeladen.length, server: ampelServer(), name: (server.stand(ID) as Json).name };
		// Weitere Eingabe ohne „Nochmal speichern“: der Reiter zeigt den alten Stand, also darf sie die fremde
		// Änderung nicht still überschreiben.
		r.wind('red');
		await r.ctl.flush();
		const nachEingabe = { state: r.ctl.state, put: puts().map((p) => p.status), server: ampelServer(), uebernommen: r.uebernommen.length };
		getErsatz = null;
		postErsatz = null;
		await r.ctl.retryConflict();
		const letzter = puts().at(-1)!;
		return {
			nachKonflikt,
			nachEingabe,
			nachNochmal: { state: r.ctl.state, put: puts().map((p) => p.status), gesendet: (letzter.anfrage as Json).display_config.ampel, server: ampelServer(), name: (server.stand(ID) as Json).name }
		};
	}
	const SOLL_KONFLIKT = { state: 'conflict', uebernommen: 0, neuGeladen: 0, server: FREMD, name: 'Fremd' };
	const EIGENE = { template: 'allgemein', metrics: { gust: { alarm_ab: 'red' }, wind: { alarm_ab: 'red' } } };
	function pruefe(p: Json): void {
		assert.deepEqual(p.nachKonflikt, SOLL_KONFLIKT);
		assert.deepEqual(p.nachEingabe, { state: 'conflict', put: [412, 412], server: FREMD, uebernommen: 0 }, 'weitere Eingabe überschreibt die fremde Änderung still');
		assert.deepEqual(p.nachNochmal.put, [412, 412, 200]);
		assert.equal(p.nachNochmal.state, 'idle');
		assert.deepEqual(p.nachNochmal.gesendet, EIGENE, '„Nochmal speichern“ verliert die eigene Eingabe');
		assert.deepEqual(p.nachNochmal.server, EIGENE);
		assert.equal(p.nachNochmal.name, 'Fremd', 'fremdes Feld ausserhalb des Reiters verloren');
	}

	// Massstab: das gescheiterte Nachladen (Verhalten vor und nach dem Umbau gleich).
	test('massstab_nachladen_scheitert', async () => {
		getErsatz = status(503);
		pruefe(await protokoll());
		assert.deepEqual(aufloesungen, [], 'Auflösung ohne geladenes Abo');
	});
	const FEHLER: Record<string, (rumpf: Json) => Promise<Response>> = {
		netzfehler: async () => {
			throw new TypeError('Failed to fetch');
		},
		status_503: status(503),
		status_400: status(400, { code: 'bad_request' }),
		antwort_null: status(200, null),
		antwort_leer: status(200, {}),
		zu_wenige_ergebnisse: status(200, { ergebnisse: [] }),
		ergebnis_ohne_ampel: status(200, { ergebnisse: [{ vorlage_id: 'wandern' }] })
	};
	for (const [art, antwort] of Object.entries(FEHLER)) {
		test(`aufloesung_scheitert_${art}_gleich_dem_massstab`, async () => {
			postErsatz = antwort;
			const p = await protokoll();
			assert.ok(aufloesungen.length >= 1, 'die Auflösung wird nicht gefragt');
			pruefe(p);
		});
	}
	test('fehler_der_aufloesung_ersetzt_den_412_nicht', async () => {
		const { SPEICHERER } = await modul('wetterTabSpeicherung.ts');
		postErsatz = status(503, { error: 'aufloesung', detail: 'Auflösung nicht erreichbar' });
		let fn: ((init?: RequestInit) => Promise<void>) | undefined;
		const start = aufgeloestVon(abo());
		SPEICHERER.vergleich({
			client: api,
			stand: () => ({ vorlageId: start.vorlage_id, ampel: start.ampel, auswahl: ['gust'], warnungenAn: true, radarAn: false, tagesfenster: { start: 5, end: 18 } }),
			vorlagen: () => refVorlagen(),
			abo: () => abo(),
			uebernehmen: () => void ablauf.push('uebernehmen'),
			saveController: { schedule: (f: typeof fn) => void (fn = f) }
		}).melden();
		fremdSchreiben();
		await assert.rejects(async () => fn!(), (e) => (e as Json)?.status === 412);
		assert.equal(aufloesungen.length, 1, 'die Auflösung wird nicht gefragt');
	});
});

describe('AC-12 (#2988): im echten Reiter', () => {
	async function reiter() {
		const ctl = createController(ID);
		const queue = createPutQueue();
		const zwischen: Json[] = [];
		let u: Json = null;
		const r = await oeffne('vergleich', abo(), {
			netz: api,
			saat: {
				saveController: ctl,
				enqueueHubWrite: (fn: () => Promise<Json>) => queue.enqueue(fn),
				onCompareUpdate: (p: Json) => {
					// Wie die Seite: das Abo wird ersetzt. Gemessen: Stand beim Uebernehmen und einen Microtask spaeter.
					u.preset = p;
					const eintrag: Json = { beim: u.stand.vorlageId };
					zwischen.push(eintrag);
					queueMicrotask(() => (eintrag.danach = u.stand.vorlageId));
				}
			}
		});
		u = r.u;
		// Nach dem Laden laeuft auch die Aufloesung ueber das Netz des Pruefservers.
		r.setzePost((pfad, rumpf) => api.post(pfad, rumpf));
		return { r, u, ctl, zwischen };
	}
	const eingabe = (r: Json) => {
		r.grenze('gust', 'upper', 'yellow', 41);
		assert.equal(r.u.stand.ampel.metrics.gust.upper.yellow, 41, 'Messaufbau: Eingabe');
	};

	test('nach_412_zeigt_der_reiter_die_fremde_ampel_und_meldet_den_konflikt', async () => {
		const { r, u, ctl, zwischen } = await reiter();
		eingabe(r);
		fremdSchreiben();
		// Offene, noch nicht uebernommene Eingabe gehoert zum alten Stand.
		u.grenzenUmschalten('wind');
		u.grenzWert('wind', 'upper', 'yellow', 12);
		await ctl.flush();
		assert.deepEqual(ablauf, ['PUT 412', 'GET 200', 'POST Auflösung']);
		assert.equal(ctl.state, 'conflict');
		const soll = aufgeloestVon(server.stand(ID));
		assert.equal(u.stand.vorlageId, 'wandern');
		assert.deepEqual(json(u.stand.ampel), soll.ampel);
		assert.equal(u.stand.ampel.metrics.wind.alarm_ab, 'red');
		assert.deepEqual([u.offen, u.entwurf, u.fehler], [null, null, []], 'Entwurf des alten Stands bleibt offen');
		assert.equal(u.gemeldet, u.signatur(u.stand), 'Neuladen gilt als Änderung');
		assert.equal(ctl.hasPending, false, 'Neuladen plant ein Speichern');
		assert.deepEqual(zwischen, [{ beim: 'allgemein', danach: 'wandern' }], 'Übernehmen und Neuladen nicht in einem Zug');
		assert.deepEqual(ampelServer(), FREMD);
	});
	test('nach_dem_neuladen_geht_die_naechste_eingabe_auf_den_fremden_stand', async () => {
		const { r, ctl } = await reiter();
		eingabe(r);
		fremdSchreiben();
		await ctl.flush();
		r.grenze('gust', 'upper', 'yellow', 42);
		await ctl.flush();
		assert.deepEqual(puts().map((p) => p.status), [412, 200], 'neu geladener Stand gilt weiter als veraltet');
		assert.equal(aufloesungen.length, 1);
		const ampel = ampelServer();
		assert.equal(ampel.template, 'wandern');
		assert.equal(ampel.metrics.wind.alarm_ab, 'red', 'fremde Änderung überschrieben');
		assert.equal(ampel.metrics.gust.upper.yellow, 42);
	});
	test('neuGeladen_ist_synchron', async () => {
		const { u } = await reiter();
		const frisch = { ...abo(), display_config: { ...abo().display_config, ampel: FREMD } };
		// Antwort fuer ein anderes Abo: der Stand folgt ihr, nicht einer eigenen Rechnung.
		const antwort = aufgeloestVon({ display_config: { ampel: { template: 'skitouren', thunder: { mittel: 'red' } } } });
		const erg = u.neuGeladen(frisch, antwort);
		assert.equal(u.stand.vorlageId, 'skitouren', 'Stand nicht sofort aus der Antwort ersetzt');
		assert.deepEqual(json(u.stand.ampel), antwort.ampel);
		assert.equal(u.gemeldet, u.signatur(u.stand));
		assert.equal(erg, undefined);
		assert.deepEqual(ablauf, [], 'Netzaufruf beim Neuladen');
	});
	test('bis_zur_antwort_bleiben_reiter_und_seite_beim_alten_stand', async () => {
		const halt = tor();
		postErsatz = async (rumpf) => {
			await halt.versprechen;
			return new Response(JSON.stringify(await echterPost(AUFLOESUNG, rumpf)), { status: 200, headers: JSON_KOPF });
		};
		const { r, u, ctl } = await reiter();
		eingabe(r);
		fremdSchreiben();
		const fertig = ctl.flush();
		for (let i = 0; i < 100 && aufloesungen.length === 0 && u.stand.vorlageId === 'allgemein'; i++) await tick();
		await tick(30);
		const vorher = { vorlage: u.stand.vorlageId, gelb: u.stand.ampel.metrics.gust.upper.yellow, seite: u.preset.name, fragen: aufloesungen.length };
		halt.auf();
		await fertig;
		assert.deepEqual(vorher, { vorlage: 'allgemein', gelb: 41, seite: 'X', fragen: 1 });
		assert.equal(u.stand.vorlageId, 'wandern');
	});
	test('aufloesung_scheitert_reiter_behaelt_die_eingabe_und_nochmal_speichern_sendet_sie', async () => {
		postErsatz = status(503);
		const { r, u, ctl, zwischen } = await reiter();
		eingabe(r);
		fremdSchreiben();
		await ctl.flush();
		assert.equal(aufloesungen.length, 1, 'die Auflösung wird nicht gefragt');
		assert.equal(ctl.state, 'conflict');
		assert.equal(u.stand.vorlageId, 'allgemein');
		assert.equal(u.stand.ampel.metrics.gust.upper.yellow, 41, 'eigene Eingabe still verloren');
		assert.deepEqual(zwischen, [], 'Seite übernimmt ohne Auflösung');
		assert.equal(u.preset.name, 'X');
		assert.equal(u.phase, 'bereit');
		assert.deepEqual(ampelServer(), FREMD);
		postErsatz = null;
		await ctl.retryConflict();
		assert.equal(ctl.state, 'idle');
		assert.equal(ampelServer().metrics.gust.upper.yellow, 41, '„Nochmal speichern“ verliert die eigene Eingabe');
	});
});

// Der Trip lädt nach einem 412 nicht nach (zwei PUTs wie bisher): keine Auflösung beim Speichern.
describe('AC-12 (#2988): der Trip bleibt unberührt', () => {
	test('trip_speicherer_fragt_keine_aufloesung', async () => {
		const tripNutzlast = await funktion('wetterTabSpeicherung.ts', 'tripNutzlast');
		const a = aufgeloestVon({ display_config: { ampel: { template: 'wandern' } } });
		const n = tripNutzlast({
			client: api,
			stand: () => ({ vorlageId: 'wandern', ampel: a.ampel, auswahl: ['gust'], warnungenAn: true, radarAn: true, tagesfenster: { start: 4, end: 19 } }),
			vorlagen: () => refVorlagen(),
			abo: () => ({ id: 't', display_config: {} })
		});
		assert.equal(n.weatherConfig.ampel.template, 'wandern');
		assert.deepEqual(aufloesungen, []);
	});
});
