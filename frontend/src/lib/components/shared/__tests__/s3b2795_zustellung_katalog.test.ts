// doc-compliance-test (liest Katalogdateien und das Glossar als DATEN: Pflichttexte der Spec wortgetreu im DE-Katalog)
//
// TDD RED — Issue #2795 S3b, Teilschritt 1b (Neubau Reiter „Zustellung“). AC-35 (+ Pflichttexte aus AC-1, AC-2,
// AC-3, AC-8, AC-9, AC-10, AC-11, AC-12, AC-13, AC-14, AC-15, AC-16, AC-17, AC-18, AC-19, AC-20, AC-21, AC-24,
// AC-26, AC-30). Spec: docs/specs/modules/feat_2795_s3b_teil1_zustellung.md §6; Regeln: docs/reference/i18n_konventionen.md
//
// Soll:
//   - frontend/src/lib/i18n/messages/{de,en}/zustellung.json existieren, gleiche Schluessel, gleiche
//     Platzhaltermengen, Schluessel im Bereich `zustellung.` (2–5 Segmente inkl. Plural `.one/.other`,
//     [a-z0-9_.]), kein leerer Wert, kein HTML; Plural-Paare vollstaendig.
//   - Beide Index-Dateien (messages/{de,en}/index.ts) vereinigen den Bereich.
//   - Die Texte aus Spec/Mockup (`viewZustellung()`) stehen wortgetreu im DE-Katalog. `{*}` = beliebiger
//     Platzhalter; geteilte Woerter (Kanal, Alarme, gering/mittel/hoch, Stille Stunden, Anpassen …) duerfen aus
//     bestehenden Bereichen kommen (GETEILT).
//   - Glossar docs/reference/i18n_glossar.md hat Zeilen fuer Zustellung, Stille Stunden, Dringlichkeit (§6).
//   - i18n/__tests__/paritaet_de_en.test.ts fuehrt `zustellung` in BEREICHE (dort ergaenzt).
//
// RED heute: messages/de/zustellung.json und messages/en/zustellung.json fehlen; Glossar ohne die drei Zeilen.
//
//   cd frontend && npm test -- src/lib/components/shared/__tests__/s3b2795_zustellung_katalog.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { de as deIndex } from '../../../i18n/messages/de/index.ts';
import { en as enIndex } from '../../../i18n/messages/en/index.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const MESSAGES = join(HIER, '..', '..', '..', 'i18n', 'messages');
const GLOSSAR = join(HIER, '..', '..', '..', '..', '..', '..', 'docs', 'reference', 'i18n_glossar.md');

type Katalog = Record<string, string>;

function lies(lang: 'de' | 'en'): Katalog {
	const p = join(MESSAGES, lang, 'zustellung.json');
	assert.ok(existsSync(p), `TDD RED: messages/${lang}/zustellung.json fehlt`);
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
	GETEILT('AC-1', '^Zustellung'),
	P('AC-1', '^Wann die Briefings kommen und auf welchem Weg Briefings und Alarme dich erreichen.'),
	GETEILT('AC-2', '^Morgen-Briefing', '^Abend-Briefing'),
	P('AC-2', '^für die Etappe des Tages', '^für die Etappe von morgen'),
	P('AC-3', '^für heute', '^für morgen'),
	P('AC-8', '^Bitte eine Zeit im Viertelstunden-Raster eintragen (00, 15, 30, 45)'),
	P('AC-9', '^{*}. Die Briefings enden nach der letzten Etappe. Die Daten pflegst du in den Etappen.'),
	GETEILT('AC-9', '^Laufzeit', '^Etappen öffnen →'),
	P('AC-10', '^Das Briefing läuft, bis du es pausierst.'),
	ODER(
		'AC-10',
		['^Danach pausiert das Briefing von selbst. Im Kopf steht dann „Laufzeit überschritten“.'],
		['^Danach pausiert das Briefing von selbst. Im Kopf steht dann ‚Laufzeit überschritten‘.']
	),
	GETEILT('AC-10', '^Bis auf Weiteres', '^Bis Datum'),
	P('AC-11', '^Kein Kanal für Briefings an.', '^So kommt kein Briefing bei dir an. Schalte unten mindestens einen Kanal ein.'),
	P('AC-12', '^Kein Kanal für Alarme an.', '^Alarme gehen nirgends hin.'),
	P('AC-13', '{*} Kanal', '{*} Kanäle', 'Briefings über', 'Alarme über'),
	P('AC-13', '^Ein Kanal ohne Verbindung ist gesperrt, bis du ihn im Konto einrichtest.'),
	GETEILT('AC-14', '^Kanal', '^Alarme'),
	P('AC-14', '^Briefing', '^Alarm schon ab Dringlichkeit'),
	GETEILT('AC-14', '^bestätigt', '^verbunden', '^nicht verbunden'),
	P('AC-14', '^unbestätigt'),
	P('AC-15', 'Telegram-Chat fehlt', '^gesperrt: {*}'),
	ODER('AC-15', ['^Im Konto verbinden →', '^Im Konto bestätigen →', '^Im Konto prüfen →'], ['^Im Konto {*} →', '^verbinden', '^bestätigen', '^prüfen']),
	P('AC-16', 'Nummer noch nicht bestätigt', 'E-Mail-Adresse fehlt', 'SMS ab Level Standard'),
	GETEILT('AC-17', '^gering', '^mittel', '^hoch'),
	ODER(
		'AC-18',
		['^Die SMS kostet wenig und bekommt deshalb schon Alarme ab „mittel“. Die Premium-SMS geht über Satellit und meldet sich nur bei „hoch“.'],
		['^Die SMS kostet wenig und bekommt deshalb schon Alarme ab ‚mittel‘. Die Premium-SMS geht über Satellit und meldet sich nur bei ‚hoch‘.']
	),
	P('AC-19', '^inReach · Rückadresse gelernt {*} · zuletzt gemeldet {*}'),
	P('AC-20', 'Rückadresse verfallen', '^Schick eine Nachricht vom Gerät, dann ist die Rückadresse wieder gültig.'),
	GETEILT('AC-21', 'Tarif wird geprüft', 'ab Level Premium'),
	GETEILT('AC-24', '^Stille Stunden', '^Minuten', '^Anpassen'),
	P('AC-24', '^keine Alarme, sie kommen mit dem nächsten Morgen-Briefing'),
	P('AC-26', '^Mindestabstand zwischen zwei Alarmen', '^derselben Metrik')
];

describe('AC-35: Katalog zustellung in DE und EN', () => {
	test('s3b2795_katalog_de_en_gleiche_schluessel_und_platzhalter', () => {
		const de = lies('de');
		const en = lies('en');
		assert.ok(Object.keys(de).length >= 30, `de/zustellung.json hat nur ${Object.keys(de).length} Schluessel`);
		assert.deepEqual(Object.keys(en).sort(), Object.keys(de).sort(), 'Schluesselmengen DE ≠ EN (Lueckenpruefung)');
		const abweichend = Object.keys(de).filter((k) => platzhalter(de[k]).join(',') !== platzhalter(en[k] ?? '').join(','));
		assert.deepEqual(abweichend, [], 'Platzhaltermengen DE ≠ EN');
	});

	test('s3b2795_katalog_schluesselform_werte_plural', () => {
		for (const lang of ['de', 'en'] as const) {
			const k = lies(lang);
			for (const [s, v] of Object.entries(k)) {
				assert.match(s, /^zustellung(\.[a-z0-9_]+){1,4}$/, `${lang}: Schluessel ${s} verletzt die Konvention`);
				assert.ok(typeof v === 'string' && v.trim().length > 0, `${lang}: ${s} leer`);
				assert.doesNotMatch(v, /<[a-z/]/i, `${lang}: ${s} enthaelt HTML`);
				if (s.endsWith('.one')) assert.ok(`${s.slice(0, -4)}.other` in k, `${lang}: ${s} ohne .other`);
				if (s.endsWith('.other')) assert.ok(`${s.slice(0, -6)}.one` in k, `${lang}: ${s} ohne .one`);
			}
		}
	});

	test('s3b2795_katalog_in_beiden_index_dateien_vereinigt', () => {
		for (const [lang, index] of [['de', deIndex], ['en', enIndex]] as const) {
			const k = lies(lang);
			const fehlt = Object.keys(k).filter((s) => (index as Katalog)[s] !== k[s]);
			assert.deepEqual(fehlt, [], `messages/${lang}/index.ts vereinigt den Bereich zustellung nicht`);
		}
	});

	test('s3b2795_englisch_ist_uebersetzt', () => {
		const de = lies('de');
		const en = lies('en');
		const gleich = Object.keys(de).filter((k) => de[k] === en[k] && /[äöüß]|\b(und|nicht|wenn|der|die|das|für|über|Kanal)\b/i.test(de[k]));
		assert.deepEqual(gleich, [], 'EN-Werte sind deutsch geblieben');
		for (const [k, v] of Object.entries(en)) assert.doesNotMatch(v, /[äöüß]/, `en: ${k} enthaelt Umlaute: „${v}“`);
	});

	test('s3b2795_datenwerte_nicht_im_katalog_uebersetzt', () => {
		// ADR-0104: Datenwerte LOW/MODERATE/HIGH sind Protokoll-Token, nie Katalogtext.
		for (const lang of ['de', 'en'] as const) {
			for (const [k, v] of Object.entries(lies(lang))) assert.doesNotMatch(v, /^(LOW|MODERATE|HIGH)$/, `${lang}: ${k} uebersetzt einen Datenwert`);
		}
	});

	test('s3b2795_uebergangsblock_hat_eigene_ueberschrift (AC-30)', () => {
		const de = lies('de');
		assert.ok(Object.keys(de).some((k) => k.startsWith('zustellung.uebergang.')), 'Ueberschrift des Uebergangsblocks fehlt (zustellung.uebergang.*)');
	});
});

describe('Pflichttexte der Spec/des Mockups wortgetreu im DE-Katalog (doc-compliance)', () => {
	for (const p of PFLICHT) {
		test(`${p.ac}: ${p.alternativen.map((a) => a.join(' + ')).join(' ODER ')}`, () => {
			const eigen = lies('de'); // RED-Grund bleibt die fehlende Datei
			const werte = Object.values(p.ueberall ? (deIndex as Katalog) : eigen);
			const erfuellt = p.alternativen.some((alt) => alt.every((m) => werte.some((v) => regex(m).test(v))));
			const fehlend = p.alternativen[0].filter((m) => !werte.some((v) => regex(m).test(v)));
			assert.ok(erfuellt, `${p.ac}: Text fehlt im DE-Katalog${p.ueberall ? '' : ' (zustellung.json)'}: ${fehlend.join(' | ')}`);
		});
	}
});

describe('§6: Glossar zuerst — Zustellung, Stille Stunden, Dringlichkeit (doc-compliance)', () => {
	const zeilen = readFileSync(GLOSSAR, 'utf-8').split('\n').filter((z) => z.startsWith('|'));
	const zelle = (z: string) => z.split('|').map((x) => x.trim());
	for (const begriff of ['Zustellung', 'Stille Stunden', 'Dringlichkeit']) {
		test(`glossar_${begriff.replace(/\s+/g, '_').toLowerCase()}`, () => {
			const z = zeilen.find((x) => zelle(x)[1] === begriff);
			assert.ok(z, `Glossar: keine Zeile „| ${begriff} | … |“ in docs/reference/i18n_glossar.md`);
			assert.ok(zelle(z!)[2].length > 0, `Glossar: ${begriff} ohne englischen Begriff`);
		});
	}
});
