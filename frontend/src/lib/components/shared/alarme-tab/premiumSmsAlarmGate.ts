// premiumSmsAlarmGate — Issue #1745 Scheibe A (AC-5, AC-6, AC-13),
// Spec docs/specs/modules/fix_1745_a_alarm_kanal_premium_sms_ui.md.
//
// Sperrzustand der Premium-SMS-Zeile im ALARME-Reiter. Bewusst NICHT
// `premiumSmsChannelState()` (shared/versand-tab/): der dortige Helfer
// verrechnet zusaetzlich die Frische der gelernten Rueckadresse
// (`premium_sms_reply_state`) zu `disabled`. Fuer den Versand-Reiter ist das
// richtig. Im Alarmpfad gilt (berichtigt #1895 S3b2): auch dort prueft der
// Versand die Rueckadresse (`_premium_sms_output()` →
// `PremiumSmsRecipient.for_user` → `check_reply_address`) und verwirft bei
// fehlender oder veralteter Adresse. Die Frische wird im Alarme-Reiter aber
// als Hinweis gezeigt (`kanaeleOhneEmpfaenger`, AlertMetricChannelsBlock),
// nicht als Sperre — die Auswahl bleibt bedienbar (D2).
//
// Einziger Eingang ist deshalb `premium_sms_allowed` (Tarif-Gate,
// model.PremiumSmsAllowed / user_tier.py:33). Die Funktion nimmt genau EIN
// Argument entgegen — ein zweiter Parameter waere die in der Spec benannte
// Mutation.
//
// Pure Funktion, kein Netz-/DOM-Zugriff — node:testbar. Der Hinweis folgt der
// aktuellen Sprache (tr); Aufrufer im Markup lesen dazu `$locale` (#2656).

export interface PremiumSmsAlarmGate {
	/** Schalter gesperrt (sichtbar bleibt die Zeile immer, D3). */
	disabled: boolean;
	/** Begruendung der Sperre; `null`, wenn die Zeile bedienbar ist. */
	hint: string | null;
}

import { tr, type MessageKey } from '../../../i18n/index.ts';

/** AC-5: Tarif `standard` — die Zeile ist sichtbar, aber gesperrt. Issue #2656 (F7):
 * Katalogschluessel, DERSELBE wie im Versand-Reiter (premiumSmsChannelState.ts). */
export const PREMIUM_SMS_ALARM_HINT_NO_TIER: MessageKey = 'versand.premium_sms.hinweis.nicht_verfuegbar';

/** AC-13: Die Tarif-Auskunft liegt (noch) nicht vor — Server-Rendering, erster
 * Frame oder fehlgeschlagene Abfrage. Fail-closed, aber mit ehrlichem Grund:
 * dem Nutzer zu sagen, ihm fehle der Tarif, waere eine Falschaussage ueber
 * sein eigenes Konto. */
export const PREMIUM_SMS_ALARM_HINT_UNKNOWN: MessageKey = 'alarme.premium_sms.tarif_wird_geprueft';

export function derivePremiumSmsAlarmGate(
	profile: { premium_sms_allowed?: boolean } | null | undefined
): PremiumSmsAlarmGate {
	if (profile == null || typeof profile.premium_sms_allowed !== 'boolean') {
		return { disabled: true, hint: tr(PREMIUM_SMS_ALARM_HINT_UNKNOWN) };
	}
	if (profile.premium_sms_allowed === false) {
		return { disabled: true, hint: tr(PREMIUM_SMS_ALARM_HINT_NO_TIER) };
	}
	return { disabled: false, hint: null };
}
