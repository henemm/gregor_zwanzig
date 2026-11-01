// Issue #2650 (i18n F1, Epic #2644) — Adversary F001: jeder auth.*-Schluessel hat
// einen EIGENEN englischen Text. Gemessen wird die Katalogdatei als Daten (kein
// Dateiinhalt-Grep im Seitenquelltext).
//   - en !== de je Schluessel, ausser die kommentierte Ausnahmeliste (gleich erlaubt).
//   - Kein deutsches Wort aus dem deutschen Satz im englischen Satz desselben Schluessels.
//
//   cd frontend && npm test -- src/lib/i18n/__tests__/auth_katalog_englisch.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const MESSAGES = join(dirname(fileURLToPath(import.meta.url)), '..', 'messages');
const lies = (lang: 'de' | 'en'): Record<string, string> =>
	JSON.parse(readFileSync(join(MESSAGES, lang, 'auth.json'), 'utf-8'));
const DE = lies('de');
const EN = lies('en');

/** Schluessel, deren englischer Text bewusst gleich dem deutschen ist. Jede Ausnahme nennt den Grund. */
const GLEICH_ERLAUBT: Record<string, string> = {
	'auth.feld.username_platzhalter':
		'„Username“ ist in beiden Sprachen derselbe Begriff (Glossar: username) und Platzhalter im Eingabefeld'
};

/** Woerter, die in beiden Sprachen gleich geschrieben werden (Glossar-Fachbegriffe, Eigennamen, Produktwoerter). */
const GLEICHE_WOERTER = new Set([
	'Token', // Glossar-Fachbegriff, in beiden Sprachen „Token“
	'Reset', // Glossar: reset password / reset link
	'Username', // Glossar: username
	'Passkey', // Glossar: passkey
	'Google', // Eigenname
	'Code', // Glossar: code / SMS-Kuerzel
	'Email', // Glossar: email
	'Briefing', // Glossar: briefing bleibt
	'Briefings',
	'level', // Glossar: Stufe (Alarm/Warnung) = level; Platzhalter {level} im Einladungshinweis
	'required' // steht schon im deutschen Bestandstext „Username required“ (byte-gleich erhalten)
]);

const woerter = (text: string): string[] => text.match(/[A-Za-zÄÖÜäöüß]{2,}/g) ?? [];

describe('#2650 F001 — jeder auth.*-Schluessel hat einen eigenen englischen Text', () => {
	test('F001_en_ungleich_de_ausser_kommentierter_ausnahmen', () => {
		const befunde = Object.keys(DE)
			.filter((k) => (k in GLEICH_ERLAUBT ? EN[k] !== DE[k] : EN[k] === DE[k]))
			.map((k) => `${k}: en „${EN[k]}“ ${k in GLEICH_ERLAUBT ? '!=' : '=='} de „${DE[k]}“`);
		assert.deepEqual(befunde, [], 'F001: englischer Text gleich deutschem Text (oder Ausnahme verfehlt)');
	});

	test('F001_keine_deutschen_woerter_aus_dem_satz_in_den_englischen_uebernommen', () => {
		const befunde: string[] = [];
		for (const k of Object.keys(DE)) {
			if (k in GLEICH_ERLAUBT) continue;
			const englisch = new Set(woerter(EN[k]));
			for (const wort of woerter(DE[k])) {
				if (wort.length >= 5 && englisch.has(wort) && !GLEICHE_WOERTER.has(wort)) {
					befunde.push(`${k}: „${wort}“ aus dem deutschen Text in „${EN[k]}“`);
				}
			}
		}
		assert.deepEqual(befunde, [], 'F001: deutsches Wort im englischen Text übernommen');
	});
});
