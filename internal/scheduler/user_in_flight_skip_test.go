package scheduler

// ---------------------------------------------------------------------------
// Fix #2149 Scheibe B — In-Flight-Register: kein zweiter POST, solange der
// Vorlauf-Aufruf noch laeuft; Spaetergebnis zaehlt nicht rueckwirkend; Cap
// gibt den Marker ohne Buchung frei; Register ist nicht persistiert.
//
// Spec: docs/specs/modules/fix_2149_scheduler_budget_teilb.md (Abschnitte 2,
// 3, 5, 6, 7). Helfer: user_call_wait_budget_test.go.
// ---------------------------------------------------------------------------

import (
	"strings"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/store"
)

// waitMarkerReleased pollt das In-Flight-Register, bis der Marker fuer
// (jobID, uid) weg ist (Cap-Ablauf hat keinen anderen beobachtbaren Effekt --
// "keine Buchung irgendeiner Art", Spec Abschnitt 3).
func waitMarkerReleased(t *testing.T, sched *Scheduler, jobID, uid string) {
	t.Helper()
	deadline := time.Now().Add(5 * time.Second)
	for time.Now().Before(deadline) {
		if !sched.callBudget.IsInFlight(jobID, uid) {
			return
		}
		time.Sleep(5 * time.Millisecond)
	}
	t.Fatalf("expected in-flight marker for (%s, %s) to be released by the call cap within 5s", jobID, uid)
}

// AC-2: B's Aufruf aus Lauf 1 laeuft beim Start von Lauf 2 noch -- der
// Python-Core bekommt fuer B KEINEN zweiten POST, B wird als
// "skipped_in_flight" gebucht. Die uebrigen Nutzer laufen normal weiter.
func TestUserInFlight_SecondRunSkipsWithoutSecondPost(t *testing.T) {
	bs := newBudgetServer(t)
	bs.setHang("bob", true)

	sched, _, _ := newBudgetScheduler(t, bs.srv.URL, "alice", "bob", "carol")
	sched.alertWaitBudget = 50 * time.Millisecond

	sched.alertChecks() // Lauf 1: bob budget, Aufruf laeuft weiter
	sched.alertChecks() // Lauf 2: bob noch in flight

	if got := bs.count("bob"); got != 1 {
		t.Fatalf("expected exactly 1 POST for bob across both runs -- no second POST while "+
			"the first call is still in flight (AC-2), got %d", got)
	}
	for _, uid := range []string{"alice", "carol"} {
		if got := bs.count(uid); got != 2 {
			t.Fatalf("expected 2 POSTs for %s (other users unaffected, AC-2), got %d", uid, got)
		}
	}
	bob := mustUserRecord(t, sched, "alert_checks", "bob")
	if bob.LastStatus != "skipped_in_flight" {
		t.Fatalf("expected bob booked as 'skipped_in_flight' in run 2 (AC-2), got %q", bob.LastStatus)
	}
	if bob.ConsecutiveFailures != 2 || bob.ConsecutivePartial != 0 {
		t.Fatalf("expected budget + skipped_in_flight to count as failures (2/0, Spec 5), got failures=%d partial=%d",
			bob.ConsecutiveFailures, bob.ConsecutivePartial)
	}
}

// AC-3: budget, skipped_in_flight, skipped_in_flight -- nach dem dritten Lauf
// genau EINE MQ-Nachricht mit Prioritaet "high" ueber die Scheibe-A-Buendelung.
func TestUserInFlight_ThreeBudgetOrSkipRunsAlertHighOnce(t *testing.T) {
	bs := newBudgetServer(t)
	bs.setHang("bob", true)

	sched, rec, _ := newBudgetScheduler(t, bs.srv.URL, "alice", "bob")
	sched.alertWaitBudget = 50 * time.Millisecond

	sched.alertChecks() // budget
	sched.alertChecks() // skipped_in_flight
	if got := rec.count.Load(); got != 0 {
		t.Fatalf("expected no alert after 2 budget/skip runs (threshold 3), got %d", got)
	}
	sched.alertChecks() // skipped_in_flight -> Schwelle 3

	if got := rec.count.Load(); got != 1 {
		t.Fatalf("expected exactly 1 MQ message after the 3rd budget/skip run (AC-3), got %d", got)
	}
	if p := rec.lastPriority(); p != "high" {
		t.Fatalf("expected priority 'high' (AC-3), got %q", p)
	}
	body := rec.lastBody()
	if !strings.Contains(body, "bob") || strings.Contains(body, "alice") {
		t.Fatalf("expected the bundled alert to name bob only, got %q", body)
	}

	sched.alertChecks() // 4. skip: kein erneuter Alarm
	if got := rec.count.Load(); got != 1 {
		t.Fatalf("expected no re-fire on the 4th skipped run, got %d", got)
	}
}

// AC-4: B antwortet in jedem Lauf knapp NACH dem Wartebudget erfolgreich. Das
// spaete "ok" wird zu Beginn des Folgelaufs geerntet (neuer POST moeglich),
// setzt ConsecutiveFailures aber NICHT zurueck -- nach dem dritten Lauf feuert
// genau ein high-Alarm.
//
// Grenze dieses Tests: die informative LastRun/LastStatus-Aktualisierung durch
// die Ernte ist von aussen nicht getrennt beobachtbar, weil derselbe Lauf B
// unmittelbar danach neu bucht. Beobachtbar ist die Ernte selbst: ohne sie
// bliebe der Marker aktiv und B bekaeme keinen neuen POST (count bliebe 1).
func TestUserInFlight_LateSuccessDoesNotResetFailureStreak(t *testing.T) {
	bs := newBudgetServer(t)
	bs.setDelay("bob", 150*time.Millisecond)

	sched, rec, _ := newBudgetScheduler(t, bs.srv.URL, "alice", "bob")
	sched.alertWaitBudget = 40 * time.Millisecond

	for run := 1; run <= 3; run++ {
		sched.alertChecks()
		bob := mustUserRecord(t, sched, "alert_checks", "bob")
		if bob.LastStatus != "budget" {
			t.Fatalf("run %d: expected bob 'budget' (late-but-successful answer), got %q", run, bob.LastStatus)
		}
		if bob.ConsecutiveFailures != run {
			t.Fatalf("run %d: expected ConsecutiveFailures=%d -- a harvested late 'ok' must not reset the streak (AC-4), got %d",
				run, run, bob.ConsecutiveFailures)
		}
		if run < 3 {
			if got := rec.count.Load(); got != 0 {
				t.Fatalf("run %d: expected no alert yet, got %d", run, got)
			}
			// alice (sofort) + bob (spaet) haben geantwortet; kurze Frist, bis
			// die Hintergrund-Goroutine das Ergebnis in ihren Kanal gelegt hat.
			bs.waitFinished(t, 2)
			time.Sleep(200 * time.Millisecond)
		}
	}

	if got := bs.count("bob"); got != 3 {
		t.Fatalf("expected 3 POSTs for bob -- the late result must be harvested at the start of the "+
			"next run so the marker is released (AC-4/Spec 6), got %d", got)
	}
	if got := rec.count.Load(); got != 1 {
		t.Fatalf("expected exactly 1 alert after the 3rd budget run despite late successes (AC-4), got %d", got)
	}
	if p := rec.lastPriority(); p != "high" {
		t.Fatalf("expected priority 'high' (AC-4), got %q", p)
	}
}

// AC-5: Der Cap von B's erstem Aufruf ist abgelaufen, Lauf 2 hat einen
// frischen Marker gesetzt. Antwortet danach der ALTE Aufruf, wird sein
// Ergebnis verworfen: keine Zustandsaenderung, und der frische Marker bleibt
// (Lauf 3 schickt keinen neuen POST).
func TestUserInFlight_StaleResultAfterCapIsDiscarded(t *testing.T) {
	bs := newBudgetServer(t)
	bs.setHang("bob", true)

	sched, _, _ := newBudgetScheduler(t, bs.srv.URL, "alice", "bob")
	sched.alertWaitBudget = 30 * time.Millisecond
	sched.alertCallCap = 150 * time.Millisecond

	sched.alertChecks() // Lauf 1: bob budget, Gate 0, Cap 150ms
	waitMarkerReleased(t, sched, "alert_checks", "bob")

	sched.alertCallCap = 20 * time.Second // Lauf-2-Aufruf soll in flight bleiben
	sched.alertChecks()                    // Lauf 2: neuer POST, Gate 1, frischer Marker
	if got := bs.count("bob"); got != 2 {
		t.Fatalf("test setup: expected a fresh POST for bob in run 2 after cap release, got %d", got)
	}
	after2 := mustUserRecord(t, sched, "alert_checks", "bob")

	// Alten Aufruf (Gate 0) antworten lassen.
	bs.releaseGate(t, 0)
	bs.waitFinished(t, 3) // alice x2 + alter bob-Aufruf
	time.Sleep(200 * time.Millisecond)

	now := mustUserRecord(t, sched, "alert_checks", "bob")
	if now != after2 {
		t.Fatalf("expected the stale result of the capped call to change nothing (AC-5):\n before=%+v\n after =%+v", after2, now)
	}

	sched.alertChecks() // Lauf 3: frischer Marker aus Lauf 2 muss greifen
	if got := bs.count("bob"); got != 2 {
		t.Fatalf("expected no new POST in run 3 -- the stale result must not release the fresh marker (AC-5), got %d POSTs", got)
	}
	bob := mustUserRecord(t, sched, "alert_checks", "bob")
	if bob.LastStatus != "skipped_in_flight" {
		t.Fatalf("expected bob 'skipped_in_flight' in run 3 (AC-5), got %q", bob.LastStatus)
	}
	if bob.ConsecutiveFailures != 3 {
		t.Fatalf("expected ConsecutiveFailures=3 (budget, budget, skipped), got %d", bob.ConsecutiveFailures)
	}

	// Kein Nutzerbezug im oeffentlichen Status.
	if lr := lastRunOf(sched, "alert_checks"); lr != nil &&
		(strings.Contains(lr.Error, "bob") || strings.Contains(lr.Error, "?user_id=")) {
		t.Fatalf("expected no user reference in public last_run.error (AC-5), got %q", lr.Error)
	}
}

// AC-6: B's Aufruf laeuft laenger als der Alarm-Cap -- der Marker wird
// freigegeben, es erfolgt KEINE Buchung, und der naechste Lauf loest fuer B
// einen neuen POST aus.
func TestUserInFlight_CapReleasesMarkerWithoutBooking(t *testing.T) {
	bs := newBudgetServer(t)
	bs.setHang("bob", true)

	sched, _, _ := newBudgetScheduler(t, bs.srv.URL, "alice", "bob")
	sched.alertWaitBudget = 20 * time.Millisecond
	sched.alertCallCap = 80 * time.Millisecond

	sched.alertChecks() // bob budget
	after1 := mustUserRecord(t, sched, "alert_checks", "bob")
	if after1.LastStatus != "budget" || after1.ConsecutiveFailures != 1 {
		t.Fatalf("test setup: expected bob budget/1 after run 1, got %+v", after1)
	}

	waitMarkerReleased(t, sched, "alert_checks", "bob")
	if now := mustUserRecord(t, sched, "alert_checks", "bob"); now != after1 {
		t.Fatalf("expected cap expiry to book nothing (AC-6):\n before=%+v\n after =%+v", after1, now)
	}

	sched.alertCallCap = 20 * time.Second
	sched.alertChecks()
	if got := bs.count("bob"); got != 2 {
		t.Fatalf("expected a new POST for bob after the cap released the marker (AC-6), got %d", got)
	}
	bob := mustUserRecord(t, sched, "alert_checks", "bob")
	if bob.LastStatus != "budget" || bob.ConsecutiveFailures != 2 {
		t.Fatalf("expected run 2 to book a fresh 'budget' (not skipped_in_flight), got %+v", bob)
	}
}

// AC-14: Das In-Flight-Register lebt nur im Prozessspeicher. Eine neue
// *Scheduler-Instanz ueber denselben Store-Pfad (simulierter Neustart) loest
// fuer B sofort einen neuen POST aus, obwohl die alte Instanz noch einen
// Marker haelt.
func TestUserInFlight_RegisterNotPersistedAcrossRestart(t *testing.T) {
	bs := newBudgetServer(t)
	bs.setHang("bob", true)

	sched1, _, tmpDir := newBudgetScheduler(t, bs.srv.URL, "alice", "bob")
	sched1.alertWaitBudget = 30 * time.Millisecond

	sched1.alertChecks() // bob in flight
	sched1.alertChecks() // Gegenprobe: alte Instanz ueberspringt bob wirklich
	if got := bs.count("bob"); got != 1 {
		t.Fatalf("test setup: expected the old instance to hold a real marker (1 POST), got %d", got)
	}

	cfg := &config.Config{PythonCoreURL: bs.srv.URL, SchedulerTimezone: "Europe/Vienna"}
	sched2, err := New(cfg, store.New(tmpDir, "alice"))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	rec2 := &recordingNotifier{}
	sched2.notifier = rec2.fn()
	sched2.alertWaitBudget = 30 * time.Millisecond

	sched2.alertChecks()
	if got := bs.count("bob"); got != 2 {
		t.Fatalf("expected a new POST for bob from the fresh instance -- no marker survives a restart (AC-14), got %d", got)
	}
	bob := mustUserRecord(t, sched2, "alert_checks", "bob")
	if bob.LastStatus != "budget" {
		t.Fatalf("expected the new instance to book bob as 'budget', not 'skipped_in_flight' (AC-14), got %q", bob.LastStatus)
	}
}

// F001 (Register-Ebene, deterministisch): Ein verspaetetes Finish mit dem
// Token eines ALTEN Aufrufs darf den frischen Marker, der inzwischen fuer
// denselben (Job, Nutzer) per Begin gesetzt wurde, nicht entfernen.
func TestInFlightRegister_StaleTokenFinishKeepsFreshMarker(t *testing.T) {
	b := newUserCallBudget()
	ch1 := make(chan error, 1)
	tok1 := b.Begin("alert_checks", "bob", ch1, 0, nil)
	ch1 <- nil
	if _, ok := b.TryHarvest("alert_checks", "bob"); !ok {
		t.Fatalf("test setup: expected the first call's result to be harvested")
	}

	ch2 := make(chan error, 1)
	tok2 := b.Begin("alert_checks", "bob", ch2, 0, nil)
	if tok1 == tok2 {
		t.Fatalf("test setup: expected distinct tokens, got %v twice", tok1)
	}

	if b.Finish("alert_checks", "bob", tok1) {
		t.Fatalf("expected Finish with the stale token to report 'not removed' (Spec 2/3)")
	}
	if !b.IsInFlight("alert_checks", "bob") {
		t.Fatalf("expected the fresh marker to survive a stale-token Finish (Spec 2/3, AC-5)")
	}
	if !b.Finish("alert_checks", "bob", tok2) {
		t.Fatalf("expected Finish with the current token to remove the marker")
	}
	if b.IsInFlight("alert_checks", "bob") {
		t.Fatalf("expected no marker after Finish with the current token")
	}
}

// F001 (Scheduler-Ebene, mit Request-Zaehler): Der Deckel von B's Lauf-1-
// Aufruf laeuft ab, sein Callback kommt aber erst zum Zug, NACHDEM fuer B
// bereits ein frischer Marker (neuer Token) hinterlegt ist. Der verspaetete
// Callback darf diesen Marker nicht freigeben: der naechste Lauf schickt
// KEINEN zweiten POST fuer B.
//
// Die Ueberholung wird deterministisch erzwungen: der Test haelt den
// Register-Mutex, bis der Deckel-Callback daran blockiert, und bildet unter
// derselben Sperre Ernte + frisches Begin nach (Eintrag mit neuem Token).
func TestUserInFlight_LateCapCallbackKeepsFreshMarkerNoSecondPost(t *testing.T) {
	bs := newBudgetServer(t)
	bs.setHang("bob", true)

	sched, _, _ := newBudgetScheduler(t, bs.srv.URL, "alice", "bob")
	sched.alertWaitBudget = 30 * time.Millisecond
	sched.alertCallCap = 150 * time.Millisecond

	sched.alertChecks() // Lauf 1: bob budget, Marker tok1 mit Deckel 150ms
	if got := bs.count("bob"); got != 1 {
		t.Fatalf("test setup: expected 1 POST for bob in run 1, got %d", got)
	}

	reg := sched.callBudget
	reg.mu.Lock()
	locked := true
	t.Cleanup(func() {
		if locked {
			reg.mu.Unlock()
		}
	})
	// Deckel feuert waehrend der Sperre; der Callback blockiert in Finish.
	time.Sleep(600 * time.Millisecond)
	old, ok := reg.state["alert_checks"]["bob"]
	if !ok {
		t.Fatalf("test setup: expected bob's run-1 marker to still be registered")
	}
	reg.removeLocked("alert_checks", "bob", old)
	reg.next++
	reg.state["alert_checks"]["bob"] = &inFlightEntry{token: reg.next, resultCh: make(chan error, 1), started: time.Now()}
	reg.mu.Unlock()
	locked = false

	// Dem blockierten Deckel-Callback Zeit geben, durchzulaufen.
	time.Sleep(300 * time.Millisecond)
	if !reg.IsInFlight("alert_checks", "bob") {
		t.Fatalf("expected the late cap callback of the old token to leave the fresh marker in place (F001)")
	}

	sched.alertCallCap = 20 * time.Second
	sched.alertChecks() // Lauf 2: frischer Marker muss greifen
	if got := bs.count("bob"); got != 1 {
		t.Fatalf("expected no second POST for bob while the fresh marker is active (F001/AC-2), got %d POSTs", got)
	}
	if bob := mustUserRecord(t, sched, "alert_checks", "bob"); bob.LastStatus != "skipped_in_flight" {
		t.Fatalf("expected bob 'skipped_in_flight' in run 2 (F001), got %q", bob.LastStatus)
	}
}
