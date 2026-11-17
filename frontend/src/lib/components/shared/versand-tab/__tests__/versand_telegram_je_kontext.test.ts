// Issue #3047 Runde 8 (Paket r8fe, Nachtrag zu F3) — Versand-Reiter: der
// Einleitungssatz und die Telegram-Unterzeile sagen je Kontext, was die
// Telegram-Ausgabe tut. Orts-Vergleich (comparison.py, AC-24): alle Zeilen,
// ab Platz 8 in einer zweiten Zeile je Ort; vorher „Telegram trägt nur ≤ 7
// Spalten“ und „Layout · 7 Spalten“. Trip (narrow.py): Etappen-Tabelle mit den
// ersten 7 Spalten, bleibt. Echter SSR-Render von VTBriefingChannels, DE/EN.
//
//   cd frontend && npm test -- src/lib/components/shared/versand-tab/__tests__/versand_telegram_je_kontext.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { locale, kanaeleRendern, PROFILE } from './f6VersandSsr.ts';

const sichtbar = (h: string) => h.replace(/<[^>]+>/g, ' ').replace(/&amp;/g, '&').replace(/\s+/g, ' ');

const SOLL = {
	de: {
		lead: 'Der Orts-Vergleich ist eine breite Tabelle — E-Mail trägt alle Spalten, Telegram alle Zeilen (ab Platz 8 in einer zweiten Zeile je Ort), SMS kein Raster, Fließtext.',
		sub: 'Layout · alle Zeilen, ab Platz 8 zweite Zeile je Ort'
	},
	en: {
		lead: 'The location comparison is a wide table — email carries all columns, Telegram all rows (from position 8 in a second line per location), SMS has no grid, plain text.',
		sub: 'Layout · all rows, from position 8 a second line per location'
	}
} as const;

afterEach(() => locale.set('de'));

describe('Versand Orts-Vergleich: Telegram ohne „≤ 7 Spalten“', () => {
	for (const lang of ['de', 'en'] as const) {
		test(`${lang}: Einleitung und Telegram-Unterzeile wahr`, () => {
			locale.set(lang);
			const text = sichtbar(kanaeleRendern('vergleich', PROFILE.alles_gekoppelt));
			assert.ok(text.includes(SOLL[lang].lead), `Einleitung fehlt: ${text.slice(0, 500)}`);
			assert.ok(text.includes(SOLL[lang].sub), 'Telegram-Unterzeile fehlt');
			assert.doesNotMatch(text, /≤ 7|7 Spalten|7 columns/);
		});
	}
	test('Trip: Etappen-Tabelle mit den ersten 7 Spalten bleibt', () => {
		const text = sichtbar(kanaeleRendern('route', PROFILE.alles_gekoppelt));
		assert.ok(text.includes('Telegram die ersten 7'));
		assert.ok(text.includes('Layout · 7 Spalten'));
	});
});
