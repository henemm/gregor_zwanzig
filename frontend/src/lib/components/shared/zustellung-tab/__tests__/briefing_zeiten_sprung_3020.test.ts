// Issue #1743 F002/F003, neu geschrieben in #3020 R1 (G26): der Anker `#versand` steht heute in BriefingZeiten.svelte.
// Der Sprung dorthin wird NACHGEFÜHRT — nach dem tick ausgerichtet und erneut, wenn der Inhalt oberhalb nachlädt und
// den Anker verschiebt. Rückbau auf einen Einmal-Scroll oder ein fehlendes Effekt-Aufräumen muss hier rot werden.
//
// Messweise (Wirkort): das ECHTE Instanz-Skript (svelteInstanzPruefstand), sein echter `$effect` mit echtem Import
// `versandSprungNachTick`. Attrappen sind nur die Browser-Primitiven, die es unter node nicht gibt
// (requestAnimationFrame, document-Lauscher), und der Anker selbst (Lage `top`, `scrollIntoView`).
//
//   cd frontend && npm test -- src/lib/components/shared/zustellung-tab/__tests__/briefing_zeiten_sprung_3020.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { umgebungFuer, effekteVon, type Knoten } from '../../__tests__/svelteInstanzPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const ORGANISMUS = resolve(HIER, '../../../organisms/zustellung-tab/BriefingZeiten.svelte');

const g = globalThis as Knoten;
const alt = { document: g.document, requestAnimationFrame: g.requestAnimationFrame, cancelAnimationFrame: g.cancelAnimationFrame };
afterEach(() => Object.assign(g, alt));

/** Browser-Primitiven als handgeführte Attrappen: Bilder laufen nur auf `bild()`. */
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

function ankerAttrappe() {
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

/** tick() + Promise-Kette abwarten. */
const nachDemTick = () => new Promise((r) => setTimeout(r, 0));

async function sprungEffekt(versandSprung: number, anker: Knoten | null) {
	const p = await umgebungFuer(
		ORGANISMUS,
		{ context: 'route', stand: { morgenZeit: '06:00', abendZeit: '18:00' }, onaendern: () => {}, versandSprung, anker },
		{ jsAlsTs: true }
	);
	// Auswahl über den Anker (nicht über den Zähler oder den Helfer) — sonst verschwände der Effekt bei genau den
	// Rückbauten, die hier rot werden sollen, schon aus der Auswahl.
	const effekte = effekteVon(p.ast, p.quelle, p.u, 'anker');
	assert.equal(effekte.length, 1, 'genau ein Sprung-Effekt in BriefingZeiten');
	return effekte[0] as () => unknown;
}

describe('#1743 F002: BriefingZeiten führt den Sprung zu #versand nach', () => {
	test('versandSprung=1: nach dem tick ausgerichtet, nach Verschiebung erneut', async () => {
		const b = browserAttrappe();
		const anker = ankerAttrappe();
		const aufraeumen = (await sprungEffekt(1, anker))();
		assert.equal(anker.ausrichtungen, 0, 'erst nach dem tick');
		await nachDemTick();
		assert.equal(anker.ausrichtungen, 1, 'nach dem tick ausgerichtet');
		anker.top = 3469; // Inhalt oberhalb ist nachgeladen
		b.bild();
		assert.equal(anker.ausrichtungen, 2, 'Verschiebung wird nachgeführt (kein Einmal-Scroll)');
		assert.equal(typeof aufraeumen, 'function', 'Effekt gibt eine Aufräumfunktion zurück');
		(aufraeumen as () => void)();
	});

	test('Effekt-Aufräumen beendet das Nachführen', async () => {
		const b = browserAttrappe();
		const anker = ankerAttrappe();
		const aufraeumen = (await sprungEffekt(1, anker))();
		await nachDemTick();
		assert.ok(b.lauscher.size > 0 && b.frames.size > 0, 'Nachführen läuft');
		assert.equal(typeof aufraeumen, 'function', 'Effekt gibt eine Aufräumfunktion zurück');
		(aufraeumen as () => void)();
		assert.equal(b.lauscher.size, 0, 'Lauscher entfernt');
		assert.equal(b.frames.size, 0, 'kein Bild mehr angemeldet');
		anker.top = 3469;
		b.bild();
		assert.equal(anker.ausrichtungen, 1, 'nach dem Aufräumen keine Ausrichtung mehr');
	});

	test('versandSprung=0: keine Ausrichtung', async () => {
		const b = browserAttrappe();
		const anker = ankerAttrappe();
		(await sprungEffekt(0, anker))();
		await nachDemTick();
		b.bild();
		assert.equal(anker.ausrichtungen, 0);
		assert.equal(b.lauscher.size, 0);
	});
});
