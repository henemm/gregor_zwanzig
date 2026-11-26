// Issue #3020 R1 (Spec docs/specs/modules/rework_3020_altbausteine_entfernen.md, AC-2; LOW-Befund R2-F1).
//
// Der Weg Reiter Wetter -> Karte „Was steht wo“ -> Speichern, gemessen dort, wo er WIRKT: die ECHTEN Instanz-Skripte
// von WetterTabInhalt.svelte und WasStehtWoKarte.svelte, die Karte gebunden über die ECHTE Einbettung im Reiter
// (Attribut-Ausdrücke und `bind:this`, tripMehrreiterPruefstand.karteImReiter), gespeichert über das echte `api`
// (If-Match, Warteschlange) gegen den Ersatz-Server. Geprüft wird der Rumpf, den der Server bekommt:
//   route      PUT /api/trips/{id}/weather-config trägt `placements`, der folgende Trip-PUT nicht
//   vergleich  PUT /api/compare/presets/{id} trägt `display_config.placements`
// Die Einzelteile (Speicherer, Tabelle) prüfen was_steht_wo_mitspeichern*.test.ts; sie laufen nicht durch den Reiter.
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei.

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import { live, liveVergleichsKatalog } from '../../shared/wetter-tab/__tests__/wetterTabDaten.ts';
import * as P from '../../trip-detail/__tests__/tripMehrreiterPruefstand.ts';

type J = any; // eslint-disable-line @typescript-eslint/no-explicit-any

const TABELLE = {
	version: 1,
	rows: [
		{ metric_id: 'temperature', places: { telegram: false } },
		{ metric_id: 'wind', formats: { email: 'raw' } }
	],
	outlook_reports: ['evening']
};
const kopie = (x: J): J => JSON.parse(JSON.stringify(x));
const ids = (p: J): string[] => p.rows.map((r: J) => r.metric_id);

let server: FakeTripServer;
beforeEach(() => {
	clearEtagRegistry();
	server = createFakeTripServer({ merge: true });
	server.install();
});
afterEach(() => server.restore());
const puts = () => server.calls.filter((c) => c.method === 'PUT');

/** Ein gemounteter Reiter samt Karte, gleiche Gesten in beiden Kontexten. */
interface Mount {
	inst: P.Instanz;
	karte: P.Instanz;
	ctl: J;
	/** Pfade der Lesevorgänge der Tabelle (GET …/placements). */
	gelesen: string[];
	/** Server-Antworten, die der Reiter an die Seite gemeldet hat. */
	uebernommen: J[];
	abo: string;
	fertig(): Promise<void>;
	/** Rumpfteil, der die Tabelle tragen muss. */
	display(): J;
}

async function trip(mitTabelle = true): Promise<Mount> {
	const doc = P.vollerTrip();
	if (mitTabelle) (doc.display_config as J).placements = kopie(TABELLE);
	server.seed(P.TRIP_ID, doc);
	await api.get(P.TRIP_PFAD);
	const a = P.neuerAufbau(doc);
	const gelesen: string[] = [];
	const w = await P.wetterReiter(a, (pfad) => {
		gelesen.push(pfad);
		return P.tabellenAntwort('route', server.stand(P.TRIP_ID).display_config as J, ['temperature', 'wind']);
	});
	return {
		inst: w.inst,
		karte: w.karte,
		ctl: a.ctl,
		gelesen,
		uebernommen: a.updates,
		abo: P.TRIP_PFAD,
		fertig: () => P.fertig(a.ctl),
		display() {
			const [wetter, rumpf] = puts();
			assert.equal(puts().length, 2, `zwei PUTs (gesehen: ${puts().map((c) => c.path).join(', ')})`);
			assert.equal(wetter.path, `${P.TRIP_PFAD}/weather-config`);
			assert.equal(rumpf.path, P.TRIP_PFAD);
			assert.deepEqual(puts().map((c) => c.status), [200, 200]);
			assert.equal('placements' in (rumpf.anfrage as object), false, 'der Trip-PUT trägt keine Tabelle');
			return wetter.anfrage;
		}
	};
}

const PRESET_ID = 'cp-3020';
const PRESET_PFAD = `/api/compare/presets/${PRESET_ID}`;
const vergleichDaten = (): Record<string, unknown> => ({
	'/api/metrics': live().metrics,
	'/api/templates': live().templates,
	'/api/metric-presets': [],
	'/api/compare/metrics?lang=de': liveVergleichsKatalog()
});

async function orte(mitTabelle = true): Promise<Mount> {
	const preset: J = {
		id: PRESET_ID,
		location_ids: ['o1', 'o2'],
		display_config: {
			active_metrics: [
				{ metric_id: 'temperature', aggregation: 'max' },
				{ metric_id: 'wind', aggregation: 'max' }
			],
			ampel: { template: 'allgemein' },
			...(mitTabelle ? { placements: kopie(TABELLE) } : {})
		}
	};
	await api.get(PRESET_PFAD);
	const ctl = P.erstelleController(PRESET_ID, 'vergleich');
	const uebernommen: J[] = [];
	const inst = await P.bauen(P.DATEI.wetter, {
		...P.LAUFZEIT,
		context: 'vergleich',
		preset,
		createMode: false,
		saveController: ctl,
		enqueueHubWrite: <T>(fn: () => Promise<T>) => fn(),
		onCompareUpdate: (p: J) => uebernommen.push(p)
	});
	await P.mitAntworten(vergleichDaten(), () => inst.u.laden());
	assert.equal(inst.u.phase, 'bereit', 'Messaufbau: Reiter Wetter (vergleich) hat nicht geladen');
	assert.deepEqual([...inst.u.stand.auswahl], ['temperature', 'wind'], 'Messaufbau: Grundauswahl');
	const gelesen: string[] = [];
	const karte = await P.karteImReiter(inst, (pfad) => {
		gelesen.push(pfad);
		const gesendet = (puts().at(-1)?.anfrage as J)?.display_config;
		return P.tabellenAntwort('vergleich', gesendet?.placements ? gesendet : preset.display_config, ['temperature', 'wind']);
	});
	return {
		inst,
		karte,
		ctl,
		gelesen,
		uebernommen,
		abo: PRESET_PFAD,
		fertig: () => P.fertig(ctl),
		display() {
			assert.equal(puts().length, 1, `ein PUT (gesehen: ${puts().map((c) => c.path).join(', ')})`);
			assert.equal(puts()[0].path, PRESET_PFAD);
			return (puts()[0].anfrage as J).display_config;
		}
	};
}

const KONTEXTE = [
	['route', trip],
	['vergleich', orte]
] as const;

for (const [name, mount] of KONTEXTE) {
	describe(`${name}: der PUT des Reiters Wetter trägt die Tabelle der Karte`, () => {
		test(`${name} „−“: Zeile der Metrik entfällt, Haken der übrigen Zeile und Ausblick-Berichte bleiben`, async () => {
			const m = await mount();
			m.inst.u.entfernen('wind');
			await m.fertig();
			assert.deepEqual(m.display().placements, { ...TABELLE, rows: [TABELLE.rows[0]] });
		});

		test(`${name} „+“: neue Zeile hinten, überall angehakt; Haken und Form der übrigen Zeilen bleiben`, async () => {
			const m = await mount();
			m.inst.u.hinzufuegen('gust');
			await m.fertig();
			const p = m.display().placements;
			assert.deepEqual(ids(p), ['temperature', 'wind', 'gust']);
			assert.deepEqual(p.rows.slice(0, 2), TABELLE.rows);
			assert.equal(Object.values(p.rows[2].places ?? {}).includes(false), false, JSON.stringify(p.rows[2]));
		});

		test(`${name} Änderung ohne Metrikwechsel: die Tabelle fährt unverändert und vollständig mit`, async () => {
			const m = await mount();
			m.inst.u.aendern({ ...m.inst.u.stand, tagesfenster: { start: 6, end: 20 } });
			await m.fertig();
			assert.deepEqual(m.display().placements, TABELLE);
		});

		test(`${name} keine gespeicherte Tabelle: kein Schlüssel placements (das Abo wechselt nicht unbemerkt den Eingang)`, async () => {
			const m = await mount(false);
			m.inst.u.entfernen('wind');
			await m.fertig();
			assert.equal('placements' in m.display(), false);
		});

		test(`${name} nach dem Speichern holt die Karte ihre Ansicht genau einmal neu`, async () => {
			const m = await mount();
			const vorher = m.gelesen.length;
			m.inst.u.entfernen('wind');
			await m.fertig();
			assert.equal(m.gelesen.length, vorher + 1);
			assert.deepEqual(ids(m.karte.u.lokal), ['temperature']);
		});
	});

	test(`${name} Reiter Wetter reicht genau die Server-Antwort an die Seite`, async () => {
		const m = await mount();
		m.inst.u.entfernen('wind');
		await m.fertig();
		assert.deepEqual(m.uebernommen, [puts().at(-1)?.body], 'genau die Antwort des letzten PUT, genau einmal');
	});

	describe(`${name}: nur eine wirkliche Änderung speichert`, () => {
		test(`${name} Öffnen allein (Laden, Karte bauen, Reiter verlassen): kein PUT`, async () => {
			const m = await mount();
			await m.fertig();
			assert.deepEqual(puts().map((c) => c.path), []);
		});

		test(`${name} Grenzen auf- und zuklappen ohne Eingabe: kein PUT`, async () => {
			const m = await mount();
			m.inst.u.grenzenUmschalten('wind');
			assert.equal(m.inst.u.offen, 'wind', 'Messaufbau: Grenzen offen');
			m.inst.u.grenzenUmschalten('wind');
			assert.equal(m.inst.u.offen, null, 'Messaufbau: Grenzen wieder zu');
			await m.fertig();
			assert.deepEqual(puts().map((c) => c.path), []);
		});

		test(`${name} Gegenprobe: dieselbe Geste mit geändertem Grenzwert speichert`, async () => {
			const m = await mount();
			m.inst.u.grenzenUmschalten('wind');
			m.inst.u.grenzWert('wind', 'upper', 'yellow', 33);
			m.inst.u.grenzenUmschalten('wind');
			await m.fertig();
			assert.equal(m.display().ampel.metrics.wind.upper.yellow, 33);
		});
	});

	// R2-F1: die Attribute der Einbettung, gemessen an ihrer Wirkung.
	describe(`${name}: die Einbettung reicht der Karte, was sie zum Speichern braucht`, () => {
		/** Schalter der Karte bedienen (`$derived aktFelder` wertet der Prüfstand nur einmal aus). */
		const kurzstil = (m: Mount) => {
			m.karte.u.aktFelder = m.karte.u.felderAusAntwort(m.karte.u.antwort);
			m.karte.u.feld('telegram_style', 'kurzform');
		};

		test(`${name} context: die Karte liest die Tabelle dieses Abos`, async () => {
			const m = await mount();
			const id = m.abo.split('/').at(-1);
			assert.deepEqual(m.gelesen, [`/api/briefings/${id}/placements?kind=${name}`]);
		});

		test(`${name} saveController: ein Schalter der Karte wartet entprellt am Controller des Hubs und geht beim Verlassen raus`, async () => {
			const m = await mount();
			kurzstil(m);
			await new Promise((r) => setTimeout(r, 30));
			assert.deepEqual(puts().map((c) => c.path), [], 'vor der Entprellung kein PUT');
			await m.ctl.flush({ keepalive: true });
			await m.fertig();
			assert.deepEqual(puts().map((c) => [c.path, c.status, c.keepalive]), [[m.abo, 200, true]]);
		});

		test(`${name} saveController: ein abgelehnter Schalter der Karte meldet den Konflikt am Hub`, async () => {
			const m = await mount();
			server.foreignWrite(m.abo.split('/').at(-1)!, { name: 'fremd' });
			kurzstil(m);
			await m.fertig();
			assert.deepEqual(puts().map((c) => c.status), [412]);
			assert.equal(m.ctl.state, 'conflict');
		});

		test(`${name} onUebernahme: die Antwort eines Schalters der Karte kommt bei der Seite an`, async () => {
			const m = await mount();
			kurzstil(m);
			await m.fertig();
			assert.equal(puts().length, 1);
			assert.deepEqual(m.uebernommen, [puts()[0].body]);
		});

		test(`${name} createMode: beim Anlegen kein GET und kein PUT, der Stand der Karte geht an die Anlege-Seite`, async () => {
			const staende: J[] = [];
			const daten =
				name === 'route'
					? { '/api/metrics': live().metrics, '/api/templates': live().templates, '/api/metric-presets': [] }
					: vergleichDaten();
			const entwurf = { display_config: {} };
			const inst = await P.bauen(P.DATEI.wetter, {
				...P.LAUFZEIT,
				context: name,
				[name === 'route' ? 'trip' : 'preset']: entwurf,
				createMode: true,
				onAnlegeStand: () => {},
				onAnlegeKarte: (s: J) => staende.push(s)
			});
			await P.mitAntworten(daten, () => inst.u.laden());
			const pfad = `/api/briefings/placements/vorschau?kind=${name}`;
			const antwort = { ...P.tabellenAntwort(name, {}, ['temperature', 'wind']), stored: false };
			const karte = await P.mitAntworten({ [pfad]: antwort }, () =>
				P.karteImReiter(inst, () => {
					throw new Error('Anlegen liest keine gespeicherte Tabelle');
				})
			);
			// `$derived aktFelder`: der Prüfstand wertet ihn nur einmal aus, vor dem Laden.
			karte.u.aktFelder = karte.u.felderAusAntwort(karte.u.antwort);
			karte.u.haken({ metrik: 'wind', stelle: 'telegram', an: false });
			assert.equal(staende.length, 1);
			assert.equal(staende[0].placements.rows.find((r: J) => r.metric_id === 'wind').places.telegram, false);
			assert.deepEqual(puts().map((c) => c.path), []);
		});
	});
}
