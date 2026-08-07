package model

var smsAllowedTiers = map[string]bool{
	"standard": true,
	"premium":  true,
}

func SmsAllowed(tier string) bool {
	return smsAllowedTiers[tier]
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
