package scheduler

// ---------------------------------------------------------------------------
// Issue #1912 — Timeout ist kein Ausfallsignal
// ---------------------------------------------------------------------------
//
// Spec: docs/specs/modules/fix_1912_scheduler_briefing_timeout.md (Fassung 2.0)
//
// triggerEndpointForUser() wertet heute JEDEN Transportfehler als harten
// Fehler (fmt.Errorf("HTTP error: %w", err)) — recordRun() setzt "error",
// tripReports() alarmiert. Diese Suite verlangt: ein echter Timeout
// (net.Error mit Timeout()==true) wird stattdessen als *partialRunError
// klassifiziert -> Status "partial", kein MQ-Alarm, kein Heartbeat-Ping. Eine
// verweigerte Verbindung (kein Timeout, Core schlicht nicht da) bleibt ein
// harter Fehler. Zusaetzlich: der Client-Timeout steigt von 120s auf 3000s.
//
// Testdatei liegt per go-overlay (Replace) auf
// internal/scheduler/timeout_kein_ausfall_test.go — edit_gate blockt .go-
// Schreibzugriffe ausserhalb von test-Verzeichnissen in Phase 5, siehe #1396.

import (
	"errors"
	"fmt"
	"net"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
)

// slowServer antwortet nach delay mit HTTP 200 — simuliert einen Core, der
// (zu) lange braucht, dabei aber erfolgreich arbeitet (Kernaussage der Spec:
// "kann dabei erfolgreich arbeiten, wie am 2026-08-16 geschehen").
func slowServer(t *testing.T, delay time.Duration) *httptest.Server {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(delay)
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, `{"status":"ok","count":1}`)
	}))
	t.Cleanup(srv.Close)
	return srv
}

// AC-1 (Transport-Ebene): triggerEndpointForUser() klassifiziert einen
// Timeout als *partialRunError, nicht als harten Fehler.
func TestTriggerEndpoint_TimeoutIsPartialNotHardError(t *testing.T) {
	srv := slowServer(t, 300*time.Millisecond)

	cfg := &config.Config{
		PythonCoreURL:     srv.URL,
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	sched.client = &http.Client{Timeout: 50 * time.Millisecond}

	err = sched.triggerEndpointForUser("/api/scheduler/trip-reports", "default")
	if err == nil {
		t.Fatal("expected a timeout error, got nil")
	}
	// Gegenprobe: der zugrundeliegende Fehler MUSS tatsaechlich ein Timeout
	// sein (net.Error mit Timeout()==true) -- sonst waere der Test blind
	// dafuer, ob die Implementierung nur geraten hat.
	var netErr net.Error
	if !errors.As(err, &netErr) || !netErr.Timeout() {
		t.Fatalf("test setup broken: underlying error is not a net.Error timeout: %T: %v", err, err)
	}
	var pe *partialRunError
	if !errors.As(err, &pe) {
		t.Fatalf("expected timeout to be classified as *partialRunError (Issue #1912 AC-1), "+
			"got %T: %v", err, err)
	}
}

// AC-1 (Job-Ebene): tripReports() endet nach Timeout mit Status "partial",
// nicht "error" -- und feuert 0 MQ-Alarme.
func TestTripReports_TimeoutRecordsPartialAndNoAlert(t *testing.T) {
	srv := slowServer(t, 300*time.Millisecond)

	cfg := &config.Config{
		PythonCoreURL:     srv.URL,
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	sched.client = &http.Client{Timeout: 50 * time.Millisecond}

	var alertCount atomic.Int32
	sched.notifier = func(_, _, _, _, _ string) error {
		alertCount.Add(1)
		return nil
	}

	sched.tripReports()

	sched.mu.RLock()
	lr := sched.lastRuns["trip_reports_hourly"]
	sched.mu.RUnlock()
	if lr == nil {
		t.Fatal("expected a recorded run for trip_reports_hourly")
	}
	if lr.Status != "partial" {
		t.Fatalf("expected status 'partial' after timeout (Issue #1912 AC-1), got %q (error=%q)",
			lr.Status, lr.Error)
	}
	if got := alertCount.Load(); got != 0 {
		t.Fatalf("expected 0 MQ alerts after timeout (Issue #1912 AC-1), got %d", got)
	}
}

// AC-2: Nach einem Timeout-Lauf (Status "partial") pingt briefingDispatch()
// den Heartbeat NICHT -- die Entwarnung bleibt an den echten Erfolg
// gebunden, ein dauerhafter Ausfall bleibt ueber den ausbleibenden Heartbeat
// sichtbar.
func TestBriefingDispatch_TimeoutSkipsHeartbeat(t *testing.T) {
	srv := slowServer(t, 300*time.Millisecond)

	var heartbeatCalls atomic.Int32
	heartbeatServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		heartbeatCalls.Add(1)
		w.WriteHeader(http.StatusOK)
	}))
	defer heartbeatServer.Close()

	cfg := &config.Config{
		PythonCoreURL:           srv.URL,
		SchedulerTimezone:       "Europe/Vienna",
		HeartbeatComparePresets: heartbeatServer.URL,
	}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	sched.client = &http.Client{Timeout: 50 * time.Millisecond}

	sched.briefingDispatch()

	if got := heartbeatCalls.Load(); got != 0 {
		t.Fatalf("expected 0 heartbeat pings after timeout run (Issue #1912 AC-2), got %d", got)
	}
}

// AC-3: Regressionsschutz -- HTTP 500 bleibt ein harter Fehler mit genau
// einem MQ-Alarm (priority=high, recipient=infra) und Status "error".
func TestTripReports_HTTP500StillAlertsHigh(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		fmt.Fprint(w, `{"error":"internal server error"}`)
	}))
	defer server.Close()

	cfg := &config.Config{
		PythonCoreURL:     server.URL,
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}

	var alertCount atomic.Int32
	var lastRecipient, lastPriority, lastSubject string
	sched.notifier = func(_, recipient, priority, subject, _ string) error {
		alertCount.Add(1)
		lastRecipient, lastPriority, lastSubject = recipient, priority, subject
		return nil
	}

	sched.tripReports()

	sched.mu.RLock()
	lr := sched.lastRuns["trip_reports_hourly"]
	sched.mu.RUnlock()
	if lr == nil || lr.Status != "error" {
		t.Fatalf("expected status 'error' for HTTP 500, got %+v", lr)
	}
	if got := alertCount.Load(); got != 1 {
		t.Fatalf("expected exactly 1 MQ alert for HTTP 500 (Issue #1912 AC-3), got %d", got)
	}
	if lastRecipient != "infra" {
		t.Fatalf("expected alert recipient 'infra', got %q", lastRecipient)
	}
	if lastPriority != "high" {
		t.Fatalf("expected alert priority 'high', got %q", lastPriority)
	}
	if !strings.Contains(lastSubject, "Trip-Briefing-Totalausfall (#1346)") {
		t.Fatalf("expected alert subject to reference #1346, got %q", lastSubject)
	}
}

// AC-4: Verbindung verweigert (kein Timeout, Core schlicht nicht da) bleibt
// ein harter Fehler -- darf NICHT als "partial" durchgehen, obwohl beide
// Faelle als *http.Client-Fehler beim Post() ankommen.
func TestTripReports_ConnectionRefusedStaysHardError(t *testing.T) {
	cfg := &config.Config{
		PythonCoreURL:     "http://127.0.0.1:19999", // nothing listening
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	sched.client = &http.Client{Timeout: 2 * time.Second}

	var alertCount atomic.Int32
	sched.notifier = func(_, _, _, _, _ string) error {
		alertCount.Add(1)
		return nil
	}

	sched.tripReports()

	sched.mu.RLock()
	lr := sched.lastRuns["trip_reports_hourly"]
	sched.mu.RUnlock()
	if lr == nil {
		t.Fatal("expected a recorded run for trip_reports_hourly")
	}
	if lr.Status != "error" {
		t.Fatalf("connection refused must stay 'error', not 'partial' (Issue #1912 AC-4), got %q",
			lr.Status)
	}
	if got := alertCount.Load(); got != 1 {
		t.Fatalf("expected exactly 1 MQ alert for connection refused (Issue #1912 AC-4), got %d", got)
	}
}

// AC-5: Regressionsschutz -- ein Antwortkoerper mit failed>0 bleibt ein
// harter Fehler mit Alarm (Issue #1447 Verhalten unveraendert).
func TestTripReports_FailedBodyStillAlerts(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, `{"status":"partial","count":2,"failed":2}`)
	}))
	defer server.Close()

	cfg := &config.Config{
		PythonCoreURL:     server.URL,
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}

	var alertCount atomic.Int32
	sched.notifier = func(_, _, _, _, _ string) error {
		alertCount.Add(1)
		return nil
	}

	sched.tripReports()

	sched.mu.RLock()
	lr := sched.lastRuns["trip_reports_hourly"]
	sched.mu.RUnlock()
	if lr == nil || lr.Status != "error" {
		t.Fatalf("expected status 'error' for failed>0 body (Issue #1912 AC-5, #1447 unchanged), got %+v", lr)
	}
	if got := alertCount.Load(); got != 1 {
		t.Fatalf("expected exactly 1 MQ alert for failed>0 body (Issue #1912 AC-5), got %d", got)
	}
}

// AC-6: Client-Timeout liegt bei 3000s (50min), nicht mehr bei 120s. Direkte
// Feldpruefung statt eines realen 3000s-Laufs (kein Realzeit-Warten in Tests,
// PO-Vorgabe aus dem Spawn-Auftrag) -- s.client.Timeout ist der Mechanismus
// selbst, der die HTTP-Aufrufe steuert, keine Kommentar-/Docstring-Aussage.
func TestClientTimeout_Is3000Seconds(t *testing.T) {
	cfg := &config.Config{
		PythonCoreURL:     "http://localhost:8000",
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}

	want := 3000 * time.Second
	if sched.client.Timeout != want {
		t.Fatalf("expected client timeout %v (Issue #1912 AC-6), got %v", want, sched.client.Timeout)
	}
}

// AC-7: Zwei Nutzer, einer schnell erfolgreich, einer im Timeout -> Gesamt-
// status "partial" (Rangfolge error > partial > ok, #1447 S2a), 0 Alarme.
func TestTripReports_MixedFastAndTimeoutUsersYieldsPartial(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		uid := r.URL.Query().Get("user_id")
		if uid == "bob" {
			time.Sleep(300 * time.Millisecond)
		}
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, `{"status":"ok","count":1}`)
	}))
	defer server.Close()

	cfg := &config.Config{
		PythonCoreURL:     server.URL,
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStoreWithUsers(t, "bob"))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	sched.client = &http.Client{Timeout: 50 * time.Millisecond}

	var alertCount atomic.Int32
	sched.notifier = func(_, _, _, _, _ string) error {
		alertCount.Add(1)
		return nil
	}

	sched.tripReports()

	sched.mu.RLock()
	lr := sched.lastRuns["trip_reports_hourly"]
	sched.mu.RUnlock()
	if lr == nil || lr.Status != "partial" {
		t.Fatalf("expected overall status 'partial' for mixed fast+timeout users (Issue #1912 AC-7), got %+v", lr)
	}
	if got := alertCount.Load(); got != 0 {
		t.Fatalf("expected 0 MQ alerts for mixed fast+timeout users (Issue #1912 AC-7), got %d", got)
	}
}

// AC-8: Ein Timeout-Lauf (partial), gefolgt von einem echten Fehler-Lauf
// (HTTP 500) -- der Alarm feuert genau einmal, beim zweiten Lauf. Die
// Flankenerkennung (ok/partial -> error) darf durch den neuen
// partial-Zustand nicht verschluckt werden.
func TestTripReports_TimeoutThenError_AlertsOnlyOnSecondRun(t *testing.T) {
	var mode atomic.Int32 // 0 = timeout, 1 = HTTP 500
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if mode.Load() == 0 {
			time.Sleep(300 * time.Millisecond)
			w.WriteHeader(http.StatusOK)
			fmt.Fprint(w, `{"status":"ok","count":1}`)
			return
		}
		w.WriteHeader(http.StatusInternalServerError)
		fmt.Fprint(w, `{"error":"boom"}`)
	}))
	defer server.Close()

	cfg := &config.Config{
		PythonCoreURL:     server.URL,
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	sched.client = &http.Client{Timeout: 50 * time.Millisecond}

	var alertCount atomic.Int32
	sched.notifier = func(_, _, _, _, _ string) error {
		alertCount.Add(1)
		return nil
	}

	// Lauf 1: Timeout -> partial, kein Alarm.
	sched.tripReports()
	sched.mu.RLock()
	lr1 := sched.lastRuns["trip_reports_hourly"]
	sched.mu.RUnlock()
	if lr1 == nil || lr1.Status != "partial" {
		t.Fatalf("expected 'partial' after run 1 (timeout), got %+v", lr1)
	}
	if got := alertCount.Load(); got != 0 {
		t.Fatalf("expected 0 alerts after run 1 (timeout, Issue #1912 AC-8), got %d", got)
	}

	// Lauf 2: echter Fehler -> error, genau 1 Alarm auf der Flanke.
	mode.Store(1)
	sched.client = &http.Client{Timeout: 2 * time.Second} // Timeout ist hier nicht das Testziel
	sched.tripReports()
	sched.mu.RLock()
	lr2 := sched.lastRuns["trip_reports_hourly"]
	sched.mu.RUnlock()
	if lr2 == nil || lr2.Status != "error" {
		t.Fatalf("expected 'error' after run 2 (HTTP 500), got %+v", lr2)
	}
	if got := alertCount.Load(); got != 1 {
		t.Fatalf("expected exactly 1 alert after run 2 (Issue #1912 AC-8), got %d", got)
	}
}

// ---------------------------------------------------------------------------
// Fix-Loop F002/F003 (Adversary-Verdict BROKEN, Runde 2): die Flankenprüfung
// in tripReports() ging bisher vom unmittelbaren Vorlauf aus -- ein
// "partial"-Zwischenlauf (Timeout) zerreisst diese binäre Annahme. Diese drei
// Tests spielen Sequenzen aus drei Läufen durch und zählen Alarme/Notizen.
// ---------------------------------------------------------------------------

// tripReportsModeServer liefert je nach mode.Load() Timeout (0, via sleep
// über den Client-Timeout hinaus), HTTP 500 (1) oder HTTP 200 (2) -- erlaubt,
// dieselbe Störungs-Sequenz über mehrere sched.tripReports()-Läufe zu fahren.
func tripReportsModeServer(t *testing.T, mode *atomic.Int32, timeoutDelay time.Duration) *httptest.Server {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch mode.Load() {
		case 0:
			time.Sleep(timeoutDelay)
			w.WriteHeader(http.StatusOK)
			fmt.Fprint(w, `{"status":"ok","count":1}`)
		case 1:
			w.WriteHeader(http.StatusInternalServerError)
			fmt.Fprint(w, `{"error":"boom"}`)
		default:
			w.WriteHeader(http.StatusOK)
			fmt.Fprint(w, `{"status":"ok","count":1}`)
		}
	}))
	t.Cleanup(srv.Close)
	return srv
}

// F002: error -> partial(Timeout) -> error ist EINE fortlaufende Störung
// (derselbe HTTP-500-Ausfall, ein Tick timet nur zufällig aus). Vor #1912
// hätte error->error->error wegen der Flankenbedingung nur einmal alarmiert
// -- das muss mit dem "partial"-Zwischenlauf ebenso gelten: genau 1 Alarm.
func TestTripReports_ErrorPartialError_AlertsExactlyOnce(t *testing.T) {
	var mode atomic.Int32 // 0=timeout, 1=error(500), 2=ok
	srv := tripReportsModeServer(t, &mode, 300*time.Millisecond)

	cfg := &config.Config{PythonCoreURL: srv.URL, SchedulerTimezone: "Europe/Vienna"}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}

	var alertCount atomic.Int32
	sched.notifier = func(_, _, _, _, _ string) error {
		alertCount.Add(1)
		return nil
	}

	// Lauf 1: echter Fehler -> error, 1. Alarm auf der Flanke ""->error.
	mode.Store(1)
	sched.client = &http.Client{Timeout: 2 * time.Second}
	sched.tripReports()

	// Lauf 2: derselbe Ausfall timet zufällig aus -> partial, kein Alarm.
	mode.Store(0)
	sched.client = &http.Client{Timeout: 50 * time.Millisecond}
	sched.tripReports()
	sched.mu.RLock()
	lr2 := sched.lastRuns["trip_reports_hourly"]
	sched.mu.RUnlock()
	if lr2 == nil || lr2.Status != "partial" {
		t.Fatalf("expected 'partial' after run 2 (timeout), got %+v", lr2)
	}

	// Lauf 3: derselbe Ausfall wieder als 500 -- KEIN zweiter Alarm, weil es
	// dieselbe fortlaufende Störung ist (Finding F002).
	mode.Store(1)
	sched.client = &http.Client{Timeout: 2 * time.Second}
	sched.tripReports()
	sched.mu.RLock()
	lr3 := sched.lastRuns["trip_reports_hourly"]
	sched.mu.RUnlock()
	if lr3 == nil || lr3.Status != "error" {
		t.Fatalf("expected 'error' after run 3, got %+v", lr3)
	}

	if got := alertCount.Load(); got != 1 {
		t.Fatalf("expected exactly 1 alert for the whole error->partial->error sequence "+
			"(Issue #1912 Finding F002), got %d", got)
	}
}

// F003: error -> partial(Timeout) -> ok muss die Recovery-Notiz "Trip-
// Briefing wieder OK (#1346)" auslösen -- der Dienst läuft tatsächlich
// wieder, infra darf die Entwarnung nicht verlieren, nur weil der letzte
// Zwischenlauf "partial" statt "error" war.
func TestTripReports_ErrorPartialOk_SendsRecoveryNotice(t *testing.T) {
	var mode atomic.Int32 // 0=timeout, 1=error(500), 2=ok
	srv := tripReportsModeServer(t, &mode, 300*time.Millisecond)

	cfg := &config.Config{PythonCoreURL: srv.URL, SchedulerTimezone: "Europe/Vienna"}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}

	var recoveryCount atomic.Int32
	sched.notifier = func(_, _, priority, subject, _ string) error {
		if priority == "normal" && strings.Contains(subject, "Trip-Briefing wieder OK") {
			recoveryCount.Add(1)
		}
		return nil
	}

	// Lauf 1: echter Fehler -> error.
	mode.Store(1)
	sched.client = &http.Client{Timeout: 2 * time.Second}
	sched.tripReports()

	// Lauf 2: Timeout -> partial (derselbe Ausfall, kein neuer Vorfall).
	mode.Store(0)
	sched.client = &http.Client{Timeout: 50 * time.Millisecond}
	sched.tripReports()

	// Lauf 3: echter Erfolg -> ok. Erwartet: Recovery-Notiz feuert, obwohl
	// der unmittelbare Vorlauf "partial" war.
	mode.Store(2)
	sched.client = &http.Client{Timeout: 2 * time.Second}
	sched.tripReports()
	sched.mu.RLock()
	lr3 := sched.lastRuns["trip_reports_hourly"]
	sched.mu.RUnlock()
	if lr3 == nil || lr3.Status != "ok" {
		t.Fatalf("expected 'ok' after run 3, got %+v", lr3)
	}

	if got := recoveryCount.Load(); got != 1 {
		t.Fatalf("expected exactly 1 recovery notice for error->partial->ok "+
			"(Issue #1912 Finding F003), got %d", got)
	}
}

// Gegenprobe zu F002: ok -> partial(Timeout) -> error muss weiterhin genau 1
// Alarm auslösen -- ein NEU auftretender Fehler nach einer Kette aus
// "partial"-Läufen darf durch lastHardStatus nicht dauerhaft verschluckt
// werden.
func TestTripReports_OkPartialError_NewFailureStillAlertsOnce(t *testing.T) {
	var mode atomic.Int32 // 0=timeout, 1=error(500), 2=ok
	srv := tripReportsModeServer(t, &mode, 300*time.Millisecond)

	cfg := &config.Config{PythonCoreURL: srv.URL, SchedulerTimezone: "Europe/Vienna"}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}

	var alertCount atomic.Int32
	sched.notifier = func(_, _, _, _, _ string) error {
		alertCount.Add(1)
		return nil
	}

	// Lauf 1: echter Erfolg -> ok, kein Alarm.
	mode.Store(2)
	sched.client = &http.Client{Timeout: 2 * time.Second}
	sched.tripReports()

	// Lauf 2 und 3: zwei Timeout-Ticks hintereinander -> partial, partial --
	// lastHardStatus bleibt "ok" (darf durch die Kette nicht einfrieren).
	mode.Store(0)
	sched.client = &http.Client{Timeout: 50 * time.Millisecond}
	sched.tripReports()
	sched.tripReports()

	// Lauf 4: neu auftretender echter Fehler -> error, MUSS alarmieren.
	mode.Store(1)
	sched.client = &http.Client{Timeout: 2 * time.Second}
	sched.tripReports()
	sched.mu.RLock()
	lr4 := sched.lastRuns["trip_reports_hourly"]
	sched.mu.RUnlock()
	if lr4 == nil || lr4.Status != "error" {
		t.Fatalf("expected 'error' after run 4, got %+v", lr4)
	}

	if got := alertCount.Load(); got != 1 {
		t.Fatalf("expected exactly 1 alert for the new failure after ok->partial->partial "+
			"(Issue #1912 Finding F002 Gegenprobe), got %d", got)
	}
}

// ---------------------------------------------------------------------------
// Geteilter Client (Spec, Abschnitt "Geteilter Client"): dieselbe
// Timeout-Klassifikation gilt auch fuer triggerGlobalEndpoint() und
// triggerPremiumSmsPollEndpoint() -- die #1912-ACs decken nur
// triggerEndpointForUser() ab, diese Tests schliessen die Luecke an den
// anderen beiden Aufrufstellen von s.client.
// ---------------------------------------------------------------------------

// triggerGlobalEndpoint(): ein Timeout wird als *partialRunError klassifiziert.
func TestTriggerGlobalEndpoint_TimeoutIsPartialNotHardError(t *testing.T) {
	srv := slowServer(t, 300*time.Millisecond)

	cfg := &config.Config{
		PythonCoreURL:     srv.URL,
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	sched.client = &http.Client{Timeout: 50 * time.Millisecond}

	err = sched.triggerGlobalEndpoint("/api/scheduler/inbound-commands")
	if err == nil {
		t.Fatal("expected a timeout error, got nil")
	}
	var netErr net.Error
	if !errors.As(err, &netErr) || !netErr.Timeout() {
		t.Fatalf("test setup broken: underlying error is not a net.Error timeout: %T: %v", err, err)
	}
	var pe *partialRunError
	if !errors.As(err, &pe) {
		t.Fatalf("expected timeout to be classified as *partialRunError (Issue #1912, geteilter Client), "+
			"got %T: %v", err, err)
	}
}

// triggerGlobalEndpoint(): eine verweigerte Verbindung bleibt ein harter
// Fehler -- Gegenprobe zur Timeout-Klassifikation, analog AC-4.
func TestTriggerGlobalEndpoint_ConnectionRefusedStaysHardError(t *testing.T) {
	cfg := &config.Config{
		PythonCoreURL:     "http://127.0.0.1:19999", // nothing listening
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	sched.client = &http.Client{Timeout: 2 * time.Second}

	err = sched.triggerGlobalEndpoint("/api/scheduler/inbound-commands")
	if err == nil {
		t.Fatal("expected a connection error, got nil")
	}
	var pe *partialRunError
	if errors.As(err, &pe) {
		t.Fatalf("connection refused must NOT be classified as *partialRunError "+
			"(Issue #1912, geteilter Client), got %T: %v", err, err)
	}
}

// triggerPremiumSmsPollEndpoint(): ein Timeout wird als *partialRunError
// klassifiziert -- dieselbe Unterscheidung wie an den anderen zwei Stellen.
func TestTriggerPremiumSmsPollEndpoint_TimeoutIsPartialNotHardError(t *testing.T) {
	srv := slowServer(t, 300*time.Millisecond)

	cfg := &config.Config{
		PythonCoreURL:     srv.URL,
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	sched.client = &http.Client{Timeout: 50 * time.Millisecond}

	err = sched.triggerPremiumSmsPollEndpoint()
	if err == nil {
		t.Fatal("expected a timeout error, got nil")
	}
	var netErr net.Error
	if !errors.As(err, &netErr) || !netErr.Timeout() {
		t.Fatalf("test setup broken: underlying error is not a net.Error timeout: %T: %v", err, err)
	}
	var pe *partialRunError
	if !errors.As(err, &pe) {
		t.Fatalf("expected timeout to be classified as *partialRunError (Issue #1912, geteilter Client), "+
			"got %T: %v", err, err)
	}
}

// triggerPremiumSmsPollEndpoint(): eine verweigerte Verbindung bleibt ein
// harter Fehler.
func TestTriggerPremiumSmsPollEndpoint_ConnectionRefusedStaysHardError(t *testing.T) {
	cfg := &config.Config{
		PythonCoreURL:     "http://127.0.0.1:19999", // nothing listening
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	sched.client = &http.Client{Timeout: 2 * time.Second}

	err = sched.triggerPremiumSmsPollEndpoint()
	if err == nil {
		t.Fatal("expected a connection error, got nil")
	}
	var pe *partialRunError
	if errors.As(err, &pe) {
		t.Fatalf("connection refused must NOT be classified as *partialRunError "+
			"(Issue #1912, geteilter Client), got %T: %v", err, err)
	}
}
