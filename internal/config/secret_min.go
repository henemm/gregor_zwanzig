package config

import "log"

// MinMachineSecretLength ist die Mindestlaenge fuer Maschinen-Geheimnisse
// (GZ_STATUS_TOKEN, selbst gewaehlte Webhook-Secrets), Issue #2961.
const MinMachineSecretLength = 32

// EffectiveMachineSecret liefert value, wenn es leer oder lang genug ist.
// Ein gesetzter, aber zu kurzer Wert wird mit einer Warnung verworfen: der
// betroffene Endpunkt bleibt dann geschlossen (fail-closed), der Start laeuft
// weiter.
func EffectiveMachineSecret(name, value string) string {
	if value != "" && len(value) < MinMachineSecretLength {
		log.Printf("WARN [config] %s ist kuerzer als %d Zeichen — der zugehoerige Endpunkt bleibt geschlossen",
			name, MinMachineSecretLength)
		return ""
	}
	return value
}
