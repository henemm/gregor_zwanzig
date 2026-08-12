// premiumSmsAlarmGate — Issue #1745 Scheibe A (AC-5, AC-6, AC-13),
// Spec docs/specs/modules/fix_1745_a_alarm_kanal_premium_sms_ui.md.
//
// Sperrzustand der Premium-SMS-Zeile im ALARME-Reiter. Bewusst NICHT
// `premiumSmsChannelState()` (shared/versand-tab/): der dortige Helfer
// verrechnet zusaetzlich die Frische der gelernten Rueckadresse
// (`premium_sms_reply_state`) zu `disabled`. Fuer den Versand-Reiter ist das
// richtig; im Alarmpfad stellt das Backend diese Frage bewusst NICHT
// (trip_alert.py:847-855, notification_service.py:1499) — volle
// Wiederverwendung wuerde also einen Haken sperren, den das Backend
// anstandslos bedient (D2).
//
// Einziger Eingang ist deshalb `premium_sms_allowed` (Tarif-Gate,
// model.PremiumSmsAllowed / user_tier.py:33). Die Funktion nimmt genau EIN
// Argument entgegen — ein zweiter Parameter waere die in der Spec benannte
// Mutation.
//
// Pure Funktion, kein Netz-/DOM-Zugriff — node:testbar.

export interface PremiumSmsAlarmGate {
	/** Schalter gesperrt (sichtbar bleibt die Zeile immer, D3). */
	disabled: boolean;
	/** Begruendung der Sperre; `null`, wenn die Zeile bedienbar ist. */
	hint: string | null;
}

/** AC-5: Tarif `standard` — die Zeile ist sichtbar, aber gesperrt. */
export const PREMIUM_SMS_ALARM_HINT_NO_TIER = 'Premium-SMS ab Level Premium verfügbar';

/** AC-13: Die Tarif-Auskunft liegt (noch) nicht vor — Server-Rendering, erster
 * Frame oder fehlgeschlagene Abfrage. Fail-closed, aber mit ehrlichem Grund:
 * dem Nutzer zu sagen, ihm fehle der Tarif, waere eine Falschaussage ueber
 * sein eigenes Konto. */
export const PREMIUM_SMS_ALARM_HINT_UNKNOWN =
	'Tarif wird geprüft — der Kanal lässt sich einen Moment lang nicht umschalten.';

export function derivePremiumSmsAlarmGate(
	profile: { premium_sms_allowed?: boolean } | null | undefined
): PremiumSmsAlarmGate {
	if (profile == null || typeof profile.premium_sms_allowed !== 'boolean') {
		return { disabled: true, hint: PREMIUM_SMS_ALARM_HINT_UNKNOWN };
	}
	if (profile.premium_sms_allowed === false) {
		return { disabled: true, hint: PREMIUM_SMS_ALARM_HINT_NO_TIER };
	}
	return { disabled: false, hint: null };
}
