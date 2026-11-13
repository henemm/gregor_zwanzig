package config

import "log"

// MinMachineSecretLength ist die empfohlene Mindestlaenge fuer
// Maschinen-Geheimnisse (GZ_STATUS_TOKEN, selbst gewaehlte Webhook-Secrets),
// Issue #2961.
const MinMachineSecretLength = 32

// EffectiveMachineSecret liefert value unveraendert. Ist ein Wert gesetzt,
// aber kuerzer als MinMachineSecretLength, wird beim Start eine Warnzeile
// geschrieben — der Endpunkt bleibt mit dem konfigurierten Wert in Betrieb,
// damit ein Deploy keinen Eingangskanal still schliesst. Fail-closed bleibt
// allein der Fall „kein Geheimnis gesetzt" (Sache der jeweiligen Route).
func EffectiveMachineSecret(name, value string) string {
	if value != "" && len(value) < MinMachineSecretLength {
		log.Printf("WARN [config] %s ist kuerzer als %d Zeichen — bitte verlaengern (Endpunkt bleibt in Betrieb)",
			name, MinMachineSecretLength)
	}
	return value
}
