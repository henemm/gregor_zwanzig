// Issue #3047 Runde 8 (Paket r8fe, Befund F3) — die Einstellungsseite zeigt
// nichts an, was die Ausgabe nicht tut. PO-Entscheidung Spec-Nachtrag Runde 7
// („Telegram-Schnittlinie: Nichts fällt weg“, AC-24):
//   * Orts-Vergleich: Zeilen ab Platz 8 erscheinen in einer ZWEITEN Telegram-
//     Zeile je Ort statt wegzufallen,
//   * Trip: alle Zeilen stehen in der Telegram-Kurzübersicht, die ersten 7
//     zusätzlich stündlich in der Tabelle.
// Die alte Trennlinie „✂ ab hier Telegram-Limit (max 7)“ behauptete eine
// Kappung, die es nicht mehr gibt.
//
// Echter SSR-Render der geteilten Reihenfolge-Komponente (svelte/server) in DE
// und EN, je Kontext; kein Mock.
//
//   cd frontend && npm test -- src/lib/components/shared/weather-metrics-tab/__tests__/telegram_schnittlinie_wahr.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

// f5Pruefstand registriert die SSR-Hooks und rendert den ganzen Reiter (WeatherMetricsTab).
import { locale, routeRendern, vergleichRendern, VERGLEICH_KATALOG } from './f5Pruefstand.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const { render } = await import('svelte/server');
const imp = async (datei: string) => await import(pathToFileURL(datei).href);
const Reihenfolge = (await imp(path.join(HERE, '..', 'WeatherV2Reihenfolge.svelte'))).default;

// Neun Zeilen in einer Folge ungleich Katalogfolge.
const IDS = ['wind', 'temperature', 'gust', 'precipitation', 'cloud_total', 'humidity', 'pressure', 'snow_line', 'uv_index'];
const metricById = Object.fromEntries(IDS.map((id) => [id, { id, label: id.toUpperCase(), unit: '', category: 'x', default_enabled: true }]));
const nix = () => {};

function rendern(activeChannel: string, context?: 'route' | 'vergleich'): string {
	const props = {
		primaryColumns: IDS, metricById, friendlyMap: {}, activeChannel, highlight: null,
		onRemove: nix, onDndReorder: nix, onMode: nix, kuerzelById: {},
		...(context ? { context } : {})
	};
	const body = render(Reihenfolge as never, { props } as never).body.replace(/<!--[\s\S]*?-->/g, '');
	return body.replace(/<[^>]+>/g, ' ').replace(/&amp;/g, '&').replace(/\s+/g, ' ');
}

const SOLL = {
	vergleich: {
		de: 'ab Platz 8 in einer zweiten Telegram-Zeile je Ort',
		en: 'from position 8 in a second Telegram line per location'
	},
	route: {
		de: 'ab Platz 8 nur in der Telegram-Kurzübersicht, nicht in der Stundentabelle',
		en: 'from position 8 only in the Telegram summary, not in the hourly table'
	}
} as const;

afterEach(() => locale.set('de'));

describe('F3: Telegram-Trennlinie sagt, was die Ausgabe tut (keine Kappung bei 7)', () => {
	for (const context of ['vergleich', 'route'] as const) {
		for (const lang of ['de', 'en'] as const) {
			test(`${context}/${lang}: wahrer Satz statt „Limit (max 7)“, vor Zeile 8`, () => {
				locale.set(lang);
				const text = rendern('telegram', context);
				assert.ok(text.includes(SOLL[context][lang]), `Erklaersatz fehlt: ${text.slice(0, 400)}`);
				assert.doesNotMatch(text, /max 7|Limit|limit from here/, 'Kappungs-Behauptung sichtbar');
				// Position: der Satz steht genau vor der 8. Zeile.
				assert.ok(text.indexOf(SOLL[context][lang]) > text.indexOf('7 PRESSURE'), 'Satz steht vor Zeile 7');
				assert.ok(text.indexOf(SOLL[context][lang]) < text.indexOf('8 SNOW_LINE'), 'Satz steht hinter Zeile 8');
			});
		}
	}
	// Verdrahtung im ganzen Reiter: Trip-Kanal-Reiter und Orts-Vergleich-Kanal-Reiter.
	const sichtbar = (h: string) => h.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');
	test('WeatherMetricsTab Trip, Telegram-Reiter (9 Metriken): Trip-Satz, keine Kappung', () => {
		const text = sichtbar(routeRendern({ activeChannel: 'telegram' }));
		assert.ok(text.includes(SOLL.route.de), 'Trip-Satz fehlt');
		assert.ok(!text.includes(SOLL.vergleich.de));
		assert.doesNotMatch(text, /max 7\)|Telegram-Limit/);
	});
	test('WeatherMetricsTab Orts-Vergleich, Telegram-Reiter (9 Zeilen): zweite Zeile je Ort', () => {
		const neun = VERGLEICH_KATALOG().slice(0, 9).map((e: { metric: string }) => e.metric);
		assert.ok(neun.every((k: unknown) => typeof k === 'string' && k.length > 0), 'Messaufbau: Kennungen fehlen');
		assert.equal(neun.length, 9, 'Messaufbau: Katalog zu klein');
		const text = sichtbar(vergleichRendern({ compareChannel: 'telegram', telegramAuswahl: neun }, neun));
		assert.ok(text.includes(SOLL.vergleich.de), 'Vergleich-Satz fehlt');
		assert.ok(!text.includes(SOLL.route.de));
		assert.doesNotMatch(text, /max 7\)|Telegram-Limit/);
	});
	test('andere Kanaele und Einbettungen ohne Kontext: keine Telegram-Trennlinie', () => {
		for (const ch of ['email', 'sms']) assert.doesNotMatch(rendern(ch, 'vergleich'), /Telegram-Zeile|Telegram-Kurz|Limit/);
		assert.doesNotMatch(rendern('telegram'), /Telegram-Zeile|Telegram-Kurz|Limit|max 7/);
	});
});
