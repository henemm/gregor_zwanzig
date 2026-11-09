package scheduler

// Issue #2883: Rotation der Diagnose-Journale openmeteo_calls.jsonl und
// enrichment_calls.jsonl. Python rotiert ab 8 MiB nach <datei>.1; die
// Go-Leser muessen aktuelle Datei UND .1 auswerten, ohne doppelt zu zaehlen.
//
// KEINE Mocks: echte Dateien in t.TempDir(), echte BriefingHealth() /
// EnrichmentHealth() bzw. die echten Aggregationsfunktionen.

import (
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"testing"
	"time"
)

func omLine(ts time.Time, source string, status int) string {
	return `{"ts":"` + ts.Format(time.RFC3339) + `","endpoint":"/v1/dwd-icon","status":` +
		strconv.Itoa(status) + `,"source":"` + source + `","error":null}`
}

func writeDiagnosticsPrev(t *testing.T, tmpDir, name string, lines ...string) {
	t.Helper()
	dir := filepath.Join(tmpDir, "diagnostics")
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("mkdir diagnostics: %v", err)
	}
	body := strings.Join(lines, "\n") + "\n"
	if err := os.WriteFile(filepath.Join(dir, name+".1"), []byte(body), 0644); err != nil {
		t.Fatalf("write %s.1: %v", name, err)
	}
}

// ---------------------------------------------------------------------------
// briefing_health (openmeteo_calls.jsonl)
// ---------------------------------------------------------------------------

// AC-7: Eine Fehlerserie reicht ueber die Rotationsgrenze. Streak-Beginn,
// 24h-Zaehler und letzter Fehler muessen ueber beide Dateien gerechnet werden,
// genauso wie bei einer ungeteilten Datei.
func TestBriefingHealth2883_FehlerserieUeberRotationsgrenze(t *testing.T) {
	now := time.Now().UTC().Truncate(time.Second)
	alt := []string{
		omLine(now.Add(-30*time.Hour), "briefing", 200),
		omLine(now.Add(-3*time.Hour), "briefing", 503),
		omLine(now.Add(-150*time.Minute), "briefing", 503),
	}
	neu := []string{
		omLine(now.Add(-2*time.Hour), "briefing", 503),
		omLine(now.Add(-90*time.Minute), "briefing_nacht", 503),
	}

	// Referenz: dieselben Zeilen in EINER ungeteilten Datei.
	refDir := t.TempDir()
	writeDiagnosticsLog(t, refDir, append(append([]string{}, alt...), neu...)...)
	refSince, refCount := analyzeBriefingProviderErrors(refDir, now)
	refLast := findLastBriefingProviderError(refDir)
	if refCount != 4 || refSince == "" {
		t.Fatalf("Referenz unplausibel: since=%q count=%d", refSince, refCount)
	}

	dir := t.TempDir()
	writeDiagnosticsPrev(t, dir, "openmeteo_calls.jsonl", alt...)
	writeDiagnosticsLog(t, dir, neu...)

	since, count := analyzeBriefingProviderErrors(dir, now)
	if since != refSince {
		t.Errorf("provider_error_streak_since: want %q (Beginn in .1), got %q", refSince, since)
	}
	if count != refCount {
		t.Errorf("provider_errors_recent_count: want %d (beide Dateien), got %d", refCount, count)
	}
	if got := findLastBriefingProviderError(dir); got != refLast {
		t.Errorf("last_provider_error_at: want %q, got %q", refLast, got)
	}

	sched := newBriefingHealthTestScheduler(t, dir, "default")
	bh := sched.BriefingHealth()
	if got := bh["provider_errors_recent_count"]; got != refCount {
		t.Errorf("BriefingHealth provider_errors_recent_count: want %d, got %v", refCount, got)
	}
	if got := bh["provider_error_streak_since"]; got != refSince {
		t.Errorf("BriefingHealth provider_error_streak_since: want %q, got %v", refSince, got)
	}
}

// AC-7: Fehler stehen NUR in .1 (aktuelle Datei hat nur Erfolge) -- 24h-Zaehler
// und letzter Fehler muessen sie trotzdem finden.
func TestBriefingHealth2883_FehlerNurInEins(t *testing.T) {
	now := time.Now().UTC().Truncate(time.Second)
	fehler := now.Add(-5 * time.Hour)
	dir := t.TempDir()
	writeDiagnosticsPrev(t, dir, "openmeteo_calls.jsonl", omLine(fehler, "briefing", 502))
	writeDiagnosticsLog(t, dir, omLine(now.Add(-time.Hour), "briefing", 200))

	if got := findLastBriefingProviderError(dir); got != fehler.Format(time.RFC3339) {
		t.Errorf("last_provider_error_at: want Fehler aus .1 %q, got %q", fehler.Format(time.RFC3339), got)
	}
	if _, count := analyzeBriefingProviderErrors(dir, now); count != 1 {
		t.Errorf("provider_errors_recent_count: want 1 (Fehler aus .1), got %d", count)
	}
}

// AC-7 (Mutationsprobe "findLast liest .1 nicht"): ohne aktuelle Datei, nur .1.
func TestBriefingHealth2883_NurEinsOhneAktuelle(t *testing.T) {
	now := time.Now().UTC().Truncate(time.Second)
	fehler := now.Add(-2 * time.Hour)
	dir := t.TempDir()
	writeDiagnosticsPrev(t, dir, "openmeteo_calls.jsonl", omLine(fehler, "briefing", 503))

	if got := findLastBriefingProviderError(dir); got != fehler.Format(time.RFC3339) {
		t.Errorf("last_provider_error_at: want %q aus .1, got %q", fehler.Format(time.RFC3339), got)
	}
	if since, count := analyzeBriefingProviderErrors(dir, now); count != 1 || since != fehler.Format(time.RFC3339) {
		t.Errorf("streak/count aus .1: want (%q,1), got (%q,%d)", fehler.Format(time.RFC3339), since, count)
	}
}

// AC-9: .1 ist per Hardlink dieselbe Datei wie die aktuelle -- kein Doppelzaehlen.
func TestBriefingHealth2883_HardlinkKeinDoppelzaehlen(t *testing.T) {
	now := time.Now().UTC().Truncate(time.Second)
	dir := t.TempDir()
	writeDiagnosticsLog(t, dir,
		omLine(now.Add(-3*time.Hour), "briefing", 503),
		omLine(now.Add(-2*time.Hour), "briefing", 503))
	cur := filepath.Join(dir, "diagnostics", "openmeteo_calls.jsonl")
	if err := os.Link(cur, cur+".1"); err != nil {
		t.Fatalf("hardlink .1: %v", err)
	}
	if _, count := analyzeBriefingProviderErrors(dir, now); count != 2 {
		t.Errorf("provider_errors_recent_count: want 2 (Einmal-Lesen), got %d", count)
	}
}

// AC-10: keine .1 und auch keine aktuelle Datei -> leer, kein Fehler.
func TestBriefingHealth2883_OhneDateienLeer(t *testing.T) {
	dir := t.TempDir()
	if since, count := analyzeBriefingProviderErrors(dir, time.Now().UTC()); since != "" || count != 0 {
		t.Errorf("leerer Zustand erwartet, got (%q,%d)", since, count)
	}
	if got := findLastBriefingProviderError(dir); got != "" {
		t.Errorf("last_provider_error_at: want leer, got %q", got)
	}
}

// AC-11 (briefing-Haelfte): .1 ist ein Verzeichnis -> fail-soft, kein
// Fehler-Flag, Auswertung der lesbaren aktuellen Datei bleibt.
func TestBriefingHealth2883_EinsAlsVerzeichnisBleibtFailSoft(t *testing.T) {
	now := time.Now().UTC().Truncate(time.Second)
	fehler := now.Add(-time.Hour)
	dir := t.TempDir()
	writeDiagnosticsLog(t, dir, omLine(fehler, "briefing", 503))
	if err := os.Mkdir(filepath.Join(dir, "diagnostics", "openmeteo_calls.jsonl.1"), 0755); err != nil {
		t.Fatalf("mkdir .1: %v", err)
	}

	if _, count := analyzeBriefingProviderErrors(dir, now); count != 1 {
		t.Errorf("provider_errors_recent_count: want 1 aus aktueller Datei, got %d", count)
	}
	if got := findLastBriefingProviderError(dir); got != fehler.Format(time.RFC3339) {
		t.Errorf("last_provider_error_at: want %q, got %q", fehler.Format(time.RFC3339), got)
	}
	sched := newBriefingHealthTestScheduler(t, dir, "default")
	assertBriefingHealthKeys2883(t, sched.BriefingHealth())
}

// AC-12: briefing_health traegt exakt dieselben Felder wie vor #2883 -- auch
// wenn beide Generationen vorliegen. Kein neues Feld (z. B. kein Fehler-Flag).
var briefingHealthKeys2883 = []string{
	"alert_anchor_rejected_recent_count", "alert_anchor_rejected_streak_since",
	"briefing_dispatch_error_streak_since", "briefing_dispatch_errors_recent_count",
	"corrupt_briefings_by_kind", "corrupt_briefings_total", "corrupt_trips_last_run_at",
	"corrupt_trips_total", "degraded_segments_total", "last_provider_error_at",
	"oldest_pending_age_hours", "open_pending_briefings", "provider_error_streak_since",
	"provider_errors_recent_count", "track_resolution_failure_streak_since",
	"track_resolution_failures_recent_count",
}

func assertBriefingHealthKeys2883(t *testing.T, bh map[string]any) {
	t.Helper()
	got := make([]string, 0, len(bh))
	for k := range bh {
		got = append(got, k)
	}
	sort.Strings(got)
	want := append([]string{}, briefingHealthKeys2883...)
	sort.Strings(want)
	if strings.Join(got, ",") != strings.Join(want, ",") {
		t.Errorf("briefing_health-Feldmenge veraendert:\n want %v\n got  %v", want, got)
	}
}

func TestBriefingHealth2883_FeldmengeUnveraendertMitBeidenGenerationen(t *testing.T) {
	now := time.Now().UTC().Truncate(time.Second)
	dir := t.TempDir()
	writeDiagnosticsPrev(t, dir, "openmeteo_calls.jsonl", omLine(now.Add(-3*time.Hour), "briefing", 503))
	writeDiagnosticsLog(t, dir, omLine(now.Add(-time.Hour), "briefing", 503))
	sched := newBriefingHealthTestScheduler(t, dir, "default")

	_, body, _ := callStatusEndpoint(t, sched)
	bh, ok := body["briefing_health"].(map[string]any)
	if !ok {
		t.Fatalf("briefing_health fehlt im Status: %#v", body["briefing_health"])
	}
	assertBriefingHealthKeys2883(t, bh)
	if got := bh["provider_errors_recent_count"]; got != float64(2) {
		t.Errorf("provider_errors_recent_count ueber den Endpunkt: want 2 (beide Dateien), got %v", got)
	}
}

// ---------------------------------------------------------------------------
// enrichment_health (enrichment_calls.jsonl)
// ---------------------------------------------------------------------------

func writeEnrichmentPrev(t *testing.T, tmpDir string, lines ...string) {
	t.Helper()
	writeDiagnosticsPrev(t, tmpDir, "enrichment_calls.jsonl", lines...)
}

// AC-8: letzter Erfolg steht nur in .1, letzter Versuch in der aktuellen Datei;
// fuer einen zweiten Pfad steht ALLES nur in .1.
func TestEnrichmentHealth2883_ErfolgNurInEins(t *testing.T) {
	base := time.Date(2026, 11, 1, 8, 0, 0, 0, time.UTC)
	dir := t.TempDir()
	sched := newEnrichmentHealthTestScheduler(t, dir)

	writeEnrichmentPrev(t, dir,
		enrichmentLine(base, "thunder", "ok", ""),
		enrichmentLine(base.Add(time.Hour), "radar_nowcast", "ok", ""),
		enrichmentLine(base.Add(2*time.Hour), "radar_nowcast", "fallback", "eu_direct"))
	writeEnrichmentJournal(t, dir,
		enrichmentLine(base.Add(3*time.Hour), "thunder", "unavailable", ""))

	health := sched.EnrichmentHealth()
	th := enrichmentEntry(t, health, "thunder")
	if got := th["last_success_at"]; got != base.Format(time.RFC3339) {
		t.Errorf("thunder.last_success_at: want Erfolg aus .1 %q, got %v", base.Format(time.RFC3339), got)
	}
	if got := th["last_attempt_at"]; got != base.Add(3*time.Hour).Format(time.RFC3339) {
		t.Errorf("thunder.last_attempt_at: want juengsten Versuch, got %v", got)
	}
	rn := enrichmentEntry(t, health, "radar_nowcast")
	if got := rn["last_attempt_at"]; got != base.Add(2*time.Hour).Format(time.RFC3339) {
		t.Errorf("radar_nowcast.last_attempt_at aus .1: got %v", got)
	}
	if got := rn["last_fallback_detail"]; got != "eu_direct" {
		t.Errorf("radar_nowcast.last_fallback_detail aus .1: got %v", got)
	}
	if _, exists := health["journal_read_error"]; exists {
		t.Errorf("journal_read_error darf nicht gesetzt sein: %v", health["journal_read_error"])
	}
}

// AC-8 (Mutationsprobe Lesereihenfolge): der juengste Wert gewinnt, egal in
// welcher Datei -- auch wenn .1 einen AELTEREN Erfolg traegt als die aktuelle.
func TestEnrichmentHealth2883_JuengsterWertUeberBeideDateien(t *testing.T) {
	base := time.Date(2026, 11, 1, 8, 0, 0, 0, time.UTC)
	dir := t.TempDir()
	sched := newEnrichmentHealthTestScheduler(t, dir)

	writeEnrichmentPrev(t, dir,
		enrichmentLine(base, "thunder", "ok", ""),
		enrichmentLine(base.Add(time.Hour), "thunder", "fallback", "alt"))
	writeEnrichmentJournal(t, dir,
		enrichmentLine(base.Add(2*time.Hour), "thunder", "ok", ""))

	th := enrichmentEntry(t, sched.EnrichmentHealth(), "thunder")
	if got := th["last_success_at"]; got != base.Add(2*time.Hour).Format(time.RFC3339) {
		t.Errorf("last_success_at: want juengsten Erfolg, got %v", got)
	}
	if got := th["last_fallback_detail"]; got != "alt" {
		t.Errorf("last_fallback_detail aus .1: want alt, got %v", got)
	}
}

// AC-9: Hardlink .1 == aktuelle Datei -> kein Doppelzaehlen (Einheiten-Liste
// und Aggregat identisch zum Einmal-Lesen), kein Fehler-Flag.
func TestEnrichmentHealth2883_HardlinkKeinDoppelzaehlen(t *testing.T) {
	base := time.Date(2026, 11, 1, 8, 0, 0, 0, time.UTC)
	dir := t.TempDir()
	writeEnrichmentJournal(t, dir,
		enrichmentLine(base, "thunder", "ok", ""),
		enrichmentLine(base.Add(time.Hour), "thunder", "self_throttled", ""))
	cur := filepath.Join(dir, "diagnostics", "enrichment_calls.jsonl")
	ref, refErr := aggregateEnrichmentCalls(cur)
	if err := os.Link(cur, cur+".1"); err != nil {
		t.Fatalf("hardlink .1: %v", err)
	}
	got, gotErr := aggregateEnrichmentCalls(cur)
	if gotErr != refErr || len(got) != len(ref) {
		t.Fatalf("Hardlink veraendert Aggregat: ref=(%d,%v) got=(%d,%v)", len(ref), refErr, len(got), gotErr)
	}
	r, g := ref["thunder"], got["thunder"]
	if g == nil || g.lastAttemptAt != r.lastAttemptAt || g.lastSuccessAt != r.lastSuccessAt ||
		g.selfThrottled != r.selfThrottled {
		t.Errorf("thunder-Aggregat weicht ab: ref=%+v got=%+v", r, g)
	}
}

// AC-10: keine .1 / keine Datei -> kein journal_read_error.
func TestEnrichmentHealth2883_OhneEinsUndOhneDateiKeinFehler(t *testing.T) {
	dir := t.TempDir()
	sched := newEnrichmentHealthTestScheduler(t, dir)
	if h := sched.EnrichmentHealth(); len(h) != 0 {
		t.Errorf("ohne Journal: want leeres Aggregat, got %#v", h)
	}

	writeEnrichmentJournal(t, dir, enrichmentLine(time.Date(2026, 11, 1, 8, 0, 0, 0, time.UTC), "thunder", "ok", ""))
	h := sched.EnrichmentHealth()
	if _, exists := h["journal_read_error"]; exists {
		t.Errorf("ohne .1: journal_read_error darf nicht gesetzt sein")
	}
	enrichmentEntry(t, h, "thunder")
}

// AC-11: .1 ist ein Verzeichnis -> journal_read_error, Daten der lesbaren
// aktuellen Datei bleiben erhalten. Bewusste Verhaltensaenderung.
func TestEnrichmentHealth2883_EinsAlsVerzeichnisSetztFlag(t *testing.T) {
	base := time.Date(2026, 11, 1, 8, 0, 0, 0, time.UTC)
	dir := t.TempDir()
	sched := newEnrichmentHealthTestScheduler(t, dir)
	writeEnrichmentJournal(t, dir, enrichmentLine(base, "thunder", "ok", ""))
	if err := os.Mkdir(filepath.Join(dir, "diagnostics", "enrichment_calls.jsonl.1"), 0755); err != nil {
		t.Fatalf("mkdir .1: %v", err)
	}

	h := sched.EnrichmentHealth()
	if got := h["journal_read_error"]; got != true {
		t.Errorf("journal_read_error: want true bei unlesbarer .1, got %v", got)
	}
	if got := enrichmentEntry(t, h, "thunder")["last_success_at"]; got != base.Format(time.RFC3339) {
		t.Errorf("Daten der aktuellen Datei muessen erhalten bleiben, got %v", got)
	}
}

// AC-11: .1 existiert, laesst sich aber nicht OEFFNEN (Rechte) -> journal_read_error.
func TestEnrichmentHealth2883_EinsNichtOeffenbarSetztFlag(t *testing.T) {
	if os.Geteuid() == 0 {
		t.Skip("root ignoriert Dateirechte")
	}
	base := time.Date(2026, 11, 1, 8, 0, 0, 0, time.UTC)
	dir := t.TempDir()
	sched := newEnrichmentHealthTestScheduler(t, dir)
	writeEnrichmentJournal(t, dir, enrichmentLine(base, "thunder", "ok", ""))
	writeEnrichmentPrev(t, dir, enrichmentLine(base.Add(-time.Hour), "thunder", "ok", ""))
	prev := filepath.Join(dir, "diagnostics", "enrichment_calls.jsonl.1")
	if err := os.Chmod(prev, 0o000); err != nil {
		t.Fatalf("chmod .1: %v", err)
	}
	t.Cleanup(func() { _ = os.Chmod(prev, 0o644) })

	h := sched.EnrichmentHealth()
	if got := h["journal_read_error"]; got != true {
		t.Errorf("journal_read_error: want true, wenn .1 nicht oeffenbar, got %v", got)
	}
	if got := enrichmentEntry(t, h, "thunder")["last_success_at"]; got != base.Format(time.RFC3339) {
		t.Errorf("aktuelle Datei muss geliefert werden, got %v", got)
	}
}
