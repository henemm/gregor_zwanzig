package scheduler

// TDD RED — Issue #2155 Scheibe S3 (Kontosperre), AC-11: der Scheduler
// liefert gesperrten Konten nichts aus.
// Spec: docs/specs/modules/admin_rolle_s3_admin_api.md
//
// Gemessen am WIRKORT: runForAllUsers ruft je bedientem Nutzer den
// Python-Core (hier ein aufzeichnender httptest-Server) — nicht an
// filterOutTestUsers isoliert. Alle 7 Fan-out-Jobs laufen ueber dieselbe
// Funktion; der Test faehrt sie einzeln, damit ein Job, der kuenftig an
// runForAllUsers vorbei fan-outet, hier nicht unbemerkt bleibt.
//
// Das Flag "disabled" wird ROH in user.json geschrieben — kein noch nicht
// existierendes Symbol (model.User.Disabled) referenziert: das RED ist eine
// Assertion, kein Uebersetzungsfehler.

import (
	"bytes"
	"fmt"
	"log"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"testing"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/store"
)

// fanOutJobs sind die 7 Jobs, die ueber runForAllUsers je Nutzer ausliefern
// (scheduler.go: trip_reports_hourly, alert_checks, radar_alert_checks,
// compare_alert_checks, compare_radar_alert_checks,
// compare_official_alert_checks, compare_presets_daily).
var fanOutJobs = []struct{ jobID, path string }{
	{"trip_reports_hourly", "/api/scheduler/trip-reports"},
	{"alert_checks", "/api/scheduler/alert-checks"},
	{"radar_alert_checks", "/api/scheduler/radar-alert-checks"},
	{"compare_alert_checks", "/api/scheduler/compare-alert-checks"},
	{"compare_radar_alert_checks", "/api/scheduler/compare-radar-alert-checks"},
	{"compare_official_alert_checks", "/api/scheduler/compare-official-alert-checks"},
	{"compare_presets_daily", "/api/scheduler/compare-presets-daily"},
}

// schreibeSperrProfil legt users/<id>/user.json roh an, optional mit
// "disabled": true.
func schreibeSperrProfil(t *testing.T, dataDir, id string, gesperrt bool) {
	t.Helper()
	dir := filepath.Join(dataDir, "users", id)
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("mkdir %s: %v", dir, err)
	}
	body := fmt.Sprintf(`{"id":%q,"mail_to":"%s@example.com"}`, id, id)
	if gesperrt {
		body = fmt.Sprintf(`{"id":%q,"mail_to":"%s@example.com","disabled":true}`, id, id)
	}
	if err := os.WriteFile(filepath.Join(dir, "user.json"), []byte(body), 0644); err != nil {
		t.Fatalf("write user.json for %s: %v", id, err)
	}
}

// fanOutFuerJob faehrt runForAllUsers fuer EINEN Job und liefert die
// sortierte Menge der bedienten user_ids sowie die Logausgabe des Laufs.
func fanOutFuerJob(t *testing.T, s *store.Store, jobID, path string) ([]string, string) {
	t.Helper()
	var mu sync.Mutex
	var served []string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		served = append(served, r.URL.Query().Get("user_id"))
		mu.Unlock()
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, `{"status":"ok"}`)
	}))
	defer server.Close()

	var logBuf bytes.Buffer
	var logMu sync.Mutex
	prev := log.Writer()
	log.SetOutput(&syncWriter{mu: &logMu, w: &logBuf})
	defer log.SetOutput(prev)

	cfg := &config.Config{PythonCoreURL: server.URL, SchedulerTimezone: "Europe/Vienna"}
	sched, err := New(cfg, s)
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	if err := sched.runForAllUsers(jobID, path); err != nil {
		t.Fatalf("runForAllUsers(%s) error: %v", jobID, err)
	}
	mu.Lock()
	out := append([]string(nil), served...)
	mu.Unlock()
	sort.Strings(out)
	logMu.Lock()
	defer logMu.Unlock()
	return out, logBuf.String()
}

type syncWriter struct {
	mu *sync.Mutex
	w  *bytes.Buffer
}

func (s *syncWriter) Write(p []byte) (int, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.w.Write(p)
}

// logNenntSperre: eine Logzeile nennt den gesperrten Nutzer UND den Grund.
func logNenntSperre(logText, uid string) bool {
	for _, zeile := range strings.Split(logText, "\n") {
		low := strings.ToLower(zeile)
		if strings.Contains(zeile, uid) && (strings.Contains(low, "disabled") || strings.Contains(low, "gesperrt")) {
			return true
		}
	}
	return false
}

// AC-11: gesperrtes Konto wird in allen 7 Fan-out-Jobs uebersprungen, das
// aktive bedient; der Log nennt den Grund. Ein unlesbares Profil bleibt im
// Lauf (fail-open, Regressionswaechter — heute schon gruen).
func TestFanOut_SkipsDisabledAccount_InAllSevenJobs_LogsReason(t *testing.T) {
	if len(fanOutJobs) != 7 {
		t.Fatalf("AC-11 nennt 7 Fan-out-Jobs, abgedeckt sind %d", len(fanOutJobs))
	}

	// Gegenprobe (heute gruen): OHNE Flag wird derselbe Nutzer bedient — der
	// Ausschluss unten haengt am Flag, nicht am Namen oder an der Fixture.
	{
		tmpDir := t.TempDir()
		s := store.New(tmpDir, "default")
		schreibeSperrProfil(t, tmpDir, "aktiv", false)
		schreibeSperrProfil(t, tmpDir, "bruno", false)
		served, logText := fanOutFuerJob(t, s, fanOutJobs[0].jobID, fanOutJobs[0].path)
		if got := strings.Join(served, ","); got != "aktiv,bruno" {
			t.Fatalf("Gegenprobe: ohne disabled-Flag muessen beide bedient werden, bedient %v", served)
		}
		if logNenntSperre(logText, "bruno") {
			t.Fatalf("Gegenprobe: ohne Flag darf keine Logzeile bruno als gesperrt nennen. Log:\n%s", logText)
		}
	}

	for _, job := range fanOutJobs {
		t.Run(job.jobID, func(t *testing.T) {
			tmpDir := t.TempDir()
			s := store.New(tmpDir, "default")
			schreibeSperrProfil(t, tmpDir, "aktiv", false)
			schreibeSperrProfil(t, tmpDir, "bruno", true)
			// Unlesbares Profil: fail-open, bleibt im Lauf (#2152-Politik).
			kaputt := filepath.Join(tmpDir, "users", "kaputt")
			if err := os.MkdirAll(kaputt, 0755); err != nil {
				t.Fatalf("mkdir: %v", err)
			}
			if err := os.WriteFile(filepath.Join(kaputt, "user.json"), []byte(`{"id":"kaputt",`), 0644); err != nil {
				t.Fatalf("write: %v", err)
			}

			served, logText := fanOutFuerJob(t, s, job.jobID, job.path)

			if got := strings.Join(served, ","); got != "aktiv,kaputt" {
				t.Errorf("AC-11/%s: Fan-out bediente %v, erwartet exakt [aktiv kaputt] "+
					"(gesperrt ausgelassen, unlesbares Profil fail-open bedient)", job.jobID, served)
			}
			// Testaufbau-Kontrolle (heute gruen): die Logumleitung greift — der
			// bestehende fail-open-Log fuer das unlesbare Profil ist sichtbar.
			if !strings.Contains(logText, "kaputt") {
				t.Fatalf("Testaufbau: Logumleitung greift nicht (kein Eintrag zum unlesbaren Profil). Log:\n%s", logText)
			}
			if !logNenntSperre(logText, "bruno") {
				t.Errorf("AC-11/%s: keine Logzeile nennt den gesperrten Nutzer samt Grund "+
					"(\"disabled\"/\"gesperrt\"). Log:\n%s", job.jobID, logText)
			}
		})
	}
}
