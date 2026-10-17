// Issue #2521 S2 — wann Willkommen und Startklar-Checkliste erscheinen.
// Reine Logik (node:test-bar), keine Svelte-Abhaengigkeit. Quelle ist nur das
// Profil (GET /api/auth/profile); der Client schreibt ausser den zwei
// Dismiss-Flags nichts davon.

export interface OnboardingProfil {
	pending: boolean;
	dismissed: boolean;
	checklistDismissed: boolean;
	testMailSentAt: string | null;
	firstBriefingAt: string | null;
	emailVerified: boolean;
	telegramVerknuepft: boolean;
	smsAllowed: boolean;
	premiumSmsAllowed: boolean;
}
export interface Bestand {
	tripCount: number;
	compareCount: number;
}
export type PunktId = 'email' | 'trip-oder-vergleich' | 'erstes-briefing' | 'testmail' | 'telegram';
export interface ChecklistenPunkt {
	id: PunktId;
	pflicht: boolean;
	erledigt: boolean;
}

const istTrue = (v: unknown): boolean => v === true;
const text = (v: unknown): string | null => (typeof v === 'string' && v !== '' ? v : null);

/** Profil-JSON (snake_case, Go) -> OnboardingProfil. Fehlend/kaputt = fail-closed. */
export function onboardingAusProfil(profil: Record<string, unknown> | null): OnboardingProfil {
	const p = profil ?? {};
	return {
		pending: istTrue(p.onboarding_pending),
		dismissed: istTrue(p.onboarding_dismissed),
		checklistDismissed: istTrue(p.checklist_dismissed),
		testMailSentAt: text(p.test_mail_sent_at),
		firstBriefingAt: text(p.first_briefing_at),
		emailVerified: istTrue(p.email_verified),
		telegramVerknuepft: text(p.telegram_chat_id) !== null,
		smsAllowed: istTrue(p.sms_allowed),
		premiumSmsAllowed: istTrue(p.premium_sms_allowed)
	};
}

const hatBestand = (b: Bestand) => b.tripCount + b.compareCount > 0;

export function checklistePunkte(p: OnboardingProfil, b: Bestand): ChecklistenPunkt[] {
	return [
		{ id: 'email', pflicht: true, erledigt: p.emailVerified },
		{ id: 'trip-oder-vergleich', pflicht: true, erledigt: hatBestand(b) },
		{ id: 'erstes-briefing', pflicht: true, erledigt: p.firstBriefingAt !== null },
		{ id: 'testmail', pflicht: false, erledigt: p.testMailSentAt !== null },
		{ id: 'telegram', pflicht: false, erledigt: p.telegramVerknuepft }
	];
}

export function zeigeWillkommen(p: OnboardingProfil, b: Bestand): boolean {
	return p.pending && !p.dismissed && !hatBestand(b);
}

export function zeigeCheckliste(p: OnboardingProfil, b: Bestand): boolean {
	return p.pending && !p.checklistDismissed && checklistePunkte(p, b).some((x) => x.pflicht && !x.erledigt);
}

export function tarifHinweise(p: OnboardingProfil): Array<'sms' | 'premium-sms'> {
	const aus: Array<'sms' | 'premium-sms'> = [];
	if (p.smsAllowed) aus.push('sms');
	if (p.premiumSmsAllowed) aus.push('premium-sms');
	return aus;
}
