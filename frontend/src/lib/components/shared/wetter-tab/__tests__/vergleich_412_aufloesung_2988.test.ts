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
import { createController as baueController } from '../../__tests__/versandVergleichPruefstand.ts';
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

const controller: Json[] = [];
function createController(id: string) {
	const c = baueController(id);
	controller.push(c);
	return c;
}

let server: GoMergeServer;
let ablauf: string[];
/** Ersatz fuer GET des Abos nach dem 412 bzw. fuer die Aufloesung; `null` = echt. */
let getErsatz: (() => Promise<Response>) | null;
let postErsatz: ((rumpf: Json) => Promise<Response>) | null;
let aufloesungen: Json[];
/** Haelt die fertige Antwort des Pruefservers (PUT, GET) bzw. der Aufloesung zurueck. */
let zurueckhalten: ((schritt: string) => Promise<void> | undefined) | null;

beforeEach(async () => {
	clearEtagRegistry();
	ablauf = [];
	getErsatz = null;
	postErsatz = null;
	aufloesungen = [];
	zurueckhalten = null;
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
			const antwort = new Response(JSON.stringify(await echterPost(pfad, rumpf)), { status: 200, headers: JSON_KOPF });
			await zurueckhalten?.('POST Auflösung');
			return antwort;
		}
		if (methode === 'GET' && getErsatz) {
			ablauf.push('GET scheitert');
			return getErsatz();
		}
		const antwort = await server.handler(input, init);
		ablauf.push(`${methode} ${antwort.status}`);
		await zurueckhalten?.(`${methode} ${antwort.status}`);
		return antwort;
	};
	await api.get(PFAD); // ETag bekannt, wie nach dem Laden der Seite
	ablauf.length = 0;
});
afterEach(() => {
	// Kein Speichern eines (gescheiterten) Tests laeuft in den naechsten hinein.
	for (const c of controller.splice(0)) c.cancel('wetter-ampel');
	server.restore();
});

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
	const ERSATZ: Record<string, { setze: () => void; fragen: number }> = {
		get_status: { setze: () => (getErsatz = status(503)), fragen: 0 },
		get_netzfehler: { setze: () => (getErsatz = FEHLER.netzfehler as () => Promise<Response>), fragen: 0 },
		aufloesung: { setze: () => (postErsatz = status(503, { error: 'aufloesung', detail: 'Auflösung nicht erreichbar' })), fragen: 1 }
	};
	for (const [art, e] of Object.entries(ERSATZ)) {
		test(`fehler_beim_nachladen_ersetzt_den_412_nicht_${art}`, async () => {
			const { SPEICHERER } = await modul('wetterTabSpeicherung.ts');
			e.setze();
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
			assert.equal(aufloesungen.length, e.fragen, 'Fragen an die Auflösung');
			assert.equal(ablauf.includes('uebernehmen'), false);
		});
	}
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

// F005: waehrend PUT, GET oder Aufloesung unterwegs sind, gibt der Nutzer weiter ein. Das Neuladen ersetzte seinen
// Stand, und der nachlaufende PUT saehe mit frischem Stempel wie ein erfolgreiches Speichern aus (Zustand idle).
describe('AC-12 (#2988, F005): Eingabe, während der Konflikt geklärt wird', () => {
	const FENSTER: Record<string, string> = { put: 'PUT 412', get: 'GET 200', aufloesung: 'POST Auflösung' };
	const RUNDE = ['PUT 412', 'GET 200', 'POST Auflösung'];
	async function reiter() {
		const ctl = createController(ID);
		const queue = createPutQueue();
		const uebernommen: Json[] = [];
		const r = await oeffneReiter({ ctl, queue, uebernommen });
		return { r, u: r.u, ctl, queue, uebernommen };
	}
	/** Eine Reiter-Instanz an Controller, Schlange und Seite des Hubs. */
	async function oeffneReiter(hub: { ctl: Json; queue: Json; uebernommen: Json[] }): Promise<Json> {
		let u: Json = null;
		const r = await oeffne('vergleich', abo(), {
			netz: api,
			saat: {
				saveController: hub.ctl,
				enqueueHubWrite: (fn: () => Promise<Json>) => hub.queue.enqueue(fn),
				onCompareUpdate: (p: Json) => {
					hub.uebernommen.push(p);
					u.preset = p;
				}
			}
		});
		u = r.u;
		r.setzePost((pfad, rumpf) => api.post(pfad, rumpf));
		const Z = await modul('wetterZustand.ts');
		return { ...r, alarmAb: (id: string, stufe: string) => u.aendern(Z.mitAlarmAb(u.stand, id, stufe)) };
	}
	type Pruefling = Awaited<ReturnType<typeof reiter>>;
	const statusFolge = () => puts().map((p) => p.status);
	/** Eingabe, fremde Aenderung, Speichern; im Fenster (erste Antwort des Schritts unterwegs) `tun`. */
	async function bisFenster(
		p: Pruefling,
		schritt: string,
		tun: () => void | Promise<void>,
		erste: (r: Json) => void = (r) => r.grenze('gust', 'upper', 'yellow', 41)
	): Promise<void> {
		const da = tor();
		const halt = tor();
		zurueckhalten = (s) => {
			if (s !== schritt) return undefined;
			zurueckhalten = null;
			da.auf();
			return halt.versprechen;
		};
		erste(p.r);
		fremdSchreiben();
		const fertig = p.ctl.flush();
		await da.versprechen;
		await tun();
		await tick(20);
		halt.auf();
		await fertig;
	}
	/** Ende: der Reiter zeigt den fremden Stand, der Konflikt ist gemeldet, nichts steht aus. */
	function zeigtFremdenStand(p: Pruefling): void {
		assert.equal(p.ctl.state, 'conflict', 'Konflikt nicht mehr gemeldet');
		assert.equal(p.ctl.hasPending, false);
		assert.deepEqual(ampelServer(), FREMD, 'fremde Ampel überschrieben');
		assert.equal((server.stand(ID) as Json).name, 'Fremd');
		assert.equal(p.u.stand.vorlageId, 'wandern');
		assert.deepEqual(json(p.u.stand.ampel), aufgeloestVon(server.stand(ID)).ampel);
		assert.equal(p.u.gemeldet, p.u.signatur(p.u.stand));
		assert.deepEqual(p.uebernommen, [server.stand(ID)], 'Seite übernimmt nicht genau einmal');
	}
	/** Direkt nach der ersten Runde: nichts ersetzt, beide Eingaben stehen im Reiter. */
	function behaeltEingaben(p: Pruefling, gust: number, wind: number | undefined): void {
		assert.equal(p.ctl.state, 'conflict');
		assert.equal(p.u.stand.vorlageId, 'allgemein', 'Eingabe im Fenster durch das Neuladen ersetzt');
		assert.equal(p.u.stand.ampel.metrics.gust.upper.yellow, gust);
		if (wind !== undefined) assert.equal(p.u.stand.ampel.metrics.wind.upper.yellow, wind);
		assert.deepEqual([p.uebernommen, p.u.preset.name], [[], 'X'], 'Seite übernimmt trotz Eingabe');
		assert.equal(p.ctl.hasPending, true, 'Messaufbau: kein nachlaufendes Speichern');
		assert.deepEqual(ablauf, RUNDE);
	}
	const EINGABEN: Record<string, { tun: (r: Json) => void; gust: number; wind?: number }> = {
		anderes_feld: { tun: (r) => r.grenze('wind', 'upper', 'yellow', 33), gust: 41, wind: 33 },
		tippen_und_zuruecknehmen: {
			tun: (r) => {
				r.grenze('gust', 'upper', 'yellow', 42);
				r.grenze('gust', 'upper', 'yellow', 41);
			},
			gust: 41
		},
		// Die Wiederholung meldet nichts mehr, das nachlaufende Speichern der echten Eingabe bleibt.
		anderes_feld_und_dasselbe_nochmal: {
			tun: (r) => {
				r.grenze('wind', 'upper', 'yellow', 33);
				r.grenze('wind', 'upper', 'yellow', 33);
			},
			gust: 41,
			wind: 33
		}
	};
	// F008: der Reiter ersetzt seinen Stand bei jeder Geste, meldet aber nur Geaendertes. Ohne Meldung laeuft kein
	// Speichern nach, also muss neu geladen werden (sonst ueberschreibt „Nochmal speichern“ die ungesehene Ampel).
	const GLEICHE: Record<string, { erste: (r: Json) => void; nochmal: (r: Json) => void }> = {
		gleicher_grenzwert: { erste: (r) => r.grenze('gust', 'upper', 'yellow', 41), nochmal: (r) => r.grenze('gust', 'upper', 'yellow', 41) },
		gleiche_vorlage: { erste: (r) => r.uebernehmen('radtour'), nochmal: (r) => r.uebernehmen('radtour') },
		gleiche_alarmstufe: { erste: (r) => r.alarmAb('gust', 'red'), nochmal: (r) => r.alarmAb('gust', 'red') }
	};
	for (const [fenster, schritt] of Object.entries(FENSTER)) {
		for (const [art, e] of Object.entries(GLEICHE)) {
			test(`${fenster}_fenster_${art}_laedt_neu_und_nochmal_speichern_laesst_die_fremde_ampel`, async () => {
				const p = await reiter();
				await bisFenster(
					p,
					schritt,
					() => {
						const vorher = p.u.stand;
						e.nochmal(p.r);
						assert.notEqual(p.u.stand, vorher, 'Messaufbau: Stand nicht ersetzt');
						assert.deepEqual(json(p.u.stand), json(vorher), 'Messaufbau: Eingabe ändert den Inhalt');
						assert.equal(p.u.signatur(p.u.stand), p.u.gemeldet, 'Messaufbau: Signatur anders');
						assert.equal(p.ctl.hasPending, false, 'Messaufbau: Eingabe wurde gemeldet');
					},
					e.erste
				);
				assert.deepEqual(statusFolge(), [412]);
				assert.deepEqual(ablauf, RUNDE);
				zeigtFremdenStand(p);
				await p.ctl.retryConflict();
				assert.deepEqual(statusFolge(), [412, 200]);
				assert.equal(p.ctl.state, 'idle');
				assert.deepEqual([ampelServer().template, ampelServer().metrics.wind.alarm_ab], ['wandern', 'red'], '„Nochmal speichern“ überschreibt die ungesehene fremde Ampel');
				assert.equal(ampelServer().metrics.gust, undefined, 'gesendet wird nicht der angezeigte Stand');
			});
		}
		// Reiterwechsel im Fenster: die neue Instanz startet mit dem alten Abo, ihre Eingabe meldet denselben Vergleich.
		test(`${fenster}_fenster_reiterwechsel_eingabe_der_neuen_instanz_ueberschreibt_nichts_still`, async () => {
			const p = await reiter();
			let neu: Json = null;
			await bisFenster(p, schritt, async () => {
				neu = await oeffneReiter(p);
				neu.grenze('wind', 'upper', 'yellow', 33);
				assert.equal(neu.u.stand.vorlageId, 'allgemein', 'Messaufbau: neue Instanz kennt die fremde Ampel schon');
			});
			assert.equal(p.ctl.hasPending, true, 'Messaufbau: kein nachlaufendes Speichern');
			assert.deepEqual([p.uebernommen, p.ctl.state], [[], 'conflict']);
			await p.ctl.flush();
			assert.deepEqual(statusFolge(), [412, 412], 'Eingabe der neuen Instanz überschreibt die fremde Ampel still');
			zeigtFremdenStand({ ...p, u: neu.u });
		});
		for (const [art, e] of Object.entries(EINGABEN)) {
			test(`${fenster}_fenster_${art}_konflikt_bleibt_gemeldet`, async () => {
				const p = await reiter();
				await bisFenster(p, schritt, () => e.tun(p.r));
				behaeltEingaben(p, e.gust, e.wind);
				await p.ctl.flush();
				assert.deepEqual(statusFolge(), [412, 412], 'nachlaufendes Speichern trifft nicht auf den Konflikt');
				assert.deepEqual(ablauf, [...RUNDE, ...RUNDE]);
				zeigtFremdenStand(p);
			});
		}
		test(`${fenster}_fenster_nachlaufendes_speichern_wartet_schon_in_der_schlange`, async () => {
			const p = await reiter();
			let zweites: Promise<void> | undefined;
			await bisFenster(p, schritt, () => {
				p.r.grenze('wind', 'upper', 'yellow', 33);
				zweites = p.ctl.flush();
			});
			await zweites;
			assert.deepEqual(statusFolge(), [412, 412]);
			assert.deepEqual(ablauf, [...RUNDE, ...RUNDE]);
			zeigtFremdenStand(p);
		});
		// Zwei Eingaben im selben Fenster, je laenger als die Entprellung auseinander: zwei nachlaufende Vorgaenge.
		test(`${fenster}_fenster_zwei_eingaben_mit_zwei_nachlaufenden_speichern`, async () => {
			const p = await reiter();
			const weitere: Promise<void>[] = [];
			await bisFenster(p, schritt, () => {
				for (const w of [33, 34]) {
					p.r.grenze('wind', 'upper', 'yellow', w);
					weitere.push(p.ctl.flush());
				}
			});
			await Promise.all(weitere);
			assert.deepEqual(statusFolge(), [412, 412, 412]);
			zeigtFremdenStand(p);
		});
		test(`${fenster}_fenster_ohne_eingabe_laedt_neu`, async () => {
			const p = await reiter();
			await bisFenster(p, schritt, () => {
				// Ansehen ist keine Eingabe: Grenzen oeffnen und ohne Aenderung schliessen.
				p.u.grenzenUmschalten('wind');
				assert.equal(p.u.fertig(), true);
			});
			assert.deepEqual(statusFolge(), [412]);
			assert.deepEqual(ablauf, RUNDE);
			zeigtFremdenStand(p);
		});
		test(`${fenster}_fenster_danach_nochmal_speichern_und_naechste_eingabe`, async () => {
			const p = await reiter();
			await bisFenster(p, schritt, () => p.r.grenze('wind', 'upper', 'yellow', 33));
			await p.ctl.flush();
			assert.equal(p.ctl.state, 'conflict');
			await p.ctl.retryConflict();
			assert.equal(p.ctl.state, 'idle', '„Nochmal speichern“ gelingt nicht');
			assert.deepEqual(statusFolge(), [412, 412, 200]);
			// Gesendet wird der neu geladene (angezeigte) Stand: die fremde Ampel bleibt.
			assert.deepEqual([ampelServer().template, ampelServer().metrics.wind.alarm_ab], ['wandern', 'red']);
			assert.deepEqual([ampelServer().metrics.gust?.upper, ampelServer().metrics.wind.upper], [undefined, undefined], 'gesendet wird nicht der angezeigte Stand');
			p.r.grenze('gust', 'upper', 'yellow', 43);
			await p.ctl.flush();
			assert.deepEqual(statusFolge(), [412, 412, 200, 200]);
			assert.deepEqual([ampelServer().metrics.gust.upper.yellow, ampelServer().metrics.wind.alarm_ab], [43, 'red']);
		});
		test(`${fenster}_fenster_danach_geht_die_naechste_eingabe_auf_den_fremden_stand`, async () => {
			const p = await reiter();
			await bisFenster(p, schritt, () => p.r.grenze('wind', 'upper', 'yellow', 33));
			await p.ctl.flush();
			assert.equal(p.ctl.state, 'conflict');
			p.r.grenze('gust', 'upper', 'yellow', 43);
			await p.ctl.flush();
			assert.deepEqual(statusFolge(), [412, 412, 200]);
			assert.equal(p.ctl.state, 'idle');
			assert.deepEqual([ampelServer().template, ampelServer().metrics.wind.alarm_ab, ampelServer().metrics.gust.upper.yellow], ['wandern', 'red', 43]);
		});
		test(`${fenster}_fenster_nochmal_speichern_vor_dem_nachlaufenden_sendet_alle_eingaben`, async () => {
			const p = await reiter();
			await bisFenster(p, schritt, () => p.r.grenze('wind', 'upper', 'yellow', 33));
			await p.ctl.retryConflict();
			assert.deepEqual(statusFolge(), [412, 200]);
			const eigene = () => ['gust', 'wind'].map((id) => ampelServer().metrics[id]?.upper?.yellow);
			assert.deepEqual(eigene(), [41, 33], 'eigene Eingabe verloren');
			await p.ctl.flush();
			assert.deepEqual(statusFolge(), [412, 200, 200]);
			assert.equal(p.ctl.state, 'idle');
			assert.deepEqual(eigene(), [41, 33]);
		});
	}
	// Das Speichern wartet hinter einem anderen Hub-Schreiber; die zweite Eingabe faellt in die Wartezeit, der erste
	// PUT traegt sie also schon, ihr eigener Vorgang laeuft trotzdem nach.
	for (const art of ['entprellt', 'eingereiht']) {
		test(`eingabe_waehrend_das_speichern_auf_die_schlange_wartet_${art}`, async () => {
			const p = await reiter();
			const halt = tor();
			const fremder = p.queue.enqueue(() => halt.versprechen);
			p.r.grenze('gust', 'upper', 'yellow', 41);
			fremdSchreiben();
			const erstes = p.ctl.flush();
			await tick();
			p.r.grenze('wind', 'upper', 'yellow', 33);
			const zweites = art === 'eingereiht' ? p.ctl.flush() : undefined;
			halt.auf();
			await Promise.all([fremder, erstes, zweites]);
			await p.ctl.flush();
			assert.deepEqual(statusFolge(), [412, 412]);
			zeigtFremdenStand(p);
		});
	}
	test('wiederholtes_nochmal_speichern_trifft_erneut_auf_fremdes_und_laedt_neu', async () => {
		const p = await reiter();
		await bisFenster(p, FENSTER.get, () => {});
		// Zwischen dem GET und dem PUT von „Nochmal speichern“ schreibt wieder jemand.
		const dritte = { template: 'skitouren', metrics: { gust: { alarm_ab: 'red' } } };
		zurueckhalten = async (s) => {
			if (s !== 'GET 200') return;
			zurueckhalten = null;
			server.fremdSchreiben(ID, { display_config: { ampel: dritte } });
		};
		await p.ctl.retryConflict();
		assert.deepEqual(statusFolge(), [412, 412]);
		assert.equal(p.ctl.state, 'conflict');
		assert.deepEqual(ampelServer(), dritte);
		assert.equal(p.u.stand.vorlageId, 'skitouren', 'zweite fremde Änderung nicht sichtbar');
	});
	// „Nochmal speichern“ misst ab dem Senden: eine frühere, längst gelaufene Meldung zählt nicht mehr.
	test('nochmal_speichern_laedt_neu_auch_wenn_das_nachlaufende_speichern_anders_scheiterte', async () => {
		const p = await reiter();
		await bisFenster(p, FENSTER.get, () => p.r.grenze('wind', 'upper', 'yellow', 33));
		const vorher = globalThis.fetch;
		(globalThis as Json).fetch = async (input: unknown, init?: RequestInit) => (init?.method === 'PUT' ? status(500)() : vorher(input as RequestInfo, init));
		await p.ctl.flush();
		(globalThis as Json).fetch = vorher;
		assert.deepEqual([p.ctl.state, p.ctl.hasPending, p.uebernommen.length], ['conflict', false, 0], 'Messaufbau: 500 des nachlaufenden Speicherns');
		zurueckhalten = async (s) => {
			if (s !== 'GET 200') return;
			zurueckhalten = null;
			server.fremdSchreiben(ID, { display_config: { ampel: FREMD } });
		};
		await p.ctl.retryConflict();
		assert.deepEqual(statusFolge(), [412, 412]);
		zeigtFremdenStand(p);
	});
	test('nochmal_speichern_eingabe_waehrend_der_wiederholung_bleibt_und_laedt_erst_danach_neu', async () => {
		const p = await reiter();
		await bisFenster(p, FENSTER.get, () => {});
		zurueckhalten = async (s) => {
			// Nach dem GET von „Nochmal speichern“ schreibt wieder jemand; im 412-Fenster danach gibt der Nutzer ein.
			if (s === 'GET 200' && statusFolge().length === 1) server.fremdSchreiben(ID, { name: 'Fremd', display_config: { ampel: FREMD } });
			if (s === 'PUT 412') {
				zurueckhalten = null;
				p.r.grenze('gust', 'upper', 'yellow', 44);
			}
		};
		await p.ctl.retryConflict();
		assert.deepEqual(statusFolge(), [412, 412]);
		assert.equal(p.u.stand.ampel.metrics.gust.upper.yellow, 44, 'Eingabe durch das Neuladen ersetzt');
		assert.deepEqual([p.uebernommen.length, p.ctl.hasPending, p.ctl.state], [1, true, 'conflict']);
		await p.ctl.flush();
		assert.deepEqual(statusFolge(), [412, 412, 412]);
		p.uebernommen.shift();
		zeigtFremdenStand(p);
	});
	// Entprellt ersetzt: die erste Meldung läuft nie. Der Lauf der zweiten trägt den aktuellen Zähler.
	test('ersetzte_nie_gelaufene_meldung_verhindert_das_neuladen_nicht', async () => {
		const p = await reiter();
		p.r.grenze('wind', 'upper', 'yellow', 33);
		await bisFenster(p, FENSTER.get, () => {});
		assert.deepEqual(statusFolge(), [412]);
		zeigtFremdenStand(p);
	});
	test('meldung_eines_anderen_vergleichs_verhindert_das_neuladen_nicht', async () => {
		const { SPEICHERER } = await modul('wetterTabSpeicherung.ts');
		const p = await reiter();
		const anderer = createController('cp-2988-anderer');
		await bisFenster(p, FENSTER.get, () => {
			SPEICHERER.vergleich({ client: api, stand: () => p.u.stand, vorlagen: () => refVorlagen(), abo: () => ({ ...abo(), id: 'cp-2988-anderer' }), saveController: anderer }).melden();
		});
		assert.deepEqual(statusFolge(), [412]);
		zeigtFremdenStand(p);
	});
	// Eine Eingabe faellt genau N Microtasks nach der Antwort der Aufloesung: entweder wird sie gesehen (nichts
	// uebernommen) oder sie kommt nach der Uebernahme. Dazwischen gibt es keinen Platz.
	test('zwischen_vergleich_und_uebernahme_kann_keine_eingabe_fallen', async () => {
		const { SPEICHERER } = await modul('wetterTabSpeicherung.ts');
		const start = aufgeloestVon(abo());
		const stand = { vorlageId: start.vorlage_id, ampel: start.ampel, auswahl: AUSWAHL, warnungenAn: true, radarAn: false, tagesfenster: { start: 5, end: 18 } };
		const folgen = new Set<string>();
		for (let n = 0; n <= 30; n++) {
			const folge: string[] = [];
			const ctl = createController(ID);
			const sp: Json = SPEICHERER.vergleich({
				client: {
					...api,
					post: async (pfad: string, rumpf: Json) => {
						const antwort = await api.post(pfad, rumpf);
						let kette = Promise.resolve();
						for (let i = 0; i < n; i++) kette = kette.then(() => {});
						void kette.then(() => {
							folge.push('eingabe');
							sp.melden();
						});
						return antwort;
					}
				},
				stand: () => stand,
				vorlagen: () => refVorlagen(),
				abo: () => abo(),
				saveController: ctl,
				uebernehmen: () => void folge.push('uebernehmen'),
				neuGeladen: () => void folge.push('neuGeladen')
			});
			sp.melden();
			fremdSchreiben();
			await ctl.flush();
			await tick();
			ctl.cancel('wetter-ampel');
			folgen.add(folge.join(' '));
		}
		assert.deepEqual([...folgen].sort(), ['eingabe', 'uebernehmen neuGeladen eingabe']);
	});
	// Der Pruefstand haelt den Stand als schlichtes Objekt; im Browser ist er ein $state-Proxy. Massgeblich ist die
	// Meldung, nicht das Objekt.
	const SETZEN: Record<string, { neu: number; tun: (s: { lies: () => Json; setze: (s: Json) => void; aendern: (s: Json) => void; Z: Json }) => void }> = {
		ohne_eingabe: { neu: 1, tun: ({ lies, setze }) => setze(lies()) },
		neues_objekt_gleicher_inhalt: { neu: 1, tun: ({ lies, setze, Z }) => setze(Z.mitAlarmAb(lies(), 'gust', 'red')) },
		mit_eingabe: { neu: 0, tun: ({ lies, aendern, Z }) => aendern(Z.mitAlarmAb(lies(), 'wind', 'red')) }
	};
	for (const [art, e] of Object.entries(SETZEN)) {
		test(`echter_svelte_state_${art}`, async () => {
			const SVELTE_CLIENT = 'svelte/internal/client';
			const $ = (await import(SVELTE_CLIENT)) as Json;
			const Z = await modul('wetterZustand.ts');
			const { SPEICHERER } = await modul('wetterTabSpeicherung.ts');
			const start = aufgeloestVon(abo());
			// Wie `let stand = $state(…)` nach dem Compiler: Lesen `get`, Zuweisen `set(…, true)` (Proxy).
			const quelle = $.state(null);
			const lies = (): Json => $.get(quelle);
			const setze = (s: Json) => void $.set(quelle, s, true);
			setze({ vorlageId: start.vorlage_id, ampel: start.ampel, auswahl: AUSWAHL, warnungenAn: true, radarAn: false, tagesfenster: { start: 5, end: 18 } });
			assert.throws(() => structuredClone(lies()), { name: 'DataCloneError' }, 'Messaufbau: kein echter Svelte-Proxy');
			const ctl = createController(ID);
			const neu: Json[] = [];
			const sp = SPEICHERER.vergleich({
				client: api,
				stand: lies,
				vorlagen: () => refVorlagen(),
				abo: () => abo(),
				saveController: ctl,
				uebernehmen: () => {},
				neuGeladen: (a: Json) => void neu.push(a)
			});
			const aendern = (s: Json) => {
				setze(s);
				sp.melden();
			};
			aendern(Z.mitAlarmAb(lies(), 'gust', 'red'));
			fremdSchreiben();
			zurueckhalten = async (s) => {
				if (s === 'GET 200') e.tun({ lies, setze, aendern, Z });
			};
			await ctl.flush();
			zurueckhalten = null;
			assert.equal(ctl.state, 'conflict');
			assert.equal(neu.length, e.neu);
		});
	}
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
