// Issue #1743 F002/F003: Der Baustein WetterMetrikenVersandPanel fuehrt den Sprung zum
// Versand-Abschnitt NACH — er richtet nach dem tick aus und erneut, wenn der Inhalt
// oberhalb nachlaedt und den Abschnitt verschiebt. Rueckbau auf einen Einmal-Scroll
// (der Defekt F002) oder ein fehlendes Effekt-Aufraeumen muss hier rot werden.
//
// Messweise (Wirkort): das ECHTE Instanz-Skript des Panels (svelteInstanzPruefstand),
// sein echter `$effect` mit echtem Import `versandSprungNachTick`. Attrappen sind nur
// die Browser-Primitiven, die es unter node nicht gibt (requestAnimationFrame,
// document-Lauscher) und der Abschnitt selbst (Lage `top`, `scrollIntoView`).
//
// Pfadregel #1409: relativ zu DIESER Datei.

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { umgebungFuer, effekteVon, type Knoten } from './svelteInstanzPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const PANEL = resolve(HIER, '../WetterMetrikenVersandPanel.svelte');

const g = globalThis as Knoten;
const alt = {
	document: g.document,
	requestAnimationFrame: g.requestAnimationFrame,
	cancelAnimationFrame: g.cancelAnimationFrame
};
afterEach(() => {
	g.document = alt.document;
	g.requestAnimationFrame = alt.requestAnimationFrame;
	g.cancelAnimationFrame = alt.cancelAnimationFrame;
});

/** Browser-Primitiven als handgefuehrte Attrappen: Bilder laufen nur auf `bild()`. */
function browserAttrappe() {
	let id = 0;
	const frames = new Map<number, () => void>();
	const lauscher = new Set<string>();
	g.requestAnimationFrame = (cb: () => void) => {
		frames.set(++id, cb);
		return id;
	};
	g.cancelAnimationFrame = (n: number) => void frames.delete(n);
	g.document = {
		addEventListener: (typ: string) => void lauscher.add(typ),
		removeEventListener: (typ: string) => void lauscher.delete(typ)
	};
	return {
		frames,
		lauscher,
		bild() {
			const jetzt = [...frames.values()];
			frames.clear();
			for (const cb of jetzt) cb();
		}
	};
}

function abschnittAttrappe() {
	const a = {
		top: 400,
		ausrichtungen: 0,
		getBoundingClientRect: () => ({ top: a.top }),
		scrollIntoView: () => {
			a.ausrichtungen++;
			a.top = 0;
		}
	};
	return a;
}

/** tick() + Promise-Kette des Panels abwarten. */
const nachDemTick = () => new Promise((r) => setTimeout(r, 0));

async function panel(versandSprung: number, abschnitt: Knoten | null) {
	const p = await umgebungFuer(PANEL, { context: 'route', versandSprung, abschnitt }, { jsAlsTs: true });
	// Auswahl über den Abschnitt (nicht über den Zähler oder den Helfer) — sonst
	// verschwände der Effekt bei genau den Rückbauten, die hier rot werden sollen,
	// schon aus der Auswahl statt an der Zusicherung zu scheitern.
	const effekte = effekteVon(p.ast, p.quelle, p.u, 'abschnitt');
	assert.equal(effekte.length, 1, 'genau ein Sprung-Effekt im Panel');
	return effekte[0] as () => unknown;
}

describe('#1743 F002: WetterMetrikenVersandPanel führt den Sprung zu #versand nach', () => {
	test('versandSprung=1: nach dem tick ausgerichtet, nach Verschiebung erneut', async () => {
		const b = browserAttrappe();
		const abschnitt = abschnittAttrappe();
		const effekt = await panel(1, abschnitt);
		const aufraeumen = effekt();
		assert.equal(abschnitt.ausrichtungen, 0, 'erst nach dem tick');
		await nachDemTick();
		assert.equal(abschnitt.ausrichtungen, 1, 'nach dem tick ausgerichtet');
		abschnitt.top = 3469; // Wetter-Metriken-Inhalt oberhalb ist nachgeladen
		b.bild();
		assert.equal(abschnitt.ausrichtungen, 2, 'Verschiebung wird nachgeführt (kein Einmal-Scroll)');
		assert.equal(typeof aufraeumen, 'function', 'Effekt gibt eine Aufräumfunktion zurück');
		(aufraeumen as () => void)();
	});

	test('Effekt-Aufräumen (Unmount/Zähler zurück) beendet das Nachführen', async () => {
		const b = browserAttrappe();
		const abschnitt = abschnittAttrappe();
		const effekt = await panel(1, abschnitt);
		const aufraeumen = effekt();
		await nachDemTick();
		assert.ok(b.lauscher.size > 0 && b.frames.size > 0, 'Nachführen läuft');
		assert.equal(typeof aufraeumen, 'function', 'Effekt gibt eine Aufräumfunktion zurück');
		(aufraeumen as () => void)();
		assert.equal(b.lauscher.size, 0, 'Lauscher entfernt');
		assert.equal(b.frames.size, 0, 'kein Bild mehr angemeldet');
		abschnitt.top = 3469;
		b.bild();
		assert.equal(abschnitt.ausrichtungen, 1, 'nach dem Aufräumen keine Ausrichtung mehr');
	});

	test('versandSprung=0: keine Ausrichtung', async () => {
		const b = browserAttrappe();
		const abschnitt = abschnittAttrappe();
		const effekt = await panel(0, abschnitt);
		effekt();
		await nachDemTick();
		b.bild();
		assert.equal(abschnitt.ausrichtungen, 0);
		assert.equal(b.lauscher.size, 0);
	});
});
