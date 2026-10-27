package scheduler

// TDD RED: Issue #1405 Scheibe S4b — "Erfolg heisst Wirkung" (Go-Seite).
// Spec: docs/specs/modules/fix_1405_s4b_erfolg_heisst_wirkung.md
//
//   AC-6   TestInboundStatus_*            Laufstatus von inbound_command_poll
//          wertet failed/partial der Antwort von /inbound-commands aus
//          (heute ROT: pollRun nutzt triggerGlobalEndpointRes, das nur den
//          HTTP-Code prueft). triggerGlobalEndpoint bleibt fuer andere Jobs
//          unveraendert (Gegenprobe, gruen).
//   AC-7   TestInboundKick_*              failed>0 koppelt KEINEN zusaetzlichen
//          Nachversuch an kickRound; Nachversuch haengt nur an processed/busy
//          (Regressionswaechter, gruen).
//   AC-26  TestNoticeFailedStatus_*       notice_failed ohne failed ⇒ "partial",
//          failed ⇒ "error", ok ⇒ "ok"; Fan-out-Rangfolge ueber die echten
//          Jobs trip_reports_hourly (AC-9/AC-10) und alert_checks (AC-25)
//          (Regressionswaechter, gruen).
//
// Fake-Python-Core per httptest; Laufstatus wird ueber Status() gelesen
// (derselbe Pfad wie /api/scheduler/status). Kein Netz, kein MQ: der
// Notifier wird auf eine stille Attrappe gesetzt (sonst echter MQ-Versand
// bei der Job-Flanke).

import (
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"

	"github.com/henemm/gregor-api/internal/config"
)

// fakeCoreFixed antwortet auf jeden Pfad mit HTTP 200 und body; zaehlt Aufrufe je Pfad.
type fakeCoreFixed struct {
	srv   *httptest.Server
	mu    sync.Mutex
	calls map[string]int
}

func newFakeCoreFixed(t *testing.T, body string) *fakeCoreFixed {
	t.Helper()
	c := &fakeCoreFixed{calls: map[string]int{}}
	c.srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		c.mu.Lock()
		c.calls[r.URL.Path]++
		c.mu.Unlock()
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, body)
	}))
	t.Cleanup(c.srv.Close)
	return c
}

func (c *fakeCoreFixed) count(p string) int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.calls[p]
}

// newSilentScheduler baut einen Scheduler gegen url, ohne echten MQ-Versand.
func newSilentScheduler(t *testing.T, url string, users ...string) *Scheduler {
	t.Helper()
	cfg := &config.Config{PythonCoreURL: url, SchedulerTimezone: "Europe/Vienna"}
	s, err := New(cfg, testStoreWithUsers(t, users...))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	s.notifier = func(_, _, _, _, _ string) error { return nil }
	return s
}

// lastRunStatusOf liest last_run.status des Jobs ueber Status() (Status-Endpunkt-Pfad).
func lastRunStatusOf(t *testing.T, s *Scheduler, jobID string) string {
	t.Helper()
	jobs, ok := s.Status()["jobs"].([]map[string]any)
	if !ok {
		t.Fatalf("Status()[\"jobs\"] hat unerwarteten Typ: %T", s.Status()["jobs"])
	}
	for _, j := range jobs {
		if j["id"] != jobID {
			continue
		}
		lr, ok := j["last_run"].(map[string]any)
		if !ok || lr == nil {
			t.Fatalf("Job %q: last_run fehlt nach dem Lauf: %#v", jobID, j["last_run"])
		}
		st, _ := lr["status"].(string)
		return st
	}
	t.Fatalf("Job %q nicht in Status()[\"jobs\"]", jobID)
	return ""
}

// ---------------------------------------------------------------------------
// AC-6: Laufstatus des Befehls-Posteingangs (inbound_command_poll)
// ---------------------------------------------------------------------------

func TestInboundStatus_LaufstatusFolgtAntwort(t *testing.T) {
	faelle := []struct {
		name string
		body string
		want string
	}{
		// ROT heute: Postfach nicht erreichbar, nichts verarbeitet -> muss "error" sein.
		{"failed>0 => error", `{"status":"partial","count":0,"processed":0,"failed":1}`, "error"},
		// ROT heute: Teilerfolg ohne failed -> muss "partial" sein.
		{"partial ohne failed => partial", `{"status":"partial","count":0,"processed":0}`, "partial"},
		// Gegenprobe (gruen): alles verarbeitet -> "ok".
		{"ok => ok", `{"status":"ok","count":2,"processed":2,"failed":0}`, "ok"},
		// Gegenprobe (gruen): fehlende Zugangsdaten bleiben kein Fehler.
		{"skipped => ok", `{"status":"skipped","count":0,"processed":0}`, "ok"},
	}
	for _, f := range faelle {
		t.Run(f.name, func(t *testing.T) {
			core := newFakeCoreFixed(t, f.body)
			s := newSilentScheduler(t, core.srv.URL, "alice", "bob")

			s.inboundCommands()

			if n := core.count(pfadMail); n != 1 {
				t.Fatalf("erwartet genau 1 Aufruf von %s, bekam %d", pfadMail, n)
			}
			if got := lastRunStatusOf(t, s, JobInboundCommandPoll); got != f.want {
				t.Fatalf("inbound_command_poll last_run.status = %q, erwartet %q (Antwort %s)",
					got, f.want, f.body)
			}
		})
	}
}

// AC-6 ueber den Push-Weg: auch ein Kick-Lauf verbucht failed>0 als "error".
func TestInboundStatus_KickLaufMitFailedMeldetError(t *testing.T) {
	core := newKickCore(t)
	core.fallback[pfadMail] = `{"status":"partial","count":0,"processed":0,"failed":1}`
	s, _ := newKickScheduler(t, core)
	s.notifier = func(_, _, _, _, _ string) error { return nil }

	s.kickRound(jobMail)

	if got := lastRunStatusOf(t, s, jobMail); got != "error" {
		t.Fatalf("Kick-Lauf mit failed=1: last_run.status = %q, erwartet \"error\"", got)
	}
}

// AC-6 Gegenprobe: triggerGlobalEndpoint (andere globale Jobs) bleibt
// unveraendert -- wertet weiterhin nur den HTTP-Code aus.
func TestInboundStatus_TriggerGlobalEndpointBleibtUnveraendert(t *testing.T) {
	core := newFakeCoreFixed(t, `{"status":"partial","count":0,"failed":3}`)
	s := newSilentScheduler(t, core.srv.URL)

	if err := s.triggerGlobalEndpoint("/api/scheduler/some-global-job"); err != nil {
		t.Fatalf("triggerGlobalEndpoint muss den Antwortkoerper weiter ignorieren, bekam %v", err)
	}
}

// AC-6 Gegenprobe: der Premium-SMS-Poll behaelt seine Auswertung.
func TestInboundStatus_PremiumSmsPollUnveraendert(t *testing.T) {
	core := newFakeCoreFixed(t, `{"status":"partial","count":0,"processed":0,"failed":1}`)
	s := newSilentScheduler(t, core.srv.URL)

	s.premiumSmsPoll()

	if got := lastRunStatusOf(t, s, JobPremiumSMSPoll); got != "error" {
		t.Fatalf("premium_sms_poll last_run.status = %q, erwartet \"error\"", got)
	}
}

// ---------------------------------------------------------------------------
// AC-7: failed>0 loest keinen zusaetzlichen Nachversuch aus
// ---------------------------------------------------------------------------

// Cron-Lauf: genau EIN Aufruf, auch bei failed>0.
func TestInboundKick_CronLaufMitFailedGenauEinAufruf(t *testing.T) {
	core := newFakeCoreFixed(t, `{"status":"partial","count":0,"processed":0,"failed":1}`)
	s := newSilentScheduler(t, core.srv.URL)

	s.inboundCommands()
	settle()

	if n := core.count(pfadMail); n != 1 {
		t.Fatalf("Cron-Lauf mit failed=1: erwartet genau 1 Aufruf, bekam %d", n)
	}
}

// Kick-Runde: die Zahl der Nachversuche haengt nur an processed/busy, nicht an
// failed. processed>0 + failed>0 -> 1 Aufruf; processed=0 + failed>0 -> gleich
// viele Aufrufe wie processed=0 ohne failed.
func TestInboundKick_NachversuchHaengtNichtAnFailed(t *testing.T) {
	faelle := []struct {
		name string
		body string
	}{
		{"processed=1 failed=1", `{"status":"partial","count":1,"processed":1,"failed":1}`},
		{"processed=1 failed=0", `{"status":"ok","count":1,"processed":1,"failed":0}`},
		{"processed=0 failed=1", `{"status":"partial","count":0,"processed":0,"failed":1}`},
		{"processed=0 failed=0", `{"status":"ok","count":0,"processed":0,"failed":0}`},
	}
	want := map[string]int{}
	for _, f := range faelle {
		core := newKickCore(t)
		core.fallback[pfadMail] = f.body
		s, _ := newKickScheduler(t, core)
		s.notifier = func(_, _, _, _, _ string) error { return nil }

		s.kickRound(jobMail)
		settle()
		want[f.name] = core.callCount(pfadMail)
	}
	if want["processed=1 failed=1"] != 1 {
		t.Errorf("processed=1 failed=1: erwartet genau 1 Aufruf (kein Nachversuch), bekam %d",
			want["processed=1 failed=1"])
	}
	if want["processed=1 failed=1"] != want["processed=1 failed=0"] {
		t.Errorf("failed veraendert die Nachversuche bei processed=1: %d vs %d",
			want["processed=1 failed=1"], want["processed=1 failed=0"])
	}
	if want["processed=0 failed=1"] != want["processed=0 failed=0"] {
		t.Errorf("failed veraendert die Nachversuche bei processed=0: %d vs %d",
			want["processed=0 failed=1"], want["processed=0 failed=0"])
	}
	if exp := len(kickRetryDelays[jobMail]); want["processed=0 failed=1"] != exp {
		t.Errorf("processed=0 failed=1: erwartet %d Aufrufe (Nachversuche wie bisher), bekam %d",
			exp, want["processed=0 failed=1"])
	}
}

// ---------------------------------------------------------------------------
// AC-26 (+ Go-Teil von AC-9/AC-10/AC-25): notice_failed ⇒ "partial"
// ---------------------------------------------------------------------------

const (
	bodyNoticePartial = `{"status":"partial","count":1,"notice_failed":1,"failed":0}`
	bodyHardFailed    = `{"status":"partial","count":0,"notice_failed":0,"failed":1}`
	bodyOkNoNotice    = `{"status":"ok","count":1,"notice_failed":0,"failed":0}`
)

func TestNoticeFailedStatus_TriggerEndpointForUserKlassifikation(t *testing.T) {
	faelle := []struct {
		name string
		body string
		want string // "partial" | "error" | "ok"
	}{
		{"notice_failed ohne failed => partial", bodyNoticePartial, "partial"},
		{"failed => error", bodyHardFailed, "error"},
		{"ok => ok", bodyOkNoNotice, "ok"},
	}
	for _, f := range faelle {
		t.Run(f.name, func(t *testing.T) {
			core := newFakeCoreFixed(t, f.body)
			s := newSilentScheduler(t, core.srv.URL)

			err := s.triggerEndpointForUser("/api/scheduler/trip-reports", "alice")
			var pe *partialRunError
			got := "ok"
			if err != nil {
				got = "error"
				if errors.As(err, &pe) {
					got = "partial"
				}
			}
			if got != f.want {
				t.Fatalf("Klassifikation %q, erwartet %q (err=%v)", got, f.want, err)
			}
		})
	}
}

// Fan-out ueber die echten Jobs: Antwort je Nutzer, Status ueber Status().
func TestNoticeFailedStatus_FanOutRangfolgeEchteJobs(t *testing.T) {
	jobs := []struct {
		id  string
		run func(s *Scheduler)
	}{
		{"trip_reports_hourly", func(s *Scheduler) { s.tripReports() }},
		{"alert_checks", func(s *Scheduler) { s.alertChecks() }},
	}
	faelle := []struct {
		name       string
		alice, bob string
		want       string
	}{
		{"alle ok => ok", bodyOkNoNotice, bodyOkNoNotice, "ok"},
		{"partial+ok => partial", bodyNoticePartial, bodyOkNoNotice, "partial"},
		{"partial+error => error", bodyNoticePartial, bodyHardFailed, "error"},
	}
	for _, j := range jobs {
		for _, f := range faelle {
			t.Run(j.id+"/"+f.name, func(t *testing.T) {
				srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
					w.WriteHeader(http.StatusOK)
					switch r.URL.Query().Get("user_id") {
					case "alice":
						fmt.Fprint(w, f.alice)
					case "bob":
						fmt.Fprint(w, f.bob)
					default:
						fmt.Fprint(w, bodyOkNoNotice)
					}
				}))
				defer srv.Close()
				s := newSilentScheduler(t, srv.URL, "alice", "bob")

				j.run(s)

				if got := lastRunStatusOf(t, s, j.id); got != f.want {
					t.Fatalf("%s last_run.status = %q, erwartet %q", j.id, got, f.want)
				}
			})
		}
	}
}
