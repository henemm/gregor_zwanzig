package scheduler

// ---------------------------------------------------------------------------
// Fix #2149 Scheibe A — Pro-Nutzer-Fehlerserie + Alarm-Flanke
//
// Spec: docs/specs/modules/fix_2149_scheduler_nutzer_sichtbarkeit.md
//
// AC-1..AC-3, AC-11: eine Buchfuehrung je (jobID, userID) existiert heute
// NICHT -- der einzige Alarmweg im Bestand ist der aggregierte #1346-Alarm in
// tripReports(). Diese Tests nutzen bewusst alertChecks() (KEIN aggregierter
// Alarm im Bestand), damit ein gruener Notifier-Aufruf eindeutig aus der
// neuen Pro-Nutzer-Logik stammt und nicht aus #1346 mitgezaehlt wird.
// ---------------------------------------------------------------------------

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"sync/atomic"
	"testing"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/store"
)

// mkUsers legt fuer jede uebergebene ID ein echtes Nutzerverzeichnis mit
// user.json unter tmpDir an -- GENAU die uebergebenen IDs, ohne den
// automatisch mitgefuehrten "default"-Nutzer von testStoreWithUsers(), damit
// Isolationstests (AC-1, AC-11) eindeutig zuordenbare Zaehler bekommen.
func mkUsers(t *testing.T, tmpDir string, ids ...string) {
	t.Helper()
	for _, id := range ids {
		dir := filepath.Join(tmpDir, "users", id)
		if err := os.MkdirAll(dir, 0755); err != nil {
			t.Fatalf("mkdir user dir %s: %v", id, err)
		}
		if err := os.WriteFile(filepath.Join(dir, "user.json"), []byte(`{"id":"`+id+`"}`), 0644); err != nil {
			t.Fatalf("write user.json for %s: %v", id, err)
		}
	}
}

// userAlarmControl steuert je Testschritt, welche user_ids der naechste
// HTTP-Aufruf mit HTTP 500 beantwortet -- alle anderen bekommen 200 ok.
type userAlarmControl struct {
	mu      sync.Mutex
	failIDs map[string]bool
}

func (c *userAlarmControl) setFail(ids ...string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.failIDs = make(map[string]bool, len(ids))
	for _, id := range ids {
		c.failIDs[id] = true
	}
}

func (c *userAlarmControl) shouldFail(id string) bool {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.failIDs[id]
}

func newUserAlarmServer(ctrl *userAlarmControl) *httptest.Server {
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		uid := r.URL.Query().Get("user_id")
		if ctrl.shouldFail(uid) {
			w.WriteHeader(http.StatusInternalServerError)
			fmt.Fprint(w, `{"error":"boom"}`)
			return
		}
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, `{"status":"ok"}`)
	}))
}

// recordingNotifier zeichnet jeden Aufruf auf (Aufrufzahl + letzter Text) --
// Slice statt echtem notify.SendMQ, wie im Test-Plan gefordert.
//
// Adversary-Fix-Runde F005: senders/recipients zusaetzlich aufgezeichnet --
// bislang unbelegt, dass Alarm/Teilerfolg-Hinweis/Entwarnung tatsaechlich an
// sender="gregor", recipient="infra" gehen statt an ein beliebiges Ziel.
type recordingNotifier struct {
	mu         sync.Mutex
	count      atomic.Int32
	bodies     []string
	priority   []string
	senders    []string
	recipients []string
}

func (r *recordingNotifier) fn() Notifier {
	return func(sender, recipient, priority, subject, body string) error {
		r.count.Add(1)
		r.mu.Lock()
		r.bodies = append(r.bodies, subject+" "+body)
		r.priority = append(r.priority, priority)
		r.senders = append(r.senders, sender)
		r.recipients = append(r.recipients, recipient)
		r.mu.Unlock()
		return nil
	}
}

func (r *recordingNotifier) lastSender() string {
	r.mu.Lock()
	defer r.mu.Unlock()
	if len(r.senders) == 0 {
		return ""
	}
	return r.senders[len(r.senders)-1]
}

func (r *recordingNotifier) lastRecipient() string {
	r.mu.Lock()
	defer r.mu.Unlock()
	if len(r.recipients) == 0 {
		return ""
	}
	return r.recipients[len(r.recipients)-1]
}

func (r *recordingNotifier) lastBody() string {
	r.mu.Lock()
	defer r.mu.Unlock()
	if len(r.bodies) == 0 {
		return ""
	}
	return r.bodies[len(r.bodies)-1]
}

func (r *recordingNotifier) lastPriority() string {
	r.mu.Lock()
	defer r.mu.Unlock()
	if len(r.priority) == 0 {
		return ""
	}
	return r.priority[len(r.priority)-1]
}

// AC-1: zwei Nutzer A und B -- B scheitert 3x in Folge, A bleibt ok. Genau
// ein Alarm, der B betrifft, A bleibt ohne Alarm und ohne "failing"-Zaehlung.
func TestUserFailureAlarm_TwoUsers_OnlyFailingUserAlarmsAfterThreeInARow(t *testing.T) {
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
	sched.Start()
	defer sched.Stop()

	rec := &recordingNotifier{}
	sched.notifier = rec.fn()

	ctrl.setFail("bob")
	sched.alertChecks()
	sched.alertChecks()
	sched.alertChecks()

	if got := rec.count.Load(); got != 1 {
		t.Fatalf("expected exactly 1 alert after 3 consecutive failures for bob, got %d", got)
	}
	// Adversary-Fix-Runde F004/F005: der Fehler-Alarm muss tatsaechlich mit
	// Prioritaet "high" und ueber sender="gregor"/recipient="infra" gehen --
	// bislang unbelegt (nur der Aufrufzaehler und der Text wurden geprueft).
	if p := rec.lastPriority(); p != "high" {
		t.Fatalf("expected priority 'high' for a user failure alarm (F004), got %q", p)
	}
	if s := rec.lastSender(); s != "gregor" {
		t.Fatalf("expected sender 'gregor' for a user failure alarm (F005), got %q", s)
	}
	if rcpt := rec.lastRecipient(); rcpt != "infra" {
		t.Fatalf("expected recipient 'infra' for a user failure alarm (F005), got %q", rcpt)
	}
	body := rec.lastBody()
	if !strings.Contains(body, "bob") {
		t.Fatalf("expected alert text to reference bob, got %q", body)
	}
	if strings.Contains(body, "alice") {
		t.Fatalf("expected alert text to NOT reference alice (Isolation, AC-1), got %q", body)
	}

	status := sched.Status()
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
		t.Fatalf("expected 'users' aggregate on alert_checks job (Section 5), got %v", job["users"])
	}
	if users["total"] != 2 {
		t.Fatalf("expected users.total=2, got %v", users["total"])
	}
	if users["failing"] != 1 {
		t.Fatalf("expected users.failing=1 (only bob), got %v (alice must not count)", users["failing"])
	}
}

// AC-2: nach dem ersten Alarm loesen der 4. und 5. Fehler von B KEINEN
// weiteren Alarm aus; der erste Erfolg danach loest genau eine Entwarnung
// aus; eine erneute Serie von 3 Fehlern loest einen neuen Alarm aus.
func TestUserFailureAlarm_NoDoubleFireThenRecoveryThenNewAlarm(t *testing.T) {
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

	rec := &recordingNotifier{}
	sched.notifier = rec.fn()

	ctrl.setFail("bob")
	sched.alertChecks() // 1
	sched.alertChecks() // 2
	sched.alertChecks() // 3 -> Alarm #1
	if got := rec.count.Load(); got != 1 {
		t.Fatalf("expected 1 alert after 3rd consecutive failure, got %d", got)
	}

	sched.alertChecks() // 4. Fehler
	sched.alertChecks() // 5. Fehler
	if got := rec.count.Load(); got != 1 {
		t.Fatalf("expected notifier count to stay at 1 during ongoing failure streak "+
			"(no re-fire, AC-2), got %d", got)
	}

	ctrl.setFail() // Bob erholt sich
	sched.alertChecks()
	if got := rec.count.Load(); got != 2 {
		t.Fatalf("expected exactly 1 recovery notification (count=2) after the first "+
			"success following an alert (AC-2), got %d", got)
	}
	// Adversary-Fix-Runde F005: die Entwarnung muss ebenfalls ueber
	// sender="gregor"/recipient="infra" gehen, nicht nur der Fehler-Alarm.
	if s := rec.lastSender(); s != "gregor" {
		t.Fatalf("expected sender 'gregor' for the recovery notice (F005), got %q", s)
	}
	if rcpt := rec.lastRecipient(); rcpt != "infra" {
		t.Fatalf("expected recipient 'infra' for the recovery notice (F005), got %q", rcpt)
	}

	ctrl.setFail("bob")
	sched.alertChecks()
	sched.alertChecks()
	sched.alertChecks()
	if got := rec.count.Load(); got != 3 {
		t.Fatalf("expected a NEW alert (count=3) after a fresh streak of 3 failures "+
			"following a recovery (AC-2), got %d", got)
	}
}

// AC-3: 2 Fehler, ok, 2 Fehler -- die Serie erreicht nie 3 am Stueck, also
// darf zu keinem Zeitpunkt ein Alarm feuern.
func TestUserFailureAlarm_InterruptedStreakNeverAlarms(t *testing.T) {
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

	rec := &recordingNotifier{}
	sched.notifier = rec.fn()

	ctrl.setFail("bob")
	sched.alertChecks() // 1
	sched.alertChecks() // 2
	ctrl.setFail()      // ok -> Serie reisst
	sched.alertChecks()
	ctrl.setFail("bob")
	sched.alertChecks() // 1
	sched.alertChecks() // 2

	if got := rec.count.Load(); got != 0 {
		t.Fatalf("expected 0 alerts -- streak never reached 3 in a row (AC-3), got %d", got)
	}

	// Gegenprobe (sonst waere diese Pruefung vor jeder Implementierung trivial
	// gruen, weil der Notifier heute NIE aufgerufen wird): die unterbrochene
	// Serie muss eine ECHTE anschliessende 3er-Serie weiterhin normal zaehlen
	// koennen -- ein Implementierung, die einfach nie alarmiert, wuerde hier
	// durchfallen.
	sched.alertChecks() // 3. Fehler in Folge (echte Serie ab dem Reset)
	if got := rec.count.Load(); got != 1 {
		t.Fatalf("expected the interrupted streak to still allow a genuine alert once "+
			"3 consecutive failures actually occur afterwards (AC-3 Gegenprobe), got %d", got)
	}
}

// AC-11: zwei Nutzer A und B desselben Jobs scheitern beide im selben Lauf
// zum dritten Mal in Folge -- genau EINE Alarm-Nachricht, die beide nennt;
// nach dem naechsten gemeinsamen Erfolg genau eine gemeinsame Entwarnung.
func TestUserFailureAlarm_BundlesMultipleUsersInSameRun(t *testing.T) {
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

	rec := &recordingNotifier{}
	sched.notifier = rec.fn()

	ctrl.setFail("alice", "bob")
	sched.alertChecks() // beide: 1
	sched.alertChecks() // beide: 2
	sched.alertChecks() // beide: 3 -> Buendelung: genau 1 Nachricht

	if got := rec.count.Load(); got != 1 {
		t.Fatalf("expected exactly 1 bundled alert when both users hit the 3rd "+
			"consecutive failure in the same run (AC-11), got %d", got)
	}
	// Adversary-Fix-Runde F004: auch die gebuendelte Fehler-Nachricht muss
	// Prioritaet "high" tragen (Regressionsschutz zusaetzlich zum Einzeltest
	// TestUserFailureAlarm_TwoUsers_OnlyFailingUserAlarmsAfterThreeInARow).
	if p := rec.lastPriority(); p != "high" {
		t.Fatalf("expected priority 'high' for the bundled user failure alarm (F004), got %q", p)
	}
	body := rec.lastBody()
	if !strings.Contains(body, "alice") || !strings.Contains(body, "bob") {
		t.Fatalf("expected the bundled alert to name BOTH users (AC-11), got %q", body)
	}

	ctrl.setFail() // beide erholen sich im selben Lauf
	sched.alertChecks()
	if got := rec.count.Load(); got != 2 {
		t.Fatalf("expected exactly 1 shared recovery notice (count=2) after both users "+
			"succeed in the same run (AC-11), got %d", got)
	}
}

// bobSequenceServer liefert fuer "bob" je nach mode.Load() einen harten
// Fehler (0), einen Teilerfolg (1) oder einen echten Erfolg (2) -- "alice"
// bleibt immer erfolgreich (Isolations-Kontrolle). Adversary-Fix-Runde
// F001/F002: erlaubt, eine echte Fehler/Teilerfolg/Fehler-Sequenz fuer EINEN
// Nutzer durchzuspielen (die vorhandenen Server-Helfer koennen das nicht,
// weil sie nur zwischen "immer fail" und "immer ok" per uid umschalten).
func bobSequenceServer(t *testing.T, mode *atomic.Int32) *httptest.Server {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		uid := r.URL.Query().Get("user_id")
		if uid != "bob" {
			w.WriteHeader(http.StatusOK)
			fmt.Fprint(w, `{"status":"ok","count":1}`)
			return
		}
		switch mode.Load() {
		case 0:
			w.WriteHeader(http.StatusInternalServerError)
			fmt.Fprint(w, `{"error":"boom"}`)
		case 1:
			w.WriteHeader(http.StatusOK)
			fmt.Fprint(w, `{"status":"partial","count":1}`)
		default:
			w.WriteHeader(http.StatusOK)
			fmt.Fprint(w, `{"status":"ok","count":1}`)
		}
	}))
	t.Cleanup(srv.Close)
	return srv
}

// F001 (Adversary-Fix-Runde, Mutations-Fund): error, error, partial, error --
// ein Teilerfolg mitten in einer Fehlerserie darf ConsecutiveFailures NICHT
// zuruecksetzen (Spec Abschnitt 1, Zaehlerregel "partial: unveraendert").
// Der 4. Aufruf ist damit der 3. ECHTE Fehler in Folge und muss alarmieren --
// eine Implementierung, die eine Fehlerserie durch einen Teilerfolg
// zuruecksetzt, wuerde hier erst beim 6. statt 4. Aufruf alarmieren.
func TestUserFailureAlarm_PartialInBetweenDoesNotResetFailureStreak(t *testing.T) {
	var mode atomic.Int32 // 0=error, 1=partial, 2=ok
	server := bobSequenceServer(t, &mode)

	tmpDir := t.TempDir()
	mkUsers(t, tmpDir, "alice", "bob")

	cfg := &config.Config{PythonCoreURL: server.URL, SchedulerTimezone: "Europe/Vienna"}
	sched, err := New(cfg, store.New(tmpDir, "alice"))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}

	rec := &recordingNotifier{}
	sched.notifier = rec.fn()

	mode.Store(0)
	sched.alertChecks() // error 1
	sched.alertChecks() // error 2
	if got := rec.count.Load(); got != 0 {
		t.Fatalf("expected 0 alerts after 2 consecutive errors (F001 setup), got %d", got)
	}

	mode.Store(1)
	sched.alertChecks() // partial (must NOT reset, must NOT count as a 3rd error)
	if got := rec.count.Load(); got != 0 {
		t.Fatalf("expected 0 alerts after an intervening partial run (F001), got %d", got)
	}

	mode.Store(0)
	sched.alertChecks() // error -- this is the 3rd REAL error in a row
	if got := rec.count.Load(); got != 1 {
		t.Fatalf("expected exactly 1 alert on the 3rd real error despite an intervening "+
			"partial run (F001 -- partial must not reset ConsecutiveFailures), got %d", got)
	}
}

// F002 (Adversary-Fix-Runde, Mutations-Fund): nach einem Fehler-Alarm darf
// ein anschliessender Teilerfolg NICHT als Erholung gelten (Spec Abschnitt 2:
// "Ein partial nach einem Fehler-Alarm gilt NICHT als Erholung"). Erst der
// naechste ECHTE Erfolg loest die Entwarnung aus.
func TestUserFailureAlarm_PartialAfterAlertIsNotRecoveryThenOkIs(t *testing.T) {
	var mode atomic.Int32 // 0=error, 1=partial, 2=ok
	server := bobSequenceServer(t, &mode)

	tmpDir := t.TempDir()
	mkUsers(t, tmpDir, "alice", "bob")

	cfg := &config.Config{PythonCoreURL: server.URL, SchedulerTimezone: "Europe/Vienna"}
	sched, err := New(cfg, store.New(tmpDir, "alice"))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}

	rec := &recordingNotifier{}
	sched.notifier = rec.fn()

	mode.Store(0)
	sched.alertChecks() // error 1
	sched.alertChecks() // error 2
	sched.alertChecks() // error 3 -> Alarm #1
	if got := rec.count.Load(); got != 1 {
		t.Fatalf("expected 1 alert after 3rd consecutive failure (F002 setup), got %d", got)
	}

	mode.Store(1)
	sched.alertChecks() // partial run right after the alert
	if got := rec.count.Load(); got != 1 {
		t.Fatalf("expected NO recovery notice after a partial run following an alert "+
			"(F002 -- partial must not count as recovery), got %d", got)
	}

	mode.Store(2)
	sched.alertChecks() // real success -> exactly 1 recovery notice
	if got := rec.count.Load(); got != 2 {
		t.Fatalf("expected exactly 1 recovery notice (count=2) after the first REAL success "+
			"following the alert, even though a partial run came first (F002), got %d", got)
	}
}
