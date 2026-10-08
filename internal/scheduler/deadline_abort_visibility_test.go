package scheduler

// ---------------------------------------------------------------------------
// Feature #1539 S0 -- Zeitobergrenzen-Abbrueche und Laufdauer im Status
// sichtbar machen (kumulativer Zaehler deadline_aborts{}, last_run.duration_s).
//
// Spec: docs/specs/modules/feat_1539_s0_s1a_beobachtbarkeit_atomare_schreiber.md
//       (Abschnitt A, AC-1 bis AC-5)
//
// Fake-Python-Server mit echten Antwortkoerpern wie api/routers/scheduler.py
// sie liefert (status:"partial", reason:"deadline", checked, skipped,
// skipped_ids, duration_s). Der Status-Body wird bewusst als map[string]any
// aus dem serialisierten JSON gelesen -- keine neuen Struct-Felder.
// ---------------------------------------------------------------------------

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"
)

const (
	abortUserA = "hikeralpha"
	abortUserB = "hikerbeta"
	abortTrip  = "gr221-etappe-geheim"
)

// deadlineBody ist die Python-Antwort eines Zeitobergrenzen-Abbruchs.
var deadlineBody = fmt.Sprintf(`{"status":"partial","reason":"deadline","count":0,"checked":2,"skipped":2,`+
	`"skipped_ids":["%s","other-trip"],"duration_s":180.02}`, abortTrip)

const okBody = `{"status":"ok","count":1,"checked":4,"skipped":0,"duration_s":0.4}`

// abortServer antwortet je user_id mit einem steuerbaren Koerper/Verzoegerung.
type abortServer struct {
	srv *httptest.Server

	mu     sync.Mutex
	bodies map[string]string
	delays map[string]time.Duration
	done   chan struct{}
}

func newAbortServer(t *testing.T) *abortServer {
	t.Helper()
	a := &abortServer{
		bodies: map[string]string{},
		delays: map[string]time.Duration{},
		done:   make(chan struct{}),
	}
	a.srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		uid := r.URL.Query().Get("user_id")
		a.mu.Lock()
		body, delay := a.bodies[uid], a.delays[uid]
		a.mu.Unlock()
		if body == "" {
			body = okBody
		}
		if delay > 0 {
			select {
			case <-time.After(delay):
			case <-a.done:
				return
			}
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, body)
	}))
	t.Cleanup(a.srv.Close)
	t.Cleanup(func() { close(a.done) }) // LIFO: vor srv.Close()
	return a
}

func (a *abortServer) set(uid, body string, delay time.Duration) {
	a.mu.Lock()
	defer a.mu.Unlock()
	a.bodies[uid] = body
	a.delays[uid] = delay
}

// statusDoc serialisiert Status() wie der HTTP-Handler und parst zurueck.
func statusDoc(t *testing.T, sched *Scheduler) (map[string]any, string) {
	t.Helper()
	raw, err := json.Marshal(sched.Status())
	if err != nil {
		t.Fatalf("marshal status: %v", err)
	}
	var doc map[string]any
	if err := json.Unmarshal(raw, &doc); err != nil {
		t.Fatalf("unmarshal status: %v", err)
	}
	return doc, string(raw)
}

// jobDoc liefert den Job-Eintrag aus dem JSON-geparsten Status.
func jobDoc(t *testing.T, doc map[string]any, jobID string) map[string]any {
	t.Helper()
	jobs, _ := doc["jobs"].([]any)
	for _, j := range jobs {
		if m, ok := j.(map[string]any); ok && m["id"] == jobID {
			return m
		}
	}
	t.Fatalf("job %s not found in status", jobID)
	return nil
}

func abortsOf(t *testing.T, job map[string]any) map[string]any {
	t.Helper()
	m, ok := job["deadline_aborts"].(map[string]any)
	if !ok || m == nil {
		t.Fatalf("expected deadline_aborts{} on job %v, got %v", job["id"], job["deadline_aborts"])
	}
	return m
}

func jsonNum(t *testing.T, m map[string]any, key string) float64 {
	t.Helper()
	v, ok := m[key].(float64)
	if !ok {
		t.Fatalf("expected numeric field %q in %v", key, m)
	}
	return v
}

// AC-1: Der Abbruch bleibt sichtbar, obwohl der naechste ok-Lauf users.partial
// wieder auf 0 setzt.
func TestDeadlineAbort_StaysVisibleAfterNextOkRun(t *testing.T) {
	as := newAbortServer(t)
	as.set(abortUserA, deadlineBody, 0)
	sched, _, _ := newBudgetScheduler(t, as.srv.URL, abortUserA)

	sched.alertChecks() // Abbruch
	as.set(abortUserA, okBody, 0)
	sched.alertChecks() // ok-Lauf danach

	doc, _ := statusDoc(t, sched)
	job := jobDoc(t, doc, "alert_checks")
	users, _ := job["users"].(map[string]any)
	if got := jsonNum(t, users, "partial"); got != 0 {
		t.Fatalf("test setup: expected users.partial=0 after ok run, got %v", got)
	}
	aborts := abortsOf(t, job)
	if got := jsonNum(t, aborts, "total"); got != 1 {
		t.Fatalf("expected deadline_aborts.total=1 after ok run (AC-1), got %v", got)
	}
	if at, _ := aborts["last_at"].(string); at == "" {
		t.Fatalf("expected deadline_aborts.last_at set (AC-1), got %v", aborts["last_at"])
	}
	if got := jsonNum(t, aborts, "last_skipped"); got != 2 {
		t.Fatalf("expected deadline_aborts.last_skipped=2 (AC-1), got %v", got)
	}
}

// AC-2: Zwei Nutzer, nur A bricht ab -- total==1, Body ohne IDs/skipped_ids.
func TestDeadlineAbort_OnlyOneOfTwoUsersCountsAndBodyLeaksNoIDs(t *testing.T) {
	as := newAbortServer(t)
	as.set(abortUserA, deadlineBody, 0)
	as.set(abortUserB, okBody, 0)
	sched, _, _ := newBudgetScheduler(t, as.srv.URL, abortUserA, abortUserB)

	sched.alertChecks()

	doc, body := statusDoc(t, sched)
	aborts := abortsOf(t, jobDoc(t, doc, "alert_checks"))
	if got := jsonNum(t, aborts, "total"); got != 1 {
		t.Fatalf("expected deadline_aborts.total=1 for one aborting user (AC-2), got %v", got)
	}
	for _, leak := range []string{abortUserA, abortUserB, abortTrip, "other-trip", "skipped_ids"} {
		if strings.Contains(body, leak) {
			t.Fatalf("status body must not contain %q (AC-2), got %s", leak, body)
		}
	}
}

// AC-3: Nachzuegler nach Wartebudget mit reason deadline zaehlt genau einmal,
// in_flight ist im selben Moment 1, duration_s enthaelt die Nachzuegler-Zeit nicht.
func TestDeadlineAbort_LateResultCountedOnceAndNotInDuration(t *testing.T) {
	as := newAbortServer(t)
	const serverDelay = 800 * time.Millisecond
	as.set(abortUserA, deadlineBody, serverDelay)
	sched, _, _ := newBudgetScheduler(t, as.srv.URL, abortUserA)
	sched.alertWaitBudget = 50 * time.Millisecond

	sched.alertChecks() // Wartebudget laeuft ab, Aufruf bleibt in flight

	doc, _ := statusDoc(t, sched)
	job := jobDoc(t, doc, "alert_checks")
	users, _ := job["users"].(map[string]any)
	if got := jsonNum(t, users, "in_flight"); got != 1 {
		t.Fatalf("expected users.in_flight=1 while the late call runs (AC-3), got %v", got)
	}
	lr, _ := job["last_run"].(map[string]any)
	dur, ok := lr["duration_s"].(float64)
	if !ok {
		t.Fatalf("expected last_run.duration_s (AC-3), got %v", lr)
	}
	if dur >= serverDelay.Seconds()/2 {
		t.Fatalf("last_run.duration_s=%v must not contain the late call time (AC-3, delay %v)", dur, serverDelay)
	}

	// Nachzuegler einsammeln (wie zu Beginn des naechsten Laufs).
	end := time.Now().Add(5 * time.Second)
	for sched.callBudget.IsInFlight("alert_checks", abortUserA) && time.Now().Before(end) {
		sched.harvestLateResult("alert_checks", abortUserA)
		time.Sleep(20 * time.Millisecond)
	}
	if sched.callBudget.IsInFlight("alert_checks", abortUserA) {
		t.Fatal("test setup: late result was never harvestable")
	}
	sched.harvestLateResult("alert_checks", abortUserA) // zweites Einsammeln darf nicht doppelt zaehlen

	doc, _ = statusDoc(t, sched)
	aborts := abortsOf(t, jobDoc(t, doc, "alert_checks"))
	if got := jsonNum(t, aborts, "total"); got != 1 {
		t.Fatalf("expected deadline_aborts.total=1 exactly once after harvest (AC-3), got %v", got)
	}
}

// AC-4: Jeder Job (Fan-out und global) traegt last_run.duration_s >= 0; die
// bisherigen Felder behalten Namen und Typen.
func TestStatusContract_EveryJobHasDurationAndKeepsOldFields(t *testing.T) {
	as := newAbortServer(t)
	sched, _, _ := newBudgetScheduler(t, as.srv.URL, abortUserA, abortUserB)

	before, _ := statusDoc(t, sched)
	var ids []string
	for _, j := range before["jobs"].([]any) {
		if m, ok := j.(map[string]any); ok {
			if id, ok := m["id"].(string); ok {
				ids = append(ids, id)
			}
		}
	}
	if len(ids) == 0 {
		t.Fatal("test setup: no jobs in status")
	}
	for _, id := range ids {
		id := id
		sched.recordRun(id, func() error {
			if fanOutJobIDs[id] {
				return sched.runForAllUsers(id, "/api/scheduler/alert-checks")
			}
			return nil // globale Jobs (u.a. data_write_selftest): Lauf ohne Seiteneffekt
		})
	}

	doc, _ := statusDoc(t, sched)
	for _, id := range ids {
		job := jobDoc(t, doc, id)
		lr, ok := job["last_run"].(map[string]any)
		if !ok {
			t.Fatalf("job %s: expected last_run after run, got %v", id, job["last_run"])
		}
		dur, ok := lr["duration_s"].(float64)
		if !ok || dur < 0 {
			t.Errorf("job %s: expected numeric last_run.duration_s >= 0 (AC-4), got %v", id, lr["duration_s"])
		}
		if _, ok := lr["time"].(string); !ok {
			t.Errorf("job %s: last_run.time must stay a string, got %v", id, lr["time"])
		}
		if s, ok := lr["status"].(string); !ok || s != "ok" {
			t.Errorf("job %s: last_run.status must stay string \"ok\", got %v", id, lr["status"])
		}
		if fanOutJobIDs[id] {
			users, ok := job["users"].(map[string]any)
			if !ok {
				t.Errorf("job %s: users{} must stay an object, got %v", id, job["users"])
				continue
			}
			for _, k := range []string{"total", "failing", "partial", "in_flight", "skipped_in_flight", "not_reached_budget"} {
				if _, ok := users[k].(float64); !ok {
					t.Errorf("job %s: users.%s must stay numeric, got %v", id, k, users[k])
				}
			}
		}
	}
}

// AC-4 (Vertrag overlap): overlap.skipped_since_last_run bleibt eine Zahl,
// und der langsame Lauf traegt danach last_run.duration_s.
func TestStatusContract_OverlapKeepsNameAndRunHasDuration(t *testing.T) {
	as := newAbortServer(t)
	sched, _, _ := newBudgetScheduler(t, as.srv.URL, abortUserA)

	release := make(chan struct{})
	started := make(chan struct{})
	finished := make(chan struct{})
	go func() {
		defer close(finished)
		sched.recordRun("alert_checks", func() error {
			close(started)
			<-release
			return nil
		})
	}()
	<-started
	sched.recordRun("alert_checks", func() error { return nil }) // Tick uebersprungen

	doc, _ := statusDoc(t, sched)
	overlap, ok := jobDoc(t, doc, "alert_checks")["overlap"].(map[string]any)
	if !ok {
		t.Fatalf("expected overlap{} while a tick was skipped, got %v", jobDoc(t, doc, "alert_checks"))
	}
	if got := jsonNum(t, overlap, "skipped_since_last_run"); got != 1 {
		t.Fatalf("expected overlap.skipped_since_last_run=1, got %v", got)
	}

	close(release)
	<-finished
	doc, _ = statusDoc(t, sched)
	lr, _ := jobDoc(t, doc, "alert_checks")["last_run"].(map[string]any)
	if _, ok := lr["duration_s"].(float64); !ok {
		t.Fatalf("expected last_run.duration_s after the overlapped run (AC-4), got %v", lr)
	}
}

// AC-5: Frischer Scheduler -- Fan-out-Jobs tragen deadline_aborts mit total 0,
// ohne last_at, mit counting_since; Nicht-Fan-out-Jobs tragen den Block nicht.
func TestDeadlineAbort_FreshSchedulerShowsZeroForFanOutOnly(t *testing.T) {
	as := newAbortServer(t)
	sched, _, _ := newBudgetScheduler(t, as.srv.URL, abortUserA)

	doc, _ := statusDoc(t, sched)
	seenFanOut := 0
	for _, j := range doc["jobs"].([]any) {
		job, ok := j.(map[string]any)
		if !ok {
			continue
		}
		id, _ := job["id"].(string)
		if id == "" {
			continue
		}
		if !fanOutJobIDs[id] {
			if _, has := job["deadline_aborts"]; has {
				t.Errorf("non-fan-out job %s must not carry deadline_aborts (AC-5)", id)
			}
			continue
		}
		seenFanOut++
		aborts := abortsOf(t, job)
		if got := jsonNum(t, aborts, "total"); got != 0 {
			t.Errorf("job %s: expected total=0 on fresh scheduler (AC-5), got %v", id, got)
		}
		if _, has := aborts["last_at"]; has {
			t.Errorf("job %s: last_at must be absent while total==0 (AC-5), got %v", id, aborts["last_at"])
		}
		if cs, _ := aborts["counting_since"].(string); cs == "" {
			t.Errorf("job %s: expected counting_since set (AC-5), got %v", id, aborts["counting_since"])
		}
	}
	if seenFanOut == 0 {
		t.Fatal("test setup: no fan-out job found in status")
	}
}

// F001: Abbruch + gescheiterter Trip (failed:1) -- gezaehlt, kein Leck.
func TestDeadlineAbort_WithFailedIsCountedAndLeaksNoIDs(t *testing.T) {
	as := newAbortServer(t)
	as.set(abortUserA, fmt.Sprintf(`{"status":"partial","reason":"deadline","count":0,"failed":1,`+
		`"checked":2,"skipped":2,"skipped_ids":["%s","other-trip"],"duration_s":180.0}`, abortTrip), 0)
	as.set(abortUserB, okBody, 0)
	sched, _, _ := newBudgetScheduler(t, as.srv.URL, abortUserA, abortUserB)

	sched.alertChecks()

	doc, body := statusDoc(t, sched)
	aborts := abortsOf(t, jobDoc(t, doc, "alert_checks"))
	if got := jsonNum(t, aborts, "total"); got != 1 {
		t.Fatalf("expected total=1 for failed+deadline, got %v", got)
	}
	for _, leak := range []string{abortUserA, abortTrip, "other-trip", "skipped_ids"} {
		if strings.Contains(body, leak) {
			t.Fatalf("status body must not contain %q, got %s", leak, body)
		}
	}
}

// F003: partial OHNE reason=deadline zaehlt nicht.
func TestDeadlineAbort_PartialWithoutDeadlineReasonNotCounted(t *testing.T) {
	as := newAbortServer(t)
	as.set(abortUserA, `{"status":"partial","count":0,"checked":2,"skipped":2}`, 0)
	sched, _, _ := newBudgetScheduler(t, as.srv.URL, abortUserA)

	sched.alertChecks()

	doc, _ := statusDoc(t, sched)
	aborts := abortsOf(t, jobDoc(t, doc, "alert_checks"))
	if got := jsonNum(t, aborts, "total"); got != 0 {
		t.Fatalf("partial without reason=deadline must not count, got %v", got)
	}
}

// F002: duration_s spiegelt die echte Laufzeit (ok- und error-Lauf).
func TestStatusContract_DurationReflectsRealRuntime(t *testing.T) {
	as := newAbortServer(t)
	const delay = 80 * time.Millisecond
	as.set(abortUserA, okBody, delay)
	sched, _, _ := newBudgetScheduler(t, as.srv.URL, abortUserA)
	sched.alertChecks()
	doc, _ := statusDoc(t, sched)
	lr, _ := jobDoc(t, doc, "alert_checks")["last_run"].(map[string]any)
	if d := jsonNum(t, lr, "duration_s"); d < delay.Seconds() {
		t.Fatalf("ok run: duration_s=%v < %v", d, delay)
	}

	sched.recordRun("alert_checks", func() error {
		time.Sleep(delay)
		return fmt.Errorf("boom")
	})
	doc, _ = statusDoc(t, sched)
	lr, _ = jobDoc(t, doc, "alert_checks")["last_run"].(map[string]any)
	if lr["status"] != "error" {
		t.Fatalf("setup: expected error status, got %v", lr["status"])
	}
	if d := jsonNum(t, lr, "duration_s"); d < delay.Seconds() {
		t.Fatalf("error run: duration_s=%v < %v", d, delay)
	}
}

// F008: failed ohne reason und HTTP 500 geben nie den Rohbody (skipped_ids) aus.
func TestStatusError_NeverEchoesRawBodySkippedIDs(t *testing.T) {
	as := newAbortServer(t)
	as.set(abortUserA, `{"status":"error","count":0,"failed":1,"checked":2,"skipped":0,"skipped_ids":[]}`, 0)
	sched, _, _ := newBudgetScheduler(t, as.srv.URL, abortUserA)
	sched.alertChecks()
	_, body := statusDoc(t, sched)
	if strings.Contains(body, "skipped_ids") {
		t.Fatalf("status must not contain skipped_ids (failed branch), got %s", body)
	}

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		fmt.Fprint(w, `{"detail":"x","skipped_ids":["`+abortTrip+`"]}`)
	}))
	defer srv.Close()
	sched2, _, _ := newBudgetScheduler(t, srv.URL, abortUserA)
	sched2.alertChecks()
	_, body2 := statusDoc(t, sched2)
	for _, leak := range []string{"skipped_ids", abortTrip} {
		if strings.Contains(body2, leak) {
			t.Fatalf("status must not contain %q (HTTP 500 branch), got %s", leak, body2)
		}
	}
}
