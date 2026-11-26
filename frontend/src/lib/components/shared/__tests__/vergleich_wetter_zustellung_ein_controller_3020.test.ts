// Issue #3020 R1, G28 (Ersatz für die vergleich-Fälle des mit #3357 gelöschten
// wetter_metriken_versand_panel_speicherung, #1743): Im Orte-Hub teilen die lebenden Reiter Wetter (samt Karte „Was
// steht wo“) und Zustellung EINEN Speicher-Controller und EINE Schreibschlange und verdrängen sich nicht.
// Gemessen über die ECHTEN Instanz-Skripte, das echte `api` und die echte Hub-Schlange (createPutQueue) gegen den
// Ersatz-Server; Server-Stand = gespeichertes Abo, gemischt mit jedem angenommenen Rumpf (Go: top-level, display_config
// auf Ebene 1). Der Trip steht in trip-detail/__tests__/trip_wetter_zustellung_ein_controller.test.ts.
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei.

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import { createPutQueue } from '../../compare/compareHubPersistenz.ts';
import * as P from '../../trip-detail/__tests__/tripMehrreiterPruefstand.ts';
import { live, liveVergleichsKatalog } from '../wetter-tab/__tests__/wetterTabDaten.ts';

type J = any; // eslint-disable-line @typescript-eslint/no-explicit-any
const ID = 'cp-3020-hub';
const PFAD = `/api/compare/presets/${ID}`;
const ABO = () => ({
	id: ID,
	user_id: 'gz3020-anna',
	name: 'Orte',
	location_ids: ['o1', 'o2'],
	morning_time: '07:00:00',
	evening_time: '18:00:00',
	alert_channels: { email: true, telegram: false, sms: false, premium_sms: false },
	display_config: {
		ampel: { template: 'allgemein' },
		active_metrics: [
			{ metric_id: 'temperature', aggregation: 'max' },
			{ metric_id: 'wind', aggregation: 'max' }
		],
		telegram_style: 'rich',
		altfeld: { bleibt: true }
	}
});
const DATEN = {
	'/api/metrics': live().metrics,
	'/api/templates': live().templates,
	'/api/metric-presets': [],
	'/api/compare/metrics?lang=de': liveVergleichsKatalog()
};

let server: FakeTripServer;
let fehler: ((rumpf: J) => boolean) | null = null;
const offen: ReturnType<typeof P.erstelleController>[] = [];
beforeEach(() => {
	clearEtagRegistry();
	fehler = null;
	server = createFakeTripServer({ merge: true });
	server.install();
	const fake = globalThis.fetch;
	(globalThis as { fetch: unknown }).fetch = async (input: unknown, init?: RequestInit) =>
		init?.method === 'PUT' && fehler?.(JSON.parse(String(init.body)))
			? new Response(JSON.stringify({ error: 'boom', detail: 'Serverfehler' }), { status: 500, headers: { 'Content-Type': 'application/json' } })
			: fake(input as never, init);
});
afterEach(async () => {
	for (const c of offen.splice(0)) await P.fertig(c);
	server.restore();
});
const puts = () => server.calls.filter((c) => c.method === 'PUT');
/** Gespeichertes Abo nach allen angenommenen PUTs (Read-Modify-Write wie Go). */
const stand = (): J =>
	puts()
		.filter((c) => c.status === 200)
		.reduce((a: J, c) => ({ ...a, ...(c.anfrage as J), display_config: { ...a.display_config, ...((c.anfrage as J).display_config ?? {}) } }), ABO());

async function reiter(abo: J, ctl = P.erstelleController(ID, 'vergleich'), schlange = createPutQueue()) {
	offen.push(ctl);
	const gemeinsam = { preset: abo, saveController: ctl, enqueueHubWrite: <T>(fn: () => Promise<T>) => schlange.enqueue(fn) };
	const wetter = await P.bauen(P.DATEI.wetter, { ...P.LAUFZEIT, context: 'vergleich', createMode: false, ...gemeinsam });
	await P.mitAntworten(DATEN, () => wetter.u.laden());
	assert.equal(wetter.u.phase, 'bereit', 'Messaufbau: Reiter Wetter hat nicht geladen');
	const karte = await P.karteImReiter(wetter, () => P.tabellenAntwort('vergleich', abo.display_config, ['temperature', 'wind'], { telegram_style: abo.display_config.telegram_style }));
	const zustellung = await P.bauen(P.DATEI.zustellung, { ...P.LAUFZEIT, context: 'vergleich', panel: gemeinsam });
	return { ctl, wetter, karte, zustellung };
}
async function hub() {
	await api.get(PFAD);
	const r = await reiter(ABO());
	const zeit = (morgenZeit: string) => r.zustellung.u.aendern({ ...r.zustellung.u.stand, morgenZeit });
	return {
		...r,
		geste: {
			wetter: () => r.wetter.u.entfernen('wind'),
			karte: () => {
				r.karte.u.aktFelder = r.karte.u.felderAusAntwort(r.karte.u.antwort); // `$derived`: einmal ausgewertet
				r.karte.u.feld('telegram_style', 'kurzform');
			},
			zustellung: () => zeit('08:00')
		} as Record<string, () => void>,
		zurueck: { wetter: () => r.wetter.u.hinzufuegen('wind'), zustellung: () => zeit('07:00') }
	};
}
const metriken = (a: J): string[] => a.display_config.active_metrics.map((m: J) => m.metric_id);
const eingaben = (a: J): J => ({ wetter: metriken(a).includes('wind'), karte: a.display_config.telegram_style, zustellung: a.morning_time });
const VORHER: J = { wetter: true, karte: 'rich', zustellung: '07:00:00' };
const NACHHER: J = { wetter: false, karte: 'kurzform', zustellung: '08:00:00' };

describe('#3020 R1 Orte-Hub: Reiter Wetter, Karte und Zustellung an einem Controller', () => {
	for (const [erster, zweiter] of [
		['wetter', 'zustellung'],
		['zustellung', 'wetter'],
		['karte', 'zustellung'],
		['zustellung', 'karte'],
		['karte', 'wetter']
	]) {
		test(`Orte: erst ${erster}, sofort danach ${zweiter}: beide Eingaben stehen auf dem Server, neu geöffnet sichtbar`, async () => {
			const h = await hub();
			assert.deepEqual(eingaben(stand()), VORHER, 'Messaufbau');
			h.geste[erster]();
			h.geste[zweiter]();
			await P.fertig(h.ctl);
			const soll = { ...VORHER, [erster]: NACHHER[erster], [zweiter]: NACHHER[zweiter] };
			assert.deepEqual(eingaben(stand()), soll);
			assert.ok(puts().every((p) => p.path === PFAD && p.status === 200 && p.ifMatch !== null), JSON.stringify(puts().map((p) => [p.path, p.status])));
			assert.equal(h.ctl.state, 'idle');
			assert.ok(h.ctl.savedAt instanceof Date);
			assert.deepEqual(stand().display_config.altfeld, { bleibt: true });
			assert.deepEqual(stand().location_ids, ['o1', 'o2']);

			const neu = await reiter(stand());
			assert.deepEqual(
				{ wetter: neu.wetter.u.stand.auswahl.includes('wind'), karte: neu.karte.u.felderAusAntwort(neu.karte.u.antwort).telegram_style, zustellung: `${neu.zustellung.u.stand.morgenZeit}:00` },
				soll
			);
		});
	}

	test('Orte: zwei Vorgänge laufen nacheinander durch die Hub-Schlange, der zweite mit dem Stempel der ersten Antwort', async () => {
		const h = await hub();
		const stempel = server.etagOf(ID);
		h.geste.wetter();
		h.geste.zustellung();
		await P.fertig(h.ctl);
		assert.equal(puts().length, 2);
		assert.equal(puts()[0].ifMatch, stempel);
		assert.notEqual(puts()[1].ifMatch, stempel);
		assert.ok(puts()[0].finishedAt <= puts()[1].startedAt, 'nie zwei PUTs gleichzeitig');
	});
});

const istWetter = (r: J) => 'ampel' in (r.display_config ?? {});
describe('#3020 R1 Orte-Hub: AC-15, der Fehler des ersten Schreibers bleibt sichtbar', () => {
	for (const [erster, zweiter, trifft] of [
		['wetter', 'zustellung', istWetter],
		['zustellung', 'wetter', (r: J) => 'morning_time' in r]
	] as [string, string, (r: J) => boolean][]) {
		test(`Orte: ${erster} scheitert (500), ${zweiter} klappt: Anzeige „Fehler“, nicht „Gespeichert“; der zweite steht auf dem Server`, async () => {
			const h = await hub();
			let versucht = 0;
			fehler = (r) => trifft(r) && ++versucht > 0;
			h.geste[erster]();
			h.geste[zweiter]();
			await P.fertig(h.ctl);
			assert.equal(versucht, 1, `${erster} wurde nie gesendet (verdrängt)`);
			assert.deepEqual(eingaben(stand()), { ...VORHER, [zweiter]: NACHHER[zweiter] });
			assert.equal(h.ctl.state, 'error');
			assert.equal(h.ctl.savedAt, null);
		});
	}
});

describe('#3020 R1 Orte-Hub: F001, Zurücksetzen binnen 700 ms nimmt den Vorgang des anderen nicht mit', () => {
	test('Orte: Zustellzeit ändern und zurücksetzen: eigener Vorgang verworfen, die Wetter-Änderung kommt an', async () => {
		const h = await hub();
		h.geste.wetter();
		h.geste.zustellung();
		h.zurueck.zustellung();
		assert.equal(h.ctl.hasPending, false, 'der zurückgenommene Vorgang steht noch aus');
		await P.fertig(h.ctl);
		assert.deepEqual(eingaben(stand()), { ...VORHER, wetter: false });
		assert.ok(puts().every((p) => !('morning_time' in (p.anfrage as object))), 'ein PUT trägt die zurückgenommene Zeit');
		assert.equal(h.ctl.state, 'idle');
	});

	test('Orte: erst Zustellung, dann Zustellzeit zurück, während Wetter aussteht: der Wetter-Vorgang bleibt ausstehend', async () => {
		const h = await hub();
		h.geste.zustellung();
		h.geste.wetter();
		h.zurueck.zustellung();
		assert.equal(h.ctl.hasPending, true, 'der Wetter-Vorgang wurde mitverworfen');
		await P.fertig(h.ctl);
		assert.equal(eingaben(stand()).wetter, false);
	});

	test('Orte: Metrik abwählen und wieder wählen: die Zustellzeit kommt an, die Auswahl bleibt, nichts steht aus', async () => {
		const h = await hub();
		h.geste.zustellung();
		h.geste.wetter();
		h.zurueck.wetter();
		await P.fertig(h.ctl);
		assert.deepEqual(eingaben(stand()), { ...VORHER, zustellung: '08:00:00' });
		assert.deepEqual(metriken(stand()).sort(), ['temperature', 'wind']);
		assert.equal(h.ctl.hasPending, false);
		assert.equal(h.ctl.state, 'idle');
	});

	test('Orte: Zustellzeit ändern und zurücksetzen ohne fremden Vorgang: kein PUT, Anzeige unverändert', async () => {
		const h = await hub();
		h.geste.zustellung();
		h.zurueck.zustellung();
		assert.equal(h.ctl.hasPending, false);
		await P.fertig(h.ctl);
		assert.deepEqual(puts(), []);
		assert.equal(h.ctl.state, 'idle');
		assert.equal(h.ctl.savedAt, null);
	});
});
