// TDD RED — Issue #2794 S3a, Teil-PR 4b: Wächter gegen alte Reiternamen (AC-33, AC-49)
// und Menü-Wortlaut (AC-48). Spec: docs/specs/modules/feat_2794_s3a_teil4_entfernen.md
//
// Seit S3a gibt es nur noch die Reiter Übersicht · Etappen/Orte · Wetter · Zustellung.
// Alte Reiter: Wertebereiche, Alarme, Layout, Wetter-Metriken, Versand
// (EN: Target ranges, Alerts, Layout, Weather metrics).
//
// Was der Wächter als „nennt einen alten Reiter" wertet (Unterscheidung Reiter ↔ Funktion):
//   R1  Reiter-Wort + alter Name:  „Reiter Versand", „im Tab „Wetter-Metriken"", „Wetter-Metriken-Tab",
//       „Layout-Reiter", EN „the Alerts tab", „in the Weather metrics tab".
//   R2  Navigation auf einen alten Reiter: „unter Wetter-Metriken", „zu „Wetter-Metriken"",
//       „… Wertebereiche … in den nächsten Tabs", EN „under Weather metrics", „to “Weather metrics”".
//   R3  Sprung-/Reiter-Beschriftung, die nur aus einem alten Namen besteht
//       („Wetter-Metriken", „→ Wetter-Metriken", „Wetter-Metriken bearbeiten →", „Change weather metrics").
//       „Versand" fällt hier NICHT darunter: Versand ist Abschnitt der Zustellung (Anker #versand).
//   R4  Reiter-Schlüssel `aktionen.reiter.*` gibt es nur für die neuen Reiter.
// Erlaubt bleiben Fachbegriffe ohne Reiterbezug („Wetter-Metriken konnten nicht geladen werden",
// „Versand-Historie", „Layout je Kanal", „Abschnitt Versand") und die Funktionsnamen der POSITIVLISTE.
//
//   cd frontend && npm test -- src/lib/i18n/__tests__/keine_alten_reiternamen.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const MESSAGES = join(dirname(fileURLToPath(import.meta.url)), '..', 'messages');
type Sprache = 'de' | 'en';

function katalog(lang: Sprache): Record<string, string> {
	const aus: Record<string, string> = {};
	for (const f of readdirSync(join(MESSAGES, lang)).filter((n) => n.endsWith('.json'))) {
		Object.assign(aus, JSON.parse(readFileSync(join(MESSAGES, lang, f), 'utf-8')));
	}
	return aus;
}

/** Funktionsnamen, die wie ein alter Reiter klingen, aber eine Funktion benennen. Jede Zeile mit Grund. */
const POSITIVLISTE: Record<string, string> = {
	'aktionen.alarms': 'Funktionsname im Listen-Menü „Alarme", Ziel Reiter Zustellung (AC-48)',
	'hilfe.alarme.titel': 'Überschrift des Hilfe-Abschnitts über die Funktion Alarme, kein Reiter',
	'trip.kanaele.fuss_alerts': 'Spaltenkopf „Alerts" der Kanal-Tabelle (Funktion), kein Reiter'
};

const ALT: Record<Sprache, string[]> = {
	de: ['Wertebereiche', 'Alarme', 'Layout', 'Wetter-Metriken', 'Versand'],
	en: ['Target ranges', 'Alerts', 'Layout', 'Weather metrics']
};
const BESCHRIFTUNG: Record<Sprache, string[]> = { de: ['Wertebereiche', 'Alarme', 'Layout', 'Wetter-Metriken'], en: ALT.en };
// #2794 Fix-Loop B1: Trip-Reiter heißt kurz „Etappen" (aktionen.reiter.etappen ersetzt etappen_wegpunkte).
const NEUE_REITER = ['uebersicht', 'etappen', 'orte', 'wetter', 'zustellung'];
const Q = `["„“”"'‚‘]?`;
const oder = (namen: string[]) => `(${namen.map((n) => n.replace(/[-]/g, '\\-')).join('|')})`;

function regeln(lang: Sprache): Array<[string, RegExp]> {
	const a = oder(ALT[lang]);
	const w = oder(['Wertebereiche', 'Wetter-Metriken', 'Target ranges', 'Weather metrics']);
	const b = oder(BESCHRIFTUNG[lang]);
	return lang === 'de'
		? [
				['R1', new RegExp(`\\b(Reiter|Tab|Registerkarte)\\s*${Q}\\s*${a}(?![\\wäöü-])`)],
				['R1', new RegExp(`${a}${Q}[- ](Reiter|Tab)\\b`)],
				['R2', new RegExp(`\\b(unter|zu|nach)\\s+${Q}${w}\\b`)],
				['R2', new RegExp(`${w}[^.]{0,60}\\b(Tabs|Reitern)\\b`)],
				['R3', new RegExp(`^(→\\s*)?${b}(\\s+(bearbeiten|ändern))?(\\s*→)?$`)]
			]
		: [
				['R1', new RegExp(`${Q}${a}${Q}\\s+tab\\b`, 'i')],
				['R1', new RegExp(`\\btab\\s+${Q}${a}\\b`, 'i')],
				['R2', new RegExp(`\\b(under|to)\\s+${Q}${w}\\b`, 'i')],
				['R2', new RegExp(`${w}[^.]{0,60}\\btabs\\b`, 'i')],
				['R3', new RegExp(`^(→\\s*)?((edit|change)\\s+)?${b}(\\s*→)?$`, 'i')]
			];
}

type Treffer = { key: string; regel: string; text: string };

/** Reine Prüffunktion: alle Nutzertexte, die einen alten Reiter als Reiter nennen. */
function alteReiternamen(k: Record<string, string>, lang: Sprache, positiv: Record<string, string> = POSITIVLISTE): Treffer[] {
	const aus: Treffer[] = [];
	for (const [key, text] of Object.entries(k)) {
		if (key in positiv || typeof text !== 'string') continue;
		if (key.startsWith('aktionen.reiter.') && !NEUE_REITER.includes(key.slice('aktionen.reiter.'.length))) {
			aus.push({ key, regel: 'R4', text });
			continue;
		}
		const r = regeln(lang).find(([, re]) => re.test(text.trim()));
		if (r) aus.push({ key, regel: r[0], text });
	}
	return aus;
}

const zeige = (t: Treffer[]) => t.map((x) => `  ${x.regel} ${x.key}: „${x.text}"`).join('\n');

describe('AC-49 Negativ-Fixture: der Wächter schlägt an', () => {
	const de: Record<string, string> = {
		'x.r1a': 'Wähle im Tab „Wetter-Metriken" Metriken aus.',
		'x.r1b': 'Eintragen im Reiter Versand bzw. im Profil.',
		'x.r1c': 'Wähle Metriken im Wetter-Metriken-Tab.',
		'x.r1d': 'Folgt der SMS-Auswahl im Layout-Reiter.',
		'x.r1e': 'Legt die Schwelle im Reiter Alarme fest.',
		'x.r2a': 'Briefing-Uhrzeiten unter Wetter-Metriken im Abschnitt Versand festlegen.',
		'x.r2b': 'Die Wertebereiche legst du in den nächsten Tabs fest.',
		'x.r3a': '→ Wetter-Metriken',
		'x.r3b': 'Wetter-Metriken bearbeiten →',
		'x.r3c': 'Wertebereiche',
		'aktionen.reiter.wertebereiche': 'Wertebereiche'
	};
	const en: Record<string, string> = {
		'x.r1a': 'Select metrics in the “Weather metrics” tab.',
		'x.r1b': 'The urgency threshold in the Alerts tab.',
		'x.r2a': 'Set the briefing times under Weather metrics in the Delivery section.',
		'x.r3a': 'Change weather metrics',
		'x.r3b': 'Target ranges'
	};
	for (const [lang, fx] of [['de', de], ['en', en]] as const) {
		test(`${lang}: jeder Fixture-Text wird gefunden`, () => {
			const gefunden = new Set(alteReiternamen(fx, lang).map((t) => t.key));
			const verpasst = Object.keys(fx).filter((k) => !gefunden.has(k));
			assert.deepEqual(verpasst, [], `nicht erkannt: ${verpasst.join(', ')}`);
		});
	}
});

describe('AC-49 Funktionsnamen und Fachbegriffe schlagen NICHT an', () => {
	test('de/en: erlaubte Texte bleiben ohne Treffer', () => {
		const de = {
			'y.1': 'Die Zeiten stehen im Reiter Zustellung im Abschnitt Versand.',
			'y.2': 'Wetter-Metriken konnten nicht geladen werden.',
			'y.3': 'Versand-Historie',
			'y.4': 'Layout je Kanal',
			'y.5': 'Versand',
			'aktionen.alarms': 'Alarme'
		};
		const en = { 'y.1': 'The times are set in the Delivery tab.', 'y.2': 'Weather metrics could not be loaded.', 'aktionen.alarms': 'Alerts' };
		assert.deepEqual(alteReiternamen(de, 'de'), []);
		assert.deepEqual(alteReiternamen(en, 'en'), []);
	});

	test('Positivliste ist nicht veraltet: jeder Eintrag existiert und würde ohne Liste anschlagen', () => {
		for (const key of Object.keys(POSITIVLISTE)) {
			const schlaegtAn = (['de', 'en'] as const).some((lang) => {
				const k = katalog(lang);
				assert.ok(key in k, `${lang}: Positivliste nennt ${key}, den es nicht mehr gibt`);
				return alteReiternamen({ [key]: k[key] }, lang, {}).length > 0;
			});
			assert.ok(schlaegtAn, `${key} schlägt in keiner Sprache an und braucht keinen Positivlisten-Eintrag mehr`);
		}
	});
});

describe('AC-33/AC-49: Kataloge nennen keinen alten Reiter mehr', () => {
	for (const lang of ['de', 'en'] as const) {
		test(`${lang}: kein Nutzertext nennt Wertebereiche, Alarme, Layout, Wetter-Metriken oder Versand als Reiter`, () => {
			const t = alteReiternamen(katalog(lang), lang);
			assert.deepEqual(t, [], `alte Reiternamen in ${lang}:\n${zeige(t)}`);
		});
	}
});

describe('AC-48: Listen-Menü „Wetter" und „Alarme" in beiden Sprachen', () => {
	test('aktionen.weather heißt „Wetter" / „Weather" (früher „Wetter-Metriken")', () => {
		assert.equal(katalog('de')['aktionen.weather'], 'Wetter');
		assert.equal(katalog('en')['aktionen.weather'], 'Weather');
	});
	test('aktionen.alarms bleibt als Funktionsname „Alarme" / „Alerts"', () => {
		assert.equal(katalog('de')['aktionen.alarms'], 'Alarme');
		assert.equal(katalog('en')['aktionen.alarms'], 'Alerts');
	});
	test('Menü-Wortlaut „Wetter" = Name des Reiters Wetter (eine Bezeichnung, kein zweiter Begriff)', () => {
		for (const lang of ['de', 'en'] as const) {
			const k = katalog(lang);
			assert.equal(k['aktionen.weather'], k['aktionen.reiter.wetter'], lang);
		}
	});
});

// doc-compliance-test: das Glossar ist Doku, kein Verhalten — geprüft wird nur, dass die
// Zeile „Wertebereiche … Reiter-Name" entfallen ist (AC-49).
describe('AC-49: Glossar führt „Wertebereiche" nicht mehr als Reiter-Name', () => {
	test('keine Glossar-Zeile „| Wertebereiche | … | Reiter-Name |"', () => {
		const glossar = readFileSync(join(MESSAGES, '..', '..', '..', '..', '..', 'docs', 'reference', 'i18n_glossar.md'), 'utf-8');
		assert.ok(!/^\|\s*Wertebereiche\s*\|[^\n]*\|\s*Reiter-Name\s*\|/m.test(glossar), 'Glossar nennt Wertebereiche noch als Reiter-Name');
	});
});
