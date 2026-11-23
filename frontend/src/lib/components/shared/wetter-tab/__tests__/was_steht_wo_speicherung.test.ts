// TDD RED — Issue #3122 Scheibe B3b: Speichern der Karte „Was steht wo“ (Spec Teil B Nr. 13, AC-20, AC-29).
//
//   Tabelle: jede Änderung -> PUT /api/briefings/{id}/placements?kind=… mit dem VOLLSTÄNDIGEN Stand, gelesen
//   erst beim Senden; danach frisches GET. Schnelle Folgeänderungen überholen sich nicht: kein verlorener
//   Klick, nie ein älterer Stand über einem neueren. 412 -> Konflikt melden, aktuellen Stand laden, Fehler
//   weiterwerfen (der Hub-Controller zeigt „Konflikt“). Anderer Fehler -> melden, gespeicherten Stand laden.
//   Schalter unter der Tabelle: nur geänderte Felder an ihrem heutigen Ort (Trip report_config bzw.
//   display_config.show_night_block, Orte hourly_enabled bzw. display_config.telegram_style).
//
// Reine Logik: shared/wetter-tab/wasStehtWoSpeicherung.ts, mit einem Schreib-Client im Speicher (kein Netz).
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/was_steht_wo_speicherung.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { erstelleTabellenSpeicherung, erstelleFelderSpeicherung, felderNutzlast, type Felder } from '../wasStehtWoSpeicherung.ts';
import type { Placements, PlacementsAntwort } from '../wasStehtWoStand.ts';

type Aufruf = { methode: 'GET' | 'PUT'; pfad: string; rumpf?: unknown; erledigen: (wert?: unknown) => void; scheitern: (e: unknown) => void };

/** Client, dessen Antworten der Test einzeln freigibt (Reihenfolge der Antworten steuerbar). */
function client() {
	const aufrufe: Aufruf[] = [];
	const neu = (methode: 'GET' | 'PUT', pfad: string, rumpf?: unknown) =>
		new Promise<any>((erledigen, scheitern) => aufrufe.push({ methode, pfad, rumpf: rumpf === undefined ? undefined : JSON.parse(JSON.stringify(rumpf)), erledigen, scheitern }));
	return {
		aufrufe,
		get: <T>(pfad: string) => neu('GET', pfad) as Promise<T>,
		put: <T>(pfad: string, rumpf: unknown) => neu('PUT', pfad, rumpf) as Promise<T>
	};
}
/** Controller mit Entprellung: der zuletzt gemeldete Vorgang je Besitzer läuft erst bei `los()`. */
function controller() {
	const offen = new Map<string, (init?: RequestInit) => Promise<void>>();
	const fehler: unknown[] = [];
	return {
		fehler,
		schedule(fn: (init?: RequestInit) => Promise<void>, _ms?: number, owner = '') {
			offen.set(owner, fn);
		},
		async los() {
			const fns = [...offen.values()];
			offen.clear();
			await Promise.all(fns.map((f) => f().catch((e) => void fehler.push(e))));
		}
	};
}
const ruhe = () => new Promise((r) => setTimeout(r, 0));
const p = (...ids: string[]): Placements => ({ version: 1, rows: ids.map((metric_id) => ({ metric_id })) });
const a = (stand: Placements): PlacementsAntwort => ({ placements: stand, rows: [] }) as unknown as PlacementsAntwort;

function aufbau() {
	const c = client();
	const ctl = controller();
	let stand = p('wind', 'gust');
	const uebernommen: PlacementsAntwort[] = [];
	const meldungen: string[] = [];
	const s = erstelleTabellenSpeicherung({
		client: c,
		kind: 'vergleich',
		id: 'cp-1',
		saveController: ctl,
		placements: () => stand,
		uebernehmen: (x) => uebernommen.push(x),
		gemeldet: (art) => meldungen.push(art)
	});
	return { c, ctl, s, uebernommen, meldungen, setze: (x: Placements) => (stand = x) };
}

describe('Tabelle: Reihenfolge der Speichervorgänge', () => {
	test('PUT auf den Pfad der Tabelle mit dem Stand beim Senden, danach frisches GET', async () => {
		const t = aufbau();
		t.s.aenderung();
		t.setze(p('gust', 'wind'));
		void t.ctl.los();
		await ruhe();
		const put = t.c.aufrufe[0];
		assert.equal(put.methode, 'PUT');
		assert.equal(put.pfad, '/api/briefings/cp-1/placements?kind=vergleich');
		assert.deepEqual(put.rumpf, p('gust', 'wind'), 'gelesen beim Senden, nicht beim Melden');
		put.erledigen({});
		await ruhe();
		const get = t.c.aufrufe[1];
		assert.equal(get?.methode, 'GET');
		assert.equal(get.pfad, '/api/briefings/cp-1/placements?kind=vergleich');
		get.erledigen(a(p('gust', 'wind')));
		await ruhe();
		assert.equal(t.uebernommen.length, 1);
	});

	test('Klick während des PUT geht nicht verloren: kein Zurückspringen, zweiter PUT trägt beide Änderungen', async () => {
		const t = aufbau();
		t.s.aenderung();
		t.setze(p('wind'));
		void t.ctl.los();
		await ruhe();
		// zweiter Klick, während der erste PUT unterwegs ist
		t.setze(p());
		t.s.aenderung();
		t.c.aufrufe[0].erledigen({});
		await ruhe();
		assert.equal(t.c.aufrufe.filter((x) => x.methode === 'GET').length, 0, 'kein GET über ungesendete Änderung');
		void t.ctl.los();
		await ruhe();
		const zweiter = t.c.aufrufe[1];
		assert.equal(zweiter.methode, 'PUT');
		assert.deepEqual(zweiter.rumpf, p());
		zweiter.erledigen({});
		await ruhe();
		t.c.aufrufe[2].erledigen(a(p()));
		await ruhe();
		assert.deepEqual(t.uebernommen.map((x) => x.placements), [p()]);
	});

	test('GET, das nach einem Klick zurückkommt, wird verworfen (lokaler Stand ist neuer)', async () => {
		const t = aufbau();
		t.s.aenderung();
		void t.ctl.los();
		await ruhe();
		t.c.aufrufe[0].erledigen({});
		await ruhe();
		t.s.aenderung(); // Klick, während das GET läuft
		t.c.aufrufe[1].erledigen(a(p('alt')));
		await ruhe();
		assert.equal(t.uebernommen.length, 0);
	});

	test('ein älteres GET überschreibt nie ein neueres', async () => {
		const t = aufbau();
		const erstes = t.s.laden();
		const zweites = t.s.laden();
		t.c.aufrufe[1].erledigen(a(p('neu')));
		await zweites;
		t.c.aufrufe[0].erledigen(a(p('alt')));
		await erstes;
		assert.deepEqual(t.uebernommen.map((x) => x.placements), [p('neu')]);
	});

	test('ohne Änderung schreibt der Vorgang nichts (auch nicht beim Wiederholen nach Konflikt)', async () => {
		const t = aufbau();
		const fns: Array<() => Promise<void>> = [];
		const s = erstelleTabellenSpeicherung({ client: t.c, kind: 'route', id: 'gr', saveController: { schedule: (fn) => void fns.push(fn) }, placements: () => p('x'), uebernehmen: () => {} });
		s.aenderung();
		const fn = fns[0];
		const lauf = fn();
		await ruhe();
		t.c.aufrufe[0].erledigen({});
		await lauf;
		await ruhe();
		const vorher = t.c.aufrufe.filter((x) => x.methode === 'PUT').length;
		await fn();
		assert.equal(t.c.aufrufe.filter((x) => x.methode === 'PUT').length, vorher, 'zweiter Lauf ohne Änderung: kein PUT');
	});
});

describe('Tabelle: Konflikt und Fehler (AC-20)', () => {
	test('412: Konflikt melden, aktuellen Stand laden und übernehmen, Fehler an den Controller', async () => {
		const t = aufbau();
		t.s.aenderung();
		const lauf = t.ctl.los();
		await ruhe();
		t.c.aufrufe[0].scheitern({ status: 412, error: 'precondition_failed' });
		await lauf;
		await ruhe();
		assert.deepEqual(t.meldungen, ['konflikt']);
		assert.equal((t.ctl.fehler[0] as { status: number }).status, 412, 'der Controller sieht den 412 (Hub-Konfliktmuster)');
		const get = t.c.aufrufe[1];
		assert.equal(get.methode, 'GET');
		get.erledigen(a(p('fremd')));
		await ruhe();
		assert.deepEqual(t.uebernommen.map((x) => x.placements), [p('fremd')]);
		assert.equal(t.s.ungespeichert, false, 'die eigene Änderung ist verworfen');
	});
	test('anderer Fehler: melden und auf den gespeicherten Stand zurücksetzen', async () => {
		const t = aufbau();
		t.s.aenderung();
		const lauf = t.ctl.los();
		await ruhe();
		t.c.aufrufe[0].scheitern({ status: 500 });
		await lauf;
		await ruhe();
		assert.deepEqual(t.meldungen, ['fehler']);
		t.c.aufrufe[1].erledigen(a(p('gespeichert')));
		await ruhe();
		assert.deepEqual(t.uebernommen.map((x) => x.placements), [p('gespeichert')]);
	});
	test('nach fremdem Speichern (Reiter Wetter) frisch laden, aber nie über ungespeicherte Änderung', async () => {
		const t = aufbau();
		t.s.nachFremdemSpeichern();
		assert.equal(t.c.aufrufe[0]?.methode, 'GET');
		t.s.aenderung();
		const zahl = t.c.aufrufe.length;
		t.s.nachFremdemSpeichern();
		assert.equal(t.c.aufrufe.length, zahl, 'ungespeicherte Änderung: kein GET');
	});
});

describe('Schalter unter der Tabelle: nur geänderte Felder am heutigen Ort', () => {
	const trip: Felder = { show_stage_stats: true, show_yesterday_comparison: true, show_night_block: true, email_format: 'full', telegram_style: 'rich', hourly_enabled: true };
	test('Trip: report_config und display_config.show_night_block', () => {
		assert.deepEqual(felderNutzlast('route', { ...trip, show_stage_stats: false }, trip), { report_config: { show_stage_stats: false } });
		assert.deepEqual(felderNutzlast('route', { ...trip, show_night_block: false, email_format: 'compact' }, trip), {
			report_config: { email_format: 'compact' },
			display_config: { show_night_block: false }
		});
		assert.deepEqual(felderNutzlast('route', { ...trip, telegram_style: 'kurzform' }, trip), { report_config: { telegram_style: 'kurzform' } });
		assert.deepEqual(felderNutzlast('route', trip, trip), {});
	});
	test('Orte: hourly_enabled oben, telegram_style in display_config; Trip-Felder nie', () => {
		assert.deepEqual(felderNutzlast('vergleich', { ...trip, hourly_enabled: false }, trip), { hourly_enabled: false });
		assert.deepEqual(felderNutzlast('vergleich', { ...trip, telegram_style: 'kurzform' }, trip), { display_config: { telegram_style: 'kurzform' } });
		assert.deepEqual(felderNutzlast('vergleich', { ...trip, show_stage_stats: false }, trip), {});
	});
	test('zwei schnelle Schalter: ein PUT mit beiden, Pfad je Fläche, danach Bezug = gesendeter Stand', async () => {
		const c = client();
		const ctl = controller();
		const antworten: unknown[] = [];
		const f = erstelleFelderSpeicherung({ client: c, kind: 'route', id: 'gr', saveController: ctl, start: trip, onAntwort: (x) => antworten.push(x) });
		f.melden({ ...trip, show_stage_stats: false });
		f.melden({ ...trip, show_stage_stats: false, show_yesterday_comparison: false });
		const lauf = ctl.los();
		await ruhe();
		assert.equal(c.aufrufe.length, 1);
		assert.equal(c.aufrufe[0].pfad, '/api/trips/gr');
		assert.deepEqual(c.aufrufe[0].rumpf, { report_config: { show_stage_stats: false, show_yesterday_comparison: false } });
		c.aufrufe[0].erledigen({ id: 'gr' });
		await lauf;
		assert.deepEqual(antworten, [{ id: 'gr' }]);
		f.melden({ ...trip, show_stage_stats: false, show_yesterday_comparison: false, show_night_block: false });
		const lauf2 = ctl.los();
		await ruhe();
		assert.deepEqual(c.aufrufe[1].rumpf, { display_config: { show_night_block: false } });
		c.aufrufe[1].erledigen({});
		await lauf2;
	});
	test('Fix-Loop F1: Fehler -> Rückmeldung mit gespeichertem Stand; der nächste Schalter schreibt die gescheiterte Änderung nicht mit', async () => {
		const c = client();
		const ctl = controller();
		const fehler: Array<{ status?: number; stand: Felder }> = [];
		const f = erstelleFelderSpeicherung({
			client: c, kind: 'route', id: 'gr', saveController: ctl, start: trip,
			onFehler: (e, stand) => fehler.push({ status: (e as { status?: number }).status, stand })
		});
		f.melden({ ...trip, show_stage_stats: false });
		const lauf = ctl.los();
		await ruhe();
		c.aufrufe[0].scheitern({ status: 500 });
		await lauf;
		assert.equal(ctl.fehler.length, 1, 'der Controller sieht den Fehler');
		assert.deepEqual(fehler, [{ status: 500, stand: trip }], 'Karte springt auf den gespeicherten Stand zurück');
		// anderer Schalter, ausgehend vom zurückgesetzten Stand der Karte
		f.melden({ ...trip, show_night_block: false });
		const lauf2 = ctl.los();
		await ruhe();
		assert.deepEqual(c.aufrufe[1].rumpf, { display_config: { show_night_block: false } }, 'gescheiterte Änderung fährt nicht still mit');
		c.aufrufe[1].erledigen({});
		await lauf2;
	});
	test('Fix-Loop F1: nach einem Fehler ist der Vorgang ohne neue Meldung leer (Wiederholen schreibt nichts)', async () => {
		const c = client();
		const fns: Array<() => Promise<void>> = [];
		const f = erstelleFelderSpeicherung({ client: c, kind: 'vergleich', id: 'cp', saveController: { schedule: (fn) => void fns.push(fn) }, start: trip });
		f.melden({ ...trip, hourly_enabled: false });
		const lauf = fns[0]().catch(() => {});
		await ruhe();
		c.aufrufe[0].scheitern({ status: 412 });
		await lauf;
		void fns[0]().catch(() => {});
		await ruhe();
		assert.equal(c.aufrufe.length, 1, 'kein zweiter PUT mit dem verworfenen Stand');
	});
	test('Orte: Pfad des Presets', async () => {
		const c = client();
		const ctl = controller();
		const f = erstelleFelderSpeicherung({ client: c, kind: 'vergleich', id: 'cp-9', saveController: ctl, start: trip });
		f.melden({ ...trip, hourly_enabled: false });
		void ctl.los();
		await ruhe();
		assert.equal(c.aufrufe[0].pfad, '/api/compare/presets/cp-9');
	});
});

// #3237 Runde 13: „−“/„+“ des Reiters fährt im PUT des Reiters mit. Ein eigener Tabellen-PUT (anderer Besitzer)
// sendete über den Besitzerwechsel des Controllers den entprellten Reiter-Vorgang vorzeitig (zwei Gesten =
// zwei Schreibvorgänge) und lief bei veraltetem Stempel als erster PUT in den 412 (Reiter-PUT fehlte).
describe('Tabelle: Stand fährt im PUT des Reiters mit', () => {
	test('mitgefuehrt plant keinen eigenen Speichervorgang ein', async () => {
		const t = aufbau();
		const geplant: string[] = [];
		const s = erstelleTabellenSpeicherung({
			client: t.c,
			kind: 'route',
			id: 't-1',
			saveController: { schedule: (_fn, _ms, owner) => void geplant.push(owner ?? '') },
			placements: () => p('wind'),
			uebernehmen: () => {}
		});
		s.mitgefuehrt();
		s.mitgefuehrt();
		await ruhe();
		assert.deepEqual(geplant, [], 'kein Tabellen-Vorgang im Controller');
		assert.equal(t.c.aufrufe.length, 0, 'kein PUT, kein GET');
		assert.equal(s.ungespeichert, true);
	});

	test('ein GET, das vor dem Mitsenden zurückkommt, überschreibt den mitgeführten Stand nicht', async () => {
		const t = aufbau();
		const laeuft = t.s.laden();
		t.s.mitgefuehrt();
		t.c.aufrufe[0].erledigen(a(p('alt')));
		await laeuft;
		assert.equal(t.uebernommen.length, 0);
	});

	test('nach erfolgreichem Reiter-PUT gilt der mitgesendete Stand als gespeichert, die Karte lädt neu', async () => {
		const t = aufbau();
		t.s.mitgefuehrt();
		const gesendet = t.s.zumMitsenden(true);
		t.s.nachFremdemSpeichern();
		assert.equal(t.c.aufrufe.length, 0, 'vor dem Speichern kein GET über den ungespeicherten Stand');
		t.s.nachReiterSpeichern(gesendet);
		assert.equal(t.s.ungespeichert, false);
		assert.equal(t.c.aufrufe[0]?.methode, 'GET');
		void t.ctl.los();
		await ruhe();
		assert.equal(t.c.aufrufe.filter((x) => x.methode === 'PUT').length, 0, 'kein Tabellen-PUT hinterher');
	});

	test('ein später mitgeführter Stand bleibt ungespeichert, auch wenn ein älterer Reiter-PUT ankommt', () => {
		const t = aufbau();
		t.s.mitgefuehrt();
		const alt = t.s.zumMitsenden(true);
		t.s.mitgefuehrt();
		t.s.nachReiterSpeichern(alt);
		assert.equal(t.s.ungespeichert, true);
	});

	test('ohne gespeicherte Tabelle (AC-3) liefert die Karte nichts zum Mitsenden', () => {
		const t = aufbau();
		t.s.mitgefuehrt();
		assert.equal(t.s.zumMitsenden(false), undefined);
	});
});
