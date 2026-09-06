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
