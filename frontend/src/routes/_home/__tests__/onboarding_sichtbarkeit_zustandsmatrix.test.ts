// TDD RED — Onboarding S2: wann Willkommens-Hinweis und Startklar-Checkliste
// erscheinen (Spec docs/specs/modules/onboarding_willkommen_checkliste.md,
// AC-2, AC-3, AC-5, AC-14, AC-15).
//
// Vertrag an die Implementierung (reine Logik, keine Svelte-Abhaengigkeit):
//   Datei  frontend/src/routes/_home/onboardingSichtbarkeit.ts
//   export interface OnboardingProfil {
//     pending: boolean;            // Profil onboarding_pending
//     dismissed: boolean;          // Profil onboarding_dismissed  ("Verstanden")
//     checklistDismissed: boolean; // Profil checklist_dismissed   ("Ausblenden")
//     testMailSentAt: string | null;   // Profil test_mail_sent_at
//     firstBriefingAt: string | null;  // Profil first_briefing_at
//     emailVerified: boolean;          // Profil email_verified
//     telegramVerknuepft: boolean;     // Profil telegram_chat_id vorhanden
//     smsAllowed: boolean;             // Profil sms_allowed
//     premiumSmsAllowed: boolean;      // Profil premium_sms_allowed
//   }
//   export interface Bestand { tripCount: number; compareCount: number }
//   export type PunktId = 'email' | 'trip-oder-vergleich' | 'erstes-briefing' | 'testmail' | 'telegram';
//   export interface ChecklistenPunkt { id: PunktId; pflicht: boolean; erledigt: boolean }
//   export function onboardingAusProfil(profil: Record<string, unknown> | null): OnboardingProfil
//   export function zeigeWillkommen(p: OnboardingProfil, b: Bestand): boolean
//   export function zeigeCheckliste(p: OnboardingProfil, b: Bestand): boolean
//   export function checklistePunkte(p: OnboardingProfil, b: Bestand): ChecklistenPunkt[]
//   export function tarifHinweise(p: OnboardingProfil): Array<'sms' | 'premium-sms'>
//
// Pflichtpunkte: email · trip-oder-vergleich · erstes-briefing.
// Info-Punkte (nie Pflicht): testmail · telegram.
//
// Gegenproben, die hier rot werden MUESSEN (Spec AC-14):
//   * Testmail oder Telegram als Pflicht  -> "alle Pflicht erledigt, ohne Testmail/Telegram => weg"
//   * erstes Briefing nicht als Pflicht   -> "Briefing offen => sichtbar"
//   * nur Trips zaehlen                   -> "nur Ortsvergleich => Pflichtpunkt erfuellt"
//   * dismissed ignoriert                 -> AC-5
//   * pending ignoriert                   -> AC-2
//
// Ausfuehren:
//   cd frontend && npm test -- src/routes/_home/__tests__/onboarding_sichtbarkeit_zustandsmatrix.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

// Pfadregel #1409: Pruefling relativ zur Testdatei.
const HERE = path.dirname(fileURLToPath(import.meta.url));
const MODUL = path.resolve(HERE, '..', 'onboardingSichtbarkeit.ts');

// Dynamisch: ein fehlendes Modul darf nicht die ganze Datei beim Linken abbrechen.
const mod: Record<string, unknown> = await import(pathToFileURL(MODUL).href).catch(() => ({}));

type Profil = {
	pending: boolean;
	dismissed: boolean;
	checklistDismissed: boolean;
	testMailSentAt: string | null;
	firstBriefingAt: string | null;
	emailVerified: boolean;
	telegramVerknuepft: boolean;
	smsAllowed: boolean;
	premiumSmsAllowed: boolean;
};
type Bestand = { tripCount: number; compareCount: number };
type Punkt = { id: string; pflicht: boolean; erledigt: boolean };

function fn<T>(name: string): T {
	assert.equal(
		typeof mod[name],
		'function',
		`frontend/src/routes/_home/onboardingSichtbarkeit.ts exportiert keine Funktion ${name}`
	);
	return mod[name] as T;
}

const zeigeWillkommen = (p: Profil, b: Bestand) => fn<(p: Profil, b: Bestand) => boolean>('zeigeWillkommen')(p, b);
const zeigeCheckliste = (p: Profil, b: Bestand) => fn<(p: Profil, b: Bestand) => boolean>('zeigeCheckliste')(p, b);
const punkte = (p: Profil, b: Bestand) => fn<(p: Profil, b: Bestand) => Punkt[]>('checklistePunkte')(p, b);
const hinweise = (p: Profil) => fn<(p: Profil) => string[]>('tarifHinweise')(p);
const ausProfil = (j: Record<string, unknown> | null) =>
	fn<(j: Record<string, unknown> | null) => Profil>('onboardingAusProfil')(j);

/** Frisch angelegter Nutzer: Merkmal gesetzt, nichts erledigt. */
function neu(over: Partial<Profil> = {}): Profil {
	return {
		pending: true,
		dismissed: false,
		checklistDismissed: false,
		testMailSentAt: null,
		firstBriefingAt: null,
		emailVerified: false,
		telegramVerknuepft: false,
		smsAllowed: false,
		premiumSmsAllowed: false,
		...over
	};
}
const LEER: Bestand = { tripCount: 0, compareCount: 0 };
const EIN_TRIP: Bestand = { tripCount: 1, compareCount: 0 };
const EIN_VERGLEICH: Bestand = { tripCount: 0, compareCount: 1 };
const ALLES_PFLICHT = { emailVerified: true, firstBriefingAt: '2026-10-16T05:00:00Z' };

describe('AC-2: Altkonto ohne Merkmal sieht nichts, neues Konto sieht beides', () => {
	test('neues Konto ohne Trips/Vergleiche: Willkommen UND Checkliste sichtbar', () => {
		assert.equal(zeigeWillkommen(neu(), LEER), true);
		assert.equal(zeigeCheckliste(neu(), LEER), true);
	});
	test('Altkonto (pending=false) mit offenen Pflichtpunkten: weder Willkommen noch Checkliste', () => {
		const alt = neu({ pending: false });
		assert.equal(zeigeWillkommen(alt, LEER), false);
		assert.equal(zeigeCheckliste(alt, LEER), false);
		assert.equal(zeigeCheckliste(alt, EIN_TRIP), false);
	});
	test('Profil ohne onboarding_pending (Altdatei) liest als false => nichts sichtbar', () => {
		const p = ausProfil({ email_verified: false, sms_allowed: false });
		assert.equal(p.pending, false);
		assert.equal(zeigeWillkommen(p, LEER), false);
		assert.equal(zeigeCheckliste(p, LEER), false);
	});
	test('kein Profil (Abruf gescheitert) => fail-closed, nichts sichtbar', () => {
		const p = ausProfil(null);
		assert.equal(p.pending, false);
		assert.equal(zeigeWillkommen(p, LEER), false);
		assert.equal(zeigeCheckliste(p, LEER), false);
	});
});

describe('onboardingAusProfil: Profilfelder (snake_case, Go) -> OnboardingProfil', () => {
	test('alle Felder werden uebernommen', () => {
		const p = ausProfil({
			onboarding_pending: true,
			onboarding_dismissed: true,
			checklist_dismissed: true,
			test_mail_sent_at: '2026-10-16T10:00:00Z',
			first_briefing_at: '2026-10-17T05:00:00Z',
			email_verified: true,
			telegram_chat_id: '12345',
			sms_allowed: true,
			premium_sms_allowed: true
		});
		assert.deepEqual(p, {
			pending: true,
			dismissed: true,
			checklistDismissed: true,
			testMailSentAt: '2026-10-16T10:00:00Z',
			firstBriefingAt: '2026-10-17T05:00:00Z',
			emailVerified: true,
			telegramVerknuepft: true,
			smsAllowed: true,
			premiumSmsAllowed: true
		});
	});
	test('fehlende Felder => false/null; leerer telegram_chat_id => nicht verknuepft', () => {
		const p = ausProfil({ onboarding_pending: true, telegram_chat_id: '' });
		assert.equal(p.pending, true);
		assert.equal(p.dismissed, false);
		assert.equal(p.checklistDismissed, false);
		assert.equal(p.testMailSentAt, null);
		assert.equal(p.firstBriefingAt, null);
		assert.equal(p.emailVerified, false);
		assert.equal(p.telegramVerknuepft, false);
		assert.equal(p.smsAllowed, false);
		assert.equal(p.premiumSmsAllowed, false);
	});
	test('nur echtes true zaehlt (kein Truthy-String als Merkmal)', () => {
		const p = ausProfil({ onboarding_pending: 'true', email_verified: 1 });
		assert.equal(p.pending, false);
		assert.equal(p.emailVerified, false);
	});
});

describe('AC-3: Willkommen nur ohne Trips und ohne Ortsvergleiche', () => {
	test('mit einem Trip: kein Willkommen', () => {
		assert.equal(zeigeWillkommen(neu(), EIN_TRIP), false);
	});
	test('mit einem Ortsvergleich (ohne Trip): kein Willkommen', () => {
		assert.equal(zeigeWillkommen(neu(), EIN_VERGLEICH), false);
	});
	test('"Verstanden" (dismissed) blendet Willkommen aus, Checkliste bleibt', () => {
		assert.equal(zeigeWillkommen(neu({ dismissed: true }), LEER), false);
		assert.equal(zeigeCheckliste(neu({ dismissed: true }), LEER), true);
	});
});

describe('AC-5: "Ausblenden" schlaegt offene Pflichtpunkte', () => {
	test('checklistDismissed bei allen Pflichtpunkten offen => Checkliste weg', () => {
		assert.equal(zeigeCheckliste(neu({ checklistDismissed: true }), LEER), false);
	});
	test('checklistDismissed laesst den Willkommens-Hinweis unberuehrt', () => {
		assert.equal(zeigeWillkommen(neu({ checklistDismissed: true }), LEER), true);
	});
});

describe('AC-14: Zustandsmatrix der Pflichtpunkte', () => {
	test('alle drei Pflichtpunkte erledigt (ohne Testmail, ohne Telegram) => Checkliste weg', () => {
		const p = neu({ ...ALLES_PFLICHT, testMailSentAt: null, telegramVerknuepft: false });
		assert.equal(zeigeCheckliste(p, EIN_TRIP), false);
	});
	test('Pflicht ueber Ortsvergleich (ohne Trip) erfuellt => Checkliste weg', () => {
		assert.equal(zeigeCheckliste(neu(ALLES_PFLICHT), EIN_VERGLEICH), false);
	});
	test('E-Mail und Trip erledigt, erstes Briefing offen => Checkliste sichtbar', () => {
		assert.equal(zeigeCheckliste(neu({ emailVerified: true }), EIN_TRIP), true);
	});
	test('Trip und Briefing erledigt, E-Mail unbestaetigt => Checkliste sichtbar', () => {
		assert.equal(zeigeCheckliste(neu({ firstBriefingAt: '2026-10-16T05:00:00Z' }), EIN_TRIP), true);
	});
	test('E-Mail und Briefing erledigt, weder Trip noch Ortsvergleich => Checkliste sichtbar', () => {
		assert.equal(zeigeCheckliste(neu(ALLES_PFLICHT), LEER), true);
	});
	test('Testmail gesendet und Telegram verknuepft ersetzen keinen Pflichtpunkt', () => {
		const p = neu({ testMailSentAt: '2026-10-16T10:00:00Z', telegramVerknuepft: true });
		assert.equal(zeigeCheckliste(p, LEER), true);
		assert.equal(zeigeCheckliste({ ...p, emailVerified: true }, EIN_TRIP), true);
	});

	test('checklistePunkte: genau drei Pflichtpunkte, Testmail und Telegram nie Pflicht', () => {
		const liste = punkte(neu(), LEER);
		const pflicht = liste.filter((x) => x.pflicht).map((x) => x.id).sort();
		assert.deepEqual(pflicht, ['email', 'erstes-briefing', 'trip-oder-vergleich']);
		const info = liste.filter((x) => !x.pflicht).map((x) => x.id).sort();
		assert.deepEqual(info, ['telegram', 'testmail']);
	});
	test('checklistePunkte: erledigt-Stand folgt Profil und Bestand', () => {
		const p = neu({
			emailVerified: true,
			testMailSentAt: '2026-10-16T10:00:00Z',
			telegramVerknuepft: false,
			firstBriefingAt: null
		});
		const stand = Object.fromEntries(punkte(p, EIN_VERGLEICH).map((x) => [x.id, x.erledigt]));
		assert.deepEqual(stand, {
			email: true,
			'trip-oder-vergleich': true,
			'erstes-briefing': false,
			testmail: true,
			telegram: false
		});
	});
	test('Checkliste sichtbar <=> pending && !checklistDismissed && ein Pflichtpunkt offen (alle 2^5 Kombinationen)', () => {
		for (let m = 0; m < 32; m++) {
			const email = !!(m & 1);
			const bestand = m & 2 ? EIN_TRIP : LEER;
			const briefing = !!(m & 4);
			const testmail = !!(m & 8);
			const telegram = !!(m & 16);
			const p = neu({
				emailVerified: email,
				firstBriefingAt: briefing ? '2026-10-16T05:00:00Z' : null,
				testMailSentAt: testmail ? '2026-10-16T10:00:00Z' : null,
				telegramVerknuepft: telegram
			});
			const soll = !(email && bestand.tripCount > 0 && briefing);
			assert.equal(zeigeCheckliste(p, bestand), soll, `Kombination ${m.toString(2).padStart(5, '0')}`);
		}
	});
});

describe('AC-15: SMS-/Premium-SMS-Hinweis nur beim passenden Tarif', () => {
	test('Tarif ohne SMS: kein Hinweis', () => {
		assert.deepEqual(hinweise(neu()), []);
	});
	test('sms_allowed: nur SMS-Hinweis', () => {
		assert.deepEqual(hinweise(neu({ smsAllowed: true })), ['sms']);
	});
	test('premium_sms_allowed: nur Premium-SMS-Hinweis', () => {
		assert.deepEqual(hinweise(neu({ premiumSmsAllowed: true })), ['premium-sms']);
	});
	test('beides: beide Hinweise, SMS zuerst', () => {
		assert.deepEqual(hinweise(neu({ smsAllowed: true, premiumSmsAllowed: true })), ['sms', 'premium-sms']);
	});
	test('Tarif-Hinweise sind keine Checklistenpunkte (blockieren nie)', () => {
		const p = neu({ ...ALLES_PFLICHT, smsAllowed: true, premiumSmsAllowed: true });
		assert.ok(!punkte(p, EIN_TRIP).some((x) => x.id === 'sms' || x.id === 'premium-sms'));
		assert.equal(zeigeCheckliste(p, EIN_TRIP), false);
	});
});
