package scheduler

// TDD RED: Issue #1676 Scheibe S1 — Premium-SMS Rueckkanal, Go-Cron-Eintrag.
// Spec: docs/specs/modules/feat_1676_s1_premium_sms_rueckkanal.md v1.1
//
// AC-9: Given der neue Cron-Job premium_sms_poll ist registriert / When
// GET /api/scheduler/status nach einem Lauf abgefragt wird / Then erscheint
// der Job mit frischem last_run — allein durch s.recordRun(...), ohne dass
// der neue Code selbst Observability-Felder pflegt.
//
// Muss FEHLSCHLAGEN bis Scheduler.premiumSmsPoll() existiert (Compile-Fehler).
// Vorbild: TestInboundCommandsRecordsOkStatus (scheduler_test.go), das
// dieselbe recordRun-Buchführung für "inbound_command_poll" prüft.
// Ausführung (Overlay, siehe RED-Artefakt): go test -overlay=... -run TestPremiumSmsPoll ./internal/scheduler/...

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/henemm/gregor-api/internal/config"
)

// AC-9: HTTP 200 vom globalen Trigger-Endpoint -> lastRuns["premium_sms_poll"]
// mit Status "ok" — analog TestInboundCommandsRecordsOkStatus.
func TestPremiumSmsPollRecordsOkStatus(t *testing.T) {
	var calledPath string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calledPath = r.URL.Path
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, `{"status":"ok"}`)
	}))
	defer server.Close()

	cfg := &config.Config{
		PythonCoreURL:     server.URL,
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStoreWithUsers(t, "alice", "bob"))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}

	sched.premiumSmsPoll()

	if !strings.HasPrefix(calledPath, "/api/scheduler/inbound-sms") {
		t.Errorf("erwartet Trigger-Pfad /api/scheduler/inbound-sms, gesehen: %q", calledPath)
	}

	sched.mu.RLock()
	defer sched.mu.RUnlock()
	lr, ok := sched.lastRuns["premium_sms_poll"]
	if !ok {
		t.Fatal("premiumSmsPoll() sollte lastRuns unter dem Schluessel 'premium_sms_poll' fuehren")
	}
	if lr.Status != "ok" {
		t.Fatalf("erwartet Status 'ok', bekam %q (error=%q)", lr.Status, lr.Error)
	}
}

// AC-9: Status() exponiert den Job mit last_run nach einem erfolgreichen Lauf.
func TestPremiumSmsPollExposedInStatus(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, `{"status":"ok"}`)
	}))
	defer server.Close()

	cfg := &config.Config{
		PythonCoreURL:     server.URL,
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStoreWithUsers(t, "alice"))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}

	sched.premiumSmsPoll()

	status := sched.Status()
	jobs, ok := status["jobs"].([]map[string]any)
	if !ok {
		t.Fatalf("Status()[\"jobs\"] hat unerwarteten Typ: %T", status["jobs"])
	}

	found := false
	for _, job := range jobs {
		if job["id"] == "premium_sms_poll" {
			found = true
			if job["last_run"] == nil {
				t.Error("premium_sms_poll: last_run sollte nach einem Lauf gesetzt sein, ist nil")
			}
		}
	}
	if !found {
		t.Fatal("premium_sms_poll ist nicht in Status()[\"jobs\"] enthalten — Cron-Eintrag fehlt")
	}
}

// ---------------------------------------------------------------------------
// Fix F002 (#1676 S1): der Python-Endpunkt meldet einen Lernfehlschlag mit
// HTTP 200 UND "failed"/"status" im Antwortkoerper (Hausnorm, Issue
// #766/#1290) -- premiumSmsPoll() muss diesen Koerper auswerten, sonst
// bleibt ein DAUERHAFTER Fehlschlag unsichtbar im Status.
// ---------------------------------------------------------------------------

// Fix F002: Given der Python-Endpunkt antwortet mit HTTP 200 und
// "failed" > 0 im Antwortkoerper / When premiumSmsPoll() laeuft / Then
// verbucht recordRun() den Lauf NICHT als "ok" und /api/scheduler/status
// zeigt den Fehlschlag.
func TestPremiumSmsPollRecordsFailureWhenLearnFailuresReported(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, `{"status":"partial","count":0,"failed":1}`)
	}))
	defer server.Close()

	cfg := &config.Config{
		PythonCoreURL:     server.URL,
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStoreWithUsers(t, "alice"))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}

	sched.premiumSmsPoll()

	sched.mu.RLock()
	lr, ok := sched.lastRuns["premium_sms_poll"]
	sched.mu.RUnlock()
	if !ok {
		t.Fatal("premiumSmsPoll() sollte lastRuns unter dem Schluessel 'premium_sms_poll' fuehren")
	}
	// F004 (Adversary, #1676 S1): "failed > 0" ist die HAERTERE Klassifikation
	// (harter Fehler) als ein blosser "status == partial" ohne failed (s.
	// TestPremiumSmsPollRecordsPartialStatusWhenStatusPartialWithoutFailed
	// unten) -- ein Test, der nur "nicht ok" verlangt, faengt nicht, wenn der
	// Failed>0-Zweig entfernt wird und der weichere partial-Fallback
	// denselben Fall unbemerkt auffaengt.
	if lr.Status != "error" {
		t.Fatalf("ein gemeldeter Lernfehlschlag (failed=1) muss als Status "+
			"'error' verbucht werden (haertere Klassifikation als 'partial'), bekam %q", lr.Status)
	}

	status := sched.Status()
	jobs, ok := status["jobs"].([]map[string]any)
	if !ok {
		t.Fatalf("Status()[\"jobs\"] hat unerwarteten Typ: %T", status["jobs"])
	}
	found := false
	for _, job := range jobs {
		if job["id"] != "premium_sms_poll" {
			continue
		}
		found = true
		lastRun, ok := job["last_run"].(map[string]any)
		if !ok {
			t.Fatalf("premium_sms_poll: last_run hat unerwarteten Typ: %T", job["last_run"])
		}
		if lastRun["status"] != "error" {
			t.Errorf("/api/scheduler/status muss den Lernfehlschlag als "+
				"'error' zeigen, last_run=%+v", lastRun)
		}
	}
	if !found {
		t.Fatal("premium_sms_poll ist nicht in Status()[\"jobs\"] enthalten")
	}
}

// F004 (Adversary, #1676 S1): Gegenprobe zum "error"-Zweig oben -- ein
// Antwortkoerper mit status=="partial" OHNE failed muss als der WEICHERE
// Job-Status "partial" verbucht werden, nicht als "error". Trennt beide
// Zweige der Go-Klassifikation (triggerPremiumSmsPollEndpoint) sauber
// voneinander, statt nur "irgendwie nicht ok" zu verlangen. Dass der
// Python-Endpunkt dieses Muster (status=partial ohne failed) heute nicht
// erzeugt, ist kein Gegenargument: der Go-Zweig existiert (Hausnorm
// triggerEndpointForUser(), Issue #1447 S2a) und soll sich definiert
// verhalten.
func TestPremiumSmsPollRecordsPartialStatusWhenStatusPartialWithoutFailed(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, `{"status":"partial","count":1,"failed":0}`)
	}))
	defer server.Close()

	cfg := &config.Config{
		PythonCoreURL:     server.URL,
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStoreWithUsers(t, "alice"))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}

	sched.premiumSmsPoll()

	sched.mu.RLock()
	lr, ok := sched.lastRuns["premium_sms_poll"]
	sched.mu.RUnlock()
	if !ok {
		t.Fatal("premiumSmsPoll() sollte lastRuns unter dem Schluessel 'premium_sms_poll' fuehren")
	}
	if lr.Status != "partial" {
		t.Fatalf("status=partial ohne failed muss als Job-Status 'partial' "+
			"verbucht werden (weicher als 'error'), bekam %q", lr.Status)
	}
}
