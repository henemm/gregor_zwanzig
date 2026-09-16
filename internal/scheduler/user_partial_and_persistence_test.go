package scheduler

// ---------------------------------------------------------------------------
// Fix #2149 Scheibe A — Teilerfolgsschwelle, Persistenz, Pruning, Nebenläufigkeit
//
// Spec: docs/specs/modules/fix_2149_scheduler_nutzer_sichtbarkeit.md
// Ablageort der Zustandsdatei laut Spec Abschnitt 6: Geschwisterdatei von
// users/ unter store.DataDir, Name "scheduler_user_state.json".
// ---------------------------------------------------------------------------

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"sync"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/store"
)

const userStateFileName = "scheduler_user_state.json"

// userPartialControl steuert, welche user_ids der naechste Aufruf mit
// status="partial" (HTTP 200, ohne "failed") beantwortet -- alle anderen
// bekommen einen echten Erfolg.
type userPartialControl struct {
	mu         sync.Mutex
	partialIDs map[string]bool
}

func (c *userPartialControl) setPartial(ids ...string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.partialIDs = make(map[string]bool, len(ids))
	for _, id := range ids {
		c.partialIDs[id] = true
	}
}

func (c *userPartialControl) shouldPartial(id string) bool {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.partialIDs[id]
}

func newUserPartialServer(ctrl *userPartialControl) *httptest.Server {
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		uid := r.URL.Query().Get("user_id")
		w.WriteHeader(http.StatusOK)
		if ctrl.shouldPartial(uid) {
			fmt.Fprint(w, `{"status":"partial","count":1}`)
			return
		}
		fmt.Fprint(w, `{"status":"ok","count":1}`)
	}))
}

// AC-4: 8 Teilerfolge in Folge -> genau eine Nachricht mit Prioritaet
// "normal"; 7 Teilerfolge + ok -> keine Nachricht.
func TestUserPartialAlarm_EightInARow_AlertsOnceWithNormalPriority(t *testing.T) {
	ctrl := &userPartialControl{}
	server := newUserPartialServer(ctrl)
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

	ctrl.setPartial("alice")
	for i := 0; i < 8; i++ {
		sched.alertChecks()
	}

	if got := rec.count.Load(); got != 1 {
		t.Fatalf("expected exactly 1 alert after 8 consecutive partial results (AC-4), got %d", got)
	}
	if p := rec.lastPriority(); p != "normal" {
		t.Fatalf("expected priority 'normal' for partial-threshold alert (AC-4), got %q", p)
	}
	// Adversary-Fix-Runde F005: der Teilerfolg-Hinweis muss ebenfalls ueber
	// sender="gregor"/recipient="infra" gehen (bislang nur fuer den
	// Fehler-Alarm und die Entwarnung belegt, s. user_failure_alarm_test.go).
	if s := rec.lastSender(); s != "gregor" {
		t.Fatalf("expected sender 'gregor' for the partial-threshold hint (F005), got %q", s)
	}
	if rcpt := rec.lastRecipient(); rcpt != "infra" {
		t.Fatalf("expected recipient 'infra' for the partial-threshold hint (F005), got %q", rcpt)
	}

	// Adversary-Fix-Runde F006: das oeffentliche users-Aggregat muss die
	// achtfache Teilerfolgsserie von alice als partial=1 zeigen -- bislang
	// war das Aggregat nur fuer "failing" (AC-1/AC-6), nie fuer "partial"
	// belegt.
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
		t.Fatalf("expected 'users' aggregate on alert_checks job (F006), got %v", job["users"])
	}
	if users["partial"] != 1 {
		t.Fatalf("expected users.partial=1 for alice's 8-in-a-row streak (F006), got %v", users["partial"])
	}
}

func TestUserPartialAlarm_SevenInARowThenOk_NeverAlerts(t *testing.T) {
	ctrl := &userPartialControl{}
	server := newUserPartialServer(ctrl)
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

	ctrl.setPartial("alice")
	for i := 0; i < 7; i++ {
		sched.alertChecks()
	}
	ctrl.setPartial() // ok -> Serie reisst vor der Schwelle von 8
	sched.alertChecks()

	if got := rec.count.Load(); got != 0 {
		t.Fatalf("expected 0 alerts -- threshold of 8 never reached (AC-4), got %d", got)
	}

	// Gegenprobe (sonst waere diese Pruefung vor jeder Implementierung trivial
	// gruen, weil der Notifier heute NIE aufgerufen wird): eine ECHTE
	// anschliessende Serie von 8 Teilerfolgen muss weiterhin normal zaehlen
	// und tatsaechlich alarmieren.
	ctrl.setPartial("alice")
	for i := 0; i < 8; i++ {
		sched.alertChecks()
	}
	if got := rec.count.Load(); got != 1 {
		t.Fatalf("expected a genuine alert after a fresh streak of 8 partial results "+
			"following the interrupted one (AC-4 Gegenprobe), got %d", got)
	}
}

// AC-5 (Neustart): zwei *Scheduler-Instanzen ueber denselben tmpDir-Pfad --
// die erste verbucht 2 Fehler und wird verworfen (simuliert Neustart), die
// zweite laedt den Zustand beim Aufbau und verbucht den 3. Fehler -> Alarm
// feuert trotzdem.
func TestUserFailureState_PersistsAcrossRestart(t *testing.T) {
	ctrl := &userAlarmControl{}
	server := newUserAlarmServer(ctrl)
	defer server.Close()

	tmpDir := t.TempDir()
	mkUsers(t, tmpDir, "alice")

	cfg := &config.Config{PythonCoreURL: server.URL, SchedulerTimezone: "Europe/Vienna"}

	sched1, err := New(cfg, store.New(tmpDir, "alice"))
	if err != nil {
		t.Fatalf("New() error (sched1): %v", err)
	}
	sched1.notifier = func(_, _, _, _, _ string) error { return nil }

	ctrl.setFail("alice")
	sched1.alertChecks() // 1
	sched1.alertChecks() // 2
	sched1 = nil         // simuliert Prozess-Neustart

	sched2, err := New(cfg, store.New(tmpDir, "alice"))
	if err != nil {
		t.Fatalf("New() error (sched2): %v", err)
	}
	rec := &recordingNotifier{}
	sched2.notifier = rec.fn()

	sched2.alertChecks() // 3. Fehler NACH Neustart

	if got := rec.count.Load(); got != 1 {
		t.Fatalf("expected the 3rd consecutive failure after a simulated restart to still "+
			"alert (AC-5, persisted state must be loaded on New()), got %d", got)
	}
}

// AC-5 (defekte Datei): eine kaputte Zustandsdatei darf New() nicht zum
// Absturz bringen; der naechste Lauf muss mit leerem Zustand normal starten.
func TestUserFailureState_CorruptStateFile_LoadsEmptyWithoutCrash(t *testing.T) {
	ctrl := &userAlarmControl{}
	server := newUserAlarmServer(ctrl)
	defer server.Close()

	tmpDir := t.TempDir()
	mkUsers(t, tmpDir, "alice")
	if err := os.WriteFile(filepath.Join(tmpDir, userStateFileName), []byte("{not-valid-json"), 0644); err != nil {
		t.Fatalf("write corrupt state file: %v", err)
	}

	cfg := &config.Config{PythonCoreURL: server.URL, SchedulerTimezone: "Europe/Vienna"}
	sched, err := New(cfg, store.New(tmpDir, "alice"))
	if err != nil {
		t.Fatalf("New() must not error on a corrupt state file (AC-5), got: %v", err)
	}

	rec := &recordingNotifier{}
	sched.notifier = rec.fn()

	ctrl.setFail("alice")
	sched.alertChecks() // 1
	sched.alertChecks() // 2
	sched.alertChecks() // 3 -> Alarm, weil bei 0 (leerer Zustand) gestartet wurde

	if got := rec.count.Load(); got != 1 {
		t.Fatalf("expected normal counting from an empty state after a corrupt file "+
			"(AC-5): 3 fresh failures should alert exactly once, got %d", got)
	}
}

// F-ADV1 (CRITICAL, Adversary Runde 2): eine Zustandsdatei kann syntaktisch
// GUELTIGES JSON enthalten, das trotzdem zu nil-Maps bzw. nil-Records
// deserialisiert (`null`, `{"alert_checks": null}`,
// `{"alert_checks": {"bob": null}}`, `[]`) -- das ist ein anderer Fall als
// TestUserFailureState_CorruptStateFile_LoadsEmptyWithoutCrash (dort
// scheitert json.Unmarshal an einem Syntaxfehler). Ohne Normalisierung
// panickt der naechste recordLocked()-Aufruf mit "assignment to entry in
// nil map" (aeusserer oder innerer Map-Zugriff) bzw. einer nil-Pointer-
// Dereferenz (Zero-Record-Fall). AC-5 verlangt "kein Absturz" fuer JEDE
// defekte Zustandsdatei, nicht nur fuer Syntaxfehler.
func TestUserFailureState_MalformedButValidJSON_LoadsEmptyWithoutCrash(t *testing.T) {
	cases := []struct {
		name        string
		content     string
		failingUser string
	}{
		{name: "top-level null", content: `null`, failingUser: "alice"},
		{name: "job entry null", content: `{"alert_checks": null}`, failingUser: "alice"},
		{
			name:        "user record null (nil pointer, same key as failing user)",
			content:     `{"alert_checks": {"bob": null}}`,
			failingUser: "bob",
		},
		{name: "top-level array instead of object", content: `[]`, failingUser: "alice"},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			ctrl := &userAlarmControl{}
			server := newUserAlarmServer(ctrl)
			defer server.Close()

			tmpDir := t.TempDir()
			mkUsers(t, tmpDir, tc.failingUser)
			if err := os.WriteFile(filepath.Join(tmpDir, userStateFileName), []byte(tc.content), 0644); err != nil {
				t.Fatalf("write state file: %v", err)
			}

			cfg := &config.Config{PythonCoreURL: server.URL, SchedulerTimezone: "Europe/Vienna"}
			sched, err := New(cfg, store.New(tmpDir, tc.failingUser))
			if err != nil {
				t.Fatalf("New() must not error on a malformed-but-valid state file (AC-5), got: %v", err)
			}

			rec := &recordingNotifier{}
			sched.notifier = rec.fn()

			ctrl.setFail(tc.failingUser)
			sched.alertChecks() // 1 -- must not panic
			sched.alertChecks() // 2 -- must not panic
			sched.alertChecks() // 3 -- alarm, starting from an empty state

			if got := rec.count.Load(); got != 1 {
				t.Fatalf("expected normal counting from an empty state after a malformed-but-"+
					"valid state file (AC-5): 3 fresh failures should alert exactly once, got %d", got)
			}
		})
	}
}

// F-ADV5 (LOW, Adversary Runde 3): eine Zustandsdatei mit einem NEGATIVEN
// Startzaehler (`consecutive_failures: -5`) darf den Alarm nicht verzoegern
// -- geladene Zaehler muessen beim Einlesen auf 0 geklammert werden, sonst
// braucht es ab Start -5 acht statt drei echte Fehler, bevor
// failureAlertThreshold (3) erstmals erreicht wird.
func TestUserFailureState_NegativeCountersInFile_ClampedToZero(t *testing.T) {
	ctrl := &userAlarmControl{}
	server := newUserAlarmServer(ctrl)
	defer server.Close()

	tmpDir := t.TempDir()
	mkUsers(t, tmpDir, "alice")
	stateContent := `{"alert_checks": {"alice": {"consecutive_failures": -5, "consecutive_partial": -3}}}`
	if err := os.WriteFile(filepath.Join(tmpDir, userStateFileName), []byte(stateContent), 0644); err != nil {
		t.Fatalf("write state file with negative counters: %v", err)
	}

	cfg := &config.Config{PythonCoreURL: server.URL, SchedulerTimezone: "Europe/Vienna"}
	sched, err := New(cfg, store.New(tmpDir, "alice"))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}

	rec := &recordingNotifier{}
	sched.notifier = rec.fn()

	ctrl.setFail("alice")
	sched.alertChecks() // 1 -- must count from 0, not -5
	sched.alertChecks() // 2
	sched.alertChecks() // 3 -> alarm, IF the negative start value was clamped to 0

	if got := rec.count.Load(); got != 1 {
		t.Fatalf("expected exactly 1 alert after 3 fresh failures starting from a negative "+
			"persisted counter (F-ADV5, negative counters must be clamped to 0 on load), got %d", got)
	}
}

// AC-7: ein geloeschter Nutzer wird nach dem naechsten Job-Lauf aus dem
// persistierten Zustand entfernt; ein Testkonto taucht NIE im Zustand auf.
func TestUserRunState_PruneRemovedUser_AndExcludeTestAccounts(t *testing.T) {
	ctrl := &userAlarmControl{}
	server := newUserAlarmServer(ctrl)
	defer server.Close()

	tmpDir := t.TempDir()
	const testAccountID = "tdd-2149-leak"
	mkUsers(t, tmpDir, "alice", "bob", testAccountID)

	cfg := &config.Config{PythonCoreURL: server.URL, SchedulerTimezone: "Europe/Vienna"}
	sched, err := New(cfg, store.New(tmpDir, "alice"))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	sched.notifier = func(_, _, _, _, _ string) error { return nil }

	ctrl.setFail("bob")
	sched.alertChecks()
	sched.alertChecks()

	statePath := filepath.Join(tmpDir, userStateFileName)
	doc := readUserStateFile(t, statePath)
	if _, ok := doc["alert_checks"]["bob"]; !ok {
		t.Fatalf("expected alert_checks/bob entry after 2 recorded failures, got %v", doc)
	}
	if _, ok := doc["alert_checks"][testAccountID]; ok {
		t.Fatalf("test account %q must never be recorded in state (AC-7), got %v", testAccountID, doc)
	}

	// Nutzer "bob" wird geloescht (verschwindet aus der Nutzerliste).
	if err := os.RemoveAll(filepath.Join(tmpDir, "users", "bob")); err != nil {
		t.Fatalf("remove bob's user dir: %v", err)
	}
	ctrl.setFail() // niemand mehr faellt aus (bob ist eh weg)
	sched.alertChecks()

	doc2 := readUserStateFile(t, statePath)
	if _, ok := doc2["alert_checks"]["bob"]; ok {
		t.Fatalf("expected bob's entry to be pruned from state after deletion (AC-7), got %v", doc2)
	}
	if _, ok := doc2["alert_checks"][testAccountID]; ok {
		t.Fatalf("test account %q must never appear in state even after another run (AC-7), "+
			"got %v", testAccountID, doc2)
	}
}

// F-ADV3 (MEDIUM, Adversary Runde 2): TestUserRunState_PruneRemovedUser_
// AndExcludeTestAccounts (AC-7) beweist "Testkonto nie im Zustand" nur ueber
// den vorgelagerten Loop-Filter (filterOutTestUsers) -- das Testkonto
// erreicht Record() dort nie, unabhaengig davon, welche Liste an Prune()
// uebergeben wird. Dieser Test speist ein Testkonto DIREKT ueber
// userState.Record() ein (umgeht den Loop-Filter, simuliert z.B. einen
// kuenftigen zweiten Record()-Aufrufer) und prueft, dass der anschliessende
// Prune(jobID, userIDs)-Aufruf mit der bereits gefilterten Liste (Spec
// Abschnitt 1) diesen Eintrag tatsaechlich entfernt -- isoliert die
// Prune-Basis selbst von der Loop-Filterung.
func TestUserRunState_PruneBasisRemovesLeakedTestAccount_IsolatedFromLoopFilter(t *testing.T) {
	ctrl := &userAlarmControl{}
	server := newUserAlarmServer(ctrl)
	defer server.Close()

	tmpDir := t.TempDir()
	const testAccountID = "tdd-2149-adv3-leak"
	mkUsers(t, tmpDir, "alice", testAccountID)

	cfg := &config.Config{PythonCoreURL: server.URL, SchedulerTimezone: "Europe/Vienna"}
	sched, err := New(cfg, store.New(tmpDir, "alice"))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	sched.notifier = func(_, _, _, _, _ string) error { return nil }

	const jobID = "alert_checks"

	// Umgeht den Loop-Filter absichtlich: das Testkonto landet im Zustand,
	// so als haette ein zweiter Aufrufer den Filter nicht angewendet.
	sched.userState.Record(jobID, testAccountID, "error", "boom")

	statePath := filepath.Join(tmpDir, userStateFileName)
	sched.userState.Prune(jobID, []string{testAccountID}) // Zwischenstand persistieren
	doc := readUserStateFile(t, statePath)
	if _, ok := doc[jobID][testAccountID]; !ok {
		t.Fatalf("test setup broken: leaked test account must be present in state before the "+
			"real job run, got %v", doc)
	}

	// Ein normaler Job-Lauf ruft intern Prune(jobID, userIDs) mit der bereits
	// testkonto-gefilterten Liste auf (nur "alice") -- das MUSS den zuvor
	// direkt eingespeisten Testkonto-Eintrag entfernen.
	sched.alertChecks()

	doc2 := readUserStateFile(t, statePath)
	if _, ok := doc2[jobID][testAccountID]; ok {
		t.Fatalf("expected the leaked test account %q to be removed by the job's own Prune "+
			"call using the filtered userIDs list (F-ADV3), got %v", testAccountID, doc2)
	}
	if _, ok := doc2[jobID]["alice"]; !ok {
		t.Fatalf("expected the real user 'alice' to remain in state, got %v", doc2)
	}
}

// readUserStateFile liest die persistierte Zustandsdatei und parst sie
// generisch (kein Zugriff auf den unexportierten Typ userJobRecord noetig).
func readUserStateFile(t *testing.T, path string) map[string]map[string]map[string]any {
	t.Helper()
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("expected persisted user-run-state file at %s, got error: %v", path, err)
	}
	var doc map[string]map[string]map[string]any
	if err := json.Unmarshal(raw, &doc); err != nil {
		t.Fatalf("persisted state file %s is not valid JSON: %v", path, err)
	}
	return doc
}

// AC-10: zwei verschiedene Fan-out-Jobs (alert_checks, compare_alert_checks)
// schreiben ECHT nebenlaeufig in denselben Zustandsspeicher -- nach Abschluss
// beider sind beide Zaehler in der persistierten Datei vorhanden und korrekt.
// Lauf mit "go test -race".
func TestUserRunState_ConcurrentDifferentJobsPreserveBothCounters(t *testing.T) {
	tmpDir := t.TempDir()
	mkUsers(t, tmpDir, "alice")

	// Beide Pfade antworten hart fehlschlagend, mit kleiner fester
	// Verzoegerung, um Ueberlappung der beiden Goroutinen zu erhoehen (reiner
	// Testaufbau, kein time.Sleep-Warten auf einen Zustand).
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(5 * time.Millisecond)
		w.WriteHeader(http.StatusInternalServerError)
		fmt.Fprint(w, `{"error":"boom"}`)
	}))
	defer server.Close()

	cfg := &config.Config{PythonCoreURL: server.URL, SchedulerTimezone: "Europe/Vienna"}
	sched, err := New(cfg, store.New(tmpDir, "alice"))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	sched.notifier = func(_, _, _, _, _ string) error { return nil }

	const rounds = 3
	for round := 0; round < rounds; round++ {
		var wg sync.WaitGroup
		wg.Add(2)
		go func() {
			defer wg.Done()
			sched.alertChecks()
		}()
		go func() {
			defer wg.Done()
			sched.compareAlertChecks()
		}()
		wg.Wait()
	}

	statePath := filepath.Join(tmpDir, userStateFileName)
	doc := readUserStateFile(t, statePath)

	alertRec, ok := doc["alert_checks"]["alice"]
	if !ok {
		t.Fatalf("expected alert_checks/alice entry in persisted state, got %v", doc)
	}
	if got := alertRec["consecutive_failures"]; got != float64(rounds) {
		t.Fatalf("expected alert_checks consecutive_failures=%d (no lost writes from "+
			"concurrent compare_alert_checks, AC-10), got %v", rounds, got)
	}
	compareRec, ok := doc["compare_alert_checks"]["alice"]
	if !ok {
		t.Fatalf("expected compare_alert_checks/alice entry in persisted state, got %v", doc)
	}
	if got := compareRec["consecutive_failures"]; got != float64(rounds) {
		t.Fatalf("expected compare_alert_checks consecutive_failures=%d (no lost writes from "+
			"concurrent alert_checks, AC-10), got %v", rounds, got)
	}
}
