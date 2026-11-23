// #3237 Runde 14 (Adversary Lauf 7, F001): Ein Trip-Speichervorgang des Reiters Wetter besteht aus ZWEI PUTs
// (/weather-config mit `placements`, danach /api/trips/{id} ohne). Der Speicherer liest die Nutzlast dabei
// mehrfach. Ändert der Nutzer die Tabelle „Was steht wo“, während der erste PUT läuft, darf diese Änderung danach
// NICHT als gespeichert gelten: sie muss beim nächsten Speichern gesendet werden, und ein Nachladen (GET) mit dem
// älteren Serverstand darf sie nicht überschreiben.
//
// Echte Bausteine: SPEICHERER.route (wetterTabSpeicherung.ts → baueWetterMetrikenSpeicherung) und
// erstelleTabellenSpeicherung (wasStehtWoSpeicherung.ts), verdrahtet wie in WetterTabInhalt/WasStehtWoKarte;
// nur der Schreib-Client und der Controller sind Prüfstand-Doubles (Antworten einzeln freigebbar, kein Netz).
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/was_steht_wo_mitspeichern_marke.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { live } from './wetterTabDaten.ts';
import { vorlagenAusTemplates } from '../ampelModell.ts';
import { standAusAbo, type AboSicht } from '../wetterZustand.ts';
import { SPEICHERER } from '../wetterTabSpeicherung.ts';
import { erstelleTabellenSpeicherung, TABELLE_OWNER } from '../wasStehtWoSpeicherung.ts';
import type { Placements, PlacementsAntwort } from '../wasStehtWoStand.ts';

type Aufruf = { methode: 'GET' | 'PUT'; pfad: string; rumpf?: any; erledigen: (w?: unknown) => void };

function client() {
	const aufrufe: Aufruf[] = [];
	const neu = (methode: 'GET' | 'PUT', pfad: string, rumpf?: unknown) =>
		new Promise<any>((erledigen) => aufrufe.push({ methode, pfad, rumpf: rumpf === undefined ? undefined : JSON.parse(JSON.stringify(rumpf)), erledigen }));
	return {
		aufrufe,
		get: <T>(pfad: string) => neu('GET', pfad) as Promise<T>,
		put: <T>(pfad: string, rumpf: unknown) => neu('PUT', pfad, rumpf) as Promise<T>
	};
}
/** Controller mit Entprellung je Besitzer: der Vorgang läuft erst bei `lauf(besitzer)`. */
function controller() {
	const offen = new Map<string, (init?: RequestInit) => Promise<void>>();
	return {
		schedule(fn: (init?: RequestInit) => Promise<void>, _ms?: number, owner = '') {
			offen.set(owner, fn);
		},
		lauf(owner: string): Promise<void> {
			const fn = offen.get(owner);
			offen.delete(owner);
			return fn ? fn() : Promise.resolve();
		}
	};
}
const ruhe = () => new Promise((r) => setTimeout(r, 0));
const p = (...ids: string[]): Placements => ({ version: 1, rows: ids.map((metric_id) => ({ metric_id })) });
const ids = (x: { rows: { metric_id: string }[] } | undefined) => x?.rows.map((r) => r.metric_id);
const TRIP: AboSicht = { id: 't-1', report_config: {}, display_config: { metrics: [{ metric_id: 'wind', enabled: true }] } };

/** Reiter + Karte wie im Browser: Karte liefert ihren Stand nur bei gespeicherter Tabelle, Reiter meldet Erfolg. */
function aufbau() {
	const c = client();
	const ctl = controller();
	let lokal: Placements = p('wind', 'gust');
	const tabelle = erstelleTabellenSpeicherung({
		client: c,
		kind: 'route',
		id: 't-1',
		saveController: ctl,
		placements: () => structuredClone(lokal),
		uebernehmen: (a: PlacementsAntwort) => (lokal = structuredClone(a.placements))
	});
	const vv = vorlagenAusTemplates(live().templates);
	const stand = standAusAbo('route', TRIP, vv);
	const reiter = SPEICHERER.route({
		client: c,
		stand: () => stand,
		vorlagen: () => vv,
		abo: () => TRIP,
		saveController: ctl as never,
		uebernehmen: (_a, gesendet) => tabelle.nachReiterSpeichern(gesendet),
		placements: () => tabelle.zumMitsenden(true)
	});
	/** „−“/„+“ bzw. Haken: neuer lokaler Stand. */
	const aendere = (x: Placements, art: 'reiter' | 'haken') => {
		lokal = x;
		if (art === 'reiter') tabelle.mitgefuehrt();
		else tabelle.aenderung();
	};
	return { c, ctl, tabelle, reiter, aendere, lokal: () => lokal };
}
const offen = (c: ReturnType<typeof client>, methode: 'GET' | 'PUT', teil: string) =>
	c.aufrufe.filter((x) => x.methode === methode && x.pfad.includes(teil));

/** Erster Reiter-Speichervorgang; `dazwischen` läuft, während der PUT /weather-config hängt. */
async function speichernMitAenderungDazwischen(t: ReturnType<typeof aufbau>, dazwischen: () => void) {
	t.aendere(p('wind', 'gust', 'rain'), 'reiter');
	t.reiter.melden();
	const lauf = t.ctl.lauf('wetter-ampel');
	await ruhe();
	const wetter = offen(t.c, 'PUT', '/weather-config');
	assert.equal(wetter.length, 1, 'erster PUT /weather-config läuft');
	assert.deepEqual(ids(wetter[0].rumpf.placements), ['wind', 'gust', 'rain']);
	dazwischen();
	wetter[0].erledigen({});
	await ruhe();
	const trip = t.c.aufrufe.filter((x) => x.methode === 'PUT' && x.pfad === '/api/trips/t-1');
	assert.equal(trip.length, 1, 'zweiter PUT /api/trips/{id} läuft');
	assert.equal('placements' in trip[0].rumpf, false, 'der Trip-PUT trägt keine placements');
	trip[0].erledigen({ id: 't-1' });
	await lauf;
	await ruhe();
}

describe('#3237 Runde 14: Änderung zwischen den beiden Trip-PUTs bleibt ungespeichert', () => {
	test('„−“/„+“ während des ersten PUT: ungespeichert, kein Überschreiben durch GET, fährt beim nächsten Speichern mit', async () => {
		const t = aufbau();
		await speichernMitAenderungDazwischen(t, () => t.aendere(p('wind', 'gust', 'rain', 'snow'), 'reiter'));
		assert.equal(t.tabelle.ungespeichert, true, 'die Änderung wurde nie gesendet');
		// Ein Nachladen mit dem älteren Serverstand darf den lokalen Stand nicht überschreiben.
		for (const g of offen(t.c, 'GET', '/placements')) g.erledigen({ placements: p('wind', 'gust', 'rain'), rows: [] });
		await ruhe();
		assert.deepEqual(ids(t.lokal()), ['wind', 'gust', 'rain', 'snow'], 'lokale Änderung bleibt stehen');
		// Nächster Speichervorgang des Reiters sendet sie.
		const vorher = offen(t.c, 'PUT', '/weather-config').length;
		t.reiter.melden();
		void t.ctl.lauf('wetter-ampel');
		await ruhe();
		const zweiter = offen(t.c, 'PUT', '/weather-config')[vorher];
		assert.deepEqual(ids(zweiter?.rumpf.placements), ['wind', 'gust', 'rain', 'snow']);
	});

	test('Haken während des ersten PUT: der eingeplante Tabellen-PUT sendet ihn', async () => {
		const t = aufbau();
		await speichernMitAenderungDazwischen(t, () => t.aendere(p('wind', 'gust', 'rain', 'snow'), 'haken'));
		assert.equal(t.tabelle.ungespeichert, true);
		void t.ctl.lauf(TABELLE_OWNER);
		await ruhe();
		const tab = offen(t.c, 'PUT', '/placements');
		assert.equal(tab.length, 1, 'Tabellen-PUT läuft');
		assert.deepEqual(ids(tab[0].rumpf), ['wind', 'gust', 'rain', 'snow']);
	});

	test('Orte (ein PUT): gesendeter Stand gilt als gespeichert, Änderung während des PUT nicht', async () => {
		const ORTE: AboSicht = { id: 'cp-1', display_config: { active_metrics: [{ metric_id: 'wind', aggregation: 'max' }] } };
		const c = client();
		const ctl = controller();
		let lokal: Placements = p('wind', 'gust');
		const tabelle = erstelleTabellenSpeicherung({ client: c, kind: 'vergleich', id: 'cp-1', saveController: ctl, placements: () => structuredClone(lokal), uebernehmen: () => {} });
		const vv = vorlagenAusTemplates(live().templates);
		const stand = standAusAbo('vergleich', ORTE, vv);
		const reiter = SPEICHERER.vergleich({ client: c, stand: () => stand, vorlagen: () => vv, abo: () => ORTE, saveController: ctl as never, uebernehmen: (_a, g) => tabelle.nachReiterSpeichern(g), placements: () => tabelle.zumMitsenden(true) });
		const einmal = async (dazwischen: () => void) => {
			reiter.melden();
			const lauf = ctl.lauf('wetter-ampel');
			await ruhe();
			const put = offen(c, 'PUT', '/api/compare/presets/cp-1').at(-1)!;
			dazwischen();
			put.erledigen({ id: 'cp-1' });
			await lauf;
		};
		lokal = p('wind', 'gust', 'rain');
		tabelle.mitgefuehrt();
		await einmal(() => {
			lokal = p('wind', 'gust', 'rain', 'snow');
			tabelle.mitgefuehrt();
		});
		assert.equal(tabelle.ungespeichert, true);
		await einmal(() => {});
		assert.equal(tabelle.ungespeichert, false);
	});

	test('ohne Änderung dazwischen gilt der gesendete Stand als gespeichert und die Karte lädt neu', async () => {
		const t = aufbau();
		await speichernMitAenderungDazwischen(t, () => {});
		assert.equal(t.tabelle.ungespeichert, false);
		assert.equal(offen(t.c, 'GET', '/placements').length, 1, 'frisches GET nach dem Speichern');
	});

	test('Antworten in umgekehrter Reihenfolge: die ältere Marke setzt den gespeicherten Stand nicht zurück (F-L8-1)', async () => {
		const c = client();
		let lokal: Placements = p('wind', 'gust');
		const tabelle = erstelleTabellenSpeicherung({ client: c, kind: 'route', id: 't-1', saveController: controller(), placements: () => structuredClone(lokal), uebernehmen: () => {} });
		lokal = p('wind', 'gust', 'rain');
		tabelle.mitgefuehrt();
		const a = tabelle.zumMitsenden(true);
		lokal = p('wind', 'gust', 'rain', 'snow');
		tabelle.mitgefuehrt();
		const b = tabelle.zumMitsenden(true);
		assert.deepEqual(ids(a), ['wind', 'gust', 'rain']);
		assert.deepEqual(ids(b), ['wind', 'gust', 'rain', 'snow']);
		// Die Antwort des jüngeren PUT (B) kommt zuerst, die des älteren (A) danach.
		tabelle.nachReiterSpeichern(b);
		assert.equal(tabelle.ungespeichert, false, 'B (jüngster Stand) ist gespeichert');
		tabelle.nachReiterSpeichern(a);
		assert.equal(tabelle.ungespeichert, false, 'die spätere Antwort mit älterer Marke fällt nicht auf A zurück');
		// Kein Rückfall: eine weitere Änderung ist ungespeichert, bis ihr eigener Stand bestätigt ist.
		lokal = p('wind');
		tabelle.mitgefuehrt();
		const d = tabelle.zumMitsenden(true);
		assert.equal(tabelle.ungespeichert, true, 'neue Änderung ist ungespeichert');
		tabelle.nachReiterSpeichern(a);
		assert.equal(tabelle.ungespeichert, true, 'eine alte Bestätigung speichert die neue Änderung nicht');
		tabelle.nachReiterSpeichern(d);
		assert.equal(tabelle.ungespeichert, false, 'ihr eigener Stand ist gespeichert');
	});
});
