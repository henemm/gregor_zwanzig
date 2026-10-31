// TDD RED — Onboarding S2, AC-17 (und AC-15 Textteil): alle Texte von Willkommen
// und Startklar-Checkliste stehen im Textkatalog de.json unter `onboarding.*`,
// sind nicht leer, sagen durchgehend „Trip" (nie „Tour"), geben keine
// Handlungsempfehlung und behaupten nie, ein Kanal ersetze einen anderen.
// Spec docs/specs/modules/onboarding_willkommen_checkliste.md.
//
// Vertrag (Pflicht-Schluessel, die die Bausteine per t(key) nutzen):
//   onboarding.willkommen.titel             Ueberschrift
//   onboarding.willkommen.text              was Gregor macht (Briefing morgens/abends, Alarme)
//   onboarding.willkommen.testmail          Knopf „Testmail senden" im Willkommen
//   onboarding.willkommen.neuer_trip        Link /trips/new
//   onboarding.willkommen.neuer_vergleich   Link /compare/new
//   onboarding.willkommen.verstanden        Knopf „Verstanden"
//   onboarding.checkliste.titel
//   onboarding.checkliste.email             Pflicht: E-Mail bestaetigt
//   onboarding.checkliste.trip_oder_vergleich  Pflicht: Trip oder Ortsvergleich
//   onboarding.checkliste.erstes_briefing   Pflicht: erstes Briefing erhalten
//   onboarding.checkliste.testmail_gesendet „Testmail gesendet am" (Datum folgt im Baustein)
//   onboarding.checkliste.testmail_senden   Knopf ohne Datum
//   onboarding.checkliste.telegram          Info: Telegram verknuepft (optional)
//   onboarding.checkliste.ausblenden        Knopf „Ausblenden"
//   onboarding.hinweis.sms                  nur bei sms_allowed
//   onboarding.hinweis.premium_sms          nur bei premium_sms_allowed
//
// Gegenprobe: die Pruefregeln laufen zusaetzlich gegen bekannt schlechte Texte
// (leer, „Tour", „solltest", „ersetzt") — so bleibt kein Fall vakuum-gruen.
//
//   cd frontend && npm test -- src/lib/i18n/__tests__/onboarding_textkatalog.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { de } from '../messages/de/index.ts';

const katalog = de as Record<string, string>;

export const PFLICHT_SCHLUESSEL = [
	'onboarding.willkommen.titel',
	'onboarding.willkommen.text',
	'onboarding.willkommen.testmail',
	'onboarding.willkommen.neuer_trip',
	'onboarding.willkommen.neuer_vergleich',
	'onboarding.willkommen.verstanden',
	'onboarding.checkliste.titel',
	'onboarding.checkliste.email',
	'onboarding.checkliste.trip_oder_vergleich',
	'onboarding.checkliste.erstes_briefing',
	'onboarding.checkliste.testmail_gesendet',
	'onboarding.checkliste.testmail_senden',
	'onboarding.checkliste.telegram',
	'onboarding.checkliste.ausblenden',
	'onboarding.hinweis.sms',
	'onboarding.hinweis.premium_sms'
];

const TOUR = /\bTour/i;
const EMPFEHLUNG = /solltest|sollte\b|empfehl|ratsam|am besten|musst du|besser/i;
const ERSETZT = /ersetz|anstelle|statt\s+(der\s+)?(E-Mail|Telegram|SMS|Premium)/i;

/** Verstoesse eines Textes; leere Liste = in Ordnung. */
function verstoesse(wert: string | undefined): string[] {
	const v: string[] = [];
	if (typeof wert !== 'string' || wert.trim() === '') return ['leer'];
	if (TOUR.test(wert)) v.push('Tour');
	if (EMPFEHLUNG.test(wert)) v.push('Handlungsempfehlung');
	if (ERSETZT.test(wert)) v.push('Kanal ersetzt Kanal');
	return v;
}

const onboardingKeys = Object.keys(katalog).filter((k) => k.startsWith('onboarding.'));

describe('Gegenprobe: die Pruefregeln fangen bekannt schlechte Texte', () => {
	test('leer, Tour, Empfehlung, Ersetzung werden erkannt; ein guter Text nicht', () => {
		assert.deepEqual(verstoesse(''), ['leer']);
		assert.deepEqual(verstoesse(undefined), ['leer']);
		assert.deepEqual(verstoesse('Leg deine erste Tour an'), ['Tour']);
		assert.deepEqual(verstoesse('Du solltest eine Testmail senden'), ['Handlungsempfehlung']);
		assert.deepEqual(verstoesse('Wir empfehlen Telegram'), ['Handlungsempfehlung']);
		assert.deepEqual(verstoesse('Premium-SMS ersetzt die E-Mail'), ['Kanal ersetzt Kanal']);
		assert.deepEqual(verstoesse('Telegram statt E-Mail'), ['Kanal ersetzt Kanal']);
		assert.deepEqual(verstoesse('Gregor schickt dir morgens und abends ein Briefing zu deinem Trip.'), []);
	});
});

describe('AC-17: Onboarding-Texte im Katalog', () => {
	test('jeder Pflicht-Schluessel ist vorhanden und nicht leer', () => {
		const fehlend = PFLICHT_SCHLUESSEL.filter((k) => !(katalog[k]?.trim().length > 0));
		assert.deepEqual(fehlend, [], `fehlende/leere onboarding.*-Schluessel in de.json`);
	});
	test('Messaufbau nicht leer: mindestens die Pflicht-Schluessel tragen das Praefix onboarding.', () => {
		assert.ok(onboardingKeys.length >= PFLICHT_SCHLUESSEL.length, `nur ${onboardingKeys.length} onboarding.*-Schluessel`);
	});
	test('kein onboarding.*-Text sagt „Tour", empfiehlt etwas oder laesst einen Kanal einen anderen ersetzen', () => {
		assert.ok(onboardingKeys.length > 0, 'keine onboarding.*-Texte — Messaufbau leer');
		const befunde = onboardingKeys
			.map((k) => [k, verstoesse(katalog[k])] as const)
			.filter(([, v]) => v.length > 0)
			.map(([k, v]) => `${k}: ${v.join(', ')} ("${katalog[k]}")`);
		assert.deepEqual(befunde, []);
	});
	test('Willkommen erklaert, was Gregor macht: Briefing morgens und abends, Alarme', () => {
		const t = katalog['onboarding.willkommen.text'] ?? '';
		for (const re of [/Briefing/, /morgens/, /abends/, /Alarm/]) {
			assert.match(t, re, `onboarding.willkommen.text nennt ${re} nicht: "${t}"`);
		}
	});
	test('Pflichtpunkt nennt „Trip" und „Ortsvergleich"; Willkommen-Links nennen Trip bzw. Vergleich', () => {
		assert.match(katalog['onboarding.checkliste.trip_oder_vergleich'] ?? '', /\bTrip\b/);
		assert.match(katalog['onboarding.checkliste.trip_oder_vergleich'] ?? '', /Ortsvergleich/);
		assert.match(katalog['onboarding.willkommen.neuer_trip'] ?? '', /\bTrip\b/);
		assert.match(katalog['onboarding.willkommen.neuer_vergleich'] ?? '', /Vergleich/);
	});
	test('Testmail-Texte nennen die Testmail; Telegram-Punkt nennt Telegram', () => {
		for (const k of ['onboarding.willkommen.testmail', 'onboarding.checkliste.testmail_gesendet', 'onboarding.checkliste.testmail_senden']) {
			assert.match(katalog[k] ?? '', /Testmail/, `${k}`);
		}
		assert.match(katalog['onboarding.checkliste.telegram'] ?? '', /Telegram/);
	});
	test('AC-15: SMS-Hinweis nennt SMS (nicht Premium-SMS), Premium-SMS-Hinweis nennt Premium-SMS', () => {
		const sms = katalog['onboarding.hinweis.sms'] ?? '';
		const prem = katalog['onboarding.hinweis.premium_sms'] ?? '';
		assert.match(sms, /SMS/);
		assert.doesNotMatch(sms, /Premium/);
		assert.match(prem, /Premium-SMS/);
	});
	test('nur die SMS-Hinweise erwaehnen SMS (sonst erschiene SMS auch beim Tarif ohne SMS)', () => {
		const fremd = onboardingKeys.filter((k) => !k.startsWith('onboarding.hinweis.') && /SMS/.test(katalog[k]));
		assert.deepEqual(fremd, []);
	});
});
