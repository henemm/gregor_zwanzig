// sendTargetLabel — Issue #1471.
// Leitet aus Konto-Profil + den im Vergleich aktivierten Kanaelen das TATSAECHLICHE
// Versandziel ab. Ersetzt die Zaehlung `preset.empfaenger.length`, die seit #1452
// strukturell inert (dauerhaft 0) und damit immer falsch ist.
//
// Spec: docs/specs/modules/fix_1471_sende_dialog_ziel.md (AC-1..AC-4, AC-6)
// Pure Funktion, kein Netz-/DOM-Zugriff — node:testbar, analog channelConnectionStatus.
//
// Die Kanal-Zustaende kommen aus `channelConnectionStatus()` und werden hier NICHT
// neu abgeleitet: nur so kann der Dialog dem Versand-Reiter nicht widersprechen (AC-6).

import { channelConnectionStatus } from './channelConnectionStatus';
import type { ConnectionProfile } from './channelConnectionStatus.js';

/** Die im Vergleich aktivierten Zusatzkanaele (Ausschnitt aus ComparePreset). */
export interface SendTargetChannels {
	send_telegram?: boolean;
	send_sms?: boolean;
}

export interface SendTargetInfo {
	/** Menschenlesbarer Ziel-Text fuer den Bestaetigungsdialog. */
	text: string;
	/** false ⇒ es wuerde nachweislich nichts zugestellt; Versand sperren. */
	deliverable: boolean;
	/**
	 * Direkt an `disabled` bindbar (= `!deliverable`).
	 *
	 * Existiert, damit im Template ein NACKTER Feldzugriff steht. Stuende dort
	 * `disabled={!ziel.deliverable}`, waere jede Verdrehung (`!!`, weglassen,
	 * `&& false`) nur ueber die Ausdrucks-FORM erkennbar — und Formpruefungen sind
	 * bodenlos: zu jeder erkannten Form gibt es eine naechste. Mit diesem Feld
	 * braucht jede Verdrehung im Template zwingend einen Operator und faellt auf,
	 * ohne dass der Test die Verdreh-Form vorher kennen muss.
	 */
	gesperrt: boolean;
}

/** Einzige Stelle, an der `gesperrt` entsteht — kein Drift zwischen den Zweigen. */
const ergebnis = (text: string, deliverable: boolean): SendTargetInfo => ({
	text,
	deliverable,
	gesperrt: !deliverable
});

/**
 * Ziel-Text + Zustellbarkeit fuer den Sofort-Versand.
 *
 * E-Mail ist immer Teil des Versands (scheduler_dispatch_service.py:335-341);
 * Telegram/SMS nur, wenn im Vergleich aktiviert UND im Konto verbunden — ein im
 * Konto fehlender Kanal darf nicht genannt werden, sonst entstuende die Falschaussage
 * aus #1471 in neuer Form.
 *
 * `preset` darf null/undefined sein (der Dialog-State ist `ComparePreset | null`);
 * das wird wie "keine Zusatzkanaele" behandelt.
 */
export function sendTargetLabel(
	profile: ConnectionProfile | null | undefined,
	preset: SendTargetChannels | null | undefined
): SendTargetInfo {
	const p = profile ?? {};
	const selected = preset ?? {};
	const status = channelConnectionStatus(p);

	// Keine Adresse hinterlegt → der Server wirft "kein Empfaenger — mail_to fehlt"
	// (scheduler_dispatch_service.py:336-340).
	if (!p.mail_to) {
		return ergebnis(
			'Im Konto ist keine E-Mail-Adresse hinterlegt — es kann nichts gesendet werden.',
			false
		);
	}

	// Adresse da, aber unbestaetigt → der Empfaengerschutz blockt die Zustellung
	// (email.py:239-285). Ein Knopf, der nichts bewirkt, waere #1471 mit umgekehrtem
	// Vorzeichen — deshalb gesperrt, mit sichtbar anderer Begruendung als oben.
	if (status.email.tone !== 'good') {
		return ergebnis(`Die Adresse ${p.mail_to} ist nicht bestätigt — es wird nichts zugestellt.`, false);
	}

	const ziele = [`E-Mail (${p.mail_to})`];
	if (selected.send_telegram === true && status.telegram.tone === 'good') ziele.push('Telegram');
	if (selected.send_sms === true && status.sms.tone === 'good') ziele.push('SMS');

	// " · " als Trenner — Konvention aus channelNamesLabel() (subscriptionHelpers.ts).
	return ergebnis(`Geht an ${ziele.join(' · ')}.`, true);
}
