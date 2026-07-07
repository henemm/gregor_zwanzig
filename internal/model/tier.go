package model

var smsAllowedTiers = map[string]bool{
	"standard": true,
	"premium":  true,
}

func SmsAllowed(tier string) bool {
	return smsAllowedTiers[tier]
}
