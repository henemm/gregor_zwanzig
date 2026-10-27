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

// Quota sind die Mengengrenzen je Tarif (Issue #2482, Epic #2138): wie viele
// aktive Trips, aktive Ortsvergleiche und Orte (gesamt) ein Nutzer neu anlegen
// darf. Admin- und Ausnahme-Konten werden VOR dieser Tabelle abgefangen
// (handler/quota.go) und sind unbegrenzt.
type Quota struct {
	Trips          int
	ComparePresets int
	Locations      int
}

// quotaTable ist die EINE Quelle der Wahrheit fuer die Grenzwerte
// (Spec docs/specs/modules/mengen_quoten_je_tier.md). Python spiegelt sie nicht.
var quotaTable = map[string]Quota{
	"free":     {Trips: 3, ComparePresets: 2, Locations: 10},
	"standard": {Trips: 15, ComparePresets: 10, Locations: 50},
	"premium":  {Trips: 50, ComparePresets: 30, Locations: 200},
}

// QuotaFor liefert die Grenzen zum Tarif. Leerer oder unbekannter Tarif ist
// fail-closed free — die Normalisierung geschieht hier selbst (EffectiveTier),
// damit kein Aufrufer sie vergessen kann.
func QuotaFor(tier string) Quota {
	return quotaTable[EffectiveTier(tier)]
}
