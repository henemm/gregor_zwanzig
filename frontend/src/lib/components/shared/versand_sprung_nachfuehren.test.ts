// Issue #1743 F002 — Sprung zum Versand-Abschnitt bleibt ausgerichtet, während der
// Wetter-Metriken-Inhalt OBERHALB nachlädt.
// Spec: docs/specs/modules/feat_1743_reiter_aufraeumen.md
//
// Zusicherung: `versandSprungNachfuehren(ziel, umgebung)` richtet das Ziel sofort aus
// und richtet es neu aus, sobald sich seine Lage verschiebt — bis zur ersten
// Nutzer-Absicht (wheel/touchstart/keydown/pointerdown, Capture auf document), bis zur
// Obergrenze oder bis zum Aufräumen. Ein `scroll`-Ereignis (löst das eigene
// scrollIntoView selbst aus) bricht NICHT ab.
//
// Prüfweg: echte Funktion mit einer handgeführten Umgebung (Frame-Schlange, Ereignis-
// Register, Timer) und einem Ziel, dessen Lage der Test verschiebt — kein Mock-Rückspiegel.
//
// Pfadregel #1409: relativ zu DIESER Datei.
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/components/shared/versand_sprung_nachfuehren.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import {
	versandSprungNachfuehren,
	versandSprungNachTick,
	NACHFUEHR_OBERGRENZE_MS,
	NUTZER_ABSICHT,
	type NachfuehrUmgebung
} from './versandSprungNachfuehren.ts';

/** Erwartete Nutzer-Absichten — bewusst LITERAL, nicht aus dem Prüfling gelesen
 *  (sonst bliebe das Entfernen eines Ereignisses grün). */
const ABSICHTEN = ['wheel', 'touchstart', 'keydown', 'pointerdown'];

/** Ziel, dessen top sich durch Nachladen oberhalb verschiebt; scrollIntoView setzt es
 *  auf `erreicht` (0 = ganz oben; > 0 = Seitenende, `start` erreicht oben nicht). */
function zielBauen() {
	const z = {
		top: 0,
		erreicht: 0,
		ausrichtungen: 0,
		getBoundingClientRect: () => ({ top: z.top }),
		scrollIntoView: (opts?: ScrollIntoViewOptions) => {
			assert.equal(opts?.block, 'start');
			z.ausrichtungen++;
			z.top = z.erreicht;
		}
	};
	return z;
}

function umgebungBauen() {
	let naechsteId = 1;
	const frames = new Map<number, () => void>();
	const listener = new Map<string, Set<EventListenerOrEventListenerObject>>();
	const timer = new Map<number, { cb: () => void; ms: number }>();
	const umgebung: NachfuehrUmgebung = {
		frame: (cb) => {
			const id = naechsteId++;
			frames.set(id, cb);
			return id;
		},
		frameAbbrechen: (id) => void frames.delete(id),
		dokument: {
			addEventListener: (typ: string, fn: EventListenerOrEventListenerObject, opts?: unknown) => {
				const capture = typeof opts === 'boolean' ? opts : (opts as AddEventListenerOptions)?.capture;
				assert.equal(capture, true, `${typ} muss per Capture lauschen`);
				if (!listener.has(typ)) listener.set(typ, new Set());
				listener.get(typ)!.add(fn);
			},
			removeEventListener: (typ: string, fn: EventListenerOrEventListenerObject) => {
				listener.get(typ)?.delete(fn);
			}
		} as NachfuehrUmgebung['dokument'],
		timer: (cb, ms) => {
			const id = naechsteId++;
			timer.set(id, { cb, ms });
			return id;
		},
		timerAbbrechen: (id) => void timer.delete(id as number)
	};
	return {
		umgebung,
		/** Führt die aktuell angemeldeten Frames aus (ein Bild). */
		bild() {
			const jetzt = [...frames.entries()];
			frames.clear();
			for (const [, cb] of jetzt) cb();
		},
		ereignis(typ: string) {
			for (const fn of [...(listener.get(typ) ?? [])]) {
				if (typeof fn === 'function') fn(new Event(typ));
				else fn.handleEvent(new Event(typ));
			}
		},
		obergrenzeErreicht() {
			for (const [id, t] of [...timer.entries()]) {
				timer.delete(id);
				t.cb();
			}
		},
		lauscher: () => [...listener.values()].reduce((n, s) => n + s.size, 0),
		timer,
		frames
	};
}

describe('#1743 F002: Versand-Sprung wird nachgeführt', () => {
	test('richtet sofort aus und bei jeder Lageverschiebung erneut', () => {
		const ziel = zielBauen();
		const u = umgebungBauen();
		ziel.top = 300;
		versandSprungNachfuehren(ziel, u.umgebung);
		assert.equal(ziel.ausrichtungen, 1, 'sofortige Ausrichtung');

		u.bild();
		assert.equal(ziel.ausrichtungen, 1, 'ohne Verschiebung keine erneute Ausrichtung');

		ziel.top = 3469; // Inhalt oberhalb ist nachgeladen
		u.bild();
		assert.equal(ziel.ausrichtungen, 2, 'Verschiebung ⇒ neu ausgerichtet');
		assert.equal(ziel.top, 0);

		ziel.top = 5000; // zweiter Nachlade-Schub
		u.bild();
		assert.equal(ziel.ausrichtungen, 3, 'auch eine zweite Verschiebung wird nachgeführt');
	});

	test('Toleranz: 1 px Verschiebung bleibt liegen, 2 px werden nachgeführt', () => {
		const ziel = zielBauen();
		const u = umgebungBauen();
		versandSprungNachfuehren(ziel, u.umgebung);
		ziel.top = 1;
		u.bild();
		assert.equal(ziel.ausrichtungen, 1, '1 px (Rundung) löst keine Neuausrichtung aus');
		ziel.top = 2;
		u.bild();
		assert.equal(ziel.ausrichtungen, 2, '2 px werden nachgeführt');
	});

	test('Seitenende: Soll folgt der erreichten Lage — kein Dauer-Scrollen, aber neue Verschiebung zählt', () => {
		const ziel = zielBauen();
		const u = umgebungBauen();
		versandSprungNachfuehren(ziel, u.umgebung);
		ziel.erreicht = 300; // ab jetzt reicht die Seite unter dem Abschnitt nicht mehr
		ziel.top = 900;
		u.bild();
		assert.equal(ziel.ausrichtungen, 2);
		assert.equal(ziel.top, 300);
		u.bild();
		u.bild();
		u.bild();
		assert.equal(ziel.ausrichtungen, 2, 'erreichte Lage 300 wird Soll — kein scrollIntoView je Bild');
		ziel.top = 900;
		u.bild();
		assert.equal(ziel.ausrichtungen, 3, 'erneute Verschiebung 300→900 wird nachgeführt');
	});

	test('Nutzer-Absichten sind genau wheel/touchstart/keydown/pointerdown', () => {
		assert.deepEqual([...NUTZER_ABSICHT], ABSICHTEN);
	});

	for (const typ of ABSICHTEN) {
		test(`Nutzer-Absicht „${typ}" beendet das Nachführen`, () => {
			const ziel = zielBauen();
			const u = umgebungBauen();
			versandSprungNachfuehren(ziel, u.umgebung);
			u.ereignis(typ);
			ziel.top = 2000;
			u.bild();
			u.bild();
			assert.equal(ziel.ausrichtungen, 1, 'nach Nutzer-Eingabe kein Zurückreißen');
			assert.equal(u.lauscher(), 0, 'Lauscher entfernt');
			assert.equal(u.timer.size, 0, 'Obergrenzen-Timer entfernt');
		});
	}

	test('scroll-Ereignis bricht NICHT ab (das eigene scrollIntoView löst es aus)', () => {
		const ziel = zielBauen();
		const u = umgebungBauen();
		versandSprungNachfuehren(ziel, u.umgebung);
		u.ereignis('scroll');
		ziel.top = 2000;
		u.bild();
		assert.equal(ziel.ausrichtungen, 2);
	});

	test('Obergrenze beendet das Nachführen', () => {
		const ziel = zielBauen();
		const u = umgebungBauen();
		versandSprungNachfuehren(ziel, u.umgebung);
		assert.deepEqual(
			[...u.timer.values()].map((t) => t.ms),
			[NACHFUEHR_OBERGRENZE_MS],
			'genau ein Obergrenzen-Timer'
		);
		assert.ok(NACHFUEHR_OBERGRENZE_MS > 0 && NACHFUEHR_OBERGRENZE_MS <= 15_000);
		u.obergrenzeErreicht();
		ziel.top = 2000;
		u.bild();
		assert.equal(ziel.ausrichtungen, 1);
		assert.equal(u.lauscher(), 0);
		assert.equal(u.frames.size, 0, 'kein Frame mehr angemeldet');
	});

	test('Aufräumfunktion beendet alles', () => {
		const ziel = zielBauen();
		const u = umgebungBauen();
		const aufraeumen = versandSprungNachfuehren(ziel, u.umgebung);
		assert.equal(u.lauscher(), ABSICHTEN.length, 'je Nutzer-Absicht ein Lauscher');
		aufraeumen();
		assert.equal(u.lauscher(), 0);
		assert.equal(u.timer.size, 0);
		assert.equal(u.frames.size, 0);
		ziel.top = 2000;
		u.bild();
		assert.equal(ziel.ausrichtungen, 1);
		aufraeumen(); // doppelt aufrufbar
	});
});

describe('#1743 F002: Panel-Einstieg nach tick()', () => {
	test('startet erst nach dem tick und führt dann nach', async () => {
		const ziel = zielBauen();
		const u = umgebungBauen();
		let loslassen = () => {};
		const warten = () => new Promise<void>((r) => (loslassen = r));
		versandSprungNachTick(ziel, warten, u.umgebung);
		assert.equal(ziel.ausrichtungen, 0, 'vor dem tick keine Ausrichtung');
		loslassen();
		await Promise.resolve();
		await Promise.resolve();
		assert.equal(ziel.ausrichtungen, 1);
		ziel.top = 900;
		u.bild();
		assert.equal(ziel.ausrichtungen, 2);
	});

	test('Aufräumen NACH dem Start beendet das laufende Nachführen', async () => {
		const ziel = zielBauen();
		const u = umgebungBauen();
		let loslassen = () => {};
		const warten = () => new Promise<void>((r) => (loslassen = r));
		const aufraeumen = versandSprungNachTick(ziel, warten, u.umgebung);
		loslassen();
		await Promise.resolve();
		await Promise.resolve();
		assert.equal(ziel.ausrichtungen, 1, 'Nachführen ist gestartet');
		assert.ok(u.lauscher() > 0 && u.frames.size > 0 && u.timer.size > 0, 'läuft');
		aufraeumen();
		assert.equal(u.lauscher(), 0, 'Lauscher entfernt');
		assert.equal(u.frames.size, 0, 'kein Frame mehr angemeldet');
		assert.equal(u.timer.size, 0, 'Obergrenzen-Timer entfernt');
		ziel.top = 900;
		u.bild();
		assert.equal(ziel.ausrichtungen, 1, 'nach dem Aufräumen keine Ausrichtung mehr');
	});

	test('Aufräumen vor dem tick verhindert den Start', async () => {
		const ziel = zielBauen();
		const u = umgebungBauen();
		let loslassen = () => {};
		const warten = () => new Promise<void>((r) => (loslassen = r));
		const aufraeumen = versandSprungNachTick(ziel, warten, u.umgebung);
		aufraeumen();
		loslassen();
		await Promise.resolve();
		await Promise.resolve();
		assert.equal(ziel.ausrichtungen, 0);
		assert.equal(u.lauscher(), 0);
		assert.equal(u.frames.size, 0);
	});
});
