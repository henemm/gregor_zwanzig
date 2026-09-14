// TDD RED — Issue #2128 (Scheibe 1 zu Epic #2127), AC-8 / AC-9 / AC-10.
//
// Spec: docs/specs/modules/pwa_installierbar_offline_start.md
// Runner: node:test (ADR-0020 — kein vitest).
//
// Ausfuehrung:
//   cd frontend && npm test -- src/lib/pwa/serviceWorkerUpdate.test.ts
//
// `./serviceWorkerUpdate.ts` existiert noch NICHT -> Import schlaegt fehl = RED.
//
// Keine Mock-Bibliothek: Registration, Worker und Container sind echte
// `EventTarget`-Doppel, die echte Ereignisse feuern. Geprueft wird das
// Verhalten des Prueflings auf diese Ereignisse, nicht eine zurueckgespiegelte
// Annahme.

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { initServiceWorkerUpdate } from './serviceWorkerUpdate.ts';
// #2317: echte SaveStatus-Instanzen fuer die Anmeldestelle (Faelle ganz unten).
import { SaveStatus } from '../stores/saveStatusStore.svelte.ts';

// ===========================================================================
// Doppel — echte EventTarget, echte Ereignisse
// ===========================================================================

class FakeWorker extends EventTarget {
	state = 'installing';
	scriptURL: string;
	/** Alles, was der Prueflings-Code an diesen Worker geschickt hat. */
	readonly posted: unknown[] = [];

	constructor(scriptURL = '/service-worker.js') {
		super();
		this.scriptURL = scriptURL;
	}

	postMessage(message: unknown): void {
		this.posted.push(message);
	}

	/** Setzt den Zustand und feuert `statechange` wie der Browser. */
	setState(state: string): void {
		this.state = state;
		this.dispatchEvent(new Event('statechange'));
	}
}

class FakeRegistration extends EventTarget {
	installing: FakeWorker | null = null;
	waiting: FakeWorker | null = null;
	active: FakeWorker | null = new FakeWorker();

	/** Der Browser haengt den neuen Worker an `installing` und feuert `updatefound`. */
	updateFound(worker: FakeWorker): void {
		this.installing = worker;
		this.dispatchEvent(new Event('updatefound'));
	}

	/** Der Browser schiebt den fertig installierten Worker nach `waiting`. */
	moveToWaiting(): void {
		this.waiting = this.installing;
		this.installing = null;
	}
}

class FakeContainer extends EventTarget {
	controller: FakeWorker | null = null;

	controllerChange(): void {
		this.dispatchEvent(new Event('controllerchange'));
	}
}

type Aufbau = {
	registration: FakeRegistration;
	container: FakeContainer;
	hinweise: number;
	neuladungen: number;
	applyUpdate: () => void;
};

/**
 * Baut den Prueflings-Aufbau. `mitController` = es laeuft bereits eine
 * installierte Fassung (kein Erstbesuch).
 */
function aufbau(mitController: boolean): Aufbau {
	const registration = new FakeRegistration();
	const container = new FakeContainer();
	if (mitController) {
		container.controller = registration.active;
	}

	const zaehler = { hinweise: 0, neuladungen: 0 };
	const steuerung = initServiceWorkerUpdate({
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		registration: registration as any,
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		container: container as any,
		onUpdateReady: () => {
			zaehler.hinweise += 1;
		},
		reload: () => {
			zaehler.neuladungen += 1;
		}
	});

	return {
		registration,
		container,
		get hinweise() {
			return zaehler.hinweise;
		},
		get neuladungen() {
			return zaehler.neuladungen;
		},
		applyUpdate: steuerung.applyUpdate
	};
}

// ===========================================================================
// AC-8 — der Hinweis erscheint nur, wenn wirklich eine NEUE Fassung bereitsteht
// ===========================================================================

test('AC-8: installierter neuer Worker bei laufender Fassung loest den Hinweis aus', () => {
	const a = aufbau(true);
	const neu = new FakeWorker('/service-worker.js?v=2');

	a.registration.updateFound(neu);
	neu.setState('installed');

	assert.equal(a.hinweise, 1, 'Hinweis "Neue Version verfuegbar" wurde nicht ausgeloest');
	assert.equal(a.neuladungen, 0, 'es darf nichts umgeschaltet und nichts neu geladen werden');
});

test('AC-8: ohne laufende Fassung (Erstinstallation) erscheint KEIN Hinweis', () => {
	const a = aufbau(false);
	const neu = new FakeWorker();

	a.registration.updateFound(neu);
	neu.setState('installed');

	assert.equal(
		a.hinweise,
		0,
		'bei der Erstinstallation gibt es keine alte Fassung — ein Update-Hinweis waere falsch'
	);
});

// ===========================================================================
// AC-9 — auf Bestaetigung wird genau die Uebernahme-Nachricht geschickt
// ===========================================================================

test('AC-9: Bestaetigung schickt genau {type:"SKIP_WAITING"} an den wartenden Worker', () => {
	const a = aufbau(true);
	const neu = new FakeWorker('/service-worker.js?v=2');

	a.registration.updateFound(neu);
	neu.setState('installed');
	a.registration.moveToWaiting();

	a.applyUpdate();

	assert.deepEqual(
		neu.posted,
		[{ type: 'SKIP_WAITING' }],
		'der wartende Worker muss genau eine SKIP_WAITING-Nachricht bekommen'
	);
});

// ===========================================================================
// AC-10 — ohne Bestaetigung passiert nichts
// ===========================================================================

test('AC-10: ohne Bestaetigung wird nichts an den wartenden Worker geschickt', () => {
	const a = aufbau(true);
	const neu = new FakeWorker('/service-worker.js?v=2');

	a.registration.updateFound(neu);
	neu.setState('installed');
	a.registration.moveToWaiting();

	// Kein applyUpdate() — der Nutzer tippt den Hinweis nicht an.
	assert.equal(a.hinweise, 1, 'der Hinweis soll sichtbar sein');
	assert.deepEqual(neu.posted, [], 'ohne Antippen darf nichts umgeschaltet werden');
	assert.equal(a.neuladungen, 0, 'ohne Antippen darf die Seite nicht neu laden');
});

// ===========================================================================
// AC-9 — der Wechsel der Kontrolle laedt GENAU EINMAL neu
// ===========================================================================

test('AC-9: controllerchange loest genau ein Neuladen aus', () => {
	const a = aufbau(true);

	a.container.controllerChange();

	assert.equal(a.neuladungen, 1, 'nach dem Wechsel der Kontrolle muss genau einmal neu geladen werden');
});

test('AC-9: zweimal controllerchange laedt trotzdem nur einmal neu', () => {
	const a = aufbau(true);

	a.container.controllerChange();
	a.container.controllerChange();

	assert.equal(
		a.neuladungen,
		1,
		'ein zweites controllerchange darf keine Neulade-Schleife ausloesen'
	);
});

// ###########################################################################
// TDD RED — Issue #2316 Scheibe B: aktive Update-Erkennung.
// Spec: docs/specs/modules/pwa_update_erkennung.md
//   § Implementation Details „serviceWorkerUpdate.ts (Scheibe B)", § AC-4/5/6/11/12/13
//
// Die sechs Faelle OBEN (#2128) bleiben unveraendert gruen. NEU und ROT sind
// alle Faelle mit Praefix „#2316 AC-…" unten.
//
// Zielschnittstelle (Erweiterung, bestehende vier Optionen unveraendert):
//   initServiceWorkerUpdate({
//     registration, container, onUpdateReady, reload,
//     document,        // EventTarget + visibilityState  -> 'visibilitychange'
//     window,          // EventTarget                    -> 'pageshow'
//     uhr,             // { now(): number }              -> 60-s-Drossel
//     timer,           // { setTimeout, clearTimeout, setInterval, clearInterval }
//     onUpdateFailed   // () => void, bei Worker-Nachricht { type: 'UPDATE_FEHLGESCHLAGEN' }
//   }) -> { applyUpdate(), spaeter() }
//
// Zeit ist ein hereingereichtes, von Hand vorgestelltes Doppel (kein
// Fake-Timer-Framework, kein waitForTimeout): echte Rueckrufe laufen genau
// dann, wenn die vorgestellte Zeit sie faellig macht.
// ###########################################################################

const SEKUNDE = 1_000;
const MINUTE = 60 * SEKUNDE;

/** Registrierung, deren Pruefaufrufe (`update()`) gezaehlt werden. */
class PruefbareRegistration extends FakeRegistration {
	pruefungen = 0;
	update(): Promise<this> {
		this.pruefungen += 1;
		return Promise.resolve(this);
	}
}

class FakeDokument extends EventTarget {
	visibilityState: 'visible' | 'hidden' = 'visible';
	setzeSichtbarkeit(s: 'visible' | 'hidden'): void {
		this.visibilityState = s;
		this.dispatchEvent(new Event('visibilitychange'));
	}
}

type Faellig = { faellig: number; fn: () => void; intervall: number | null };

/** Uhr + Zeitgeber in einem: Zeit laeuft nur, wenn der Test sie vorstellt. */
class FakeZeit {
	jetzt = 1_000_000;
	private naechsteId = 1;
	private readonly laufend = new Map<number, Faellig>();

	now = (): number => this.jetzt;
	setTimeout = (fn: () => void, ms: number): number => this.planen(fn, ms, null);
	setInterval = (fn: () => void, ms: number): number => this.planen(fn, ms, ms);
	clearTimeout = (id: unknown): void => void this.laufend.delete(id as number);
	clearInterval = (id: unknown): void => void this.laufend.delete(id as number);

	private planen(fn: () => void, ms: number, intervall: number | null): number {
		const id = this.naechsteId++;
		this.laufend.set(id, { faellig: this.jetzt + ms, fn, intervall });
		return id;
	}

	aktiveIntervalle(): number {
		return [...this.laufend.values()].filter((t) => t.intervall !== null).length;
	}

	/** Stellt die Uhr vor und fuehrt jeden faellig gewordenen Rueckruf in Reihenfolge aus. */
	vergehen(ms: number): void {
		const ziel = this.jetzt + ms;
		for (;;) {
			let naechster: [number, Faellig] | null = null;
			for (const eintrag of this.laufend) {
				if (eintrag[1].faellig <= ziel && (!naechster || eintrag[1].faellig < naechster[1].faellig)) {
					naechster = eintrag;
				}
			}
			if (!naechster) break;
			const [id, t] = naechster;
			this.jetzt = t.faellig;
			if (t.intervall === null) this.laufend.delete(id);
			else t.faellig += t.intervall;
			t.fn();
		}
		this.jetzt = ziel;
	}
}

type ModulUnterTest = typeof import('./serviceWorkerUpdate.ts');

let kaltstartZaehler = 0;
/** Frische Modul-Instanz = Kaltstart der App (Modul-Neuinitialisierung). */
async function kaltstart(): Promise<ModulUnterTest> {
	kaltstartZaehler += 1;
	return import(new URL(`./serviceWorkerUpdate.ts?kaltstart=${kaltstartZaehler}`, import.meta.url).href);
}

type AufbauMitAusloesern = {
	registration: PruefbareRegistration;
	container: FakeContainer;
	dokument: FakeDokument;
	fenster: EventTarget;
	zeit: FakeZeit;
	zaehler: { hinweise: number; neuladungen: number; fehlschlaege: number };
	steuerung: { applyUpdate: () => void | Promise<void>; spaeter: () => void };
};

function aufbauMitAusloesern(
	optionen: {
		modul?: ModulUnterTest;
		registration?: PruefbareRegistration;
		zeit?: FakeZeit;
		dokument?: FakeDokument;
		fenster?: EventTarget;
		/** #2317 — nur gesetzt, wenn ein Test ihn ausdruecklich hereinreicht. */
		awaitPendingSave?: () => Promise<boolean>;
	} = {}
): AufbauMitAusloesern {
	const registration = optionen.registration ?? new PruefbareRegistration();
	const container = new FakeContainer();
	container.controller = registration.active;
	const dokument = optionen.dokument ?? new FakeDokument();
	const fenster = optionen.fenster ?? new EventTarget();
	const zeit = optionen.zeit ?? new FakeZeit();
	const zaehler = { hinweise: 0, neuladungen: 0, fehlschlaege: 0 };
	const init = optionen.modul?.initServiceWorkerUpdate ?? initServiceWorkerUpdate;

	const steuerung = init({
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		registration: registration as any,
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		container: container as any,
		onUpdateReady: () => void (zaehler.hinweise += 1),
		reload: () => void (zaehler.neuladungen += 1),
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		document: dokument as any,
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		window: fenster as any,
		uhr: zeit,
		timer: zeit,
		onUpdateFailed: () => void (zaehler.fehlschlaege += 1),
		...(optionen.awaitPendingSave ? { awaitPendingSave: optionen.awaitPendingSave } : {})
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
	} as any) as unknown as AufbauMitAusloesern['steuerung'];

	return { registration, container, dokument, fenster, zeit, zaehler, steuerung };
}

/** Eine neue Fassung ist installiert und wartet. */
function neueFassungWartet(a: AufbauMitAusloesern): FakeWorker {
	const neu = new FakeWorker('/service-worker.js');
	a.registration.updateFound(neu);
	neu.setState('installed');
	a.registration.moveToWaiting();
	return neu;
}

// ===========================================================================
// #2316 AC-4 — Drossel 60 s, Intervall 30 min nur bei sichtbarer Seite
// ===========================================================================

test('#2316 AC-4: mehrere Pruef-Ausloeser binnen 60 s pruefen genau einmal, danach wieder', () => {
	const a = aufbauMitAusloesern();
	a.zeit.vergehen(61 * SEKUNDE);
	const basis = a.registration.pruefungen;

	a.fenster.dispatchEvent(new Event('pageshow'));
	a.dokument.setzeSichtbarkeit('visible');
	a.fenster.dispatchEvent(new Event('pageshow'));
	a.zeit.vergehen(10 * SEKUNDE);
	a.dokument.setzeSichtbarkeit('visible');

	assert.equal(
		a.registration.pruefungen - basis,
		1,
		'binnen 60 s darf genau EINE Pruefung stattfinden — nicht keine (Ausloeser wirkungslos), nicht mehrere (keine Drossel)'
	);

	a.zeit.vergehen(60 * SEKUNDE);
	a.fenster.dispatchEvent(new Event('pageshow'));
	assert.equal(a.registration.pruefungen - basis, 2, 'nach Ablauf der 60 s muss ein Ausloeser wieder pruefen');
});

test('#2316 AC-4: das 30-Minuten-Intervall laeuft nur, solange die Seite sichtbar ist', () => {
	const a = aufbauMitAusloesern();
	a.zeit.vergehen(61 * SEKUNDE);

	let basis = a.registration.pruefungen;
	a.zeit.vergehen(30 * MINUTE);
	assert.equal(a.registration.pruefungen - basis, 1, 'bei sichtbarer Seite muss alle 30 Minuten geprueft werden');

	a.dokument.setzeSichtbarkeit('hidden');
	assert.equal(a.zeit.aktiveIntervalle(), 0, 'beim Verstecken muss das Intervall gestoppt werden');
	basis = a.registration.pruefungen;
	a.zeit.vergehen(2 * 60 * MINUTE);
	assert.equal(a.registration.pruefungen - basis, 0, 'bei versteckter Seite darf das Intervall nicht pruefen');

	a.dokument.setzeSichtbarkeit('visible');
	assert.equal(a.zeit.aktiveIntervalle(), 1, 'beim Sichtbarwerden muss das Intervall neu starten — genau eines');
	basis = a.registration.pruefungen;
	a.zeit.vergehen(30 * MINUTE);
	assert.equal(a.registration.pruefungen - basis, 1, 'nach dem Sichtbarwerden laeuft das 30-Minuten-Intervall wieder');
});

// ===========================================================================
// #2316 AC-5 — wartet schon ein Worker, wird nicht weiter geprueft
// ===========================================================================

test('#2316 AC-5: solange ein Worker wartet, loesen Ausloeser keine Pruefanfrage mehr aus', () => {
	const a = aufbauMitAusloesern();
	// Gegenprobe: ohne wartenden Worker prueft derselbe Ausloeser tatsaechlich —
	// sonst waere „0 Pruefungen" unten auch mit wirkungslosen Ausloesern erfuellt.
	a.zeit.vergehen(61 * SEKUNDE);
	const vorher = a.registration.pruefungen;
	a.fenster.dispatchEvent(new Event('pageshow'));
	assert.equal(a.registration.pruefungen - vorher, 1, 'Vorbedingung: ohne wartenden Worker prueft pageshow');

	neueFassungWartet(a);
	a.zeit.vergehen(61 * SEKUNDE);
	const basis = a.registration.pruefungen;

	a.fenster.dispatchEvent(new Event('pageshow'));
	a.dokument.setzeSichtbarkeit('visible');
	a.zeit.vergehen(31 * MINUTE);
	a.fenster.dispatchEvent(new Event('pageshow'));

	assert.equal(a.registration.pruefungen - basis, 0, 'mit wartendem Worker darf keine weitere Pruefanfrage entstehen');
});

// ===========================================================================
// #2316 AC-6 — „Später" haelt bis zum naechsten Kaltstart
// ===========================================================================

test('#2316 AC-6: nach „Später" erscheint der Hinweis nicht erneut — erst nach einem Kaltstart', async () => {
	const zeit = new FakeZeit();
	const registration = new PruefbareRegistration();
	const sitzung = aufbauMitAusloesern({ modul: await kaltstart(), registration, zeit });
	neueFassungWartet(sitzung);
	assert.equal(sitzung.zaehler.hinweise, 1, 'Vorbedingung: der Hinweis wird angezeigt');

	assert.equal(typeof sitzung.steuerung.spaeter, 'function', 'die Steuerung muss spaeter() anbieten');
	sitzung.steuerung.spaeter();

	// Weitere Ausloeser und sogar eine noch neuere Fassung in derselben Sitzung.
	zeit.vergehen(2 * MINUTE);
	sitzung.fenster.dispatchEvent(new Event('pageshow'));
	sitzung.dokument.setzeSichtbarkeit('hidden');
	sitzung.dokument.setzeSichtbarkeit('visible');
	zeit.vergehen(31 * MINUTE);
	const nochNeuer = new FakeWorker('/service-worker.js');
	registration.updateFound(nochNeuer);
	nochNeuer.setState('installed');

	assert.equal(sitzung.zaehler.hinweise, 1, 'nach „Später" darf der Hinweis in derselben Sitzung nicht wiederkommen');
	assert.equal(sitzung.zaehler.neuladungen, 0, '„Später" darf nichts umschalten');

	// Kaltstart: frische Modul-Instanz, derselbe wartende Worker.
	const nachKaltstart = aufbauMitAusloesern({ modul: await kaltstart(), registration, zeit: new FakeZeit() });
	assert.equal(nachKaltstart.zaehler.hinweise, 1, 'nach einem Kaltstart muss der Hinweis wieder erscheinen');
});

// ===========================================================================
// #2316 AC-11 — Fehlschlag im Worker: Meldung, kein Neuladen, erneut antippbar
// ===========================================================================

test('#2316 AC-11: meldet der Worker den Fehlschlag, gibt es eine Meldung, kein Neuladen, und Aktualisieren geht erneut', () => {
	const a = aufbauMitAusloesern();
	const neu = neueFassungWartet(a);

	a.steuerung.applyUpdate();
	a.container.dispatchEvent(new MessageEvent('message', { data: { type: 'UPDATE_FEHLGESCHLAGEN' } }));

	assert.equal(a.zaehler.fehlschlaege, 1, 'die Fehlschlag-Nachricht des Workers muss beim Fenster ankommen');
	a.zeit.vergehen(10 * SEKUNDE);
	assert.equal(a.zaehler.neuladungen, 0, 'nach einem Fehlschlag darf NICHT neu geladen werden');

	a.steuerung.applyUpdate();
	assert.deepEqual(
		neu.posted,
		[{ type: 'SKIP_WAITING' }, { type: 'SKIP_WAITING' }],
		'„Aktualisieren" muss nach dem Fehlschlag erneut wirken'
	);
});

test('#2316 AC-11: fremde Nachrichten des Workers gelten nicht als Fehlschlag', () => {
	const a = aufbauMitAusloesern();
	neueFassungWartet(a);
	a.steuerung.applyUpdate();
	a.container.dispatchEvent(new MessageEvent('message', { data: { type: 'ETWAS_ANDERES' } }));
	assert.equal(a.zaehler.fehlschlaege, 0, 'nur UPDATE_FEHLGESCHLAGEN ist ein Fehlschlag');

	// Gegenprobe: dieselbe Verdrahtung erkennt die echte Meldung.
	a.container.dispatchEvent(new MessageEvent('message', { data: { type: 'UPDATE_FEHLGESCHLAGEN' } }));
	assert.equal(a.zaehler.fehlschlaege, 1);
});

// ===========================================================================
// #2316 AC-12 — Rueckfall: activated ohne controllerchange -> genau EIN Neuladen nach 4 s
// ===========================================================================

test('#2316 AC-12: bleibt controllerchange nach „activated" aus, wird nach 4 s genau einmal neu geladen', () => {
	const a = aufbauMitAusloesern();
	const neu = neueFassungWartet(a);

	a.steuerung.applyUpdate();
	neu.setState('activating');
	neu.setState('activated');

	a.zeit.vergehen(3_999);
	assert.equal(a.zaehler.neuladungen, 0, 'vor Ablauf der 4 s darf noch nicht neu geladen werden');
	a.zeit.vergehen(2);
	assert.equal(a.zaehler.neuladungen, 1, 'nach 4 s ohne controllerchange muss genau einmal neu geladen werden');

	a.zeit.vergehen(60 * SEKUNDE);
	a.container.controllerChange();
	assert.equal(a.zaehler.neuladungen, 1, 'kein zweites Neuladen — weder per Timer noch per verspaetetem controllerchange');
});

test('#2316 AC-12: kommt controllerchange rechtzeitig, bleibt es beim einen Neuladen (kein Timer-Nachschlag)', () => {
	const a = aufbauMitAusloesern();
	const neu = neueFassungWartet(a);

	a.steuerung.applyUpdate();
	neu.setState('activated');
	a.zeit.vergehen(1_000);
	a.container.controllerChange();
	a.zeit.vergehen(10 * SEKUNDE);

	assert.equal(a.zaehler.neuladungen, 1);
});

// ===========================================================================
// #2316 AC-13 — haengt der Worker in „installed", kein blinder Reload
// ===========================================================================

test('#2316 AC-13: bleibt der Worker nach dem Antippen in „installed", loest kein Timer ein Neuladen aus', () => {
	const a = aufbauMitAusloesern();
	const neu = neueFassungWartet(a);

	a.steuerung.applyUpdate();
	a.zeit.vergehen(10 * MINUTE);

	assert.equal(a.zaehler.neuladungen, 0, 'ein haengender Download darf keinen blinden Reload ausloesen');

	// Gegenprobe: der Rueckfall haengt am Zustand „activated", nicht an der
	// verstrichenen Zeit — sonst waere „0 Neuladungen" oben auch ohne jeden
	// Rueckfall erfuellt.
	neu.setState('activated');
	a.zeit.vergehen(4_001);
	assert.equal(a.zaehler.neuladungen, 1, 'erst mit „activated" greift der 4-s-Rueckfall');
});

// ###########################################################################
// TDD RED — Issue #2317 (Epic #2127): „Aktualisieren" wartet auf eine
// ausstehende Speicherung.
// Spec: docs/specs/modules/speicherung_beim_neuladen.md
//   § Implementation Details „Baustein 2 — „Aktualisieren" wartet", § AC-6 (Unit-Anteil), § AC-7
//
// Zielschnittstelle:
//   serviceWorkerUpdate.ts: neue Option `awaitPendingSave?: () => Promise<boolean>`;
//     `applyUpdate()` darf ein Promise liefern. Erst `awaitPendingSave` abwarten;
//     bei false ODER Wurf: KEIN SKIP_WAITING, KEIN reload, spaeter erneut antippbar.
//   stores/aktiveSpeicherung.ts (neu, svelte-frei):
//     erzeugeSpeicherAnmeldestelle() -> { anmelden(ctl) -> abmelden, wartenAufAusstehendeSpeicherung() }
//
// 🔴 VERTRAGSZWANG fuer /50: OHNE `awaitPendingSave` muss `applyUpdate()` die
// SKIP_WAITING-Nachricht weiterhin SYNCHRON im selben Tick schicken. Die
// bestehenden Faelle oben (#2128 AC-9, #2316 AC-11/12/13) pruefen `neu.posted`
// direkt nach dem Aufruf, ohne zu warten — schon ein `await undefined` vor dem
// postMessage macht sie rot. Nur MIT Option darf gewartet werden.
//
// Die Anmeldestelle arbeitet mit ECHTEN SaveStatus-Instanzen (Prototype-Methoden
// schedule/flush/doSave); `saveFn` ist ein aufzeichnender Transport-Doppel.
// ###########################################################################

type Anmeldestelle = {
	anmelden(ctl: SaveStatus): () => void;
	wartenAufAusstehendeSpeicherung(): Promise<boolean>;
};

async function erzeugeAnmeldestelle(): Promise<Anmeldestelle> {
	const m = (await import('../stores/aktiveSpeicherung.ts')) as unknown as {
		erzeugeSpeicherAnmeldestelle?: () => Anmeldestelle;
	};
	assert.equal(typeof m.erzeugeSpeicherAnmeldestelle, 'function', 'erzeugeSpeicherAnmeldestelle fehlt');
	return m.erzeugeSpeicherAnmeldestelle!();
}

/** Echte SaveStatus-Instanz ohne Konstruktor (Muster aus saveStatus.test.ts). */
function createSaveStatus(tripId?: string): SaveStatus {
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
	if (tripId) fields._tripId = tripId;
	return inst;
}

async function ruhe(): Promise<void> {
	for (let i = 0; i < 5; i++) await new Promise<void>((r) => setImmediate(r));
}

/** Konfliktantwort, wie `api.ts` sie bei 412 wirft (Status + deutsche Servermeldung). */
function konflikt412() {
	return {
		status: 412,
		error: 'precondition_failed',
		detail: 'Der Stand wurde zwischenzeitlich an anderer Stelle geaendert.'
	};
}

/** Offline-Ablehnung, wie `api.ts` sie ohne Verbindung wirft (#2131). */
function offlineFehler() {
	return Object.assign(new Error('Ohne Verbindung lässt sich nichts speichern — die Änderung wurde nicht abgeschickt.'), {
		status: 0
	});
}

// ===========================================================================
// AC-7 — serviceWorkerUpdate: ohne Freigabe kein Fassungswechsel
// ===========================================================================

test('#2317 AC-7: awaitPendingSave meldet false → kein SKIP_WAITING, kein Neuladen, spaeter erneut antippbar', async () => {
	// GIVEN: eine neue Fassung wartet; die ausstehende Speicherung scheitert
	let freigabe = false;
	const a = aufbauMitAusloesern({ awaitPendingSave: async () => freigabe });
	const neu = neueFassungWartet(a);

	// WHEN: der Nutzer tippt „Aktualisieren"
	await a.steuerung.applyUpdate();
	await ruhe();

	// THEN: die Seite bleibt, die Fehler-/Konfliktanzeige bleibt sichtbar
	assert.deepEqual(neu.posted, [], 'ohne gesicherte Speicherung darf keine SKIP_WAITING-Nachricht rausgehen');
	neu.setState('activated');
	a.zeit.vergehen(5 * SEKUNDE);
	assert.equal(a.zaehler.neuladungen, 0, 'ohne gesicherte Speicherung darf nicht neu geladen werden (auch kein 4-s-Rueckfall)');

	// Gegenprobe/Wiederholung: ist das Speichern spaeter gelungen, wirkt „Aktualisieren" erneut
	neu.setState('installed');
	freigabe = true;
	await a.steuerung.applyUpdate();
	await ruhe();
	assert.deepEqual(neu.posted, [{ type: 'SKIP_WAITING' }], 'nach gelungener Speicherung muss „Aktualisieren" wieder wirken');
});

test('#2317 AC-7: awaitPendingSave wirft → kein SKIP_WAITING, kein Neuladen, spaeter erneut antippbar', async () => {
	let wirft = true;
	const a = aufbauMitAusloesern({
		awaitPendingSave: async () => {
			if (wirft) throw new Error('Speichern unerwartet abgebrochen');
			return true;
		}
	});
	const neu = neueFassungWartet(a);

	// Ob applyUpdate den Wurf weiterreicht oder schluckt, ist nicht festgelegt —
	// festgelegt ist nur, dass KEIN Fassungswechsel folgt.
	await Promise.resolve()
		.then(() => a.steuerung.applyUpdate())
		.catch(() => {});
	await ruhe();

	assert.deepEqual(neu.posted, [], 'nach einem Wurf beim Warten darf keine SKIP_WAITING-Nachricht rausgehen');
	a.zeit.vergehen(5 * SEKUNDE);
	assert.equal(a.zaehler.neuladungen, 0, 'nach einem Wurf darf nicht neu geladen werden');

	wirft = false;
	await a.steuerung.applyUpdate();
	await ruhe();
	assert.deepEqual(neu.posted, [{ type: 'SKIP_WAITING' }], '„Aktualisieren" muss nach einem Wurf erneut wirken');
});

test('#2317 AC-6 (Unit): solange awaitPendingSave offen ist, kein SKIP_WAITING — erst nach resolve(true) genau einmal', async () => {
	let freigeben!: (ok: boolean) => void;
	const offen = new Promise<boolean>((r) => {
		freigeben = r;
	});
	const a = aufbauMitAusloesern({ awaitPendingSave: () => offen });
	const neu = neueFassungWartet(a);

	const lauf = a.steuerung.applyUpdate();
	await ruhe();
	assert.deepEqual(neu.posted, [], 'waehrend die Speicherung laeuft, darf die neue Fassung noch nicht uebernehmen');
	assert.equal(a.zaehler.neuladungen, 0);

	freigeben(true);
	await lauf;
	await ruhe();
	assert.deepEqual(neu.posted, [{ type: 'SKIP_WAITING' }], 'nach abgeschlossener Speicherung genau EINE SKIP_WAITING-Nachricht');
});

test('#2317 F006: zweimal „Aktualisieren" ueberlappend → awaitPendingSave laeuft EINMAL, genau eine SKIP_WAITING-Nachricht', async () => {
	let aufrufe = 0;
	let freigeben!: (ok: boolean) => void;
	const a = aufbauMitAusloesern({
		awaitPendingSave: () => {
			aufrufe++;
			return new Promise<boolean>((r) => {
				freigeben = r;
			});
		}
	});
	const neu = neueFassungWartet(a);

	const erster = a.steuerung.applyUpdate();
	const zweiter = a.steuerung.applyUpdate();
	await ruhe();
	assert.equal(aufrufe, 1, 'ein zweites Antippen waehrend des Wartens darf keinen zweiten Speicher-Abschluss starten');
	assert.deepEqual(neu.posted, [], 'solange gewartet wird, kein SKIP_WAITING');

	freigeben(true);
	await Promise.all([erster, zweiter]);
	await ruhe();
	assert.deepEqual(neu.posted, [{ type: 'SKIP_WAITING' }], 'beide Antipper zusammen ergeben genau EINE SKIP_WAITING-Nachricht');
});

// ===========================================================================
// AC-6/AC-7 — Anmeldestelle: ausstehende Speicherung regulaer abschliessen
// ===========================================================================

test('#2317 Anmeldestelle: nichts angemeldet → true (Aktualisieren darf weiter)', async () => {
	const stelle = await erzeugeAnmeldestelle();
	assert.equal(await stelle.wartenAufAusstehendeSpeicherung(), true);
});

test('#2317 Anmeldestelle: angemeldet, aber nichts ausstehend → true ohne Speichervorgang', async () => {
	const stelle = await erzeugeAnmeldestelle();
	const ctl = createSaveStatus('gr20');
	stelle.anmelden(ctl);

	assert.equal(await stelle.wartenAufAusstehendeSpeicherung(), true);
	assert.equal(ctl.state, 'idle', 'ohne ausstehende Eingabe kein Speichervorgang');
	assert.equal(ctl.savedAt, null, 'ohne Speichervorgang kein neuer Gespeichert-Zeitstempel');
});

test('#2317 AC-6 Anmeldestelle: ausstehende Eingabe wird OHNE keepalive gespeichert, danach true', async () => {
	// GIVEN: eine Eingabe wartet im 700-ms-Fenster
	const stelle = await erzeugeAnmeldestelle();
	const ctl = createSaveStatus('gr20');
	stelle.anmelden(ctl);
	const inits: Array<RequestInit | undefined> = [];
	ctl.schedule(async (init) => {
		inits.push(init);
	});

	// WHEN
	const ergebnis = await stelle.wartenAufAusstehendeSpeicherung();

	// THEN
	assert.equal(inits.length, 1, 'die ausstehende Speicherung muss genau einmal abgesetzt werden');
	assert.notEqual(
		inits[0]?.keepalive,
		true,
		'regulaer speichern: ohne keepalive — nur dann laeuft sie durch die Warteschlange mit If-Match'
	);
	assert.equal(ergebnis, true, 'nach gelungener Speicherung darf die neue Fassung uebernommen werden');
	assert.equal(ctl.hasPending, false);
	assert.equal(ctl.state, 'idle');
});

test('#2317 AC-7 Anmeldestelle: Konflikt (412) → false, Konfliktanzeige steht, Wiederholen bleibt moeglich', async () => {
	const stelle = await erzeugeAnmeldestelle();
	const ctl = createSaveStatus('gr20');
	stelle.anmelden(ctl);
	const saveFn = async () => {
		throw konflikt412();
	};
	ctl.schedule(saveFn);

	const ergebnis = await stelle.wartenAufAusstehendeSpeicherung();

	assert.equal(ergebnis, false, 'ein Konflikt darf das Aktualisieren nicht freigeben');
	assert.equal(ctl.state, 'conflict', 'die Konfliktanzeige des Reiters muss sichtbar bleiben');
	// Sekundaer: die Eingabe ist nicht verworfen — der gescheiterte Vorgang liegt
	// fuer „Wiederholen" (retryConflict) bereit. `_pendingFn` leert doSave bewusst.
	const lastFailed = (ctl as unknown as { _lastFailed: { fn: unknown } | null })._lastFailed;
	assert.equal(lastFailed?.fn, saveFn, 'der abgelehnte Speichervorgang muss fuer Wiederholen erhalten bleiben');
});

test('#2317 AC-7 Anmeldestelle: offline / Netzfehler → false, Fehleranzeige steht', async () => {
	const stelle = await erzeugeAnmeldestelle();
	const ctl = createSaveStatus('gr20');
	stelle.anmelden(ctl);
	ctl.schedule(async () => {
		throw offlineFehler();
	});

	const ergebnis = await stelle.wartenAufAusstehendeSpeicherung();

	assert.equal(ergebnis, false, 'ohne Verbindung darf das Aktualisieren nicht freigegeben werden');
	assert.equal(ctl.state, 'error', 'die Fehleranzeige des Reiters muss sichtbar bleiben');
});

test('#2317 Anmeldestelle: nach dem Abmelden → true ohne Speichervorgang', async () => {
	const stelle = await erzeugeAnmeldestelle();
	const ctl = createSaveStatus('gr20');
	const abmelden = stelle.anmelden(ctl);
	let aufrufe = 0;
	ctl.schedule(async () => {
		aufrufe++;
	});

	abmelden();
	const ergebnis = await stelle.wartenAufAusstehendeSpeicherung();

	assert.equal(ergebnis, true, 'eine abgemeldete Seite darf das Aktualisieren nicht aufhalten');
	assert.equal(aufrufe, 0, 'eine abgemeldete Seite darf nicht mehr gespeichert werden');
	ctl.cancel();
});

/**
 * #2317 AC-6 (Nachbesserung): der Speicher-Takt ist schon abgelaufen, der
 * regulaere PUT ist UNTERWEGS (`hasPending` false). Liefert den Freigabe-Schalter.
 */
async function speicherungUnterwegs(ctl: SaveStatus): Promise<{ antworten: (fehler?: unknown) => void }> {
	let aufloesen!: () => void;
	let ablehnen!: (e: unknown) => void;
	let abgesetzt = false;
	ctl.schedule(async () => {
		abgesetzt = true;
		await new Promise<void>((res, rej) => {
			aufloesen = res;
			ablehnen = rej;
		});
	}, 1);
	for (let i = 0; i < 50 && !abgesetzt; i++) await new Promise<void>((r) => setTimeout(r, 2));
	assert.equal(abgesetzt, true, 'Vorbedingung: der Speicher-Takt ist abgelaufen, der PUT ist unterwegs');
	assert.equal(ctl.hasPending, false, 'Vorbedingung: nichts steht mehr aus — nur der laufende PUT');
	assert.equal(ctl.state, 'saving', 'Vorbedingung: der PUT laeuft noch');
	return { antworten: (fehler) => (fehler === undefined ? aufloesen() : ablehnen(fehler)) };
}

test('#2317 AC-6 Anmeldestelle: ein UNTERWEGS befindlicher PUT wird abgewartet — erst nach seiner Antwort true', async () => {
	const stelle = await erzeugeAnmeldestelle();
	const ctl = createSaveStatus('gr20');
	stelle.anmelden(ctl);
	const put = await speicherungUnterwegs(ctl);

	let ergebnis: boolean | undefined;
	const warten = stelle.wartenAufAusstehendeSpeicherung().then((ok) => (ergebnis = ok));
	await ruhe();
	assert.equal(ergebnis, undefined, 'solange der PUT unterwegs ist, darf das Warten nicht freigeben — das Neuladen braeche ihn ab');

	put.antworten();
	await warten;
	assert.equal(ergebnis, true, 'nach angenommenem PUT darf die neue Fassung uebernehmen');
	assert.equal(ctl.state, 'idle');
});

test('#2317 AC-7 Anmeldestelle: scheitert der UNTERWEGS befindliche PUT (offline) → false, Fehleranzeige steht', async () => {
	const stelle = await erzeugeAnmeldestelle();
	const ctl = createSaveStatus('gr20');
	stelle.anmelden(ctl);
	const put = await speicherungUnterwegs(ctl);

	let ergebnis: boolean | undefined;
	const warten = stelle.wartenAufAusstehendeSpeicherung().then((ok) => (ergebnis = ok));
	await ruhe();
	assert.equal(ergebnis, undefined, 'solange der PUT unterwegs ist, darf das Warten nicht freigeben');

	put.antworten(offlineFehler());
	await warten;
	assert.equal(ergebnis, false, 'ein gescheiterter laufender PUT darf das Aktualisieren nicht freigeben');
	assert.equal(ctl.state, 'error', 'die Fehleranzeige des Reiters muss sichtbar bleiben');
});

// ===========================================================================
// AC-6/AC-7 — Zusammenspiel: Anmeldestelle als awaitPendingSave
// ===========================================================================

test('#2317 AC-6 Zusammenspiel: SKIP_WAITING erst NACH abgeschlossener regulaerer Speicherung', async () => {
	// GIVEN: Detailseite angemeldet, Eingabe ausstehend, neue Fassung wartet
	const stelle = await erzeugeAnmeldestelle();
	const ctl = createSaveStatus('gr20');
	stelle.anmelden(ctl);
	const inits: Array<RequestInit | undefined> = [];
	let unterwegsFreigeben!: () => void;
	const unterwegs = new Promise<void>((r) => {
		unterwegsFreigeben = r;
	});
	ctl.schedule(async (init) => {
		inits.push(init);
		await unterwegs;
	});
	const a = aufbauMitAusloesern({ awaitPendingSave: () => stelle.wartenAufAusstehendeSpeicherung() });
	const neu = neueFassungWartet(a);

	// WHEN: „Aktualisieren"
	const lauf = a.steuerung.applyUpdate();
	await ruhe();

	// THEN: erst speichern ...
	assert.equal(inits.length, 1, 'die ausstehende Speicherung muss sofort abgesetzt werden');
	assert.notEqual(inits[0]?.keepalive, true, 'regulaer, ohne keepalive');
	assert.deepEqual(neu.posted, [], 'solange die Speicherung unterwegs ist, kein SKIP_WAITING');

	// ... dann die neue Fassung
	unterwegsFreigeben();
	await lauf;
	await ruhe();
	assert.deepEqual(neu.posted, [{ type: 'SKIP_WAITING' }], 'nach der Speicherung genau eine SKIP_WAITING-Nachricht');
	assert.equal(ctl.state, 'idle');
});

for (const [fall, fehler, zustand] of [
	['Konflikt (412)', konflikt412, 'conflict'],
	['offline', offlineFehler, 'error']
] as const) {
	test(`#2317 AC-7 Zusammenspiel: ${fall} beim Speichern → Seite laedt NICHT neu, Anzeige „${zustand}" bleibt`, async () => {
		const stelle = await erzeugeAnmeldestelle();
		const ctl = createSaveStatus('gr20');
		stelle.anmelden(ctl);
		ctl.schedule(async () => {
			throw fehler();
		});
		const a = aufbauMitAusloesern({ awaitPendingSave: () => stelle.wartenAufAusstehendeSpeicherung() });
		const neu = neueFassungWartet(a);

		await Promise.resolve()
			.then(() => a.steuerung.applyUpdate())
			.catch(() => {});
		await ruhe();
		neu.setState('activated');
		a.zeit.vergehen(5 * SEKUNDE);

		assert.deepEqual(neu.posted, [], 'ohne gesicherte Speicherung keine SKIP_WAITING-Nachricht');
		assert.equal(a.zaehler.neuladungen, 0, 'die Seite darf nicht neu laden');
		assert.equal(ctl.state, zustand, 'die bestehende Fehler-/Konfliktanzeige muss sichtbar bleiben');
	});
}
