package store

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

// TDD RED — Issue #2436 AC-9: Freigabe loescht den kompletten Antrag samt
// Benachrichtigungs-Nachweis; alle uebrigen Felder (auch unbekannte) bleiben.
func TestSetUserTierAdmin_LoeschtAntragUndNachweis_BehaeltRest(t *testing.T) {
	s := New(t.TempDir(), "default")
	dir := filepath.Join(s.DataDir, "users", "u2436a")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	other := filepath.Join(s.DataDir, "users", "u2436b")
	_ = os.MkdirAll(other, 0o755)
	const doc = `{"id":"u2436a","tier":"free","display_name":"A","fremdfeld":{"x":[1,2]},"requested_tier":"premium","requested_at":"2026-10-01T10:00:00Z","requested_notified_at":"2026-10-01T10:00:05Z"}`
	const docB = `{"id":"u2436b","tier":"free","requested_tier":"standard","requested_at":"2026-10-01T10:00:00Z","requested_notified_at":"2026-10-01T10:00:05Z"}`
	_ = os.WriteFile(filepath.Join(dir, "user.json"), []byte(doc), 0o644)
	_ = os.WriteFile(filepath.Join(other, "user.json"), []byte(docB), 0o644)

	if err := s.SetUserTierAdmin("u2436a", "premium"); err != nil {
		t.Fatal(err)
	}
	read := func(p string) map[string]any {
		b, _ := os.ReadFile(filepath.Join(p, "user.json"))
		var m map[string]any
		_ = json.Unmarshal(b, &m)
		return m
	}
	m := read(dir)
	for _, k := range []string{"requested_tier", "requested_at", "requested_notified_at"} {
		if _, ok := m[k]; ok {
			t.Errorf("%s muss geloescht sein", k)
		}
	}
	if m["tier"] != "premium" || m["display_name"] != "A" || m["id"] != "u2436a" || m["fremdfeld"] == nil {
		t.Errorf("uebrige Felder muessen erhalten bleiben: %v", m)
	}
	if mb := read(other); mb["requested_notified_at"] == nil || mb["requested_tier"] != "standard" {
		t.Errorf("anderer Nutzer darf nicht beruehrt werden: %v", mb)
	}
}
