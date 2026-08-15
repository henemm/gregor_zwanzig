package model

// Premium-SMS (Garmin inReach) — Issue #1717 Scheibe S3.
//
// Die gelernte Rueckadresse (S1, User.PremiumSmsReplyTo/-At) verfaellt. Der
// Sendepfad prueft das seit S2a in Python
// (src/output/channels/premium_sms.py). Damit `GET /api/auth/profile` der
// Oberflaeche denselben Zustand FERTIG ABGELEITET liefern kann — und die
// Oberflaeche keine eigene Frist braucht — steht hier das Go-Pendant.
//
// Zwei Prozesse, zwei Konstanten: Go-API (Port 8090) und Python-Kern teilen
// keinen Code. Die Deckungsgleichheit der Zahl bewacht deshalb
// tests/test_premium_sms_ttl_drift.py (AC-11) — laeuft eine der beiden
// auseinander, zeigt die Oberflaeche "frisch", wo der Sendepfad schon blockt.

import "time"

// PremiumSmsReplyTTL = Verfallsfrist der gelernten Rueckadresse.
//
// GO-PENDANT zu PREMIUM_SMS_REPLY_TTL in src/output/channels/premium_sms.py
// (dort: timedelta(days=30), Spec D6, PO-Entscheid 2026-08-10). BEIDE Werte
// gemeinsam aendern — der Drift-Waechter tests/test_premium_sms_ttl_drift.py
// nennt bei einer Abweichung beide Fundstellen.
const PremiumSmsReplyTTL = 30 * 24 * time.Hour

// Zustandswerte der gelernten Rueckadresse. Wire-Vertrag mit dem Frontend
// (`premium_sms_reply_state`, ausgewertet in
// frontend/src/lib/components/shared/versand-tab/premiumSmsChannelState.ts) —
// wer sie umbenennt, bricht die Anzeige, ohne dass ein Renderer rot wird.
const (
	// PremiumSmsStateNone: das Geraet hat sich noch nie gemeldet.
	PremiumSmsStateNone = "none"
	// PremiumSmsStateStale: gemeldet, aber laut Frist verfallen.
	PremiumSmsStateStale = "stale"
	// PremiumSmsStateFresh: gemeldet und innerhalb der Frist.
	PremiumSmsStateFresh = "fresh"
)

// DerivePremiumSmsReplyState bewertet die gelernte Rueckadresse.
//
// Bedingung 1 ist die des Sendepfads (`not reply_to or reply_at is None`,
// premium_sms.py): fehlt eines von beiden, ist das "noch nie gemeldet" — nicht
// "veraltet". Als "stale" gemeldet wuerde die Oberflaeche ein Verfallsdatum
// behaupten, das es nie gab.
//
// Bedingung 2 ist die Frist, Semantik wie im Sendepfad: `age > TTL` ist
// veraltet, genau auf der Frist ist noch frisch.
//
// Das Alter wird auf ganze Sekunden abgeschnitten. Der Meldezeitpunkt kommt als
// RFC3339-Zeitstempel; Bruchteile einer Sekunde sind darin Rauschen und duerfen
// den Zustand nicht kippen. Ohne das Abschneiden entscheidet die Laufzeit
// zwischen Lesen des Zeitstempels und Vergleich darueber, ob eine genau auf der
// Frist stehende Adresse noch gilt.
func DerivePremiumSmsReplyState(replyTo string, replyAt *time.Time) string {
	if replyTo == "" || replyAt == nil {
		return PremiumSmsStateNone
	}
	age := time.Since(*replyAt).Truncate(time.Second)
	if age > PremiumSmsReplyTTL {
		return PremiumSmsStateStale
	}
	return PremiumSmsStateFresh
}
