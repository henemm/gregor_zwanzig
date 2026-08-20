package scheduler

import (
	"net/http"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/store"
)

// TDD RED: Issue #1581 — enrichment_health im /api/scheduler/status
//
// Spec: docs/specs/modules/fix_1581_enrichment_health.md (AC-5, AC-7 plus die
// Radar-Faelle aus Scheibe 2).
//
// KEINE Mocks: echte JSONL-Dateien in t.TempDir(), echter EnrichmentHealth()-
// Aufruf bzw. echter httptest-Roundtrip gegen Status() (Muster
// briefing_health_test.go / warn_service_health_test.go).

// newEnrichmentHealthTestScheduler builds a Scheduler backed by tmpDir.
func newEnrichmentHealthTestScheduler(t *testing.T, tmpDir string) *Scheduler {
	t.Helper()
	s := store.New(tmpDir, "default")
	cfg := &config.Config{
		PythonCoreURL:     "http://localhost:8000",
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, s)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	return sched
}

// writeEnrichmentJournal writes data/diagnostics/enrichment_calls.jsonl with
// the given raw lines — exactly the file src/providers/enrichment_health.py
// appends to.
func writeEnrichmentJournal(t *testing.T, tmpDir string, lines ...string) {
	t.Helper()
	dir := filepath.Join(tmpDir, "diagnostics")
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("mkdir diagnostics: %v", err)
	}
	body := ""
	for _, l := range lines {
		body += l + "\n"
	}
	path := filepath.Join(dir, "enrichment_calls.jsonl")
	if err := os.WriteFile(path, []byte(body), 0644); err != nil {
		t.Fatalf("write enrichment_calls.jsonl: %v", err)
	}
}

// enrichmentLine renders one journal line as log_enrichment_call() writes it.
func enrichmentLine(ts time.Time, path, outcome, detail string) string {
	d := "null"
	if detail != "" {
		d = `"` + detail + `"`
	}
	return `{"ts":"` + ts.Format(time.RFC3339) + `","path":"` + path +
		`","outcome":"` + outcome + `","detail":` + d + `}`
}

func enrichmentEntry(t *testing.T, health map[string]any, path string) map[string]any {
	t.Helper()
	entry, ok := health[path].(map[string]any)
	if !ok {
		t.Fatalf("enrichment_health[%q] fehlt oder hat den falschen Typ: %#v (ganzes Aggregat: %#v)",
			path, health[path], health)
	}
	return entry
}

// ---------------------------------------------------------------------------
// AC-5: Dauerausfall ist als wachsender Abstand ablesbar
// ---------------------------------------------------------------------------

// AC-5: Ueber mehrere simulierte Tage stehen NUR "unavailable"-Zeilen fuer
// path="thunder". Dann traegt enrichment_health.thunder ein frisches
// last_attempt_at und last_success_at=null — nie gab es einen Erfolg.
func TestEnrichmentHealthDauerausfallOhneErfolgLiefertNullSuccess(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newEnrichmentHealthTestScheduler(t, tmpDir)

	now := time.Now().UTC()
	writeEnrichmentJournal(t, tmpDir,
		enrichmentLine(now.Add(-72*time.Hour), "thunder", "unavailable", ""),
		enrichmentLine(now.Add(-48*time.Hour), "thunder", "unavailable", ""),
		enrichmentLine(now.Add(-24*time.Hour), "thunder", "unavailable", ""),
		enrichmentLine(now.Add(-5*time.Minute), "thunder", "unavailable", ""),
	)

	code, body, raw := callStatusEndpoint(t, sched)
	if code != http.StatusOK {
		t.Fatalf("erwartet 200, bekommen %d (%s)", code, raw)
	}
	health, ok := body["enrichment_health"].(map[string]any)
	if !ok {
		t.Fatalf("enrichment_health fehlt im Status oder hat den falschen Typ: %#v", body["enrichment_health"])
	}
	thunder := enrichmentEntry(t, health, "thunder")

	if got := thunder["last_success_at"]; got != nil {
		t.Errorf("last_success_at: erwartet nil (nie ein Erfolg im Journal), bekommen %#v", got)
	}
	attempt, ok := thunder["last_attempt_at"].(string)
	if !ok || attempt == "" {
		t.Fatalf("last_attempt_at fehlt oder ist kein Zeitstempel: %#v", thunder["last_attempt_at"])
	}
	ts, err := time.Parse(time.RFC3339, attempt)
	if err != nil {
		t.Fatalf("last_attempt_at ist kein RFC3339: %v", err)
	}
	if alter := time.Since(ts); alter > time.Hour {
		t.Errorf("last_attempt_at ist %v alt — erwartet der JUENGSTE Versuch (vor 5 Minuten), nicht der aelteste", alter)
	}
}

// AC-5, der eigentliche Kern: der Abstand zwischen jetzt und last_success_at
// WAECHST mit der simulierten Ausfalldauer. Zwei Laeufe mit demselben Aufbau,
// nur der letzte Erfolg liegt unterschiedlich weit zurueck — eine
// Implementierung, die last_success_at etwa auf den JUENGSTEN Versuch setzt
// (statt auf den juengsten ERFOLG), liefert in beiden Laeufen denselben Wert.
func TestEnrichmentHealthAbstandZumLetztenErfolgWaechstMitDerAusfalldauer(t *testing.T) {
	now := time.Now().UTC()

	abstand := func(ausfalldauer time.Duration) time.Duration {
		tmpDir := t.TempDir()
		sched := newEnrichmentHealthTestScheduler(t, tmpDir)
		erfolg := now.Add(-ausfalldauer)
		writeEnrichmentJournal(t, tmpDir,
			enrichmentLine(erfolg, "thunder", "ok", ""),
			enrichmentLine(erfolg.Add(time.Hour), "thunder", "unavailable", ""),
			enrichmentLine(now.Add(-time.Minute), "thunder", "unavailable", ""),
		)
		thunder := enrichmentEntry(t, sched.EnrichmentHealth(), "thunder")
		raw, ok := thunder["last_success_at"].(string)
		if !ok {
			t.Fatalf("last_success_at fehlt oder ist kein Zeitstempel: %#v", thunder["last_success_at"])
		}
		ts, err := time.Parse(time.RFC3339, raw)
		if err != nil {
			t.Fatalf("last_success_at ist kein RFC3339: %v", err)
		}
		return now.Sub(ts)
	}

	kurz := abstand(6 * time.Hour)
	lang := abstand(72 * time.Hour)

	if kurz < 5*time.Hour || kurz > 7*time.Hour {
		t.Errorf("Abstand nach 6h Ausfall: erwartet ~6h, bekommen %v", kurz)
	}
	if lang < 71*time.Hour || lang > 73*time.Hour {
		t.Errorf("Abstand nach 72h Ausfall: erwartet ~72h, bekommen %v", lang)
	}
	if lang <= kurz {
		t.Errorf("AC-5: der Abstand zum letzten Erfolg muss mit der Ausfalldauer WACHSEN — kurz=%v, lang=%v", kurz, lang)
	}
}

// AC-5, Gegenprobe: eine dauerhaft ueber die Vertretung bediente Quelle ist
// degradiert, nicht gesund. `fallback` darf deshalb NICHT als Erfolg zaehlen,
// sonst bliebe last_success_at frisch, waehrend die Primaerquelle seit Tagen
// ausfaellt — genau der Zustand, den ADR-0018 sichtbar machen will.
func TestEnrichmentHealthFallbackZaehltNichtAlsErfolg(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newEnrichmentHealthTestScheduler(t, tmpDir)

	now := time.Now().UTC()
	erfolg := now.Add(-96 * time.Hour)
	writeEnrichmentJournal(t, tmpDir,
		enrichmentLine(erfolg, "thunder", "ok", ""),
		enrichmentLine(now.Add(-2*time.Hour), "thunder", "fallback", "eu_direct"),
		enrichmentLine(now.Add(-time.Minute), "thunder", "fallback", "eu_direct"),
	)

	thunder := enrichmentEntry(t, sched.EnrichmentHealth(), "thunder")

	if got, want := thunder["last_success_at"], erfolg.Format(time.RFC3339); got != want {
		t.Errorf("last_success_at: erwartet %v (der letzte ECHTE Erfolg), bekommen %#v — eine dauerhafte Vertretung darf nicht als gesund durchgehen", want, got)
	}
	fallback, ok := thunder["last_fallback_at"].(string)
	if !ok || fallback == "" {
		t.Fatalf("last_fallback_at fehlt oder ist kein Zeitstempel: %#v", thunder["last_fallback_at"])
	}
	if ts, err := time.Parse(time.RFC3339, fallback); err != nil {
		t.Fatalf("last_fallback_at ist kein RFC3339: %v", err)
	} else if time.Since(ts) > time.Hour {
		t.Errorf("last_fallback_at ist %v alt — erwartet die juengste Vertretung (vor 1 Minute)", time.Since(ts))
	}
	if got := thunder["last_attempt_at"]; got != now.Add(-time.Minute).Format(time.RFC3339) {
		t.Errorf("last_attempt_at: erwartet den juengsten Versuch, bekommen %#v", got)
	}
}

// ---------------------------------------------------------------------------
// Radar-Faelle (Scheibe 2): eigener Pfad, self_throttled getrennt vom Ausfall
// ---------------------------------------------------------------------------

// Beide Pfade schreiben in DASSELBE Journal und muessen im Aggregat getrennt
// erscheinen — ein Aggregator ohne Gruppierung nach `path` wuerde den
// Radar-Erfolg dem Gewitter-Dauerausfall gutschreiben.
func TestEnrichmentHealthTrenntThunderUndRadarNowcast(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newEnrichmentHealthTestScheduler(t, tmpDir)

	now := time.Now().UTC()
	radarErfolg := now.Add(-10 * time.Minute)
	writeEnrichmentJournal(t, tmpDir,
		enrichmentLine(now.Add(-48*time.Hour), "thunder", "unavailable", ""),
		enrichmentLine(now.Add(-30*time.Minute), "thunder", "unavailable", ""),
		enrichmentLine(now.Add(-20*time.Minute), "radar_nowcast", "unavailable", ""),
		enrichmentLine(radarErfolg, "radar_nowcast", "ok", ""),
	)

	health := sched.EnrichmentHealth()
	thunder := enrichmentEntry(t, health, "thunder")
	radar := enrichmentEntry(t, health, "radar_nowcast")

	if got := thunder["last_success_at"]; got != nil {
		t.Errorf("thunder.last_success_at: erwartet nil, bekommen %#v — der Radar-Erfolg wurde dem Gewitterpfad gutgeschrieben", got)
	}
	if got, want := radar["last_success_at"], radarErfolg.Format(time.RFC3339); got != want {
		t.Errorf("radar_nowcast.last_success_at: erwartet %v, bekommen %#v", want, got)
	}
}

// AC-10 auf der Leseseite: die eigene Budget-Drosselung ist ein eigener
// Ausgang — sie setzt weder einen Erfolg noch bleibt sie unsichtbar. Ein
// Anbieterausfall allein darf das Flag NICHT setzen.
func TestEnrichmentHealthSelfThrottledNurBeiEigenerDrosselung(t *testing.T) {
	now := time.Now().UTC()

	flagFuer := func(outcome string) bool {
		tmpDir := t.TempDir()
		sched := newEnrichmentHealthTestScheduler(t, tmpDir)
		writeEnrichmentJournal(t, tmpDir,
			enrichmentLine(now.Add(-time.Hour), "radar_nowcast", outcome, ""),
		)
		radar := enrichmentEntry(t, sched.EnrichmentHealth(), "radar_nowcast")
		flag, ok := radar["self_throttled"].(bool)
		if !ok {
			t.Fatalf("self_throttled fehlt oder ist kein bool: %#v", radar["self_throttled"])
		}
		return flag
	}

	if !flagFuer("self_throttled") {
		t.Errorf("self_throttled: erwartet true nach einer Drosselungs-Zeile, bekommen false")
	}
	if flagFuer("unavailable") {
		t.Errorf("self_throttled: erwartet false bei einem reinen Anbieterausfall — sonst eskaliert die externe Auswertung einen selbst gewaehlten Rueckzug als Fremdausfall")
	}
	if flagFuer("ok") {
		t.Errorf("self_throttled: erwartet false nach einem erfolgreichen Abruf, bekommen true")
	}
}

// Eine Drosselung ist ein Abrufversuch, aber kein Erfolg: sonst saehe ein
// dauerhaft gedrosselter Pfad von aussen gesund aus.
func TestEnrichmentHealthDrosselungIstKeinErfolg(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newEnrichmentHealthTestScheduler(t, tmpDir)

	now := time.Now().UTC()
	writeEnrichmentJournal(t, tmpDir,
		enrichmentLine(now.Add(-time.Hour), "radar_nowcast", "self_throttled", ""),
	)

	radar := enrichmentEntry(t, sched.EnrichmentHealth(), "radar_nowcast")
	if got := radar["last_success_at"]; got != nil {
		t.Errorf("last_success_at: erwartet nil nach einer reinen Drosselung, bekommen %#v", got)
	}
	if got := radar["last_attempt_at"]; got == nil {
		t.Errorf("last_attempt_at: erwartet den Zeitpunkt der Drosselung — ein unterbliebener Abruf bleibt ein Abrufversuch")
	}
}

// ---------------------------------------------------------------------------
// Fehlende / defekte Journaldatei (Muster warn_service_health)
// ---------------------------------------------------------------------------

// Frischer Deploy: keine Journaldatei. Das ist ein legitimer Zustand, KEIN
// Lesefehler — sonst meldete jede neue Installation sofort einen Defekt.
func TestEnrichmentHealthFehlendeDateiIstKeinFehler(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newEnrichmentHealthTestScheduler(t, tmpDir)

	health := sched.EnrichmentHealth()

	if got, ok := health["journal_read_error"]; ok {
		t.Errorf("journal_read_error: erwartet abwesend ohne Journaldatei, bekommen %#v", got)
	}
	if len(health) != 0 {
		t.Errorf("erwartet ein leeres Aggregat ohne Journaldatei, bekommen %#v", health)
	}
}

// Echter Lesefehler (Pfad ist ein Verzeichnis) muss sich von "gibt es noch
// nicht" unterscheiden — nur er ist unser eigener Fehler.
func TestEnrichmentHealthLesefehlerSetztFlag(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newEnrichmentHealthTestScheduler(t, tmpDir)

	if err := os.MkdirAll(filepath.Join(tmpDir, "diagnostics", "enrichment_calls.jsonl"), 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}

	health := sched.EnrichmentHealth()
	if got, ok := health["journal_read_error"].(bool); !ok || !got {
		t.Errorf("journal_read_error: erwartet true bei einem echten Lesefehler, bekommen %#v", health["journal_read_error"])
	}
}

// Eine kaputte Zeile darf den Rest des Journals nicht mitreissen (fail-soft,
// wie findLastBriefingProviderError).
func TestEnrichmentHealthUeberspringtKaputteZeilen(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newEnrichmentHealthTestScheduler(t, tmpDir)

	now := time.Now().UTC()
	writeEnrichmentJournal(t, tmpDir,
		`{nicht mal JSON`,
		enrichmentLine(now.Add(-time.Hour), "thunder", "ok", ""),
		`{"ts":"","path":"thunder","outcome":"ok","detail":null}`,
	)

	thunder := enrichmentEntry(t, sched.EnrichmentHealth(), "thunder")
	if got, want := thunder["last_success_at"], now.Add(-time.Hour).Format(time.RFC3339); got != want {
		t.Errorf("last_success_at: erwartet %v (die eine gueltige Zeile), bekommen %#v — eine Zeile ohne Zeitstempel darf keine gueltige verdraengen", want, got)
	}
}

// ---------------------------------------------------------------------------
// AC-7: eigener Top-Level-Schluessel, briefing_health unberuehrt
// ---------------------------------------------------------------------------

// AC-7: `enrichment_health` steht als eigenstaendiger Geschwister-Schluessel
// neben `briefing_health` und `warn_service_health` — NICHT darin
// verschachtelt. Und: das Anreicherungs-Journal veraendert `briefing_health`
// in Struktur und Werten nicht.
func TestStatusEnthaeltEnrichmentHealthAlsGeschwisterVonBriefingHealth(t *testing.T) {
	now := time.Now().UTC()

	briefingHealthOhneJournal := func() map[string]any {
		tmpDir := t.TempDir()
		sched := newEnrichmentHealthTestScheduler(t, tmpDir)
		_, body, _ := callStatusEndpoint(t, sched)
		bh, ok := body["briefing_health"].(map[string]any)
		if !ok {
			t.Fatalf("briefing_health fehlt: %#v", body["briefing_health"])
		}
		return bh
	}
	referenz := briefingHealthOhneJournal()

	tmpDir := t.TempDir()
	sched := newEnrichmentHealthTestScheduler(t, tmpDir)
	writeEnrichmentJournal(t, tmpDir,
		enrichmentLine(now.Add(-time.Hour), "thunder", "unavailable", ""),
		enrichmentLine(now.Add(-time.Minute), "radar_nowcast", "self_throttled", ""),
	)

	code, body, raw := callStatusEndpoint(t, sched)
	if code != http.StatusOK {
		t.Fatalf("erwartet 200, bekommen %d (%s)", code, raw)
	}

	health, ok := body["enrichment_health"].(map[string]any)
	if !ok {
		t.Fatalf("AC-7: enrichment_health fehlt als Top-Level-Schluessel oder hat den falschen Typ: %#v", body["enrichment_health"])
	}
	enrichmentEntry(t, health, "thunder")
	enrichmentEntry(t, health, "radar_nowcast")

	bh, ok := body["briefing_health"].(map[string]any)
	if !ok {
		t.Fatalf("briefing_health fehlt: %#v", body["briefing_health"])
	}
	if _, verschachtelt := bh["enrichment_health"]; verschachtelt {
		t.Errorf("AC-7: enrichment_health liegt INNERHALB von briefing_health — check-gregor20.sh liest briefing_health als 'ist das Briefing gesund' und wuerde die Anreicherung mitbewerten")
	}
	if len(bh) != len(referenz) {
		t.Errorf("AC-7: briefing_health hat %d Schluessel statt %d — Struktur veraendert.\n  mit Journal: %#v\n  Referenz:    %#v", len(bh), len(referenz), bh, referenz)
	}
	for k, want := range referenz {
		got, vorhanden := bh[k]
		if !vorhanden {
			t.Errorf("AC-7: briefing_health-Schluessel %q ist verschwunden", k)
			continue
		}
		if got != want {
			t.Errorf("AC-7: briefing_health[%q] hat sich geaendert: %#v statt %#v — das Anreicherungs-Journal darf den Briefing-Kanal nicht beruehren", k, got, want)
		}
	}
	if _, ok := body["warn_service_health"]; !ok {
		t.Errorf("warn_service_health ist aus dem Status verschwunden")
	}
}

// ---------------------------------------------------------------------------
// AC-8 (#1992): neue path-Werte erscheinen automatisch, ohne diese Datei zu
// aendern -- der Aggregator gruppiert bereits generisch ueber entry.Path.
// ---------------------------------------------------------------------------

// AC-8: zwei neue path-Werte (snowgrid, thunder_additive, #1992) tauchen im
// Aggregat auf, obwohl enrichment_health.go sie an keiner Stelle kennt --
// kein Enum, kein switch ueber erlaubte path-Werte. Belegt die Spec-
// Architektur-Entscheidung 3 (aggregateEnrichmentCalls gruppiert generisch
// nach Path, nicht nach einem geschlossenen Vokabular).
func TestEnrichmentHealthNeuePathWerteErscheinenAutomatisch(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newEnrichmentHealthTestScheduler(t, tmpDir)

	now := time.Now().UTC()
	snowgridErfolg := now.Add(-30 * time.Minute)
	thunderAdditiveAusfall := now.Add(-10 * time.Minute)
	writeEnrichmentJournal(t, tmpDir,
		enrichmentLine(snowgridErfolg, "snowgrid", "ok", ""),
		enrichmentLine(thunderAdditiveAusfall, "thunder_additive", "unavailable", "geosphere"),
	)

	health := sched.EnrichmentHealth()

	snowgrid := enrichmentEntry(t, health, "snowgrid")
	if got, want := snowgrid["last_success_at"], snowgridErfolg.Format(time.RFC3339); got != want {
		t.Errorf("snowgrid.last_success_at: erwartet %v, bekommen %#v", want, got)
	}
	if _, ok := snowgrid["self_throttled"].(bool); !ok {
		t.Errorf("snowgrid: erwartet dieselben Rohdaten-Felder wie thunder/radar_nowcast (self_throttled fehlt oder falscher Typ): %#v", snowgrid)
	}

	thunderAdditive := enrichmentEntry(t, health, "thunder_additive")
	if got := thunderAdditive["last_success_at"]; got != nil {
		t.Errorf("thunder_additive.last_success_at: erwartet nil (nur ein Ausfall im Journal), bekommen %#v", got)
	}
	attempt, ok := thunderAdditive["last_attempt_at"].(string)
	if !ok || attempt != thunderAdditiveAusfall.Format(time.RFC3339) {
		t.Errorf("thunder_additive.last_attempt_at: erwartet %v, bekommen %#v", thunderAdditiveAusfall.Format(time.RFC3339), thunderAdditive["last_attempt_at"])
	}
}
