package scheduler

import (
	"encoding/json"
	"strings"
	"testing"
	"time"
)

// TDD RED: Issue #2218 (Scheibe B, C5-32) — failed_units je Pfad.
//
// Spec: docs/specs/modules/fix_2218_alarm_ausfaelle.md (AC-5, AC-6, AC-8, AC-10).
// Echte JSONL-Datei in t.TempDir() (Helfer aus enrichment_health_test.go).

// unitLine renders a journal line as log_enrichment_call(..., unit=...) writes it.
func unitLine(ts time.Time, path, outcome, unit string) string {
	return `{"ts":"` + ts.Format(time.RFC3339) + `","path":"` + path +
		`","outcome":"` + outcome + `","detail":null,"unit":"` + unit + `"}`
}

// failedUnits reads enrichment_health[path].failed_units as []string; a missing
// or null list fails the test (AC-10: empty list, never null).
func failedUnits(t *testing.T, health map[string]any, path string) []string {
	t.Helper()
	entry := enrichmentEntry(t, health, path)
	raw, present := entry["failed_units"]
	if !present || raw == nil {
		t.Fatalf("failed_units fehlt oder ist null fuer %q: %#v", path, entry)
	}
	switch v := raw.(type) {
	case []string:
		return v
	case []any:
		out := make([]string, 0, len(v))
		for _, x := range v {
			out = append(out, x.(string))
		}
		return out
	}
	t.Fatalf("failed_units hat den falschen Typ: %#v", raw)
	return nil
}

// AC-5: ok NACH unavailable loest die Einheit ab; unavailable NACH ok setzt sie.
func TestEnrichmentHealthFailedUnitsOkLoestAusfallAb(t *testing.T) {
	tmpDir := t.TempDir()
	base := time.Now().UTC().Add(-3 * time.Hour)
	writeEnrichmentJournal(t, tmpDir,
		unitLine(base, "alert_fetch", "unavailable", "u1/trip-a"),
		unitLine(base.Add(10*time.Minute), "alert_fetch", "ok", "u1/trip-a"),
		unitLine(base, "alert_fetch", "ok", "u1/trip-b"),
		unitLine(base.Add(10*time.Minute), "alert_fetch", "unavailable", "u1/trip-b"),
	)
	got := failedUnits(t, newEnrichmentHealthTestScheduler(t, tmpDir).EnrichmentHealth(), "alert_fetch")
	if len(got) != 1 || got[0] != "u1/trip-b" {
		t.Fatalf("failed_units = %v, erwartet [u1/trip-b]", got)
	}
}

// AC-6: Altzeilen ohne unit bleiben fuer die Pfad-Ebene wirksam, fuellen aber
// failed_units nicht; alle Pfad-Felder sind unveraendert.
func TestEnrichmentHealthFailedUnitsAltzeilenOhneUnitBleibenUnveraendert(t *testing.T) {
	tmpDir := t.TempDir()
	t0 := time.Now().UTC().Add(-2 * time.Hour)
	writeEnrichmentJournal(t, tmpDir,
		enrichmentLine(t0, "thunder", "ok", ""),
		enrichmentLine(t0.Add(time.Minute), "thunder", "unavailable", ""),
		enrichmentLine(t0, "radar_nowcast", "fallback", "eu_direct"),
		unitLine(t0, "alert_fetch", "unavailable", "u1/trip-x"),
	)
	health := newEnrichmentHealthTestScheduler(t, tmpDir).EnrichmentHealth()

	thunder := enrichmentEntry(t, health, "thunder")
	if thunder["last_success_at"] != t0.Format(time.RFC3339) ||
		thunder["last_attempt_at"] != t0.Add(time.Minute).Format(time.RFC3339) {
		t.Fatalf("Pfad-Ebene thunder veraendert: %#v", thunder)
	}
	if u := failedUnits(t, health, "thunder"); len(u) != 0 {
		t.Fatalf("Altzeilen ohne unit duerfen failed_units nicht fuellen: %v", u)
	}
	radar := enrichmentEntry(t, health, "radar_nowcast")
	if radar["last_fallback_detail"] != "eu_direct" {
		t.Fatalf("Pfad-Ebene radar_nowcast veraendert: %#v", radar)
	}
}

// AC-8: gleiche Bezeichnung bei zwei Nutzern — ok von A loescht B nicht.
func TestEnrichmentHealthFailedUnitsOkEinesNutzersLoeschtDenAnderenNicht(t *testing.T) {
	tmpDir := t.TempDir()
	base := time.Now().UTC().Add(-time.Hour)
	writeEnrichmentJournal(t, tmpDir,
		unitLine(base, "alert_fetch", "unavailable", "userA/trip-1"),
		unitLine(base.Add(time.Minute), "alert_fetch", "unavailable", "userB/trip-1"),
		unitLine(base.Add(2*time.Minute), "alert_fetch", "ok", "userA/trip-1"),
	)
	got := failedUnits(t, newEnrichmentHealthTestScheduler(t, tmpDir).EnrichmentHealth(), "alert_fetch")
	if len(got) != 1 || got[0] != "userB/trip-1" {
		t.Fatalf("failed_units = %v, erwartet nur [userB/trip-1]", got)
	}
}

// AC-10: Deckel 20, neueste Ausfaelle zuerst; Pfad ohne Ausfall -> [] (nicht null).
func TestEnrichmentHealthFailedUnitsDeckelUndLeereListe(t *testing.T) {
	tmpDir := t.TempDir()
	base := time.Now().UTC().Add(-5 * time.Hour)
	lines := []string{}
	for i := 0; i < 25; i++ {
		lines = append(lines, unitLine(base.Add(time.Duration(i)*time.Minute),
			"alert_fetch", "unavailable", "u1/trip-"+string(rune('a'+i))))
	}
	lines = append(lines, unitLine(base, "snowgrid", "ok", "u1/leer"))
	writeEnrichmentJournal(t, tmpDir, lines...)
	health := newEnrichmentHealthTestScheduler(t, tmpDir).EnrichmentHealth()

	got := failedUnits(t, health, "alert_fetch")
	if len(got) != 20 {
		t.Fatalf("len(failed_units) = %d, erwartet 20 (Deckel)", len(got))
	}
	if got[0] != "u1/trip-"+string(rune('a'+24)) {
		t.Fatalf("neuester Ausfall muss zuerst stehen, ist %q", got[0])
	}
	if leer := failedUnits(t, health, "snowgrid"); len(leer) != 0 {
		t.Fatalf("Pfad ohne Ausfall: erwartet [], ist %v", leer)
	}
}

// F001 (#2218, AC-10): Das Health-Ergebnis, so wie die API es ausliefert
// (json.Marshal), traegt bei einem Pfad ohne scheiternde Einheit
// "failed_units":[] — nie null. Eine nil-Slice im Interface faengt der
// ==nil-Vergleich im Helfer failedUnits nicht; erst die Serialisierung zeigt es.
func TestEnrichmentHealthFailedUnitsSerialisiertAlsLeereListeNichtNull(t *testing.T) {
	tmpDir := t.TempDir()
	base := time.Now().UTC().Add(-2 * time.Hour)
	writeEnrichmentJournal(t, tmpDir,
		unitLine(base, "snowgrid", "ok", "u1/leer"),
		enrichmentLine(base, "thunder", "ok", ""),
	)
	health := newEnrichmentHealthTestScheduler(t, tmpDir).EnrichmentHealth()
	for _, path := range []string{"snowgrid", "thunder"} {
		b, err := json.Marshal(enrichmentEntry(t, health, path))
		if err != nil {
			t.Fatalf("json.Marshal %s: %v", path, err)
		}
		out := string(b)
		if strings.Contains(out, `"failed_units":null`) || !strings.Contains(out, `"failed_units":[]`) {
			t.Fatalf("%s: erwartet failed_units:[], ist %s", path, out)
		}
	}
}
