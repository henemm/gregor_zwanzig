// TDD RED — Onboarding S3 (Issue #2521): Textkatalog fuer Standardwerte-Knopf,
// Hilfeseite und Hilfelinks sowie die zwei Korrekturen der Erklaer-Hinweise.
// Spec: docs/specs/modules/onboarding_standardwerte_hilfe.md — AC-14, AC-16
// (Katalogteil), AC-21 (Katalogteil).
//
// Vertrag (Schluessel, die die Bausteine per t(key) nutzen):
//   standardwerte.knopf               Beschriftung „Mit Standardwerten speichern"
//   hilfe.titel                       Seitentitel „So funktioniert Gregor"
//   hilfe.briefing.titel / .morgens / .abends
//   hilfe.alarme.titel / .text
//   hilfe.kanaele.titel / .email / .telegram / .sms / .premium_sms
//   hilfe.befehle.titel
//   hilfe.befehle.<wort>.befehl / .text   je Antwort-Befehl (Drift-Test:
//                                     tests/test_hilfe_befehle_drift.py)
//   nav.hilfe                         Linktext in Seitenleiste und Konto-Menue
//   onboarding.checkliste.hilfe       Linktext in der Startklar-Checkliste
//
// Gegenprobe: jede Pruefregel laeuft zusaetzlich gegen einen bekannt schlechten
// Text („Tour", Handlungsempfehlung, „Hauptkanal", alter Infobox-Wortlaut) — so
// bleibt keine Regel vakuum-gruen.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/i18n/__tests__/standardwerte_hilfe_textkatalog.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { de } from '../messages/de/index.ts';

const katalog = de as Record<string, string>;

export const PFLICHT_SCHLUESSEL = [
	'standardwerte.knopf',
	'hilfe.titel',
	'hilfe.briefing.titel',
	'hilfe.briefing.morgens',
	'hilfe.briefing.abends',
	'hilfe.alarme.titel',
	'hilfe.alarme.text',
	'hilfe.kanaele.titel',
	'hilfe.kanaele.email',
	'hilfe.kanaele.telegram',
	'hilfe.kanaele.sms',
	'hilfe.kanaele.premium_sms',
	'hilfe.befehle.titel',
	'nav.hilfe',
	'onboarding.checkliste.hilfe'
];

const TOUR = /\bTour/i;
const EMPFEHLUNG = /solltest|sollte\b|empfehl|ratsam|am besten|musst du|besser/i;
const HAUPTKANAL = /Hauptkanal|wichtigste[rn]? Kanal|bevorzugte[rn]? Kanal/i;
const ERSETZT = /ersetz|anstelle|statt\s+(der\s+)?(E-Mail|Telegram|SMS|Premium)/i;
const SIGNAL = /\bSignal\b/;

/** Alle Schluessel dieser Scheibe (fest + Befehlseintraege). */
function neueSchluessel(): string[] {
	const befehle = Object.keys(katalog).filter((k) => k.startsWith('hilfe.'));
	return [...new Set([...PFLICHT_SCHLUESSEL, ...befehle])];
}

/** Verstoesse eines Textes; leere Liste = in Ordnung. */
function verstoesse(wert: string | undefined): string[] {
	const v: string[] = [];
	if (typeof wert !== 'string' || !wert.trim()) return ['leer oder fehlt'];
	if (TOUR.test(wert)) v.push('„Tour" statt „Trip"');
	if (EMPFEHLUNG.test(wert)) v.push('Handlungsempfehlung');
	if (HAUPTKANAL.test(wert)) v.push('ein Kanal als Hauptkanal');
	if (ERSETZT.test(wert)) v.push('ein Kanal ersetze einen anderen');
	if (SIGNAL.test(wert)) v.push('Signal (seit #610 entfernt)');
	return v;
}

describe('Gegenprobe: die Pruefregeln erkennen schlechte Texte', () => {
	for (const schlecht of [
		'',
		'Plane deine Tour',
		'Du solltest morgens lesen',
		'E-Mail ist der Hauptkanal',
		'Premium-SMS ersetzt die E-Mail',
		'Auch per Signal'
	]) {
		test(`erkannt: ${JSON.stringify(schlecht)}`, () => assert.notDeepEqual(verstoesse(schlecht), []));
	}
});

describe('AC-21: alle neuen Texte stehen im Katalog, sagen „Trip", ohne Empfehlung', () => {
	for (const key of PFLICHT_SCHLUESSEL) {
		test(`${key}`, () => assert.deepEqual(verstoesse(katalog[key]), [], `${key}: ${JSON.stringify(katalog[key])}`));
	}
	test('auch alle uebrigen hilfe.*-Eintraege (Befehle) sind regelkonform', () => {
		const schlecht = neueSchluessel()
			.map((k) => [k, verstoesse(katalog[k])] as const)
			.filter(([, v]) => v.length > 0);
		assert.deepEqual(schlecht, []);
	});
	test('standardwerte.knopf sagt „Standardwerte" und „speichern"', () => {
		assert.match(katalog['standardwerte.knopf'] ?? '', /Standardwert/);
		assert.match(katalog['standardwerte.knopf'] ?? '', /speicher/i);
	});
	test('nav.hilfe heisst „Hilfe"', () => assert.equal(katalog['nav.hilfe'], 'Hilfe'));
	test('Antwort-Befehle: mindestens ein Eintrag hilfe.befehle.<wort>.befehl mit Beschreibung .text', () => {
		const befehle = Object.keys(katalog).filter((k) => /^hilfe\.befehle\.[^.]+\.befehl$/.test(k));
		assert.ok(befehle.length > 0, 'keine Befehlseintraege im Katalog');
		for (const k of befehle) {
			const t = k.replace(/\.befehl$/, '.text');
			assert.ok(katalog[t]?.trim(), `${t} fehlt`);
		}
	});
});

describe('AC-16 (Katalog): vier Kanaele gleichrangig, SMS und Premium-SMS „je nach Tarif"', () => {
	const KANAL: Array<[string, RegExp]> = [
		['hilfe.kanaele.email', /E-Mail/],
		['hilfe.kanaele.telegram', /Telegram/],
		['hilfe.kanaele.sms', /\bSMS\b/],
		['hilfe.kanaele.premium_sms', /Premium-SMS/]
	];
	for (const [key, name] of KANAL) {
		test(`${key} nennt den Kanal`, () => assert.match(katalog[key] ?? '', name));
	}
	test('SMS und Premium-SMS tragen „je nach Tarif"', () => {
		assert.match(katalog['hilfe.kanaele.sms'] ?? '', /je nach Tarif/);
		assert.match(katalog['hilfe.kanaele.premium_sms'] ?? '', /je nach Tarif/);
	});
	test('kein hilfe.*-Text nennt einen Hauptkanal oder sagt, ein Kanal ersetze einen anderen', () => {
		for (const k of neueSchluessel()) {
			assert.doesNotMatch(katalog[k] ?? '', HAUPTKANAL, k);
			assert.doesNotMatch(katalog[k] ?? '', ERSETZT, k);
		}
	});
});

describe('AC-14: korrigierter Wertebereiche-Hinweis im Ortsvergleich', () => {
	const ALT_WB = /keine Wertebereiche/;
	const wbOk = (t: string) => !ALT_WB.test(t) && /vorbelegt/.test(t) && /Aktivit(ä|ae)tsprofil/.test(t);

	test('Gegenprobe: alter Wortlaut wird erkannt', () => {
		assert.equal(wbOk('Standard: keine Wertebereiche, im Briefing wird nichts hervorgehoben.'), false);
	});
	test('info.wertebereiche.vergleich: Wertebereiche werden aus dem Aktivitaetsprofil vorbelegt', () => {
		assert.ok(wbOk(katalog['info.wertebereiche.vergleich'] ?? ''), katalog['info.wertebereiche.vergleich']);
	});
	test('korrigierter Hinweis bleibt regelkonform (Trip, keine Empfehlung)', () => {
		for (const k of ['info.wertebereiche.vergleich']) {
			assert.doesNotMatch(katalog[k], TOUR, k);
		}
	});
});
