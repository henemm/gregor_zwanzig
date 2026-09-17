package scheduler

// ---------------------------------------------------------------------------
// Fix #2149 Scheibe B — Wartebudget je Nutzeraufruf ("warten aufhoeren, nicht
// abbrechen"), eigene Fehlerklasse vor #1912, Laufzeitstempel.
//
// Spec: docs/specs/modules/fix_2149_scheduler_budget_teilb.md
//
// Diese Datei enthaelt zusaetzlich die geteilten Testhelfer fuer die Scheibe-B-
// Tests (budgetServer, newBudgetScheduler, userRecord): echter httptest-Server
// mit steuerbarer Verzoegerung/Blockade je user_id, echter Scheduler, echte
// Zustandsdatei in t.TempDir(). Budgets werden ueber die in der Spec
// festgelegten, unexported Felder im Millisekundenbereich gesetzt.
// ---------------------------------------------------------------------------

import (
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/store"
)

// budgetServer ist ein Python-Core-Ersatz, der je user_id zaehlt, die
// Ankunftsreihenfolge/-zeit festhaelt und einzelne Nutzer verzoegert (delay)
// oder bis zur expliziten Freigabe blockiert (hang). Alle blockierenden
// Handler werden am Testende ueber done freigegeben, BEVOR srv.Close() laeuft.
type budgetServer struct {
	srv *httptest.Server

	mu       sync.Mutex
	counts   map[string]int
	order    []string
	arrivals map[string][]time.Time
	delays   map[string]time.Duration
	hang     map[string]bool
	gates    []chan struct{}

	done     chan struct{}
	finished chan string
}

func newBudgetServer(t *testing.T) *budgetServer {
	t.Helper()
	b := &budgetServer{
		counts:   make(map[string]int),
		arrivals: make(map[string][]time.Time),
		delays:   make(map[string]time.Duration),
		hang:     make(map[string]bool),
		done:     make(chan struct{}),
		finished: make(chan string, 256),
	}
	b.srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		uid := r.URL.Query().Get("user_id")
		b.mu.Lock()
		b.counts[uid]++
		b.order = append(b.order, uid)
		b.arrivals[uid] = append(b.arrivals[uid], time.Now())
		delay := b.delays[uid]
		var gate chan struct{}
		if b.hang[uid] {
			gate = make(chan struct{})
			b.gates = append(b.gates, gate)
		}
		b.mu.Unlock()

		if gate != nil {
			select {
			case <-gate:
			case <-b.done:
				return
			}
		} else if delay > 0 {
			select {
			case <-time.After(delay):
			case <-b.done:
				return
			}
		}
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, `{"status":"ok","count":1}`)
		if f, ok := w.(http.Flusher); ok {
			f.Flush()
		}
		select {
		case b.finished <- uid:
		default:
		}
	}))
	// LIFO: close(done) laeuft VOR srv.Close(), sonst haengt Close() an den
	// noch blockierten Handlern.
	t.Cleanup(b.srv.Close)
	t.Cleanup(func() { close(b.done) })
	return b
}

func (b *budgetServer) setDelay(uid string, d time.Duration) {
	b.mu.Lock()
	defer b.mu.Unlock()
	b.delays[uid] = d
}

func (b *budgetServer) setHang(uid string, on bool) {
	b.mu.Lock()
	defer b.mu.Unlock()
	b.hang[uid] = on
}

// releaseGate gibt die i-te blockierte Anfrage (Ankunftsreihenfolge) frei.
func (b *budgetServer) releaseGate(t *testing.T, i int) {
	t.Helper()
	b.mu.Lock()
	defer b.mu.Unlock()
	if i >= len(b.gates) {
		t.Fatalf("test setup broken: gate %d does not exist (only %d blocked requests)", i, len(b.gates))
	}
	close(b.gates[i])
}

func (b *budgetServer) count(uid string) int {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.counts[uid]
}

// takeOrder liefert die seit dem letzten Aufruf kontaktierten user_ids in
// Ankunftsreihenfolge und setzt die Liste zurueck.
func (b *budgetServer) takeOrder() []string {
	b.mu.Lock()
	defer b.mu.Unlock()
	out := b.order
	b.order = nil
	return out
}

func (b *budgetServer) lastArrival(uid string) (time.Time, bool) {
	b.mu.Lock()
	defer b.mu.Unlock()
	a := b.arrivals[uid]
	if len(a) == 0 {
		return time.Time{}, false
	}
	return a[len(a)-1], true
}

// waitFinished wartet (Signalkanal, keine feste Schlafzeit) auf n
// abgeschlossene Server-Antworten.
func (b *budgetServer) waitFinished(t *testing.T, n int) {
	t.Helper()
	deadline := time.After(5 * time.Second)
	for i := 0; i < n; i++ {
		select {
		case <-b.finished:
		case <-deadline:
			t.Fatalf("server never finished %d responses (got %d)", n, i)
		}
	}
}

// newBudgetScheduler baut einen echten Scheduler ueber einem Store mit GENAU
// den uebergebenen Nutzern und injiziert einen recordingNotifier. Alle
// Budgets werden grosszuegig vorbelegt; die einzelnen Tests verkleinern gezielt.
func newBudgetScheduler(t *testing.T, srvURL string, ids ...string) (*Scheduler, *recordingNotifier, string) {
	t.Helper()
	tmpDir := t.TempDir()
	mkUsers(t, tmpDir, ids...)
	cfg := &config.Config{PythonCoreURL: srvURL, SchedulerTimezone: "Europe/Vienna"}
	sched, err := New(cfg, store.New(tmpDir, ids[0]))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	rec := &recordingNotifier{}
	sched.notifier = rec.fn()
	sched.alertWaitBudget = 5 * time.Second
	sched.alertRunBudget = 10 * time.Second
	sched.alertCallCap = 20 * time.Second
	sched.briefingWaitBudget = 5 * time.Second
	sched.briefingRunBudget = 10 * time.Second
	return sched, rec, tmpDir
}

// userRecord liefert eine Kopie des (jobID, userID)-Zustands, gelesen unter
// dem userState-Mutex. ok=false, wenn es (noch) keinen Eintrag gibt.
func userRecord(sched *Scheduler, jobID, uid string) (userJobRecord, bool) {
	sched.userState.mu.Lock()
	defer sched.userState.mu.Unlock()
	byUser, ok := sched.userState.state[jobID]
	if !ok {
		return userJobRecord{}, false
	}
	r, ok := byUser[uid]
	if !ok || r == nil {
		return userJobRecord{}, false
	}
	return *r, true
}

func mustUserRecord(t *testing.T, sched *Scheduler, jobID, uid string) userJobRecord {
	t.Helper()
	r, ok := userRecord(sched, jobID, uid)
	if !ok {
		t.Fatalf("expected a user-run-state record for (%s, %s), got none", jobID, uid)
	}
	return r
}

func lastRunOf(sched *Scheduler, jobID string) *jobResult {
	sched.mu.RLock()
	defer sched.mu.RUnlock()
	lr := sched.lastRuns[jobID]
	if lr == nil {
		return nil
	}
	cp := *lr
	return &cp
}

// AC-1: B antwortet erst deutlich nach dem Wartebudget -- B wird als "budget"
// gebucht, und der Lauf wartet NICHT auf B's Antwort: der nach B kontaktierte
// Nutzer bekommt seinen POST kurz nach B's Wartebudget, der ganze Lauf endet
// lange bevor B antwortet.
func TestUserCallWaitBudget_SlowUserDoesNotDelayOthers(t *testing.T) {
	bs := newBudgetServer(t)
	bs.setDelay("bob", 3*time.Second) // steht fuer "500s" bei 300s Wartebudget

	sched, _, _ := newBudgetScheduler(t, bs.srv.URL, "alice", "bob", "carol")
	sched.alertWaitBudget = 100 * time.Millisecond

	start := time.Now()
	sched.alertChecks()
	elapsed := time.Since(start)

	if elapsed >= 1500*time.Millisecond {
		t.Fatalf("expected alertChecks to return well before bob's 3s answer (wait budget 100ms, AC-1), took %v", elapsed)
	}
	for _, uid := range []string{"alice", "bob", "carol"} {
		if got := bs.count(uid); got != 1 {
			t.Fatalf("expected exactly 1 POST for %s in the run (AC-1), got %d", uid, got)
		}
	}
	// Der Nutzer, der direkt nach bob an der Reihe war (Rotation beliebig),
	// darf hoechstens ~Wartebudget nach bob's POST kontaktiert worden sein.
	order := bs.takeOrder()
	for i, uid := range order {
		if uid == "bob" && i+1 < len(order) {
			bobAt, _ := bs.lastArrival("bob")
			nextAt, _ := bs.lastArrival(order[i+1])
			if gap := nextAt.Sub(bobAt); gap >= 1500*time.Millisecond {
				t.Fatalf("expected next user %s to be contacted right after bob's wait budget, gap was %v (AC-1)", order[i+1], gap)
			}
		}
	}

	bob := mustUserRecord(t, sched, "alert_checks", "bob")
	if bob.LastStatus != "budget" {
		t.Fatalf("expected bob booked as outcome 'budget' (AC-1), got %q", bob.LastStatus)
	}
	if bob.ConsecutiveFailures != 1 {
		t.Fatalf("expected bob.ConsecutiveFailures=1 after one budget run (Spec 5), got %d", bob.ConsecutiveFailures)
	}
	for _, uid := range []string{"alice", "carol"} {
		if r := mustUserRecord(t, sched, "alert_checks", uid); r.LastStatus != "ok" {
			t.Fatalf("expected %s booked 'ok' (AC-1), got %q", uid, r.LastStatus)
		}
	}
	if lr := lastRunOf(sched, "alert_checks"); lr == nil || lr.Status != "partial" {
		t.Fatalf("expected job run ranked 'partial' with a budget user (Spec 4), got %+v", lr)
	}
}

// AC-9 (Typ-Ebene): budgetExceededError dockt per Unwrap an die
// partialRunError-Kette an -- ein Job-Lauf, der damit endet, rankt "partial",
// nicht "error" (sonst #1346-Fehlalarm).
func TestBudgetExceededError_RanksJobPartial(t *testing.T) {
	var err error = &budgetExceededError{msg: "alert_checks: Wartebudget ueberschritten"}
	var pe *partialRunError
	if !errors.As(err, &pe) {
		t.Fatalf("expected *budgetExceededError to unwrap to *partialRunError (Spec 4), got %T", err)
	}
	var be *budgetExceededError
	if !errors.As(err, &be) {
		t.Fatalf("expected errors.As to find *budgetExceededError, got %T", err)
	}

	bs := newBudgetServer(t)
	sched, _, _ := newBudgetScheduler(t, bs.srv.URL, "alice")
	sched.recordRun("alert_checks", func() error { return err })
	if lr := lastRunOf(sched, "alert_checks"); lr == nil || lr.Status != "partial" {
		t.Fatalf("expected recordRun to rank a budgetExceededError as 'partial' (Spec 4), got %+v", lr)
	}
}

// AC-9 (Pruefreihenfolge): Das Wartebudget laeuft ab, waehrend der Aufruf
// noch in der #1912-Client-Frist steckt. Der Ausgang ist BEIDES -- ein
// budgetExceededError UND (per Unwrap) ein partialRunError. Die Budget-
// Pruefung muss zuerst greifen: Outcome "budget" (zaehlt in
// ConsecutiveFailures), NICHT "partial".
func TestUserCallWaitBudget_BudgetCheckedBeforeTimeoutPartial(t *testing.T) {
	bs := newBudgetServer(t)
	bs.setDelay("bob", 5*time.Second)

	sched, _, _ := newBudgetScheduler(t, bs.srv.URL, "alice", "bob")
	sched.client = &http.Client{Timeout: 2 * time.Second}
	sched.alertWaitBudget = 30 * time.Millisecond

	sched.alertChecks()

	bob := mustUserRecord(t, sched, "alert_checks", "bob")
	if bob.LastStatus != "budget" {
		t.Fatalf("expected outcome 'budget' (budget check before isTimeoutTransportError, AC-9), got %q", bob.LastStatus)
	}
	if bob.ConsecutiveFailures != 1 || bob.ConsecutivePartial != 0 {
		t.Fatalf("expected budget to count as failure (failures=1, partial=0, AC-9), got failures=%d partial=%d",
			bob.ConsecutiveFailures, bob.ConsecutivePartial)
	}
}

// AC-9 (Gegenrichtung): Ein echter #1912-Transport-Timeout, der INNERHALB des
// Wartebudgets eintritt, bleibt unveraendert "partial" -- die neue Klasse darf
// die #1912-Klassifikation nicht verschlucken.
func TestUserCallWaitBudget_RealClientTimeoutStaysPartial(t *testing.T) {
	bs := newBudgetServer(t)
	bs.setDelay("bob", 2*time.Second)

	sched, _, _ := newBudgetScheduler(t, bs.srv.URL, "alice", "bob")
	sched.client = &http.Client{Timeout: 50 * time.Millisecond}
	sched.alertWaitBudget = 3 * time.Second

	sched.alertChecks()

	bob := mustUserRecord(t, sched, "alert_checks", "bob")
	if bob.LastStatus != "partial" {
		t.Fatalf("expected a genuine #1912 client timeout within the wait budget to stay 'partial', got %q", bob.LastStatus)
	}
	if bob.ConsecutiveFailures != 0 || bob.ConsecutivePartial != 1 {
		t.Fatalf("expected failures=0 partial=1 for a #1912 timeout, got failures=%d partial=%d",
			bob.ConsecutiveFailures, bob.ConsecutivePartial)
	}
}

// AC-12: Ein Lauf mit "budget"- bzw. "skipped_in_flight"-Nutzer setzt
// last_run.time trotzdem frisch (check-gregor20.sh-Frischepruefung).
func TestUserCallWaitBudget_LastRunTimeFreshWithBudgetAndSkip(t *testing.T) {
	bs := newBudgetServer(t)
	bs.setHang("bob", true)

	sched, _, _ := newBudgetScheduler(t, bs.srv.URL, "alice", "bob")
	sched.alertWaitBudget = 50 * time.Millisecond

	before1 := time.Now()
	sched.alertChecks() // bob: budget
	lr1 := lastRunOf(sched, "alert_checks")
	if lr1 == nil || lr1.Time.Before(before1) {
		t.Fatalf("expected last_run.time >= run start after a budget run (AC-12), got %+v (start %v)", lr1, before1)
	}
	if bob := mustUserRecord(t, sched, "alert_checks", "bob"); bob.LastStatus != "budget" {
		t.Fatalf("test setup: expected bob 'budget' in run 1, got %q", bob.LastStatus)
	}

	before2 := time.Now()
	sched.alertChecks() // bob: skipped_in_flight
	lr2 := lastRunOf(sched, "alert_checks")
	if lr2 == nil || lr2.Time.Before(before2) {
		t.Fatalf("expected last_run.time >= run start after a skipped_in_flight run (AC-12), got %+v (start %v)", lr2, before2)
	}
	if bob := mustUserRecord(t, sched, "alert_checks", "bob"); bob.LastStatus != "skipped_in_flight" {
		t.Fatalf("test setup: expected bob 'skipped_in_flight' in run 2, got %q", bob.LastStatus)
	}

	// Oeffentliche Sicht: last_run.time im Status ist ebenfalls frisch.
	job := statusJob(t, sched, "alert_checks")
	last, ok := job["last_run"].(map[string]any)
	if !ok {
		t.Fatalf("expected last_run object in status (AC-12), got %v", job["last_run"])
	}
	ts, err := time.Parse(time.RFC3339, fmt.Sprint(last["time"]))
	if err != nil {
		t.Fatalf("last_run.time not RFC3339: %v", err)
	}
	if ts.Before(before2.Truncate(time.Second)) {
		t.Fatalf("expected status last_run.time >= %v (AC-12), got %v", before2, ts)
	}
}

// Spec Abschnitt 8: Produktions-Defaults der injizierbaren Budget-Felder.
func TestBudgetDefaults_MatchSpec(t *testing.T) {
	cfg := &config.Config{PythonCoreURL: "http://localhost:8000", SchedulerTimezone: "Europe/Vienna"}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	checks := []struct {
		name string
		got  time.Duration
		want time.Duration
	}{
		{"alertRunBudget", sched.alertRunBudget, 720 * time.Second},
		{"alertWaitBudget", sched.alertWaitBudget, 300 * time.Second},
		{"alertCallCap", sched.alertCallCap, 1800 * time.Second},
		{"briefingRunBudget", sched.briefingRunBudget, 1440 * time.Second},
		{"briefingWaitBudget", sched.briefingWaitBudget, 600 * time.Second},
	}
	for _, c := range checks {
		if c.got != c.want {
			t.Errorf("expected default %s=%v (Spec 8), got %v", c.name, c.want, c.got)
		}
	}
}

// statusJob sucht den Status-Eintrag eines Jobs (beide Status()-Zweige).
func statusJob(t *testing.T, sched *Scheduler, jobID string) map[string]any {
	t.Helper()
	jobs, ok := sched.Status()["jobs"].([]map[string]any)
	if !ok {
		t.Fatalf("status jobs should be []map[string]any")
	}
	for _, j := range jobs {
		if j["id"] == jobID {
			return j
		}
	}
	t.Fatalf("job %s not found in status", jobID)
	return nil
}

// F002 (Spec Abschnitt 7): Ist das Rest-Laufbudget kleiner als das
// Wartebudget, wartet der Aufruf nur das Rest-Laufbudget -- der Lauf endet
// nahe am Laufbudget, nicht erst nach dem vollen Wartebudget.
func TestUserCallWaitBudget_WaitCappedByRemainingRunBudget(t *testing.T) {
	bs := newBudgetServer(t)
	bs.setHang("bob", true)

	sched, _, _ := newBudgetScheduler(t, bs.srv.URL, "bob")
	sched.alertWaitBudget = 3 * time.Second
	sched.alertRunBudget = 150 * time.Millisecond

	start := time.Now()
	sched.alertChecks()
	elapsed := time.Since(start)

	if elapsed >= 1500*time.Millisecond {
		t.Fatalf("expected the wait to be capped by the remaining run budget (150ms), not the 3s wait budget (Spec 7), took %v", elapsed)
	}
	if got := bs.count("bob"); got != 1 {
		t.Fatalf("test setup: expected 1 POST for bob, got %d", got)
	}
	if bob := mustUserRecord(t, sched, "alert_checks", "bob"); bob.LastStatus != "budget" {
		t.Fatalf("expected bob 'budget' after waiting the remaining run budget, got %q", bob.LastStatus)
	}
}

// F003 (Spec Abschnitte 3/8): Briefing-Teiljobs verwenden die Briefing-
// Budgets, nicht die Alarm-Werte. Alarm-Budgets winzig, Briefing gross --
// ein Nutzer mit mittlerer Antwortzeit ist in beiden Briefing-Jobs "ok".
func TestUserCallWaitBudget_BriefingJobsUseBriefingBudgets(t *testing.T) {
	bs := newBudgetServer(t)
	bs.setDelay("bob", 200*time.Millisecond)

	sched, _, _ := newBudgetScheduler(t, bs.srv.URL, "alice", "bob")
	sched.alertWaitBudget = 20 * time.Millisecond
	sched.alertRunBudget = 40 * time.Millisecond
	sched.briefingWaitBudget = 3 * time.Second
	sched.briefingRunBudget = 6 * time.Second

	sched.tripReports()
	sched.comparePresetsDaily()

	for _, jobID := range []string{"trip_reports_hourly", "compare_presets_daily"} {
		for _, uid := range []string{"alice", "bob"} {
			if r := mustUserRecord(t, sched, jobID, uid); r.LastStatus != "ok" {
				t.Fatalf("expected %s/%s 'ok' under the briefing budgets (Spec 8), got %q", jobID, uid, r.LastStatus)
			}
		}
		if lr := lastRunOf(sched, jobID); lr == nil || lr.Status != "ok" {
			t.Fatalf("expected %s ranked 'ok', got %+v", jobID, lr)
		}
	}
}

// F003 (Spec Abschnitt 3): Briefing-Teiljobs haben KEINEN eigenen Deckel --
// ein haengender Briefing-Aufruf bleibt markiert, auch wenn der Alarm-Deckel
// laengst abgelaufen waere.
func TestUserCallWaitBudget_BriefingJobHasNoCallCap(t *testing.T) {
	bs := newBudgetServer(t)
	bs.setHang("bob", true)

	sched, _, _ := newBudgetScheduler(t, bs.srv.URL, "alice", "bob")
	sched.alertCallCap = 60 * time.Millisecond
	sched.alertWaitBudget = 30 * time.Millisecond
	sched.briefingWaitBudget = 30 * time.Millisecond

	sched.tripReports()
	if bob := mustUserRecord(t, sched, "trip_reports_hourly", "bob"); bob.LastStatus != "budget" {
		t.Fatalf("test setup: expected bob 'budget' in trip_reports_hourly, got %q", bob.LastStatus)
	}
	time.Sleep(400 * time.Millisecond) // mehr als das Sechsfache des Alarm-Deckels
	if !sched.callBudget.IsInFlight("trip_reports_hourly", "bob") {
		t.Fatalf("expected the briefing call to stay in flight -- briefing jobs get no call cap (Spec 3)")
	}
}

// F003 (Gegenrichtung): Alarm-Jobs verwenden die Alarm-Budgets, nicht die
// Briefing-Werte. Briefing-Budgets winzig, Alarm gross -- derselbe Nutzer ist
// im Alarm-Job "ok".
func TestUserCallWaitBudget_AlertJobUsesAlertBudgets(t *testing.T) {
	bs := newBudgetServer(t)
	bs.setDelay("bob", 200*time.Millisecond)

	sched, _, _ := newBudgetScheduler(t, bs.srv.URL, "alice", "bob")
	sched.briefingWaitBudget = 20 * time.Millisecond
	sched.briefingRunBudget = 40 * time.Millisecond
	sched.alertWaitBudget = 3 * time.Second
	sched.alertRunBudget = 6 * time.Second

	sched.alertChecks()

	for _, uid := range []string{"alice", "bob"} {
		if r := mustUserRecord(t, sched, "alert_checks", uid); r.LastStatus != "ok" {
			t.Fatalf("expected %s 'ok' under the alert budgets (Spec 8), got %q", uid, r.LastStatus)
		}
	}
}
