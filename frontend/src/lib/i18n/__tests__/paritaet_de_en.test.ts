// doc-compliance-test (Paritaetstest: liest die Katalogdateien als DATEN)
//
// Issue #2647 (i18n S2) — AC-3: je Bereichsdatei sind Schluesselmenge und
// Platzhaltermenge in `de` und `en` gleich. Die Pruefung laeuft erst gegen
// absichtlich kaputte Katalog-Objekte (muss rot werden und Bereich + Schluessel
// nennen) und dann gegen die echten 17 Bereichspaare (muss gruen sein).
// Zusaetzlich: die Index-Dateien vereinigen GENAU die Bereichsdateien, und kein
// Schluessel steht in zwei Bereichen (sonst ueberschriebe einer den anderen).
// Spec: docs/specs/modules/i18n_s2_frontend_sprachkern_2647.md
//
//   cd frontend && npm test -- src/lib/i18n/__tests__/paritaet_de_en.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { de } from '../messages/de/index.ts';
import { en } from '../messages/en/index.ts';

const MESSAGES = join(dirname(fileURLToPath(import.meta.url)), '..', 'messages');

export const BEREICHE = [
	'start', 'auth', 'nav', 'home', 'listen', 'konto', 'admin', 'wertebereiche', 'versand',
	'alarme', 'layout', 'trip', 'vergleich', 'aktionen', 'bausteine', 'fehler', 'hilfe'
] as const;

type Katalog = Record<string, string>;
type Paar = { de: Katalog; en: Katalog };

function platzhalter(text: string): string[] {
	return [...new Set([...text.matchAll(/\{([a-z0-9_]+)\}/g)].map((m) => m[1]))].sort();
}

/** Befunde der Paritaet; leere Liste = in Ordnung. */
export function paritaetsBefunde(bereiche: Record<string, Paar>): string[] {
	const befunde: string[] = [];
	for (const [bereich, { de: d, en: e }] of Object.entries(bereiche)) {
		for (const k of Object.keys(d)) {
			if (!(k in e)) befunde.push(`${bereich}: ${k} fehlt in en`);
		}
		for (const k of Object.keys(e)) {
			if (!(k in d)) befunde.push(`${bereich}: ${k} fehlt in de`);
		}
		for (const k of Object.keys(d)) {
			if (!(k in e)) continue;
			const pd = platzhalter(d[k]).join(',');
			const pe = platzhalter(e[k]).join(',');
			if (pd !== pe) befunde.push(`${bereich}: ${k} Platzhalter de {${pd}} != en {${pe}}`);
		}
	}
	return befunde;
}

function lies(lang: 'de' | 'en', bereich: string): Katalog {
	return JSON.parse(readFileSync(join(MESSAGES, lang, `${bereich}.json`), 'utf-8'));
}

describe('Gegenprobe: kaputte Kataloge sind rot und nennen Bereich und Schluessel', () => {
	test('fehlender englischer Schluessel', () => {
		const b = paritaetsBefunde({ home: { de: { 'home.a': 'A', 'home.b': 'B' }, en: { 'home.a': 'A' } } });
		assert.deepEqual(b, ['home: home.b fehlt in en']);
	});
	test('zusaetzlicher englischer Schluessel', () => {
		const b = paritaetsBefunde({ nav: { de: {}, en: { 'nav.x': 'X' } } });
		assert.deepEqual(b, ['nav: nav.x fehlt in de']);
	});
	test('abweichende Platzhalter', () => {
		const b = paritaetsBefunde({
			trip: { de: { 'trip.gruss': 'Hallo {name}' }, en: { 'trip.gruss': 'Hello {user_name}' } }
		});
		assert.equal(b.length, 1);
		assert.match(b[0], /^trip: trip\.gruss Platzhalter/);
	});
	test('gleiche Schluessel und Platzhalter sind gruen', () => {
		assert.deepEqual(
			paritaetsBefunde({ x: { de: { 'x.a': '{count} Min {n}' }, en: { 'x.a': '{n} {count} min' } } }),
			[]
		);
	});
});

describe('AC-3: die echten 17 Bereichspaare', () => {
	test('je Sprache existieren genau die 17 Bereichsdateien', () => {
		const soll = BEREICHE.map((b) => `${b}.json`).sort();
		for (const lang of ['de', 'en']) {
			const ist = readdirSync(join(MESSAGES, lang)).filter((f) => f.endsWith('.json')).sort();
			assert.deepEqual(ist, soll, `messages/${lang}/`);
		}
	});
	test('Schluessel- und Platzhaltermengen sind je Bereich gleich', () => {
		const paare = Object.fromEntries(BEREICHE.map((b) => [b, { de: lies('de', b), en: lies('en', b) }]));
		assert.deepEqual(paritaetsBefunde(paare), []);
	});
	test('kein Schluessel steht in zwei Bereichsdateien', () => {
		for (const lang of ['de', 'en'] as const) {
			const gesehen = new Map<string, string>();
			const doppelt: string[] = [];
			for (const b of BEREICHE) {
				for (const k of Object.keys(lies(lang, b))) {
					if (gesehen.has(k)) doppelt.push(`${k} in ${gesehen.get(k)} und ${b}`);
					gesehen.set(k, b);
				}
			}
			assert.deepEqual(doppelt, [], lang);
		}
	});
	test('index.ts vereinigt genau die Bereichsdateien (de und en)', () => {
		for (const [lang, karte] of [['de', de], ['en', en]] as const) {
			const soll: Katalog = Object.assign({}, ...BEREICHE.map((b) => lies(lang, b)));
			assert.deepEqual({ ...karte }, soll, `messages/${lang}/index.ts`);
		}
	});
	test('kein Katalogwert ist leer', () => {
		for (const [lang, karte] of [['de', de], ['en', en]] as const) {
			const leer = Object.entries(karte as Katalog).filter(([, v]) => typeof v !== 'string' || !v.trim());
			assert.deepEqual(leer, [], lang);
		}
	});
});
