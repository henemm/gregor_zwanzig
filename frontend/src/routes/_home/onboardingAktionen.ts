// Issue #2521 S2 — Klick-Logik der Startseite (Verstanden, Ausblenden,
// Testmail) als testbares Modul, aus +page.svelte herausgezogen; Verhalten
// unveraendert. Die Seite haelt nur den Svelte-Zustand und reicht ihn ueber
// Callbacks herein.

import type { OnboardingProfil } from './onboardingSichtbarkeit.js';
import { ZEITLIMIT_TEST_NACHRICHT_MS, type AbrufOptionen } from '../../lib/api.ts';

export type DismissFeld = 'onboarding_dismissed' | 'checklist_dismissed';

/** Body des PUT /api/auth/profile fuer "Verstanden" bzw. "Ausblenden": NUR dieses Flag. */
export function dismissPayload(feld: DismissFeld): Record<string, true> {
	return { [feld]: true };
}

/** Lokale Spiegelung des geklickten Flags (die Wahrheit liegt im Profil). */
export function dismissOverride(
	feld: DismissFeld,
	bisher: Partial<OnboardingProfil>
): Partial<OnboardingProfil> {
	return feld === 'onboarding_dismissed'
		? { ...bisher, dismissed: true }
		: { ...bisher, checklistDismissed: true };
}

export type TestmailAusgang = { ok: true } | { ok: false; fehler: string };

/**
 * Wertet die Antwort von POST /api/notify/test aus. Der Core meldet Fehler als
 * HTTP 200 mit {error}; nur status === "ok" gilt als gesendet.
 */
export function testmailAusgang(
	resp: { status?: string; error?: string } | null | undefined,
	fallbackFehler: string
): TestmailAusgang {
	if (resp?.status === 'ok') return { ok: true };
	return { ok: false, fehler: resp?.error ?? fallbackFehler };
}

/** Fehlertext einer geworfenen API-Ausnahme. */
export function testmailAusnahmeFehler(e: unknown, fallbackFehler: string): string {
	const body = e as { detail?: string; error?: string } | null;
	return body?.detail ?? body?.error ?? fallbackFehler;
}

export type TestmailStatus = 'idle' | 'loading' | 'error';

export interface OnboardingApi {
	put(pfad: string, body: unknown): Promise<unknown>;
	post(pfad: string, body: unknown, extra?: AbrufOptionen): Promise<unknown>;
}

export interface OnboardingAktionenDeps {
	api: OnboardingApi;
	/** Uebersetzung (Katalog). */
	t: (key: 'onboarding.testmail.fehler') => string;
	getLokal: () => Partial<OnboardingProfil>;
	setLokal: (neu: Partial<OnboardingProfil>) => void;
	setTestmail: (status: TestmailStatus, fehler: string | null) => void;
	jetzt?: () => string;
}

export function erzeugeOnboardingAktionen(d: OnboardingAktionenDeps) {
	async function flag(feld: DismissFeld): Promise<void> {
		try {
			await d.api.put('/api/auth/profile', dismissPayload(feld));
			d.setLokal(dismissOverride(feld, d.getLokal()));
		} catch {
			// Fail-soft: Hinweis bleibt stehen, naechster Klick versucht es erneut.
		}
	}

	async function sendeTestmail(): Promise<void> {
		d.setTestmail('loading', null);
		const fallback = d.t('onboarding.testmail.fehler');
		try {
			// #2361: eigenes Budget 130 s (Go-Proxy 120 s) statt des Standard-Limits.
			const resp = (await d.api.post(
				'/api/notify/test',
				{ channel: 'email' },
				{ zeitlimitMs: ZEITLIMIT_TEST_NACHRICHT_MS }
			)) as {
				status?: string;
				error?: string;
			} | null;
			const ausgang = testmailAusgang(resp, fallback);
			if (ausgang.ok) {
				d.setLokal({
					...d.getLokal(),
					testMailSentAt: (d.jetzt ?? (() => new Date().toISOString()))()
				});
				d.setTestmail('idle', null);
			} else {
				d.setTestmail('error', ausgang.fehler);
			}
		} catch (e: unknown) {
			d.setTestmail('error', testmailAusnahmeFehler(e, fallback));
		}
	}

	return {
		verstanden: () => void flag('onboarding_dismissed'),
		ausblenden: () => void flag('checklist_dismissed'),
		sendeTestmail
	};
}
