// TDD RED — Issue #3155 (Scheibe B4 von #3122): ein Name „3-Tages-Ausblick", eine
// steuernde Stelle. Spec: docs/specs/modules/feat_3155_ein_name_ausblick.md
// (AC-6, AC-7, AC-11; Entscheidungen 4, 7, 8). Ober-Spec feat_3122 AC-34, Nr. 15.
//
// Geprueft wird an dem, was der Nutzer sieht: die gerenderten Reiter (SSR ueber die
// echten Svelte-Komponenten, Pruefstaende f5Pruefstand.ts / f6VersandSsr.ts) und die
// Bausteine der Karte „E-Mail-Inhalt" (`mailInhaltBausteine()`, die Quelle der
// Haken-Beschriftungen der MailInhaltCard). Katalogwerte nur ueber den echten
// Aufloeser (`trFor`), nie per Dateiinhalt. Das Soll steht hier von Hand.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/ausblick_ein_name_3155.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { routeRendern, locale, trFor } from '../weather-metrics-tab/__tests__/f5Pruefstand.ts';
import { kanaeleRendern, tabRendern, PROFILE } from '../versand-tab/__tests__/f6VersandSsr.ts';
import { mailInhaltBausteine } from '../mailInhaltKonstanten.ts';

afterEach(() => locale.set('de'));

const NAME = { de: '3-Tages-Ausblick', en: '3-day outlook' } as const;
/** Verbotene Namen des Ausblick-Blocks / einer Beschriftung (AC-11). */
const ALT = {
	de: ['Mehrtages-Trend', '3-Tages-Vorschau', 'Nächste Etappen', 'Trend-Block', '3–7-Tage-Ausblick'],
	en: ['Multi-day trend', '3-day preview', 'Next stages', 'trend block', '3–7-day outlook']
} as const;

const leerraum = (s: string) => s.replace(/\s+/g, ' ');
const sichtbar = (html: string) =>
	leerraum(html.replace(/<style[\s\S]*?<\/style>/g, ' ').replace(/<[^>]*>/g, ' ').replace(/&amp;/g, '&')).trim();
const attribute = (html: string) => [...html.matchAll(/\s(?:title|aria-label)="([^"]*)"/g)].map((m) => m[1]);

function inSprache<T>(lang: 'de' | 'en', f: () => T): T {
	locale.set(lang);
	return f();
}

describe('AC-6: Haken „Ausblick" der Karte „E-Mail-Inhalt" heisst „Großwetterlage"', () => {
	for (const [lang, name] of [['de', 'Großwetterlage'], ['en', 'Weather pattern']] as const) {
		test(`${lang}: show_outlook traegt den Namen der Grosswetterlage`, () => {
			const b = inSprache(lang, () => mailInhaltBausteine());
			assert.equal(b.show_outlook.label, name, `show_outlook heisst ${JSON.stringify(b.show_outlook.label)}`);
			// Beschreibung = die der Grosswetterlage, nicht mehr „…, nächste Etappen und …".
			assert.equal(b.show_outlook.description, b.show_stability.description);
		});
		test(`${lang}: kein Baustein heisst „Ausblick"/„Outlook" und keine Beschreibung nennt alte Namen`, () => {
			const b = inSprache(lang, () => mailInhaltBausteine());
			for (const [k, { label, description }] of Object.entries(b)) {
				assert.ok(!['ausblick', 'outlook'].includes(label.trim().toLowerCase()), `${k}: Baustein heisst ${JSON.stringify(label)}`);
				for (const alt of [...ALT.de, ...ALT.en, 'nächste Etappen', 'next stages'])
					assert.ok(!description.includes(alt), `${k}: Beschreibung nennt ${JSON.stringify(alt)}: ${description}`);
			}
		});
	}
});

describe('AC-11/Nr. 15: Reiter Wetter (Trip) nennt den Block „3-Tages-Ausblick"', () => {
	for (const lang of ['de', 'en'] as const) {
		test(`${lang}: Ausblick-Abschnitt und Schwellen-Hinweis tragen den einen Namen, keine alten Namen`, () => {
			const html = inSprache(lang, () => routeRendern({ pendingPreset: 'wandern', showSavePresetDialog: true }));
			const text = sichtbar(html) + ' ' + attribute(html).join(' ');
			assert.ok(text.includes(NAME[lang]), `${lang}: „${NAME[lang]}" fehlt im Reiter Wetter`);
			for (const alt of ALT[lang]) assert.ok(!text.includes(alt), `${lang}: „${alt}" steht noch im Reiter Wetter`);
		});
	}
	test('aufgeloeste Katalogwerte: wertebereiche.ausblick.titel ist der eine Name', () => {
		assert.equal(trFor('de', 'wertebereiche.ausblick.titel'), NAME.de);
		assert.equal(trFor('en', 'wertebereiche.ausblick.titel'), NAME.en);
	});
	test('aufgeloeste Katalogwerte: wertebereiche.schwelle.hinweis nennt den Block mit dem einen Namen', () => {
		const de = trFor('de', 'wertebereiche.schwelle.hinweis');
		const en = trFor('en', 'wertebereiche.schwelle.hinweis');
		assert.ok(de.includes(NAME.de), `de: ${de}`);
		assert.ok(en.includes(NAME.en), `en: ${en}`);
		assert.ok(!/trend/i.test(de) && !/trend/i.test(en), `Trend-Block noch genannt: ${de} | ${en}`);
	});
});

describe('AC-7/Entscheidung 4: Versand-Reiter (Trip-Anlage) ohne Karte „Mehrtages-Trend"', () => {
	for (const lang of ['de', 'en'] as const) {
		test(`${lang}: weder Titel, Unterzeile noch die Haken report-*-trend`, () => {
			const html = inSprache(lang, () => kanaeleRendern('route', PROFILE.alles_gekoppelt) + tabRendern('route'));
			// Messaufbau: der Reiter ist wirklich gerendert (Zeitplan-Karte da).
			assert.ok(html.includes(lang === 'de' ? 'Briefing-Zeitplan' : 'Briefing schedule'), 'Messaufbau: Versand-Reiter nicht gerendert');
			for (const id of ['report-morning-trend', 'report-evening-trend'])
				assert.ok(!html.includes(`data-testid="${id}"`), `${lang}: Testid ${id} steht noch im Versand-Reiter`);
			const text = sichtbar(html);
			for (const alt of ALT[lang]) assert.ok(!text.includes(alt), `${lang}: „${alt}" steht noch im Versand-Reiter`);
		});
	}
});
