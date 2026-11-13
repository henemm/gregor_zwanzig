package model

// NormalizePremiumSmsNumber liefert die Vergleichsform einer Premium-SMS-
// Rueckadresse (Issue #2961, ADR-0116): nur Ziffern, ein fuehrendes "+" bzw.
// "00" entfaellt, Leerzeichen, Bindestriche und Klammern ebenso. Verglichen
// wird ausschliesslich in dieser Form (Lernen, Eindeutigkeit, Schluessel der
// Absender-Bremse); gespeichert wird weiter die Form aus dem Journal, mit der
// das Gateway sendet. Python-Pendant:
// src/output/channels/recipient.py::normalize_premium_number; gemeinsame
// Tabelle tests/fixtures/premium_sms_nummern_normalform.json.
func NormalizePremiumSmsNumber(number string) string {
	digits := make([]byte, 0, len(number))
	for i := 0; i < len(number); i++ {
		if c := number[i]; c >= '0' && c <= '9' {
			digits = append(digits, c)
		}
	}
	out := string(digits)
	if len(out) >= 2 && out[:2] == "00" {
		out = out[2:]
	}
	return out
}
