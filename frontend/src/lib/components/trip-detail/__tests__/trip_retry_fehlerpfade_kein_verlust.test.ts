// Fix-Loop 1, Issue #1433 — F001/F003/F004/F005/F006/M27: Fehlerpfade von
// „Nochmal speichern", Seitenaufbau waehrend eines Konflikts, Dedup, null-Felder.
//
// Spec: docs/specs/bugfix/trip_mehrreiter_konfliktschutz.md — AC-3, AC-19, §2.2, §4.4/4.5.
// Gemessen am SERVER-STAND (Fake im Go-Merge-Modus) und an der echten Trip-Seite
// (`tripSeite`, Skript der +page.svelte): der Retry gibt den per GET geholten Trip
// an die Seite, bevor er die Eintraege erneut sendet; scheitert eine Wiederholung
// (500/Netz) oder der GET, bleibt jeder Eintrag erhalten und der Nutzer kann erneut
// „Nochmal speichern" druecken.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/trip-detail/__tests__/trip_retry_fehlerpfade_kein_verlust.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import * as registry from '../../../etagRegistry.ts';
import { clearEtagRegistry, getKnownEtag, istKonflikt } from '../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import * as P from './tripMehrreiterPruefstand.ts';

let server: FakeTripServer;
// Fehlerinjektion VOR dem Ersatz-Server: liefert fuer passende Anfragen 500 (Server-
// Fehler), der Fake-Server sieht sie nicht (kein Schreibvorgang).
let fehler: ((method: string, path: string, init?: RequestInit) => boolean) | null = null;

beforeEach(async () => {
	clearEtagRegistry();
	fehler = null;
	server = createFakeTripServer({ merge: true });
	server.install();
	const fake = globalThis.fetch;
	(globalThis as { fetch: unknown }).fetch = async (input: unknown, init?: RequestInit) => {
		const method = (init?.method ?? 'GET').toUpperCase();
		if (fehler?.(method, String(input), init)) {
			return new Response(JSON.stringify({ error: 'boom', detail: 'Serverfehler' }), {
				status: 500,
				headers: { 'Content-Type': 'application/json' }
			});
		}
		return fake(input as never, init);
	};
	server.seed(P.TRIP_ID, P.vollerTrip());
	await api.get(P.TRIP_PFAD);
});
afterEach(() => server.restore());

const puts = () => server.calls.filter((c) => c.method === 'PUT');
const stand = () => server.stand(P.TRIP_ID);
const dc = () => stand().display_config as Record<string, unknown>;
const levels = () => dc().metric_alert_levels as Record<string, unknown>;

async function konfliktInA(a: P.Aufbau, stufe = 'sensibel') {
	const alarme = await P.alarmeReiter(a);
	alarme.empfindlichkeitAendern('wind', stufe);
	await P.fertig(a.ctl);
	assert.equal(a.ctl.state, 'conflict', 'Vorbedingung: Konflikt');
	return alarme;
}

describe('F001 / AC-19: der Retry gibt den geholten Trip an die Seite, BEVOR er erneut sendet', () => {
	test('onAdopt bekommt den GET-Trip (Fremdaenderung) vor dem ersten Wiederholungs-PUT, danach ein Abschluss-Signal', async () => {
		server.foreignWrite(P.TRIP_ID, { name: 'Fremder Name' });
		const a = P.neuerAufbau();
		await konfliktInA(a);

		const log: Array<{ phase: string; name: unknown; at: number }> = [];
		(a.ctl as unknown as { onAdopt: unknown }).onAdopt = (t: Record<string, unknown>, phase: string) => {
			log.push({ phase, name: t?.name, at: performance.now() });
		};
		const putsVorher = puts().length;
		await a.ctl.retryConflict();

		assert.equal(log[0]?.phase, 'geholt', 'zuerst die GET-Fassung');
		assert.equal(log[0]?.name, 'Fremder Name', 'die Seite bekommt den Trip der GET-Antwort');
		const erster = puts()[putsVorher];
		assert.ok(erster, 'Messaufbau: ein Wiederholungs-PUT');
		assert.ok(log[0].at <= erster.startedAt, 'AC-19: erst Trip an die Seite, DANN die eigenen Aenderungen senden');
		assert.equal(log.at(-1)?.phase, 'wiederholt', 'nach vollstaendigem Erfolg meldet der Retry den Abschluss');
	});

	test('Seite: scheitern alle Wiederholungen mit 500, steht `trip` auf GET-Stand ⊕ Eingaben, OHNE Neuaufbau der Reiter; die Eingabe bleibt im Reiter und in der Liste', async () => {
		server.foreignWrite(P.TRIP_ID, { name: 'Fremder Name', display_config: { metric_alert_levels: { wind: 'ruhig', precipitation: 'sensibel' } } });
		const a = P.neuerAufbau();
		const alarme = await konfliktInA(a); // A (alter Stand) wollte wind → sensibel
		const seite = await P.tripSeite(a, server);

		fehler = (m) => m === 'PUT';
		await a.ctl.retryConflict();
		assert.equal(a.ctl.state, 'conflict', 'F004: eine gescheiterte Wiederholung hinterlaesst keinen stillen Fehler — der Knopf bleibt');
		assert.equal(levels().wind, 'ruhig', 'Vorbedingung: nichts geschrieben');
		const tripLevels = (seite.trip().display_config as Record<string, unknown>).metric_alert_levels as Record<string, unknown>;
		// Fix-Loop 3 (F201): Seitenstand = GET-Stand ⊕ ausstehende Eingaben — Fremdaenderung aus dem
		// GET, die Eingabe von A darueber (sonst zeigte ein neu gemounteter Reiter sie nicht).
		assert.equal(seite.trip().name, 'Fremder Name', 'F001: die Seite fuehrt den Trip der GET-Antwort (Fremdaenderung), nicht den veralteten Altstand');
		assert.equal(tripLevels.wind, 'sensibel', 'F201: ueber dem GET-Stand liegt die ausstehende Eingabe von A');
		assert.equal(seite.inst.u.uebernommeneFassung, 0, 'F101/Regel 1: bei \'geholt\' (und Teil-/Fehlschlag) KEIN Neuaufbau der Reiter');
		assert.equal(alarme.inst.u.routeMetricLevels.wind, 'sensibel', 'die sichtbare Eingabe im Reiter bleibt');

		fehler = null;
		await a.ctl.retryConflict();
		assert.equal(levels().wind, 'sensibel', 'F004: der Eintrag von A blieb in der Liste und wird jetzt geschrieben');
		assert.equal(a.ctl.state, 'idle');
		assert.equal(istKonflikt(P.TRIP_ID), false);
		assert.equal(seite.inst.u.uebernommeneFassung, 1, 'F103: nach VOLLEM Erfolg baut die Seite die Reiter einmal neu auf');
	});
});

describe('F101 (Regel 2): was der Nutzer zuletzt sah und gespeichert hat, gewinnt', () => {
	test('(a) Retry scheitert 500, derselbe Reiter speichert danach mit 412 ⇒ Eingabe bleibt erhalten, kein „Gespeichert"; Nochmal speichern schreibt sie', async () => {
		server.foreignWrite(P.TRIP_ID, { display_config: { metric_alert_levels: { wind: 'ruhig', precipitation: 'ruhig' } } });
		const a = P.neuerAufbau();
		const alarme = await konfliktInA(a); // wind → sensibel
		await P.tripSeite(a, server);
		fehler = (m) => m === 'PUT';
		await a.ctl.retryConflict();
		fehler = null;
		assert.equal(a.ctl.state, 'conflict');

		server.foreignWrite(P.TRIP_ID, { name: 'Zweiter Fremder' }); // der Stempel des GET ist wieder veraltet
		alarme.empfindlichkeitAendern('precipitation', 'sensibel');
		await P.fertig(a.ctl);
		assert.equal(a.ctl.state, 'conflict', 'der 412 zeigt „Nochmal speichern", NIE „Gespeichert" ohne Server-Stand');
		assert.equal(levels().wind, 'ruhig', 'Vorbedingung: noch nichts geschrieben');

		await a.ctl.retryConflict();
		assert.equal(levels().wind, 'sensibel', 'die ERSTE Eingabe (wind) ging nicht verloren');
		assert.equal(levels().precipitation, 'sensibel', 'und die zweite auch nicht');
		assert.equal(stand().name, 'Zweiter Fremder');
		assert.equal(a.ctl.state, 'idle');
	});

	// Fix-Loop 4 (F301a) AENDERT diese Zusicherung bewusst: nach einem gescheiterten Retry traegt
	// die Registry wieder den Stempel von VOR dem GET — ein Save des (veralteten) offenen Reiters
	// bekommt 412 statt 200 (sonst ueberschriebe er die Fremdaenderung, PX3). Der neuere Rumpf
	// ersetzt den alten Eintrag (Dedup), „Nochmal speichern" schreibt ihn, danach nichts mehr.
	test('(b) Retry scheitert 500, derselbe Reiter speichert danach ⇒ 412 (Konflikt bleibt), neuerer Rumpf ersetzt den Eintrag, Nochmal speichern schreibt ihn, kein Altstand darueber', async () => {
		server.foreignWrite(P.TRIP_ID, { display_config: { metric_alert_levels: { wind: 'ruhig', precipitation: 'ruhig' } } });
		const a = P.neuerAufbau();
		const alarme = await konfliktInA(a); // wind → sensibel (alter Rumpf)
		fehler = (m) => m === 'PUT';
		await a.ctl.retryConflict();
		fehler = null;

		alarme.empfindlichkeitAendern('wind', 'maessig'); // neuere Eingabe, Stempel von vor dem GET ⇒ 412
		await P.fertig(a.ctl);
		assert.equal(puts().at(-1)!.status, 412);
		assert.equal(levels().wind, 'ruhig', 'Server unveraendert');
		assert.equal(a.ctl.state, 'conflict');
		assert.equal(istKonflikt(P.TRIP_ID), true);

		await a.ctl.retryConflict();
		assert.equal(puts().at(-1)!.status, 200);
		assert.equal(levels().wind, 'maessig', 'die neuere Eingabe gewinnt, nicht der alte Rumpf (sensibel)');
		assert.equal(a.ctl.state, 'idle');
		assert.equal(istKonflikt(P.TRIP_ID), false);

		const vorher = puts().length;
		await a.ctl.retryConflict();
		assert.equal(puts().length, vorher, 'es gibt nichts mehr zu wiederholen');
		assert.equal(levels().wind, 'maessig', 'kein Altstand ueber der neueren Eingabe');
	});

	test('(b2) bei einem zweiten offenen Eintrag bleibt der Konflikt, der erneuerte Reiter wird nicht mit dem Altstand ueberspielt', async () => {
		server.foreignWrite(P.TRIP_ID, { name: 'Fremder Name' });
		const a = P.neuerAufbau();
		const alarme = await konfliktInA(a);
		const b = await P.versandReiter(a);
		b.aendern({ morning_time: '08:00:00' });
		await P.fertig(a.ctl);
		fehler = (m) => m === 'PUT';
		await a.ctl.retryConflict();
		fehler = null;

		alarme.empfindlichkeitAendern('wind', 'maessig');
		await P.fertig(a.ctl);
		assert.equal(a.ctl.state, 'conflict', 'Versand (B) ist weiter offen');
		await a.ctl.retryConflict();
		assert.equal(levels().wind, 'maessig', 'A: die neuere Eingabe gewinnt');
		assert.equal((stand().report_config as Record<string, unknown>).morning_time, '08:00:00', 'B wird gesendet');
	});
});

describe('F104: Retry-Fehlerpfad und Abschluss-Signal', () => {
	test('N5: scheitert die Wiederholung (500), bleibt die Konflikt-Markierung gesetzt (der Unload-Flush traegt If-Match)', async () => {
		server.foreignWrite(P.TRIP_ID, { name: 'Fremder Name' });
		const a = P.neuerAufbau();
		await konfliktInA(a);
		fehler = (m) => m === 'PUT';
		await a.ctl.retryConflict();
		assert.equal(istKonflikt(P.TRIP_ID), true, 'ohne Markierung ginge der naechste keepalive-Flush ohne If-Match raus');
	});

	test('N8: bei Teilerfolg (ein Eintrag 500) kommt KEIN \'wiederholt\'-Signal', async () => {
		server.foreignWrite(P.TRIP_ID, { name: 'Fremder Name' });
		const a = P.neuerAufbau();
		await konfliktInA(a);
		const b = await P.versandReiter(a);
		b.aendern({ morning_time: '08:00:00' });
		await P.fertig(a.ctl);
		const phasen: string[] = [];
		(a.ctl as unknown as { onAdopt: unknown }).onAdopt = (_t: unknown, phase: string) => phasen.push(phase);
		fehler = (m, _p, init) => m === 'PUT' && String(init?.body).includes('metric_alert_levels');
		await a.ctl.retryConflict();
		assert.equal(a.ctl.state, 'conflict');
		assert.deepEqual(phasen, ['geholt']);
	});
});

describe('F004: scheitert der Retry-GET, bleibt die Liste vollstaendig', () => {
	test('GET 500 im Retry ⇒ Konflikt-Anzeige und Markierung bleiben; der naechste Retry sendet BEIDE Saetze', async () => {
		server.foreignWrite(P.TRIP_ID, { name: 'Fremder Name' });
		const a = P.neuerAufbau();
		await konfliktInA(a);
		const b = await P.versandReiter(a);
		b.aendern({ morning_time: '08:00:00' });
		await P.fertig(a.ctl);

		fehler = (m) => m === 'GET';
		await a.ctl.retryConflict();
		assert.equal(a.ctl.state, 'conflict', 'nach GET-Fehler weiter „Nochmal speichern"');
		assert.equal(istKonflikt(P.TRIP_ID), true, 'die Markierung bleibt, solange kein frischer GET vorliegt');
		assert.notEqual(levels().wind, 'sensibel');

		fehler = null;
		await a.ctl.retryConflict();
		assert.equal(a.ctl.state, 'idle');
		assert.equal(levels().wind, 'sensibel', 'A ging nicht verloren');
		assert.equal((stand().report_config as Record<string, unknown>).morning_time, '08:00:00', 'B ging nicht verloren');
		assert.equal(stand().name, 'Fremder Name');
	});

	test('ein Wiederholungs-PUT scheitert mit 500: nur dieser Eintrag bleibt in der Liste, der andere geht durch', async () => {
		const a = P.neuerAufbau();
		server.foreignWrite(P.TRIP_ID, { name: 'Fremder Name' });
		await konfliktInA(a);
		const b = await P.versandReiter(a);
		b.aendern({ morning_time: '08:00:00' });
		await P.fertig(a.ctl);

		fehler = (m, _p, init) => m === 'PUT' && String(init?.body).includes('metric_alert_levels');
		await a.ctl.retryConflict();
		assert.equal((stand().report_config as Record<string, unknown>).morning_time, '08:00:00', 'B ging beim ersten Retry durch');
		assert.equal(a.ctl.state, 'conflict', 'A scheiterte (500) ⇒ weiter „Nochmal speichern"');
		fehler = null;
		await a.ctl.retryConflict();
		assert.equal(levels().wind, 'sensibel', 'der gescheiterte Eintrag (A) wurde erneut gesendet');
		assert.equal((stand().report_config as Record<string, unknown>).morning_time, '08:00:00');
	});
});

describe('F005: Dedup — derselbe Reiter speichert zweimal waehrend des Konflikts', () => {
	test('ein Listeneintrag mit dem NEUESTEN Rumpf, genau ein Wiederholungs-PUT', async () => {
		server.foreignWrite(P.TRIP_ID, { name: 'Fremder Name' });
		const a = P.neuerAufbau();
		const alarme = await konfliktInA(a, 'sensibel');
		alarme.empfindlichkeitAendern('wind', 'ruhig');
		await P.fertig(a.ctl);
		assert.equal(a.ctl.state, 'conflict');

		const vorher = puts().length;
		await a.ctl.retryConflict();
		const retry = puts().slice(vorher);
		assert.equal(retry.length, 1, `genau ein Eintrag je Reiter, gesehen: ${retry.length} Wiederholungs-PUTs`);
		assert.equal(levels().wind, 'ruhig', 'der NEUESTE Rumpf wird gesendet');
	});
});

describe('F003: ein frischer Seitenaufbau beendet den Konflikt dieser Ressource', () => {
	test('Konflikt, Navigation weg und zurueck (neuer Page-Load): Markierung weg, Stempel uebernommen, Speichern ohne falsches 412', async () => {
		server.foreignWrite(P.TRIP_ID, { name: 'Fremder Name' });
		const a = P.neuerAufbau();
		await konfliktInA(a);
		assert.equal(istKonflikt(P.TRIP_ID), true);

		// neuer Page-Load: Trip und Stempel kommen gemeinsam vom Server
		const frisch = { id: P.TRIP_ID, ...stand() };
		const b = P.neuerAufbau(frisch);
		await P.tripSeite(b, server, server.etagOf(P.TRIP_ID));
		assert.equal(istKonflikt(P.TRIP_ID), false, 'der Seitenaufbau loescht die Konflikt-Markierung');
		assert.equal(getKnownEtag(P.TRIP_ID), server.etagOf(P.TRIP_ID), 'und uebernimmt den Stempel');

		const alarme = await P.alarmeReiter(b);
		alarme.empfindlichkeitAendern('wind', 'sensibel');
		await P.fertig(b.ctl);
		assert.equal(puts().at(-1)!.status, 200, 'kein falsches 412 nach dem Neuaufbau');
		assert.equal(levels().wind, 'sensibel');
		assert.equal(stand().name, 'Fremder Name');
	});

	test('Registry: adoptEtagFromPageLoad allein bleibt unveraendert (re-laufendes load() bei offenem Konflikt adoptiert nichts)', async () => {
		const a = P.neuerAufbau();
		server.foreignWrite(P.TRIP_ID, { name: 'Fremder Name' });
		await konfliktInA(a);
		const alt = getKnownEtag(P.TRIP_ID);
		assert.equal(registry.adoptEtagFromPageLoad(P.TRIP_ID, server.etagOf(P.TRIP_ID)), false);
		assert.equal(getKnownEtag(P.TRIP_ID), alt);
		assert.equal(istKonflikt(P.TRIP_ID), true);
	});
});

describe('F105: Server-Rendering beschreibt die nutzeruebergreifend geteilte Registry nicht', () => {
	test('im SSR-Prozess (browser=false) uebernimmt der Seitenkopf keinen Stempel; im Browser schon', async () => {
		const a = P.neuerAufbau();
		clearEtagRegistry();
		await P.tripSeite(a, server, server.etagOf(P.TRIP_ID), false);
		assert.equal(getKnownEtag(P.TRIP_ID), undefined, 'SSR: Registry bleibt unberuehrt');
		await P.tripSeite(a, server, server.etagOf(P.TRIP_ID), true);
		assert.equal(getKnownEtag(P.TRIP_ID), server.etagOf(P.TRIP_ID), 'Browser: Stempel uebernommen');
	});
});

describe('M27: Pausieren — trip und Stempel nie nur eines von beiden', () => {
	test('aendert ein anderer Vorgang den Eintrag waehrend des GET, wird der GET-Trip NICHT uebernommen', async () => {
		server.restore();
		server = createFakeTripServer({
			merge: true,
			latencyMs: (m) => (m === 'PATCH' ? 40 : m === 'GET' ? 80 : 0)
		});
		server.install();
		server.seed(P.TRIP_ID, P.vollerTrip());
		await api.get(P.TRIP_PFAD);
		const a = P.neuerAufbau();
		const seite = await P.tripSeite(a, server);

		const lauf = seite.pausieren();
		await new Promise((r) => setTimeout(r, 15));
		server.foreignWrite(P.TRIP_ID, { name: 'Fremder Name' }); // nach PATCH-Ankunft, vor GET-Ankunft
		await new Promise((r) => setTimeout(r, 70)); // GET laeuft (Antwort unterwegs)
		registry.setKnownEtag(P.TRIP_ID, server.etagOf(P.TRIP_ID)); // anderer Vorgang beruehrt den Eintrag
		await lauf;

		assert.ok(seite.trip().paused_at, 'der neue Status ist uebernommen');
		assert.notEqual(seite.trip().name, 'Fremder Name', 'GET-Trip ohne passenden Stempel wird nicht uebernommen');
	});
});

describe('F006 / M23: nie eingestellte Wetter-Felder werden weggelassen, nicht als null gesendet', () => {
	test('outlook_metrics === null ⇒ kein outlook_metrics-Schluessel in irgendeinem PUT-Rumpf', async () => {
		const a = P.neuerAufbau();
		const w = await P.wetterMetrikenReiter(a);
		w.inst.u.outlookMetricKeysRoute = null;
		w.inst.u.outlookMetricFormatsRoute = null;
		w.metrikenSpeichern();
		await P.fertig(a.ctl);
		const geschrieben = puts();
		assert.ok(geschrieben.length > 0, 'Messaufbau: es wurde gespeichert');
		for (const p of geschrieben) {
			const body = (p.anfrage ?? {}) as Record<string, unknown>;
			const d = (p.path.includes('/weather-config') ? body : (body.display_config ?? {})) as Record<string, unknown>;
			assert.equal('outlook_metrics' in d, false, `PUT ${p.path}: outlook_metrics darf nicht gesendet werden`);
			assert.equal('outlook_metric_formats' in d, false, `PUT ${p.path}: outlook_metric_formats darf nicht gesendet werden`);
		}
		assert.deepEqual(dc().outlook_metrics, ['temp_max_c'], 'Bestand unveraendert');
	});
});

describe('F301a (Fix-Loop 4): ein GESCHEITERTER Retry laesst keinen Save mit veraltetem Reiterstand durch', () => {
	test('PX3: Fremd alert_cooldown_minutes=99, Retry 500, Speichern im weiter offenen Alarme-Reiter => 412, Server bleibt 99, Konflikt-Anzeige bleibt', async () => {
		server.foreignWrite(P.TRIP_ID, { alert_cooldown_minutes: 99, name: 'Fremder Name' });
		const a = P.neuerAufbau();
		const alarme = await konfliktInA(a);
		await P.tripSeite(a, server);

		fehler = (m) => m === 'PUT';
		await a.ctl.retryConflict();
		fehler = null;
		assert.equal(a.ctl.state, 'conflict');
		assert.equal(istKonflikt(P.TRIP_ID), true, 'die Markierung bleibt nach dem gescheiterten Retry');

		alarme.empfindlichkeitAendern('precipitation', 'ruhig');
		await P.fertig(a.ctl);
		assert.equal(stand().alert_cooldown_minutes, 99, 'die Fremdaenderung wird NICHT mit dem Reiter-Altstand ueberschrieben');
		assert.notEqual(levels().precipitation, 'ruhig', 'der Save des veralteten Reiters wurde abgelehnt');
		assert.equal(a.ctl.state, 'conflict', 'kein „Gespeichert"');

		await a.ctl.retryConflict();
		assert.equal(a.ctl.state, 'idle');
		// Der Retry sendet den ganzen Eigenfeld-Satz des Reiters (ADR-0036, Teilfeld je Reiter) —
		// ein Fremdwert in DERSELBEN Gruppe (cooldown) wird dort bewusst ueberschrieben, einer
		// ausserhalb (name) bleibt.
		assert.equal(stand().name, 'Fremder Name', 'Fremdaenderung ausserhalb der Reiter-Gruppe bleibt');
		assert.equal(levels().wind, 'sensibel', 'erste Eingabe auf dem Server');
		assert.equal(levels().precipitation, 'ruhig', 'zweite Eingabe auf dem Server');
	});

	test('Teil-Erfolg: erster Eintrag geht durch, zweiter scheitert => danach 412 fuer einen Save aus dem offenen Reiter; Liste vollstaendig', async () => {
		server.foreignWrite(P.TRIP_ID, { alert_cooldown_minutes: 99, name: 'Fremder Name' });
		const a = P.neuerAufbau();
		const alarme = await konfliktInA(a);
		const versand = await P.versandReiter(a);
		versand.aendern({ morning_time: '08:00:00' });
		await P.fertig(a.ctl);

		let n = 0;
		fehler = (m) => m === 'PUT' && ++n === 2; // erster Wiederholungs-PUT ok, zweiter 500
		await a.ctl.retryConflict();
		fehler = null;
		assert.equal(a.ctl.state, 'conflict');
		assert.equal(istKonflikt(P.TRIP_ID), true);

		const vorher = stand().alert_cooldown_minutes;
		alarme.empfindlichkeitAendern('precipitation', 'ruhig');
		await P.fertig(a.ctl);
		assert.equal(stand().alert_cooldown_minutes, vorher, 'kein stiller Altstand-Save');
		assert.equal(a.ctl.state, 'conflict');

		await a.ctl.retryConflict();
		assert.equal(a.ctl.state, 'idle');
		assert.equal(stand().name, 'Fremder Name');
		assert.equal(levels().wind, 'sensibel');
		assert.equal(levels().precipitation, 'ruhig');
		assert.equal((stand().report_config as Record<string, unknown>).morning_time, '08:00:00');
	});

	test('F501 Teil-Erfolg: ein NIE gespeicherter, veralteter Reiter bekommt danach 412 — Fremdaenderung bleibt, Eingabe nicht still geschrieben', async () => {
		server.foreignWrite(P.TRIP_ID, { name: 'Fremder Name', report_config: { day_window_end_hour: 21 } });
		const a = P.neuerAufbau();
		await P.tripSeite(a, server);
		const wm = await P.wetterMetrikenReiter(a); // veralteter Reiter, bisher nie gespeichert
		const alarme = await P.alarmeReiter(a);
		alarme.empfindlichkeitAendern('wind', 'sensibel');
		await P.fertig(a.ctl);
		assert.equal(a.ctl.state, 'conflict', 'Vorbedingung: Konflikt');
		const versand = await P.versandReiter(a);
		versand.aendern({ morning_time: '08:00:00' });
		await P.fertig(a.ctl);

		let n = 0;
		fehler = (m) => m === 'PUT' && ++n === 2; // erster Wiederholungs-PUT ok, zweiter 500
		await a.ctl.retryConflict();
		fehler = null;
		assert.equal(a.ctl.state, 'conflict');
		assert.equal(istKonflikt(P.TRIP_ID), true);

		const rc = () => stand().report_config as Record<string, unknown>;
		wm.reportConfigSpeichern({ show_outlook: false });
		await P.fertig(a.ctl);
		assert.equal(rc().day_window_end_hour, 21, 'Fremdaenderung darf nicht still ueberschrieben werden');
		assert.notEqual(rc().show_outlook, false, 'die Eingabe des veralteten Reiters wurde abgelehnt, nicht still geschrieben');
		assert.equal(a.ctl.state, 'conflict');
	});

	test('F502 Konflikt OHNE Stempel, Retry scheitert: Folge-Save traegt If-Match und bekommt 412, Server unveraendert', async () => {
		const a = P.neuerAufbau();
		await P.tripSeite(a, server);
		server.foreignWrite(P.TRIP_ID, { name: 'Fremder Name' });
		const alarme = await P.alarmeReiter(a);
		alarme.empfindlichkeitAendern('wind', 'sensibel');
		await P.fertig(a.ctl);
		assert.equal(a.ctl.state, 'conflict', 'Vorbedingung: Konflikt');
		registry.discardEtag(P.TRIP_ID); // synthetisch: kein Stempel vor dem GET

		fehler = (m) => m === 'PUT';
		await a.ctl.retryConflict();
		fehler = null;
		assert.equal(a.ctl.state, 'conflict');
		assert.equal(istKonflikt(P.TRIP_ID), true);

		server.foreignWrite(P.TRIP_ID, { name: 'Fremder Name 2' });
		const vorher = puts().length;
		alarme.empfindlichkeitAendern('precipitation', 'ruhig');
		await P.fertig(a.ctl);
		const neue = puts().slice(vorher);
		assert.ok(neue.length > 0, 'Messaufbau: der Folge-Save wurde gesendet');
		assert.ok(neue.every((c) => !!c.ifMatch), 'jeder Folge-Save traegt ein If-Match');
		assert.ok(neue.every((c) => c.status === 412), 'jeder Folge-Save wird abgelehnt');
		assert.equal(stand().name, 'Fremder Name 2', 'Fremdaenderung bleibt');
		assert.notEqual(levels().precipitation, 'ruhig', 'Eingabe nicht still geschrieben');
		assert.equal(a.ctl.state, 'conflict');
	});
});
