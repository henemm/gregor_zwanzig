package scheduler

// ---------------------------------------------------------------------------
// Fix #2149 Scheibe A — Oeffentlicher Status bleibt anonym
//
// Spec: docs/specs/modules/fix_2149_scheduler_nutzer_sichtbarkeit.md,
// Abschnitt 3 ("Redaktion des oeffentlichen Fehlertexts").
//
// AC-9 ist bewusst NICHT durch einen HTTP-500-Fall ersetzbar: err aus
// s.client.Post(...) ist bei einer verweigerten Verbindung ein *url.Error,
// dessen Error()-Text IMMER die volle angefragte URL inkl. ?user_id=...
// enthaelt (Format `Post "<url>": <ursache>`) -- ein reines Weglassen von
// userID im umgebenden fmt.Errorf reicht NICHT, weil %w den vollen
// err.Error()-Text einbettet.
// ---------------------------------------------------------------------------

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/store"
)

// AC-6: ein Nutzer scheitert 3x in Folge (HTTP 500, harter Fehler) --
// die oeffentliche Status-Antwort darf an KEINER Stelle irgendeine
// Nutzerkennung enthalten, waehrend das Aggregat failing=1 zeigt.
func TestSchedulerStatus_HTTP500Error_NoUserIDLeak(t *testing.T) {
	ctrl := &userAlarmControl{}
	server := newUserAlarmServer(ctrl)
	defer server.Close()

	tmpDir := t.TempDir()
	mkUsers(t, tmpDir, "alice", "bob")

	cfg := &config.Config{PythonCoreURL: server.URL, SchedulerTimezone: "Europe/Vienna"}
	sched, err := New(cfg, store.New(tmpDir, "alice"))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	sched.notifier = func(_, _, _, _, _ string) error { return nil }

	ctrl.setFail("bob")
	sched.alertChecks()
	sched.alertChecks()
	sched.alertChecks()

	status := sched.Status()
	raw, err := json.Marshal(status)
	if err != nil {
		t.Fatalf("json.Marshal(status) failed: %v", err)
	}
	body := string(raw)
	if strings.Contains(body, "bob") {
		t.Fatalf("public status JSON leaks user id 'bob' (AC-6): %s", body)
	}
	if strings.Contains(body, "alice") {
		t.Fatalf("public status JSON leaks user id 'alice' (AC-6): %s", body)
	}

	jobs, ok := status["jobs"].([]map[string]any)
	if !ok {
		t.Fatalf("status jobs should be []map[string]any, got %T", status["jobs"])
	}
	var job map[string]any
	for _, j := range jobs {
		if j["id"] == "alert_checks" {
			job = j
		}
	}
	if job == nil {
		t.Fatal("alert_checks job not found in status")
	}
	users, ok := job["users"].(map[string]any)
	if !ok || users == nil {
		t.Fatalf("expected 'users' aggregate on alert_checks job (AC-6), got %v", job["users"])
	}
	if users["failing"] != 1 {
		t.Fatalf("expected users.failing=1 for the failing user (AC-6), got %v", users["failing"])
	}
}

// AC-9: ein Nutzer scheitert an einem Transportfehler (Verbindung
// verweigert, kein HTTP-Statuscode) -- auch dieser Fehlertext darf keine
// Nutzerkennung enthalten, obwohl die zugrundeliegende *url.Error-Meldung
// die volle angefragte URL inkl. user_id traegt.
func TestSchedulerStatus_TransportError_NoUserIDLeak(t *testing.T) {
	tmpDir := t.TempDir()
	mkUsers(t, tmpDir, "alice")

	// Server sofort schliessen, sodass der Post auf eine verweigerte
	// Verbindung trifft (kein HTTP-Statuscode, echter Transportfehler).
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	server.Close()

	cfg := &config.Config{PythonCoreURL: server.URL, SchedulerTimezone: "Europe/Vienna"}
	sched, err := New(cfg, store.New(tmpDir, "alice"))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	sched.client = &http.Client{Timeout: 2 * time.Second}
	sched.notifier = func(_, _, _, _, _ string) error { return nil }

	sched.alertChecks()

	status := sched.Status()
	raw, err := json.Marshal(status)
	if err != nil {
		t.Fatalf("json.Marshal(status) failed: %v", err)
	}
	body := string(raw)
	if strings.Contains(body, "user_id") {
		t.Fatalf("expected no 'user_id' substring in status JSON after a transport error "+
			"(AC-9, *url.Error trap), got: %s", body)
	}
	if strings.Contains(body, "alice") {
		t.Fatalf("expected no user id 'alice' leaked in status JSON after a transport error "+
			"(AC-9), got: %s", body)
	}
}

// F-ADV2 (HIGH, Adversary Runde 2): ein Nutzer scheitert an einem ECHTEN
// Timeout (isTimeoutTransportError-Zweig in triggerEndpointForUser) -- diese
// Konstruktionsstelle ist die einzige der vier redigierten Stellen, die
// bislang von keinem Test angesteuert wurde (AC-9 traf nur "connection
// refused", nie den Timeout-Zweig). Analog zu timeout_kein_ausfall_test.go:
// slowServer + kurzer Client-Timeout erzwingt echten net.Error-Timeout.
func TestSchedulerStatus_TimeoutError_NoUserIDLeak(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(300 * time.Millisecond)
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, `{"status":"ok","count":1}`)
	}))
	defer server.Close()

	tmpDir := t.TempDir()
	mkUsers(t, tmpDir, "alice")

	cfg := &config.Config{PythonCoreURL: server.URL, SchedulerTimezone: "Europe/Vienna"}
	sched, err := New(cfg, store.New(tmpDir, "alice"))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	sched.client = &http.Client{Timeout: 50 * time.Millisecond}
	sched.notifier = func(_, _, _, _, _ string) error { return nil }

	sched.alertChecks()

	status := sched.Status()
	raw, err := json.Marshal(status)
	if err != nil {
		t.Fatalf("json.Marshal(status) failed: %v", err)
	}
	body := string(raw)
	if strings.Contains(body, "user_id") {
		t.Fatalf("expected no 'user_id' substring in status JSON after a timeout error "+
			"(F-ADV2), got: %s", body)
	}
	if strings.Contains(body, "alice") {
		t.Fatalf("expected no user id 'alice' leaked in status JSON after a timeout error "+
			"(F-ADV2), got: %s", body)
	}

	// Gegenprobe: der Test muss tatsaechlich den Timeout-Zweig getroffen
	// haben (Status "partial", Issue #1912), sonst waere er blind dafuer, ob
	// er den richtigen Code-Pfad ueberhaupt erreicht.
	jobs, ok := status["jobs"].([]map[string]any)
	if !ok {
		t.Fatalf("status jobs should be []map[string]any, got %T", status["jobs"])
	}
	var job map[string]any
	for _, j := range jobs {
		if j["id"] == "alert_checks" {
			job = j
		}
	}
	if job == nil {
		t.Fatal("alert_checks job not found in status")
	}
	lastRun, ok := job["last_run"].(map[string]any)
	if !ok || lastRun["status"] != "partial" {
		t.Fatalf("test setup broken: expected alert_checks last_run.status='partial' after a "+
			"timeout (sanity check that the timeout branch was actually hit), got %v", job["last_run"])
	}
}

// F003 (HIGH, Adversary-Fix-Runde): ein fachlicher Fehlschlag ueber den
// Antwortkoerper (HTTP 200, {"failed":1,...}) durchlaeuft eine ANDERE
// Konstruktionsstelle in triggerEndpointForUser() als AC-6 (HTTP-Statuscode)
// und AC-9 (Transportfehler) -- bislang von keinem Test abgedeckt.
func TestSchedulerStatus_FailedBodyError_NoUserIDLeak(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		uid := r.URL.Query().Get("user_id")
		w.WriteHeader(http.StatusOK)
		if uid == "bob" {
			fmt.Fprint(w, `{"status":"error","count":1,"failed":1}`)
			return
		}
		fmt.Fprint(w, `{"status":"ok","count":1}`)
	}))
	defer server.Close()

	tmpDir := t.TempDir()
	mkUsers(t, tmpDir, "alice", "bob")

	cfg := &config.Config{PythonCoreURL: server.URL, SchedulerTimezone: "Europe/Vienna"}
	sched, err := New(cfg, store.New(tmpDir, "alice"))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	sched.notifier = func(_, _, _, _, _ string) error { return nil }

	sched.alertChecks()

	status := sched.Status()
	raw, err := json.Marshal(status)
	if err != nil {
		t.Fatalf("json.Marshal(status) failed: %v", err)
	}
	body := string(raw)
	if strings.Contains(body, "user_id") {
		t.Fatalf("expected no 'user_id' substring in status JSON after a failed>0 body "+
			"(F003), got: %s", body)
	}
	if strings.Contains(body, "bob") {
		t.Fatalf("public status JSON leaks user id 'bob' after a failed>0 body (F003): %s", body)
	}
}

// F003 (HIGH, Adversary-Fix-Runde): status="partial" im Antwortkoerper (HTTP
// 200) durchlaeuft ebenfalls eine eigene Konstruktionsstelle in
// triggerEndpointForUser() -- separat von AC-9 (Transportfehler-Timeout).
func TestSchedulerStatus_PartialBodyError_NoUserIDLeak(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		uid := r.URL.Query().Get("user_id")
		w.WriteHeader(http.StatusOK)
		if uid == "bob" {
			fmt.Fprint(w, `{"status":"partial","count":1}`)
			return
		}
		fmt.Fprint(w, `{"status":"ok","count":1}`)
	}))
	defer server.Close()

	tmpDir := t.TempDir()
	mkUsers(t, tmpDir, "alice", "bob")

	cfg := &config.Config{PythonCoreURL: server.URL, SchedulerTimezone: "Europe/Vienna"}
	sched, err := New(cfg, store.New(tmpDir, "alice"))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	sched.notifier = func(_, _, _, _, _ string) error { return nil }

	sched.alertChecks()

	status := sched.Status()
	raw, err := json.Marshal(status)
	if err != nil {
		t.Fatalf("json.Marshal(status) failed: %v", err)
	}
	body := string(raw)
	if strings.Contains(body, "user_id") {
		t.Fatalf("expected no 'user_id' substring in status JSON after a partial-status "+
			"body (F003), got: %s", body)
	}
	if strings.Contains(body, "bob") {
		t.Fatalf("public status JSON leaks user id 'bob' after a partial-status body "+
			"(F003): %s", body)
	}
}

// Regressionsschutz gegen die #1447-"overlap"-Falle, hier auf "users"
// uebertragen: trip_reports_hourly erscheint AUSSCHLIESSLICH im subs-
// Expansionszweig von Status(), alert_checks im Hauptzweig -- ein
// gemeinsamer Helfer muss das "users"-Aggregat in BEIDEN Zweigen einhaengen.
// Globale Jobs ohne Nutzer-Fan-out (z.B. inbound_command_poll) duerfen das
// Feld gar nicht erst tragen.
func TestSchedulerStatus_UsersAggregate_PresentInBothMainAndSubsBranch(t *testing.T) {
	ctrl := &userAlarmControl{}
	server := newUserAlarmServer(ctrl)
	defer server.Close()

	tmpDir := t.TempDir()
	mkUsers(t, tmpDir, "alice", "bob")

	cfg := &config.Config{PythonCoreURL: server.URL, SchedulerTimezone: "Europe/Vienna"}
	sched, err := New(cfg, store.New(tmpDir, "alice"))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	sched.notifier = func(_, _, _, _, _ string) error { return nil }
	sched.Start()
	defer sched.Stop()

	sched.alertChecks() // Hauptzweig-Job
	sched.tripReports() // subs-Zweig-Job (trip_reports_hourly)

	status := sched.Status()
	jobs, ok := status["jobs"].([]map[string]any)
	if !ok {
		t.Fatalf("status jobs should be []map[string]any, got %T", status["jobs"])
	}
	var alertJob, tripJob, inboundJob map[string]any
	for _, j := range jobs {
		switch j["id"] {
		case "alert_checks":
			alertJob = j
		case "trip_reports_hourly":
			tripJob = j
		case "inbound_command_poll":
			inboundJob = j
		}
	}
	if alertJob == nil {
		t.Fatal("alert_checks job not found in status (main branch)")
	}
	if tripJob == nil {
		t.Fatal("trip_reports_hourly job not found in status (subs branch)")
	}
	if inboundJob == nil {
		t.Fatal("inbound_command_poll job not found in status (global job)")
	}

	if _, ok := alertJob["users"].(map[string]any); !ok {
		t.Fatalf("expected 'users' aggregate on alert_checks (main branch), got %v", alertJob["users"])
	}
	if _, ok := tripJob["users"].(map[string]any); !ok {
		t.Fatalf("expected 'users' aggregate on trip_reports_hourly (subs branch), got %v", tripJob["users"])
	}
	if _, present := inboundJob["users"]; present {
		t.Fatalf("expected NO 'users' field on global job inbound_command_poll "+
			"(no user fan-out), got %v", inboundJob["users"])
	}
}
