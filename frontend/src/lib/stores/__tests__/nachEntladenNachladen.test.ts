// TDD RED — Issue #2317 (Epic #2127): begrenztes Nachladen nach dem Browser-Neuladen.
//
// Spec: docs/specs/modules/speicherung_beim_neuladen.md
//   § Implementation Details „Baustein 3 — Anzeige nach Browser-Neuladen"
//   § Acceptance Criteria AC-8, AC-9, AC-10
//
// Zielschnittstelle (existiert noch NICHT → RED per ERR_MODULE_NOT_FOUND bzw.
// fehlendem Export; jeder Test importiert dynamisch, damit jeder Fall einzeln
// mit eigenem Namen rot wird):
//
//   frontend/src/lib/stores/nachEntladenNachladen.ts   (svelte-frei, kein $app/*)
//     NACHLADE_VERSUCHE = 6, NACHLADE_ABSTAND_MS = 500
//     starteNachladenNachEntladen<T>({ kennung, ctl, ausgelieferteFassung, holen,
//                                      uebernehmen, zeitgeber? })
//       -> { stoppen(): void; fertig: Promise<void> }
//   frontend/src/lib/pwa/geraetespeicher.ts
//     merkeSpeicherungBeimEntladen(kennung) / nimmSpeicherungBeimEntladen(kennung)
//
// Kein Mock-Theater:
//   - `ctl` ist eine ECHTE SaveStatus-Instanz (Prototype-Methoden schedule/flush/
//     cancel), erzeugt wie in ausstehendeSpeicherungSichern.test.ts.
//   - `holen` ist ein aufzeichnender Transport-Doppel, der die Server-Antwort
//     je Versuch liefert; `uebernehmen` zeichnet auf, was die Seite anzeigen wuerde.
//   - Der Zeitgeber ist ein aufzeichnendes Doppel: Timer laufen NUR, wenn der
//     Test sie ausloest. So sind Anzahl, Abstand und offene Timer messbar.
//   - sessionStorage ist ein echtes In-Memory-Storage (Node 22 hat keins).
//
// Hinweis zu `ctl.schedule()`: SaveStatus nutzt den ECHTEN globalen setTimeout
// (700 ms), nicht den hereingereichten Zeitgeber. Tests, die schedule() ohne
// flush() stehen lassen, raeumen mit `ctl.cancel()` auf.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/stores/__tests__/nachEntladenNachladen.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { SaveStatus } from '../saveStatusStore.svelte.ts';
import {
	installiereSitzungsspeicher,
	entferneSitzungsspeicher
} from '../../__tests__/sitzungsspeicherDoppel.ts';

type Kennung = { typ: 'trip' | 'vergleich'; id: string };
type Antwort = { stand: { name: string }; fassung: string };

type NachladeModul = {
	NACHLADE_VERSUCHE: number;
	NACHLADE_ABSTAND_MS: number;
	starteNachladenNachEntladen: (o: {
		kennung: Kennung;
		ctl: SaveStatus;
		ausgelieferteFassung: string;
		holen: () => Promise<Antwort>;
		uebernehmen: (stand: Antwort['stand'], fassung: string) => void;
		zeitgeber?: unknown;
	}) => { stoppen(): void; fertig: Promise<void> };
};
type GeraetespeicherModul = {
	merkeSpeicherungBeimEntladen: (k: Kennung) => void;
};

async function lade(): Promise<{ nach: NachladeModul; speicher: GeraetespeicherModul }> {
	const nach = (await import('../nachEntladenNachladen.ts')) as unknown as NachladeModul;
	const speicher = (await import('../../pwa/geraetespeicher.ts')) as unknown as GeraetespeicherModul;
	assert.equal(typeof nach.starteNachladenNachEntladen, 'function', 'starteNachladenNachEntladen fehlt');
	assert.equal(
		typeof speicher.merkeSpeicherungBeimEntladen,
		'function',
		'geraetespeicher.ts muss merkeSpeicherungBeimEntladen exportieren'
	);
	return { nach, speicher };
}

/** Echte SaveStatus-Instanz ohne Konstruktor (Muster aus saveStatus.test.ts). */
function createTestInstance(): SaveStatus {
	const inst = Object.create(SaveStatus.prototype) as SaveStatus;
	const fields = inst as unknown as Record<string, unknown>;
	fields.state = 'idle';
	fields.savedAt = null;
	fields.error = null;
	fields._timer = null;
	fields._pendingFn = null;
	fields._inflight = null;
	fields._lastFailed = null;
	fields._unresolvedError = null;
	return inst;
}

type Timer = { fn: () => void; ms: number; geloescht: boolean; ausgeloest: boolean };

/** Aufzeichnender Zeitgeber: nichts laeuft von selbst, der Test loest Timer einzeln aus. */
class AufzeichnenderZeitgeber {
	readonly timer: Timer[] = [];
	setTimeout = (fn: () => void, ms: number): unknown => {
		const t: Timer = { fn, ms, geloescht: false, ausgeloest: false };
		this.timer.push(t);
		return t;
	};
	clearTimeout = (h: unknown): void => {
		const t = this.timer.find((x) => x === h);
		if (t) t.geloescht = true;
	};
	offene(): Timer[] {
		return this.timer.filter((t) => !t.geloescht && !t.ausgeloest);
	}
	loeseNaechstenAus(): boolean {
		const t = this.offene()[0];
		if (!t) return false;
		t.ausgeloest = true;
		t.fn();
		return true;
	}
}

/** Laesst alle anstehenden Microtasks und Promise-Ketten durchlaufen. */
async function ruhe(): Promise<void> {
	for (let i = 0; i < 5; i++) await new Promise<void>((r) => setImmediate(r));
}

/** Loest Timer aus, bis `holen` n-mal gerufen wurde (oder kein Timer mehr offen ist). */
async function bisVersuch(zeit: AufzeichnenderZeitgeber, holen: { aufrufe: number }, n: number): Promise<void> {
	await ruhe();
	for (let i = 0; i < 50 && holen.aufrufe < n; i++) {
		if (!zeit.loeseNaechstenAus()) break;
		await ruhe();
	}
}

/** Loest jeden offenen Timer aus, bis keiner mehr uebrig ist. */
async function alleDurchlaufen(zeit: AufzeichnenderZeitgeber): Promise<void> {
	await ruhe();
	for (let i = 0; i < 50; i++) {
		if (!zeit.loeseNaechstenAus()) break;
		await ruhe();
	}
}

async function fertigBinnen(p: Promise<void>, ms = 1_000): Promise<void> {
	let h: ReturnType<typeof setTimeout> | undefined;
	const frist = new Promise<never>((_, rej) => {
		h = setTimeout(() => rej(new Error('`fertig` hat sich nicht aufgeloest')), ms);
	});
	try {
		await Promise.race([p, frist]);
	} finally {
		clearTimeout(h);
	}
}

/** Transport-Doppel: liefert je Versuch die vorgegebene Antwort (letzte wiederholt sich). */
function holenDoppel(antworten: Array<Antwort | Error>) {
	const rec = { aufrufe: 0 };
	const holen = async (): Promise<Antwort> => {
		const a = antworten[Math.min(rec.aufrufe, antworten.length - 1)];
		rec.aufrufe++;
		if (a instanceof Error) throw a;
		return a;
	};
	return { holen, rec };
}

function uebernahmeDoppel() {
	const calls: Array<[Antwort['stand'], string]> = [];
	return { uebernehmen: (s: Antwort['stand'], f: string) => void calls.push([s, f]), calls };
}

const TRIP: Kennung = { typ: 'trip', id: 'gr20' };
const VERGLEICH: Kennung = { typ: 'vergleich', id: 'cp-alpen' };
const AUSGELIEFERT = '"fp-1"';
const ALT: Antwort = { stand: { name: 'alt' }, fassung: AUSGELIEFERT };
const NEU: Antwort = { stand: { name: 'neu' }, fassung: '"fp-2"' };

beforeEach(() => {
	installiereSitzungsspeicher();
});
afterEach(() => {
	entferneSitzungsspeicher();
});

// ===========================================================================
// AC-9 — ohne Merker keine einzige zusaetzliche Anfrage
// ===========================================================================

describe('Issue #2317 AC-9: normales Laden ohne Merker', () => {
	for (const kennung of [TRIP, VERGLEICH]) {
		test(`AC-9 (${kennung.typ}): kein Merker → 0 holen-Aufrufe, 0 Timer, fertig sofort`, async () => {
			// GIVEN: kein Merker im Geraetespeicher
			const { nach } = await lade();
			const zeit = new AufzeichnenderZeitgeber();
			const { holen, rec } = holenDoppel([NEU]);
			const { uebernehmen, calls } = uebernahmeDoppel();

			// WHEN: die Detailseite oeffnet
			const h = nach.starteNachladenNachEntladen({
				kennung,
				ctl: createTestInstance(),
				ausgelieferteFassung: AUSGELIEFERT,
				holen,
				uebernehmen,
				zeitgeber: zeit
			});
			await fertigBinnen(h.fertig);
			await ruhe();

			// THEN: keine Anfrage, kein Timer, keine Aenderung der Anzeige
			assert.equal(rec.aufrufe, 0, 'ohne Merker darf keine einzige Nachlade-Anfrage entstehen');
			assert.equal(zeit.timer.length, 0, 'ohne Merker darf kein Timer geplant werden');
			assert.equal(calls.length, 0, 'ohne Merker darf nichts uebernommen werden');
		});
	}
});

// ===========================================================================
// AC-10 — hoechstens 6 Versuche im Abstand von 500 ms, dann still Schluss
// ===========================================================================

describe('Issue #2317 AC-10: begrenztes Nachladen', () => {
	for (const kennung of [TRIP, VERGLEICH]) {
		test(`AC-10 (${kennung.typ}): Server liefert dauerhaft den ausgelieferten Stand → genau 6 Versuche je 500 ms, keine Uebernahme, kein offener Timer`, async () => {
			// GIVEN: Merker liegt vor, der Server bleibt beim ausgelieferten Stand
			const { nach, speicher } = await lade();
			speicher.merkeSpeicherungBeimEntladen(kennung);
			const zeit = new AufzeichnenderZeitgeber();
			const { holen, rec } = holenDoppel([ALT]);
			const { uebernehmen, calls } = uebernahmeDoppel();

			assert.equal(nach.NACHLADE_VERSUCHE, 6, 'Versuchszahl laut Spec: 6');
			assert.equal(nach.NACHLADE_ABSTAND_MS, 500, 'Abstand laut Spec: 500 ms');

			// WHEN: die Detailseite laedt und alle Timer laufen ab
			const h = nach.starteNachladenNachEntladen({
				kennung,
				ctl: createTestInstance(),
				ausgelieferteFassung: AUSGELIEFERT,
				holen,
				uebernehmen,
				zeitgeber: zeit
			});
			await alleDurchlaufen(zeit);
			await fertigBinnen(h.fertig);

			// THEN
			assert.equal(rec.aufrufe, 6, 'es muessen genau 6 Versuche stattfinden — nicht weniger, nicht mehr');
			assert.ok(zeit.timer.length > 0, 'zwischen den Versuchen muss ueber den Zeitgeber gewartet werden');
			assert.deepEqual(
				zeit.timer.map((t) => t.ms),
				zeit.timer.map(() => 500),
				'jeder Abstand zwischen zwei Versuchen muss 500 ms betragen'
			);
			assert.equal(zeit.offene().length, 0, 'nach dem letzten Versuch darf kein Timer mehr offen sein');
			assert.equal(calls.length, 0, 'ein unveraenderter Server-Stand darf die Anzeige nicht veraendern');
		});
	}

	test('Positivfall: der 2. Versuch liefert eine neue Fassung → genau eine Uebernahme mit Stand+Fassung, danach keine weiteren Versuche', async () => {
		// GIVEN: Merker liegt vor; erst alter, dann neuer Server-Stand
		const { nach, speicher } = await lade();
		speicher.merkeSpeicherungBeimEntladen(TRIP);
		const zeit = new AufzeichnenderZeitgeber();
		const { holen, rec } = holenDoppel([ALT, NEU]);
		const { uebernehmen, calls } = uebernahmeDoppel();

		// WHEN
		const h = nach.starteNachladenNachEntladen({
			kennung: TRIP,
			ctl: createTestInstance(),
			ausgelieferteFassung: AUSGELIEFERT,
			holen,
			uebernehmen,
			zeitgeber: zeit
		});
		await alleDurchlaufen(zeit);
		await fertigBinnen(h.fertig);

		// THEN
		assert.deepEqual(calls, [[NEU.stand, NEU.fassung]], 'die neue Fassung muss genau einmal uebernommen werden');
		assert.equal(rec.aufrufe, 2, 'nach der Uebernahme darf kein weiterer Versuch folgen');
		assert.equal(zeit.offene().length, 0, 'nach der Uebernahme darf kein Timer offen bleiben');
	});

	test('holen wirft dauerhaft → jeder Fehlschlag zaehlt als Versuch, nach 6 still Schluss', async () => {
		const { nach, speicher } = await lade();
		speicher.merkeSpeicherungBeimEntladen(TRIP);
		const zeit = new AufzeichnenderZeitgeber();
		const { holen, rec } = holenDoppel([new Error('Failed to fetch')]);
		const { uebernehmen, calls } = uebernahmeDoppel();

		const h = nach.starteNachladenNachEntladen({
			kennung: TRIP,
			ctl: createTestInstance(),
			ausgelieferteFassung: AUSGELIEFERT,
			holen,
			uebernehmen,
			zeitgeber: zeit
		});
		await alleDurchlaufen(zeit);
		await fertigBinnen(h.fertig);

		assert.equal(rec.aufrufe, 6, 'auch fehlgeschlagene Abrufe zaehlen als Versuch — genau 6');
		assert.equal(calls.length, 0);
		assert.equal(zeit.offene().length, 0, 'kein offener Timer nach dem letzten Fehlschlag');
	});

	test('holen wirft beim 1. Versuch → es wird weiter versucht, der 2. Versuch uebernimmt', async () => {
		const { nach, speicher } = await lade();
		speicher.merkeSpeicherungBeimEntladen(TRIP);
		const zeit = new AufzeichnenderZeitgeber();
		const { holen, rec } = holenDoppel([new Error('Failed to fetch'), NEU]);
		const { uebernehmen, calls } = uebernahmeDoppel();

		const h = nach.starteNachladenNachEntladen({
			kennung: TRIP,
			ctl: createTestInstance(),
			ausgelieferteFassung: AUSGELIEFERT,
			holen,
			uebernehmen,
			zeitgeber: zeit
		});
		await alleDurchlaufen(zeit);
		await fertigBinnen(h.fertig);

		assert.equal(rec.aufrufe, 2, 'ein Wurf darf das Nachladen nicht beenden');
		assert.deepEqual(calls, [[NEU.stand, NEU.fassung]]);
	});

	test('der Merker wird beim Start verbraucht: ein zweiter Start ohne neuen Merker holt nichts', async () => {
		const { nach, speicher } = await lade();
		speicher.merkeSpeicherungBeimEntladen(TRIP);
		const zeit1 = new AufzeichnenderZeitgeber();
		const erster = holenDoppel([ALT]);
		const h1 = nach.starteNachladenNachEntladen({
			kennung: TRIP,
			ctl: createTestInstance(),
			ausgelieferteFassung: AUSGELIEFERT,
			holen: erster.holen,
			uebernehmen: () => {},
			zeitgeber: zeit1
		});
		await ruhe();
		assert.equal(
			(globalThis as unknown as { sessionStorage: Storage }).sessionStorage.length,
			0,
			'der Merker muss beim Start sofort geloescht werden'
		);
		await alleDurchlaufen(zeit1);
		await fertigBinnen(h1.fertig);
		assert.ok(erster.rec.aufrufe > 0, 'Vorbedingung: der erste Start hat nachgeladen');

		// WHEN: dieselbe Seite wird ein zweites Mal geoeffnet (z.B. normales Neuladen)
		const zeit2 = new AufzeichnenderZeitgeber();
		const zweiter = holenDoppel([NEU]);
		const h2 = nach.starteNachladenNachEntladen({
			kennung: TRIP,
			ctl: createTestInstance(),
			ausgelieferteFassung: AUSGELIEFERT,
			holen: zweiter.holen,
			uebernehmen: () => {},
			zeitgeber: zeit2
		});
		await fertigBinnen(h2.fertig);
		await ruhe();

		// THEN
		assert.equal(zweiter.rec.aufrufe, 0, 'ein verbrauchter Merker darf kein zweites Nachladen ausloesen');
		assert.equal(zeit2.timer.length, 0);
	});

	test('stoppen() (Seite verlassen) beendet das Nachladen: keine weiteren Versuche, kein offener Timer', async () => {
		const { nach, speicher } = await lade();
		speicher.merkeSpeicherungBeimEntladen(TRIP);
		const zeit = new AufzeichnenderZeitgeber();
		const { holen, rec } = holenDoppel([ALT, ALT, NEU]);
		const { uebernehmen, calls } = uebernahmeDoppel();

		const h = nach.starteNachladenNachEntladen({
			kennung: TRIP,
			ctl: createTestInstance(),
			ausgelieferteFassung: AUSGELIEFERT,
			holen,
			uebernehmen,
			zeitgeber: zeit
		});
		await bisVersuch(zeit, rec, 1);
		assert.equal(rec.aufrufe, 1, 'Vorbedingung: der erste Versuch lief');

		h.stoppen();
		await ruhe();
		assert.equal(zeit.offene().length, 0, 'stoppen() muss den geplanten Timer aufheben (clearTimeout)');
		await alleDurchlaufen(zeit);
		await fertigBinnen(h.fertig);

		assert.equal(rec.aufrufe, 1, 'nach stoppen() darf kein weiterer Versuch folgen');
		assert.equal(calls.length, 0);
	});
});

// ===========================================================================
// AC-8 — eine neue Eingabe waehrend des Nachladens wird nicht ueberschrieben
// ===========================================================================

describe('Issue #2317 AC-8: Nachladen ueberschreibt keine neue Eingabe', () => {
	test('AC-8 (a): der Nutzer tippt waehrend des Nachladens (Speicherung geplant) → keine Uebernahme', async () => {
		// GIVEN: Merker liegt vor, erster Versuch sieht noch den alten Stand
		const { nach, speicher } = await lade();
		speicher.merkeSpeicherungBeimEntladen(TRIP);
		const zeit = new AufzeichnenderZeitgeber();
		const ctl = createTestInstance();
		const { holen, rec } = holenDoppel([ALT, NEU]);
		const { uebernehmen, calls } = uebernahmeDoppel();

		const h = nach.starteNachladenNachEntladen({
			kennung: TRIP,
			ctl,
			ausgelieferteFassung: AUSGELIEFERT,
			holen,
			uebernehmen,
			zeitgeber: zeit
		});
		await bisVersuch(zeit, rec, 1);
		assert.equal(rec.aufrufe, 1, 'Vorbedingung: der erste Versuch lief');

		// WHEN: der Nutzer traegt einen neuen Wert ein (700-ms-Fenster laeuft)
		ctl.schedule(async () => {});
		assert.equal(ctl.hasPending, true, 'Vorbedingung: die neue Eingabe wartet aufs Speichern');
		await alleDurchlaufen(zeit);
		await fertigBinnen(h.fertig);

		// THEN: die neue Server-Fassung darf die Eingabe NICHT ueberschreiben
		// (Ob danach weiter versucht oder aufgehoert wird, ist offen — belastbar ist nur: keine Uebernahme.)
		assert.equal(calls.length, 0, 'eine geplante, noch nicht abgesetzte Eingabe darf nicht ueberschrieben werden');
		assert.equal(zeit.offene().length, 0);
		ctl.cancel();
	});

	test('AC-8 (c, F001): zurueckgestellte Eingabe per defer() (Zustand „dirty", kein „saving") → keine Uebernahme', async () => {
		// GIVEN: Merker liegt vor, erster Versuch sieht noch den alten Stand
		const { nach, speicher } = await lade();
		speicher.merkeSpeicherungBeimEntladen(TRIP);
		const zeit = new AufzeichnenderZeitgeber();
		const ctl = createTestInstance();
		const { holen, rec } = holenDoppel([ALT, NEU]);
		const { uebernehmen, calls } = uebernahmeDoppel();

		const h = nach.starteNachladenNachEntladen({
			kennung: TRIP,
			ctl,
			ausgelieferteFassung: AUSGELIEFERT,
			holen,
			uebernehmen,
			zeitgeber: zeit
		});
		await bisVersuch(zeit, rec, 1);
		assert.equal(rec.aufrufe, 1, 'Vorbedingung: der erste Versuch lief');

		// WHEN: eine Etappen-Aenderung wird zurueckgestellt (Kaskaden-Rueckfrage, #1389)
		ctl.defer(async () => {});
		assert.equal(ctl.state, 'dirty', 'Vorbedingung: defer() setzt „dirty", nicht „saving"');
		assert.equal(ctl.hasPending, true, 'Vorbedingung: die zurueckgestellte Eingabe steht aus');
		assert.equal(ctl.savedAt, null, 'Vorbedingung: kein Gespeichert-Zeitstempel');
		await alleDurchlaufen(zeit);
		await fertigBinnen(h.fertig);

		// THEN: allein hasPending traegt hier „ungeschriebene Eingabe" — sie darf nicht ueberschrieben werden
		assert.equal(calls.length, 0, 'eine zurueckgestellte Eingabe darf nicht durch den Server-Stand ueberschrieben werden');
		assert.equal(zeit.offene().length, 0);
		ctl.cancel();
	});

	test('AC-8 (b): die neue Eingabe ist schon gespeichert (hasPending wieder false) → trotzdem KEINE Uebernahme', async () => {
		// GIVEN: Merker liegt vor; Versuch 1 und 2 sehen den alten Stand, ab 3 den neuen
		const { nach, speicher } = await lade();
		speicher.merkeSpeicherungBeimEntladen(TRIP);
		const zeit = new AufzeichnenderZeitgeber();
		const ctl = createTestInstance();
		const { holen, rec } = holenDoppel([ALT, ALT, NEU]);
		const { uebernehmen, calls } = uebernahmeDoppel();

		const h = nach.starteNachladenNachEntladen({
			kennung: TRIP,
			ctl,
			ausgelieferteFassung: AUSGELIEFERT,
			holen,
			uebernehmen,
			zeitgeber: zeit
		});
		await bisVersuch(zeit, rec, 1);
		assert.equal(rec.aufrufe, 1, 'Vorbedingung: der erste Versuch lief');

		// WHEN: der Nutzer tippt — Versuch 2 laeuft, WAEHREND die Speicherung aussteht ...
		let gespeichert = 0;
		ctl.schedule(async () => {
			gespeichert++;
		});
		await bisVersuch(zeit, rec, 2);
		assert.equal(rec.aufrufe, 2, 'Vorbedingung: Versuch 2 lief bei ausstehender Speicherung');
		assert.equal(calls.length, 0);

		// ... dann ist die Speicherung abgeschlossen
		await ctl.flush();
		assert.equal(gespeichert, 1, 'Vorbedingung: die Eingabe wurde gespeichert');
		assert.equal(ctl.hasPending, false, 'Vorbedingung: nichts steht mehr aus');
		await alleDurchlaufen(zeit);
		await fertigBinnen(h.fertig);

		// THEN: der Nutzer hat seit dem Laden etwas geaendert → nie mehr uebernehmen
		// (Ob danach weiter versucht oder aufgehoert wird, ist offen — belastbar ist nur: keine Uebernahme.)
		assert.equal(
			calls.length,
			0,
			'nach einer eigenen Aenderung seit dem Laden darf nie mehr uebernommen werden — auch wenn ihre Speicherung schon abgeschlossen ist'
		);
		assert.equal(zeit.offene().length, 0);
	});
});
