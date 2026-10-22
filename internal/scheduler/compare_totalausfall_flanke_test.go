package scheduler

// ---------------------------------------------------------------------------
// Fix #2286 — Ortsvergleich-Versand: Job-weite Flanke (Totalausfall / wieder OK)
//
// Spec: docs/specs/modules/fix_2286_compare_betrieb_health.md
// (Implementierungsdetails 1, AC-1, AC-2, AC-3).
//
// Heute bucht comparePresetsDaily() nur den Lauf (recordRun) -- eine Job-weite
// Meldung an infra gibt es nicht, waehrend tripReports() "Trip-Briefing-
// Totalausfall (#1346)" / "Trip-Briefing wieder OK (#1346)" meldet. Diese
// Suite faehrt den ECHTEN comparePresetsDaily()-Pfad (httptest-Core +
// Notifier-Naht s.notifier) und zaehlt die aufgezeichneten Meldungen.
// Der Nutzer-Flankenalarm aus #2149 ("Nutzer-Fehlerserie bei Job ...") wird
// ueber den Betreff getrennt gezaehlt.
// ---------------------------------------------------------------------------

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/store"
)

const (
	cmpFlankUserA = "tdd-2286-usera"
	cmpFlankUserB = "tdd-2286-userb"

	cmpTotalausfallSubject = "Vergleichs-Briefing-Totalausfall"
	cmpRecoverySubject     = "Vergleichs-Briefing wieder OK"
	cmpComparePath         = "/api/scheduler/compare-presets-daily"
	cmpTripPath            = "/api/scheduler/trip-reports"
)

// Antwortarten des Test-Cores je Nutzer.
const (
	cmpRespOK          int32 = iota // 200 {"status":"ok","count":1}
	cmpRespHTTP500                  // 500 -- harter Fehler
	cmpRespFailedBody               // 200 {"status":"partial","count":2,"failed":2} -- Provider-Totalausfall-Form
	cmpRespPartialBody              // 200 {"status":"partial","count":1} -- Teilerfolg ohne failed
)

// cmpFlankCore ist ein Test-Core, der je (Pfad, user_id) eine einstellbare
// Antwortart liefert. Nicht eingetragene Kombinationen antworten "ok".
type cmpFlankCore struct {
	mu    sync.Mutex
	modes map[string]int32 // key: path + "|" + uid
}

func (c *cmpFlankCore) set(path, uid string, mode int32) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.modes == nil {
		c.modes = map[string]int32{}
	}
	c.modes[path+"|"+uid] = mode
}

func (c *cmpFlankCore) setAll(path string, mode int32, uids ...string) {
	for _, uid := range uids {
		c.set(path, uid, mode)
	}
}

func (c *cmpFlankCore) mode(path, uid string) int32 {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.modes[path+"|"+uid]
}

func (c *cmpFlankCore) server(t *testing.T) *httptest.Server {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch c.mode(r.URL.Path, r.URL.Query().Get("user_id")) {
		case cmpRespHTTP500:
			w.WriteHeader(http.StatusInternalServerError)
			fmt.Fprint(w, `{"error":"boom"}`)
		case cmpRespFailedBody:
			w.WriteHeader(http.StatusOK)
			fmt.Fprint(w, `{"status":"partial","count":2,"failed":2}`)
		case cmpRespPartialBody:
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

// cmpFlankMsg ist eine aufgezeichnete Notifier-Meldung (Betreff getrennt vom
// Text, damit die Zaehlung je Meldungsart eindeutig ist).
type cmpFlankMsg struct {
	sender, recipient, priority, subject, body string
}

type cmpFlankRecorder struct {
	mu   sync.Mutex
	msgs []cmpFlankMsg
}

func (r *cmpFlankRecorder) fn() Notifier {
	return func(sender, recipient, priority, subject, body string) error {
		r.mu.Lock()
		defer r.mu.Unlock()
		r.msgs = append(r.msgs, cmpFlankMsg{sender, recipient, priority, subject, body})
		return nil
	}
}

// withSubject liefert alle Meldungen, deren Betreff sub enthaelt.
func (r *cmpFlankRecorder) withSubject(sub string) []cmpFlankMsg {
	r.mu.Lock()
	defer r.mu.Unlock()
	var out []cmpFlankMsg
	for _, m := range r.msgs {
		if strings.Contains(m.subject, sub) {
			out = append(out, m)
		}
	}
	return out
}

func newCmpFlankScheduler(t *testing.T, core *cmpFlankCore) (*Scheduler, *cmpFlankRecorder) {
	t.Helper()
	srv := core.server(t)
	tmpDir := t.TempDir()
	mkUsers(t, tmpDir, cmpFlankUserA, cmpFlankUserB)
	cfg := &config.Config{PythonCoreURL: srv.URL, SchedulerTimezone: "Europe/Vienna"}
	sched, err := New(cfg, store.New(tmpDir, cmpFlankUserA))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	rec := &cmpFlankRecorder{}
	sched.notifier = rec.fn()
	return sched, rec
}

// cmpJobStatusFromStatus liest last_run.status eines Jobs aus der
// oeffentlichen Status()-Antwort (dieselbe Struktur wie /api/scheduler/status).
func cmpJobStatusFromStatus(t *testing.T, sched *Scheduler, jobID string) string {
	t.Helper()
	jobs, ok := sched.Status()["jobs"].([]map[string]any)
	if !ok {
		t.Fatalf("status jobs should be []map[string]any")
	}
	for _, j := range jobs {
		if j["id"] != jobID {
			continue
		}
		lr, ok := j["last_run"].(map[string]any)
		if !ok {
			t.Fatalf("job %s has no last_run map: %v", jobID, j["last_run"])
		}
		s, _ := lr["status"].(string)
		return s
	}
	t.Fatalf("job %s not found in status", jobID)
	return ""
}

func assertNoUserIDs(t *testing.T, m cmpFlankMsg) {
	t.Helper()
	for _, uid := range []string{cmpFlankUserA, cmpFlankUserB} {
		if strings.Contains(m.subject, uid) || strings.Contains(m.body, uid) {
			t.Fatalf("job-wide Totalausfall message must not contain user id %q (AC-1): %+v", uid, m)
		}
	}
}

func assertExactlyOneTotalausfall(t *testing.T, rec *cmpFlankRecorder, ctx string) {
	t.Helper()
	got := rec.withSubject(cmpTotalausfallSubject)
	if len(got) != 1 {
		t.Fatalf("%s: expected exactly 1 %q message (AC-1), got %d: %+v",
			ctx, cmpTotalausfallSubject, len(got), got)
	}
	m := got[0]
	if m.recipient != "infra" || m.priority != "high" || m.sender != "gregor" {
		t.Fatalf("%s: Totalausfall must go gregor->infra with priority high, got %+v", ctx, m)
	}
	assertNoUserIDs(t, m)
}

// AC-1: ok -> error (ein Nutzer HTTP 500) -> genau 1 Totalausfall high an
// infra ohne Nutzerkennung, Job steht in Status() auf "error".
func TestComparePresetsDaily_OkToError_HTTP500_SendsOneTotalausfall(t *testing.T) {
	core := &cmpFlankCore{}
	sched, rec := newCmpFlankScheduler(t, core)

	sched.comparePresetsDaily() // Lauf 1: ok
	if n := len(rec.withSubject("Vergleichs-Briefing")); n != 0 {
		t.Fatalf("expected 0 compare job messages after an ok run, got %d", n)
	}

	core.set(cmpComparePath, cmpFlankUserB, cmpRespHTTP500)
	sched.comparePresetsDaily() // Lauf 2: error

	if st := cmpJobStatusFromStatus(t, sched, "compare_presets_daily"); st != "error" {
		t.Fatalf("expected compare_presets_daily status 'error', got %q", st)
	}
	assertExactlyOneTotalausfall(t, rec, "ok->error (HTTP 500)")
}

// AC-1 im Hauptszenario (Provider-Stoerung): der Core antwortet HTTP 200 mit
// failed>0 im Body -- das muss genauso die Job-Flanke ausloesen.
func TestComparePresetsDaily_OkToError_FailedBody_SendsOneTotalausfall(t *testing.T) {
	core := &cmpFlankCore{}
	sched, rec := newCmpFlankScheduler(t, core)

	sched.comparePresetsDaily() // ok
	core.set(cmpComparePath, cmpFlankUserB, cmpRespFailedBody)
	sched.comparePresetsDaily() // error via failed>0

	if st := cmpJobStatusFromStatus(t, sched, "compare_presets_daily"); st != "error" {
		t.Fatalf("expected compare_presets_daily status 'error' for failed>0 body, got %q", st)
	}
	assertExactlyOneTotalausfall(t, rec, "ok->error (failed>0 body)")
}

// AC-1 "Job-weit, nicht pro Nutzer": beide Nutzer scheitern im selben Lauf
// -> trotzdem genau EINE Totalausfall-Meldung.
func TestComparePresetsDaily_BothUsersFail_StillExactlyOneTotalausfall(t *testing.T) {
	core := &cmpFlankCore{}
	sched, rec := newCmpFlankScheduler(t, core)

	sched.comparePresetsDaily() // ok
	core.setAll(cmpComparePath, cmpRespHTTP500, cmpFlankUserA, cmpFlankUserB)
	sched.comparePresetsDaily()

	assertExactlyOneTotalausfall(t, rec, "both users failing")
}

// AC-2: error -> ok -> genau 1 "wieder OK" (normal) an infra.
func TestComparePresetsDaily_ErrorToOk_SendsOneRecovery(t *testing.T) {
	core := &cmpFlankCore{}
	sched, rec := newCmpFlankScheduler(t, core)

	core.set(cmpComparePath, cmpFlankUserB, cmpRespHTTP500)
	sched.comparePresetsDaily() // error
	core.set(cmpComparePath, cmpFlankUserB, cmpRespOK)
	sched.comparePresetsDaily() // ok

	got := rec.withSubject(cmpRecoverySubject)
	if len(got) != 1 {
		t.Fatalf("expected exactly 1 %q message after error->ok (AC-2), got %d", cmpRecoverySubject, len(got))
	}
	if got[0].recipient != "infra" || got[0].priority != "normal" {
		t.Fatalf("recovery must go to infra with priority normal, got %+v", got[0])
	}
	if n := len(rec.withSubject(cmpTotalausfallSubject)); n != 1 {
		t.Fatalf("expected exactly 1 Totalausfall over error->ok, got %d", n)
	}
}

// AC-2: error -> error -> keine zweite Totalausfall-Meldung (nur der Wechsel meldet).
func TestComparePresetsDaily_ErrorError_NoSecondTotalausfall(t *testing.T) {
	core := &cmpFlankCore{}
	sched, rec := newCmpFlankScheduler(t, core)

	core.set(cmpComparePath, cmpFlankUserB, cmpRespHTTP500)
	sched.comparePresetsDaily()
	sched.comparePresetsDaily()

	assertExactlyOneTotalausfall(t, rec, "error->error")
}

// AC-2: error -> partial -> ok: partial ueberschreibt den gespeicherten Status
// "error" nicht -- kein Recovery und kein Totalausfall im partial-Lauf, die
// Recovery-Meldung kommt erst beim echten ok-Lauf (genau 1).
func TestComparePresetsDaily_ErrorPartialOk_RecoveryOnlyAfterOk(t *testing.T) {
	core := &cmpFlankCore{}
	sched, rec := newCmpFlankScheduler(t, core)

	core.set(cmpComparePath, cmpFlankUserB, cmpRespHTTP500)
	sched.comparePresetsDaily() // error

	core.set(cmpComparePath, cmpFlankUserB, cmpRespPartialBody)
	sched.comparePresetsDaily() // partial
	if st := cmpJobStatusFromStatus(t, sched, "compare_presets_daily"); st != "partial" {
		t.Fatalf("test setup: expected run status 'partial', got %q", st)
	}
	if n := len(rec.withSubject(cmpRecoverySubject)); n != 0 {
		t.Fatalf("partial run must not send a recovery message (AC-2), got %d", n)
	}

	core.set(cmpComparePath, cmpFlankUserB, cmpRespOK)
	sched.comparePresetsDaily() // ok

	if n := len(rec.withSubject(cmpRecoverySubject)); n != 1 {
		t.Fatalf("expected exactly 1 recovery after error->partial->ok (AC-2), got %d", n)
	}
	assertExactlyOneTotalausfall(t, rec, "error->partial->ok")
}

// AC-2: error -> partial -> error ist EINE fortlaufende Stoerung -> genau 1 Totalausfall.
func TestComparePresetsDaily_ErrorPartialError_ExactlyOneTotalausfall(t *testing.T) {
	core := &cmpFlankCore{}
	sched, rec := newCmpFlankScheduler(t, core)

	core.set(cmpComparePath, cmpFlankUserB, cmpRespHTTP500)
	sched.comparePresetsDaily()
	core.set(cmpComparePath, cmpFlankUserB, cmpRespPartialBody)
	sched.comparePresetsDaily()
	core.set(cmpComparePath, cmpFlankUserB, cmpRespHTTP500)
	sched.comparePresetsDaily()

	assertExactlyOneTotalausfall(t, rec, "error->partial->error")
	if n := len(rec.withSubject(cmpRecoverySubject)); n != 0 {
		t.Fatalf("expected 0 recovery messages for error->partial->error, got %d", n)
	}
}

// AC-3: Nutzer B scheitert 3x in Folge, Nutzer A bleibt ok. Erwartet: die
// Job-weite Totalausfall-Meldung (genau 1, ohne Nutzerkennung) UND der
// #2149-Nutzeralarm (genau 1, nennt B, nicht A) -- beide unabhaengig.
func TestComparePresetsDaily_JobFlankAndUserAlarm_BothFire_OnlyFailingUser(t *testing.T) {
	core := &cmpFlankCore{}
	sched, rec := newCmpFlankScheduler(t, core)

	core.set(cmpComparePath, cmpFlankUserB, cmpRespHTTP500)
	sched.comparePresetsDaily()
	sched.comparePresetsDaily()
	sched.comparePresetsDaily()

	userAlarms := rec.withSubject("Nutzer-Fehlerserie bei Job compare_presets_daily")
	if len(userAlarms) != 1 {
		t.Fatalf("expected exactly 1 #2149 user alarm for compare_presets_daily, got %d", len(userAlarms))
	}
	if !strings.Contains(userAlarms[0].body, cmpFlankUserB) {
		t.Fatalf("user alarm must name the failing user %q, got %q", cmpFlankUserB, userAlarms[0].body)
	}
	if strings.Contains(userAlarms[0].body, cmpFlankUserA) {
		t.Fatalf("user alarm must NOT name the unaffected user %q (Mandantentrennung), got %q",
			cmpFlankUserA, userAlarms[0].body)
	}
	assertExactlyOneTotalausfall(t, rec, "job flank alongside #2149 user alarm")
}

// Getrennte Flanken-Zustaende je Job (geteilter Helper darf nicht auf die
// falsche jobID schluesseln): Trip ist bereits im Fehler, dann faellt der
// Vergleich aus -- die Vergleichs-Meldung kommt trotzdem, und Trip-Betreffe
// stammen nie aus dem Vergleichs-Lauf.
func TestBriefingDispatch_TripAndCompareFlanksAreIndependent(t *testing.T) {
	core := &cmpFlankCore{}
	sched, rec := newCmpFlankScheduler(t, core)

	core.set(cmpTripPath, cmpFlankUserB, cmpRespHTTP500)
	sched.briefingDispatch() // Trip error, Compare ok

	if n := len(rec.withSubject("Trip-Briefing-Totalausfall")); n != 1 {
		t.Fatalf("expected 1 Trip-Briefing-Totalausfall after trip error, got %d", n)
	}
	if n := len(rec.withSubject(cmpTotalausfallSubject)); n != 0 {
		t.Fatalf("compare ok must not send %q, got %d", cmpTotalausfallSubject, n)
	}

	core.set(cmpComparePath, cmpFlankUserB, cmpRespHTTP500)
	sched.briefingDispatch() // Trip error (weiterhin), Compare ok->error

	if n := len(rec.withSubject("Trip-Briefing-Totalausfall")); n != 1 {
		t.Fatalf("trip error->error must not re-alert, got %d Trip alerts", n)
	}
	assertExactlyOneTotalausfall(t, rec, "compare flank independent of trip flank")

	core.set(cmpTripPath, cmpFlankUserB, cmpRespOK)
	sched.briefingDispatch() // Trip error->ok, Compare error->error

	if n := len(rec.withSubject("Trip-Briefing wieder OK")); n != 1 {
		t.Fatalf("expected 1 Trip recovery, got %d", n)
	}
	if n := len(rec.withSubject(cmpRecoverySubject)); n != 0 {
		t.Fatalf("compare still in error must not send %q, got %d", cmpRecoverySubject, n)
	}
}
