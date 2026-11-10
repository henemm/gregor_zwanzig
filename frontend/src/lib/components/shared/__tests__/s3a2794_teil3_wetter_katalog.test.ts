// doc-compliance-test (liest die Katalogdateien als DATEN: Pflichttexte der Spec wortgetreu im DE-Katalog)
//
// TDD RED — Issue #2794 S3a, Teil-PR 3 (Reiter Wetter), Stufe 3.1/3.2. AC-41 (+ Pflichttexte aus
// AC-9, AC-10, AC-11, AC-12, AC-14, AC-15, AC-16, AC-18, AC-19, AC-20, AC-21, AC-42).
// Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md; Regeln: docs/reference/i18n_konventionen.md §2
//
// Soll:
//   - frontend/src/lib/i18n/messages/{de,en}/wetter.json existieren, gleiche Schluessel, gleiche
//     Platzhaltermengen, Schluessel im Bereich `wetter.` (2–4 Segmente, [a-z0-9_.]), kein leerer Wert, kein HTML.
//   - Beide Index-Dateien (messages/{de,en}/index.ts) vereinigen den Bereich (sonst findet `t()` die Texte nicht).
//   - Die PO-freigegebenen Texte stehen wortgetreu im DE-Katalog. `{*}` steht fuer einen beliebigen
//     Platzhalter `{name}`; Knopf-/Farbwoerter duerfen aus dem geteilten Katalog kommen (Wiederverwendung).
// Hinweis: frontend/src/lib/i18n/__tests__/paritaet_de_en.test.ts erfasst den neuen Bereich NICHT
// automatisch (feste Liste BEREICHE, „genau die 17 Bereichsdateien“) — dort muss `wetter` ergaenzt werden.
//
// RED heute: messages/de/wetter.json und messages/en/wetter.json fehlen.
//
//   cd frontend && npm test -- src/lib/components/shared/__tests__/s3a2794_teil3_wetter_katalog.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { de as deIndex } from '../../../i18n/messages/de/index.ts';
import { en as enIndex } from '../../../i18n/messages/en/index.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const MESSAGES = join(HIER, '..', '..', '..', 'i18n', 'messages');

type Katalog = Record<string, string>;

function lies(lang: 'de' | 'en'): Katalog {
	const p = join(MESSAGES, lang, 'wetter.json');
	assert.ok(existsSync(p), `TDD RED: messages/${lang}/wetter.json fehlt`);
	return JSON.parse(readFileSync(p, 'utf-8'));
}

const platzhalter = (t: string) => [...new Set([...t.matchAll(/\{([a-z0-9_]+)\}/g)].map((m) => m[1]))].sort();

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
/** Muster -> RegExp: `{*}` = beliebiger Platzhalter, fuehrendes `^` = ganzer Wert. */
function regex(muster: string): RegExp {
	const ganz = muster.startsWith('^');
	const kern = escape(ganz ? muster.slice(1) : muster).replace(/\\\{\\\*\\\}/g, '\\{[a-z0-9_]+\\}');
	return new RegExp(ganz ? `^${kern}$` : kern);
}

type Pflicht = { ac: string; alternativen: string[][]; ueberall?: boolean };
const P = (ac: string, ...muster: string[]): Pflicht => ({ ac, alternativen: [muster] });
const ODER = (ac: string, ...alternativen: string[][]): Pflicht => ({ ac, alternativen });
const GETEILT = (ac: string, ...muster: string[]): Pflicht => ({ ac, alternativen: [muster], ueberall: true });

const PFLICHT: Pflicht[] = [
	P('AC-9', '^Wetter', 'Was im Briefing steht, was für dich zu viel oder zu wenig ist und ab wann du einen Alarm bekommst.'),
	P('AC-9', 'Lade Metriken …'),
	P('AC-9', 'Die Metriken konnten nicht geladen werden. Die Verbindung zum Server ist abgebrochen. Deine Einstellungen sind gespeichert und gehen nicht verloren.'),
	GETEILT('AC-9', '^Erneut laden'),
	P('AC-10', '^unverändert', '^{*} Abweichungen', '{*} Metriken'),
	ODER('AC-10', ['^{*} Abweichung'], ['^1 Abweichung']),
	GETEILT('AC-10', '^Eigene', '^Vorlagen'),
	ODER(
		'AC-11',
		['‚{*}‘ übernehmen? Ersetzt Metrik-Auswahl, Ampel-Grenzen und Alarmstufen dieses {*}.'],
		[
			'‚{*}‘ übernehmen? Ersetzt Metrik-Auswahl, Ampel-Grenzen und Alarmstufen dieses Trips.',
			'‚{*}‘ übernehmen? Ersetzt Metrik-Auswahl, Ampel-Grenzen und Alarmstufen dieses Orts-Briefings.'
		]
	),
	P('AC-11', 'Deine {*} Abweichungen von ‚{*}‘ gehen verloren.', 'Zustellung, Etappen und Orte bleiben unverändert.'),
	GETEILT('AC-11', '^Übernehmen', '^Abbrechen'),
	P('AC-12', 'Auf ‚{*}‘ zurücksetzen'),
	P('AC-14', 'Alarm ab für alle'),
	P('AC-14', '{*} von {*} Metriken lösen einen Alarm aus. {*} können keinen auslösen (Vorboten und reine Anzeige).'),
	P('AC-14', 'Keine der gewählten Metriken kann einen Alarm auslösen. Nimm z.B. Wind, Böen oder Gewitter dazu.'),
	GETEILT('AC-14', '^Nie', '^Gelb', '^Orange', '^Rot'),
	P('AC-15', 'grün: {*} bis {*}', 'grün: ab {*}', 'grün: bis {*}', 'immer grün (keine Grenze gesetzt)'),
	P('AC-15', 'kein Alarm (Vorbote)', '^kein Alarm', '^Grenzen ändern'),
	P('AC-16', 'Grün ist alles zwischen ‚gelb unten‘ und ‚gelb oben‘. Ein leeres Feld heißt: auf dieser Seite keine Grenze.'),
	P('AC-16', 'Abweichend von der Vorlage ‚{*}‘.'),
	GETEILT('AC-16', '^Fertig'),
	P('AC-16', 'Alarm, wenn der Wert seit dem letzten Briefing über {*} {*} steigt', 'dazu bei sehr großen Sprüngen. Entwarnung, wenn er zurückgeht.', 'oder unter {*} {*} fällt'),
	P('AC-18', '‚keins‘ ist immer grün.', 'keine Ampel, nur Anzeige'),
	P('AC-18', 'Alarm, wenn die Gewitter-Stufe seit dem letzten Briefing auf {*} steigt ({*}). Entwarnung, wenn sie wieder fällt.'),
	P('AC-18', 'Mit diesen Farben erreicht Gewitter nie {*}, daher kein Alarm.'),
	P('AC-18', 'Kein Alarm. Die Farbe erscheint nur im Briefing.', 'Nur im Briefing gefärbt. Vorboten lösen keinen Alarm aus.'),
	P('AC-18', 'Nur Anzeige: keine Ampel und kein Alarm. Roh oder Einfach stellst du unten je Liste ein.', 'Für {*} ist keine Grenze gesetzt, daher kein Alarm.'),
	P('AC-19', '{*} ist jetzt im Briefing und steht in allen Listen unter ‚Inhalt je Kanal und Fläche‘. Dort stellst du Roh oder Einfach ein.'),
	P('AC-19', 'Nicht im Briefing', '{*} aus dem Briefing nehmen'),
	P('AC-20', 'im Briefing und als Alarm, sobald sie dein Gebiet betreffen'),
	P('AC-21', 'Radar-Regen', 'Alarm, wenn in der nächsten Stunde Regen auf {*} zukommt', '^Anpassen'),
	P('AC-42', 'Als eigene Vorlage speichern', 'Gib der Vorlage einen Namen.'),
	ODER('AC-42', ['Als Standard für neue {*}'], ['Als Standard für neue Trips', 'Als Standard für neue Orte']),
	P('AC-42', 'Gespeichert werden Metrik-Auswahl, Ampel-Grenzen und Alarmstufen. Zustellung, Etappen und Orte gehören nicht dazu.'),
	P('AC-42', 'Eine Vorlage ‚{*}‘ gibt es schon. Wähle einen anderen Namen.'),
	P('AC-42', 'Vorlage ‚{*}‘ gespeichert. Du findest sie unter ‚Eigene‘.')
];

describe('AC-41: Katalog wetter in DE und EN', () => {
	test('s3a2794_t3_katalog_de_en_gleiche_schluessel_und_platzhalter', () => {
		const de = lies('de');
		const en = lies('en');
		assert.ok(Object.keys(de).length >= 40, `de/wetter.json hat nur ${Object.keys(de).length} Schluessel`);
		assert.deepEqual(Object.keys(en).sort(), Object.keys(de).sort(), 'Schluesselmengen DE ≠ EN');
		const abweichend = Object.keys(de).filter((k) => platzhalter(de[k]).join(',') !== platzhalter(en[k] ?? '').join(','));
		assert.deepEqual(abweichend, [], 'Platzhaltermengen DE ≠ EN');
	});

	test('s3a2794_t3_katalog_schluesselform_und_werte', () => {
		for (const lang of ['de', 'en'] as const) {
			for (const [k, v] of Object.entries(lies(lang))) {
				assert.match(k, /^wetter(\.[a-z0-9_]+){1,3}$/, `${lang}: Schluessel ${k} verletzt die Konvention`);
				assert.ok(typeof v === 'string' && v.trim().length > 0, `${lang}: ${k} leer`);
				assert.doesNotMatch(v, /<[a-z/]/i, `${lang}: ${k} enthaelt HTML`);
			}
		}
	});

	test('s3a2794_t3_katalog_in_beiden_index_dateien_vereinigt', () => {
		for (const [lang, index] of [['de', deIndex], ['en', enIndex]] as const) {
			const fehlt = Object.keys(lies(lang)).filter((k) => (index as Katalog)[k] !== lies(lang)[k]);
			assert.deepEqual(fehlt, [], `messages/${lang}/index.ts vereinigt den Bereich wetter nicht`);
		}
	});

	test('s3a2794_t3_englisch_ist_uebersetzt', () => {
		const de = lies('de');
		const en = lies('en');
		const gleich = Object.keys(de).filter((k) => de[k] === en[k] && /[äöüß]|\b(und|nicht|wenn|der|die|das)\b/i.test(de[k]));
		assert.deepEqual(gleich, [], 'EN-Werte sind deutsch geblieben');
	});
});

describe('Pflichttexte der Spec wortgetreu im DE-Katalog (doc-compliance)', () => {
	for (const p of PFLICHT) {
		test(`${p.ac}: ${p.alternativen.map((a) => a.join(' + ')).join(' ODER ')}`, () => {
			const werte = Object.values(p.ueberall ? (deIndex as Katalog) : lies('de'));
			if (p.ueberall) lies('de'); // RED-Grund bleibt die fehlende Datei
			const erfuellt = p.alternativen.some((alt) => alt.every((m) => werte.some((v) => regex(m).test(v))));
			const fehlend = p.alternativen[0].filter((m) => !werte.some((v) => regex(m).test(v)));
			assert.ok(erfuellt, `${p.ac}: Text fehlt im DE-Katalog${p.ueberall ? '' : ' (wetter.json)'}: ${fehlend.join(' | ')}`);
		});
	}
});
