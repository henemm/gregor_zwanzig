package handler

// Issue #1159 — Config-Merge-Helfer: konsolidiert die seit #102 sechsfach
// wiederholte Blind-Replace-Fehlerklasse (BUG-DATALOSS-GR221: #102 -> #1082
// -> #1103 -> #1129 -> #1151 -> #1159) in einer einzigen, getesteten
// Implementierung. Spec: docs/specs/modules/config_merge_helper.md

// mergeConfigMap fuehrt Read-Modify-Write feldweise aus: Keys aus src
// ueberschreiben/ergaenzen dst, nicht mitgesendete Keys von dst bleiben
// erhalten. nil-sicher. Ersetzt die 5 inline-Loops in trip.go/weather_config.go.
func mergeConfigMap(dst, src map[string]interface{}) map[string]interface{} {
	if src == nil {
		return dst
	}
	if dst == nil {
		dst = map[string]interface{}{}
	}
	for k, v := range src {
		dst[k] = v
	}
	return dst
}
