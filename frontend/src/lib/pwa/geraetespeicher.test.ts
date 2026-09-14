// TDD RED — Issue #2317 (Epic #2127): Nachlade-Merker im mandantengetrennten Geraetespeicher.
//
// Spec: docs/specs/modules/speicherung_beim_neuladen.md
//   § Implementation Details „Baustein 3 — Anzeige nach Browser-Neuladen"
//   § Acceptance Criteria AC-14, AC-15 · ADR-0003
//
// Zielschnittstelle (Erweiterung von geraetespeicher.ts — existiert noch NICHT;
// jeder Test importiert dynamisch, damit jeder Fall einzeln rot wird):
//   NACHLADE_MERKER = 'gz-nachladen'           Wert: JSON.stringify({ typ, id })
//   merkeSpeicherungBeimEntladen(kennung)
//   nimmSpeicherungBeimEntladen(kennung): boolean
//     - true nur bei genau dieser Kennung, Merker danach geloescht
//     - fremde Kennung: false, Merker bleibt liegen
//     - unlesbarer Inhalt: false, Merker geloescht
//   raeumeGeraetespeicher() loescht den Merker SYNCHRON zu Beginn
//   nachEntladenNachladen.ts: starteNachladenNachEntladen(...)
//
// Laufzeit: Node 22 kennt weder `sessionStorage` noch `window`. sessionStorage
// ist ein echtes In-Memory-Storage; `window = {}` (ohne `caches`), `navigator`
// hat in Node kein `serviceWorker` → das Raeumen misst sofort "leer" und kehrt
// nach der Ruhezeit (~1,5 s) mit true zurueck.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/pwa/geraetespeicher.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { SaveStatus } from '../stores/saveStatusStore.svelte.ts';
import {
	installiereSitzungsspeicher,
	entferneSitzungsspeicher,
	type SitzungsspeicherDoppel
} from '../__tests__/sitzungsspeicherDoppel.ts';

type Kennung = { typ: 'trip' | 'vergleich'; id: string };

type GeraetespeicherModul = {
	NACHLADE_MERKER: string;
	merkeSpeicherungBeimEntladen: (k: Kennung) => void;
	nimmSpeicherungBeimEntladen: (k: Kennung) => boolean;
	raeumeGeraetespeicher: () => Promise<boolean>;
};

async function ladeGeraetespeicher(): Promise<GeraetespeicherModul> {
	const m = (await import('./geraetespeicher.ts')) as unknown as GeraetespeicherModul;
	assert.equal(typeof m.NACHLADE_MERKER, 'string', 'NACHLADE_MERKER muss exportiert sein');
	assert.equal(m.NACHLADE_MERKER, 'gz-nachladen', 'Schluessel laut Vertrag: gz-nachladen');
	assert.equal(typeof m.merkeSpeicherungBeimEntladen, 'function', 'merkeSpeicherungBeimEntladen fehlt');
	assert.equal(typeof m.nimmSpeicherungBeimEntladen, 'function', 'nimmSpeicherungBeimEntladen fehlt');
	return m;
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

let speicher: SitzungsspeicherDoppel;

beforeEach(() => {
	speicher = installiereSitzungsspeicher();
	(globalThis as { window?: unknown }).window = {};
});

afterEach(() => {
	entferneSitzungsspeicher();
	delete (globalThis as { window?: unknown }).window;
});

// ===========================================================================
// Format und Kennungspruefung des Merkers
// ===========================================================================

describe('Issue #2317: Nachlade-Merker — Format und Kennung', () => {
	test('merkeSpeicherungBeimEntladen legt unter gz-nachladen genau {typ,id} ab', async () => {
		const m = await ladeGeraetespeicher();

		m.merkeSpeicherungBeimEntladen({ typ: 'vergleich', id: 'cp-alpen' });

		assert.equal(speicher.length, 1, 'genau ein Eintrag');
		assert.deepEqual(JSON.parse(speicher.getItem('gz-nachladen') as string), { typ: 'vergleich', id: 'cp-alpen' });
	});

	test('nimmSpeicherungBeimEntladen: Treffer → true, danach ist der Merker weg (zweites Lesen → false)', async () => {
		const m = await ladeGeraetespeicher();
		m.merkeSpeicherungBeimEntladen({ typ: 'trip', id: 'gr20' });

		assert.equal(m.nimmSpeicherungBeimEntladen({ typ: 'trip', id: 'gr20' }), true, 'eigene Kennung muss erkannt werden');
		assert.equal(speicher.getItem(m.NACHLADE_MERKER), null, 'nach dem Lesen muss der Merker geloescht sein');
		assert.equal(m.nimmSpeicherungBeimEntladen({ typ: 'trip', id: 'gr20' }), false, 'ein verbrauchter Merker gilt nicht erneut');
	});

	test('nimmSpeicherungBeimEntladen: fremde ID → false, der Merker bleibt liegen', async () => {
		const m = await ladeGeraetespeicher();
		m.merkeSpeicherungBeimEntladen({ typ: 'trip', id: 'gr20' });

		assert.equal(m.nimmSpeicherungBeimEntladen({ typ: 'trip', id: 'khw' }), false, 'fremde Trip-ID darf nicht zaehlen');
		assert.notEqual(speicher.getItem(m.NACHLADE_MERKER), null, 'der Merker einer anderen Seite darf nicht verbraucht werden');
	});

	test('nimmSpeicherungBeimEntladen: gleiche ID, anderer Typ (trip vs. vergleich) → false, Merker bleibt', async () => {
		const m = await ladeGeraetespeicher();
		m.merkeSpeicherungBeimEntladen({ typ: 'trip', id: 'gr20' });

		assert.equal(m.nimmSpeicherungBeimEntladen({ typ: 'vergleich', id: 'gr20' }), false, 'Typ gehoert zur Kennung');
		assert.notEqual(speicher.getItem(m.NACHLADE_MERKER), null);
	});

	test('nimmSpeicherungBeimEntladen: unlesbarer Inhalt → false und geloescht', async () => {
		const m = await ladeGeraetespeicher();
		speicher.setItem(m.NACHLADE_MERKER, '{kaputt');

		assert.equal(m.nimmSpeicherungBeimEntladen({ typ: 'trip', id: 'gr20' }), false, 'kaputtes JSON darf nicht als Treffer gelten');
		assert.equal(speicher.getItem(m.NACHLADE_MERKER), null, 'ein unlesbarer Merker muss geraeumt werden');
	});
});

// ===========================================================================
// AC-14 — Abmelden raeumt den Merker
// ===========================================================================

describe('Issue #2317 AC-14: Abmelden loescht den Nachlade-Merker', () => {
	test('AC-14: Merker liegt vor → raeumeGeraetespeicher() → Merker ist geloescht (synchron zu Beginn)', async () => {
		// GIVEN: ein Merker liegt im Geraetespeicher
		const m = await ladeGeraetespeicher();
		m.merkeSpeicherungBeimEntladen({ typ: 'trip', id: 'gr20' });
		assert.notEqual(speicher.getItem(m.NACHLADE_MERKER), null, 'Vorbedingung: Merker liegt vor');

		// WHEN: der Nutzer meldet sich ab (Raeumen auf der Anmeldeseite)
		const lauf = m.raeumeGeraetespeicher();
		// Synchron gemessen — BEVOR der Raeumvorgang abgewartet wird. Das Ergebnis
		// wird erst nach dem Abwarten geprueft, damit der Lauf nie den Test ueberdauert.
		const sofort = speicher.getItem(m.NACHLADE_MERKER);
		const geraeumt = await lauf;

		// THEN
		assert.equal(sofort, null, 'der Merker muss synchron zu Beginn des Raeumens geloescht werden');
		assert.equal(speicher.getItem(m.NACHLADE_MERKER), null, 'der Merker darf nach dem Raeumen nicht mehr da sein');
		assert.equal(geraeumt, true, 'Vorbedingung der Laufzeit: das Raeumen meldet Erfolg');
	});
});

// ===========================================================================
// AC-15 — Nutzerwechsel auf demselben Geraet: kein Nachladen fremder Daten
// ===========================================================================

describe('Issue #2317 AC-15: Nutzer B loest keinen Merker von Nutzer A aus', () => {
	test('AC-15: A hinterlaesst Merker fuer trip gr20 und meldet sich ab; B oeffnet gr20 → 0 Nachlade-Anfragen', async () => {
		// GIVEN: Nutzer A hat beim Entladen einen Merker hinterlassen und sich abgemeldet
		const m = await ladeGeraetespeicher();
		const nach = (await import('../stores/nachEntladenNachladen.ts')) as unknown as {
			starteNachladenNachEntladen: (o: Record<string, unknown>) => { stoppen(): void; fertig: Promise<void> };
		};
		assert.equal(typeof nach.starteNachladenNachEntladen, 'function', 'starteNachladenNachEntladen fehlt');
		const kennung: Kennung = { typ: 'trip', id: 'gr20' };
		m.merkeSpeicherungBeimEntladen(kennung);
		await m.raeumeGeraetespeicher();

		// WHEN: Nutzer B oeffnet auf demselben Geraet die Detailseite mit derselben Kennung
		const timer: number[] = [];
		const zeitgeber = {
			setTimeout: (_fn: () => void, ms: number) => void timer.push(ms),
			clearTimeout: () => {}
		};
		let holenAufrufe = 0;
		const uebernahmen: unknown[] = [];
		const h = nach.starteNachladenNachEntladen({
			kennung,
			ctl: createTestInstance(),
			ausgelieferteFassung: '"fp-b-1"',
			holen: async () => {
				holenAufrufe++;
				return { stand: { name: 'Stand von Nutzer B' }, fassung: '"fp-b-2"' };
			},
			uebernehmen: (stand: unknown) => void uebernahmen.push(stand),
			zeitgeber
		});
		// Fristwaechter: bleibt ein (hier nie ausgeloester) Nachlade-Timer haengen,
		// soll der Test rot werden statt ewig zu warten.
		let frist: ReturnType<typeof setTimeout> | undefined;
		await Promise.race([
			h.fertig,
			new Promise<void>((r) => {
				frist = setTimeout(r, 500);
			})
		]);
		clearTimeout(frist);
		h.stoppen();
		await new Promise<void>((r) => setImmediate(r));

		// THEN
		assert.equal(holenAufrufe, 0, 'der geraeumte Merker von Nutzer A darf bei Nutzer B kein Nachladen ausloesen');
		assert.equal(timer.length, 0, 'kein Nachlade-Timer fuer Nutzer B');
		assert.equal(uebernahmen.length, 0, 'keine Uebernahme');
	});

	test('AC-15 Gegenprobe: OHNE Raeumen loest derselbe Merker wirklich ein Nachladen aus', async () => {
		// Ohne diese Gegenprobe waere „0 Nachlade-Anfragen" oben auch mit einem
		// Nachlade-Baustein erfuellt, der nie etwas holt — die 0 muss vom Raeumen kommen.
		const m = await ladeGeraetespeicher();
		const nach = (await import('../stores/nachEntladenNachladen.ts')) as unknown as {
			starteNachladenNachEntladen: (o: Record<string, unknown>) => { stoppen(): void; fertig: Promise<void> };
		};
		assert.equal(typeof nach.starteNachladenNachEntladen, 'function', 'starteNachladenNachEntladen fehlt');
		const kennung: Kennung = { typ: 'trip', id: 'gr20' };
		m.merkeSpeicherungBeimEntladen(kennung);

		let holenAufrufe = 0;
		const h = nach.starteNachladenNachEntladen({
			kennung,
			ctl: createTestInstance(),
			ausgelieferteFassung: '"fp-a-1"',
			holen: async () => {
				holenAufrufe++;
				return { stand: { name: 'alt' }, fassung: '"fp-a-1"' };
			},
			uebernehmen: () => {},
			// Timer werden nie ausgeloest: es geht nur darum, DASS nachgeladen wird
			zeitgeber: { setTimeout: () => ({}), clearTimeout: () => {} }
		});
		for (let i = 0; i < 5; i++) await new Promise<void>((r) => setImmediate(r));
		h.stoppen();

		assert.ok(holenAufrufe >= 1, 'Vorbedingung: mit erhaltenem Merker laedt der Baustein wirklich nach');
	});
});
