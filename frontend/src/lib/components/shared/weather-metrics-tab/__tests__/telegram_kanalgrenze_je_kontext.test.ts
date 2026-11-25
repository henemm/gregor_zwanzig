// Issue #3047 Runde 8 (Paket r8fe, Nachtrag zu F3) — die Einstellungsseite zeigt
// je Kontext nur, was die Telegram-Ausgabe wirklich tut:
//   * Orts-Vergleich (comparison.py, AC-24): ALLE Zeilen, ab Platz 8 in einer
//     zweiten Zeile je Ort. Also kein „zu breit — max 7“, kein Ueberlauf-Chip
//     „−n“, kein Grenz-Badge „Telegram 7“.
//   * Trip (narrow.py): die ersten 7 Metriken stehen stuendlich in der
//     Etappen-Tabelle, der Rest nur als Tageswert in der Kurzuebersicht. Die
//     Spalten-Grenze 7 der Stundentabelle ist dort wahr und bleibt sichtbar.
// Echter SSR-Render des ganzen Reiters (WeatherMetricsTab) in DE und EN.
//
//   cd frontend && npm test -- src/lib/components/shared/weather-metrics-tab/__tests__/telegram_kanalgrenze_je_kontext.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { locale, VERGLEICH_KATALOG } from './f5Pruefstand.ts';
import { routeRendern, vergleichRendern } from './f5Altbausteine.ts';

const sichtbar = (h: string) => h.replace(/<[^>]+>/g, ' ').replace(/&amp;/g, '&').replace(/\s+/g, ' ');
const keys = (n: number) => VERGLEICH_KATALOG().slice(0, n).map((e: { metric: string }) => e.metric);
const orte = (n: number, kanal: 'email' | 'telegram' | 'sms' = 'telegram') =>
	sichtbar(vergleichRendern({ compareChannel: kanal, telegramAuswahl: keys(n) }, keys(n)));

const SOLL = {
	de: {
		umbruch: 'Telegram: 9 Metriken · alle in der Nachricht, ab Platz 8 in einer zweiten Zeile je Ort',
		eine: 'Telegram: 5 Metriken · alle in einer Zeile je Ort'
	},
	en: {
		umbruch: 'Telegram: 9 metrics · all in the message, from position 8 in a second line per location',
		eine: 'Telegram: 5 metrics · all in one line per location'
	}
} as const;

afterEach(() => locale.set('de'));

describe('Orts-Vergleich: Telegram-Hinweise ohne Kappung (AC-24)', () => {
	for (const lang of ['de', 'en'] as const) {
		test(`${lang}: 9 Zeilen -> zweite Zeile je Ort, kein „zu breit“, kein Chip, kein Badge 7`, () => {
			locale.set(lang);
			assert.equal(keys(9).length, 9, 'Messaufbau: Katalog zu klein');
			const text = orte(9);
			assert.ok(text.includes(SOLL[lang].umbruch), `Hinweis fehlt: ${text.slice(-600)}`);
			assert.doesNotMatch(text, /zu breit|too wide|max 7/);
			assert.doesNotMatch(text, /−\d/, 'Ueberlauf-Chip sichtbar');
			assert.doesNotMatch(text, /Telegram 7/, 'Grenz-Badge 7 sichtbar');
		});
		test(`${lang}: 5 Zeilen -> eine Zeile je Ort`, () => {
			locale.set(lang);
			assert.ok(orte(5).includes(SOLL[lang].eine));
		});
	}
	test('E-Mail-Reiter des Vergleichs: auch dort kein Telegram-Chip/-Badge 7', () => {
		const text = orte(9, 'email');
		assert.doesNotMatch(text, /−\d/);
		assert.doesNotMatch(text, /Telegram 7/);
	});
});

describe('Trip: Spalten-Grenze der Stundentabelle bleibt (wahr laut narrow.py)', () => {
	test('9 Metriken, Telegram-Reiter: Badge 7, Chip −2, Hinweis zu breit', () => {
		const text = sichtbar(routeRendern({ activeChannel: 'telegram' }));
		assert.match(text, /Telegram 7 −2/);
		assert.ok(text.includes('Telegram: 9 Metriken · zu breit — max 7'));
		assert.doesNotMatch(text, /zweiten Zeile je Ort/);
	});
});
