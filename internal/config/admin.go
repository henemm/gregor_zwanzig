package config

import "strings"

// ParseAdminUserIDs liest die komma-getrennte Admin-Liste aus GZ_ADMIN_USER_IDS
// (Issue #2155 S1, ADR-0078). Eintraege werden getrimmt, leere verworfen; der
// Vergleich bleibt exakt (keine Umwandlung der Schreibweise). Leerer Wert =>
// leere Menge, niemand ist Admin (fail-closed).
func ParseAdminUserIDs(raw string) map[string]struct{} {
	admins := map[string]struct{}{}
	for _, id := range strings.Split(raw, ",") {
		if trimmed := strings.TrimSpace(id); trimmed != "" {
			admins[trimmed] = struct{}{}
		}
	}
	return admins
}
