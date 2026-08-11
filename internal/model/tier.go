package model

var smsAllowedTiers = map[string]bool{
	"standard": true,
	"premium":  true,
}

func SmsAllowed(tier string) bool {
	return smsAllowedTiers[tier]
}

// PremiumSmsAllowed — Issue #1717 Scheibe S3, eigenstaendiges Tarif-Gate fuer
// Premium-SMS (Garmin inReach).
//
// BEWUSST KEINE Delegation an SmsAllowed: das laesst `standard` mit durch
// (smsAllowedTiers oben). Ein standard-Nutzer koennte den Kanal dann in der
// Oberflaeche einschalten, obwohl der Sendepfad ihn ohnehin sperrt (S2a AC-8) —
// eine Checkbox, die etwas verspricht, das serverseitig nie passiert.
// Python-Vorbild: premium_sms_allowed() (S2a).
//
// Erwartet einen bereits normalisierten Tier (EffectiveTier) — nur exakt
// "premium" ist erlaubt.
func PremiumSmsAllowed(tier string) bool {
	return tier == "premium"
}

// EffectiveTier normalisiert den gespeicherten Tier-Wert am Lesezeitpunkt auf
// free/standard/premium.
//
// Liegt hier (und nicht im handler-Paket), damit alle Leser dieselbe
// Normalisierung benutzen statt driftender Kopien: Profil-Response
// (toProfileResponse), Antragslogik (RequestTierChangeHandler) und die
// Auswertung offener Anträge (internal/scheduler/tier_request_health.go,
// Issue #1555).
func EffectiveTier(tier string) string {
	if tier != "free" && tier != "standard" && tier != "premium" {
		return "free"
	}
	return tier
}
