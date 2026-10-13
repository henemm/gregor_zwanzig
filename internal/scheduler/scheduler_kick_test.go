package scheduler

// TDD RED: Issue #2439 Scheibe (a) — Push-Eingang fuer Befehle (Premium-SMS +
// E-Mail), "Webhook = Weckruf". Spec:
// docs/specs/modules/feat_2439_befehle_push_eingang.md
//
// Dieser Test treibt den ECHTEN Pfad (Scheduler.Kick -> recordRun-Bucht ->
// HTTP-POST an den Python-Core) gegen einen httptest-Server, der Aufrufe zaehlt,
// gleichzeitige Aufrufe misst, Antworten der Reihe nach skriptet und den ersten
// Aufruf je Kanal blockieren kann. Zugesichert wird dort, wo es WIRKT: an den
// Aufrufen, die der Server tatsaechlich sieht -- nicht an einem internen Flag.
//
// AC-Zuordnung:
//   AC-5   TestKick_*Coalescing*, TestKick_KehrtSofortZurueck..., TestKick_NieZweiLaeufe...,
//          TestKick_WeckrufWaehrendLaufGehtNichtVerloren, TestKick_MindestabstandZwischenLaeufen
//   AC-6   TestKick_BusyAntwortSetztWeckrufErneutAufPending (busy-Teil, Go-Seite)
//   AC-7   TestKick_SMSNachversuch*, TestKick_MailNachversuch*
//   AC-8   TestPushEingang_CronFallbackBleibtUndPushLastReceivedFehltOhneWebhook
//   AC-9   TestPushStatus_Zaehler* (Scheduler-Seite; Handler-Seite in
//          internal/handler/inbound_webhooks_test.go)
//   AC-13  TestPushMissed_*
//
// Festgelegte Schnittstelle (die Tests DEFINIEREN sie):
//   s.Kick(jobID string)                 -- asynchron, kehrt sofort zurueck
//   s.kickSleep func(time.Duration)      -- injizierbare Wartefunktion
//   s.RecordPushReceived(jobID) / s.RecordPushRejected(jobID)
//   Status()["jobs"][i]["push"] fuer premium_sms_poll + inbound_command_poll:
//     last_received (RFC3339|nil), received_total, rejected_total,
//     kicks_coalesced, missed_total, last_missed
//   Python-Antwort {"status":"busy"} -> Go setzt pending erneut;
//   Antwortfeld "processed" (int) steuert den Nachversuch-Abbruch und AC-13.
//
// Hinweis zur Mail-Antwort: der Fake liefert fuer /inbound-commands BEIDE Felder
// "processed" und "count" mit demselben Wert -- welches der beiden die
// Python-Seite fuer E-Mail ausgibt, legt die Spec nicht fest.
//
// Keine t.Parallel(): gemeinsame Wartezeiten/Zaehler pro Test.

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
)

const (
	pfadSMS  = "/api/scheduler/inbound-sms"
	pfadMail = "/api/scheduler/inbound-commands"

	jobSMS  = "premium_sms_poll"
	jobMail = "inbound_command_poll"
)

// kickCore ist der Fake-Python-Core: zaehlt, misst Gleichzeitigkeit, skriptet.
type kickCore struct {
	srv *httptest.Server

	mu          sync.Mutex
	calls       map[string]int
	inFlight    map[string]int
	maxInFlight map[string]int
	script      map[string][]string // je Pfad: Antworten der Reihe nach
	fallback    map[string]string   // je Pfad: Antwort, wenn das Skript erschoepft ist
	gate        map[string]chan struct{}
	entered     chan string
}

func processedBody(n int) string {
	return fmt.Sprintf(`{"status":"ok","processed":%d,"count":%d}`, n, n)
}

func newKickCore(t *testing.T) *kickCore {
	t.Helper()
	c := &kickCore{
		calls:       map[string]int{},
		inFlight:    map[string]int{},
		maxInFlight: map[string]int{},
		script:      map[string][]string{},
		fallback:    map[string]string{pfadSMS: processedBody(1), pfadMail: processedBody(1)},
		gate:        map[string]chan struct{}{},
		entered:     make(chan string, 64),
	}
	c.srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		p := r.URL.Path
		c.mu.Lock()
		c.calls[p]++
		n := c.calls[p]
		c.inFlight[p]++
		if c.inFlight[p] > c.maxInFlight[p] {
			c.maxInFlight[p] = c.inFlight[p]
		}
		body := c.fallback[p]
		if n-1 < len(c.script[p]) {
			body = c.script[p][n-1]
		}
		gate := c.gate[p]
		c.mu.Unlock()

		if n == 1 && gate != nil {
			c.entered <- p
			<-gate
		}

		c.mu.Lock()
		c.inFlight[p]--
		c.mu.Unlock()
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, body)
	}))
	t.Cleanup(c.srv.Close)
	return c
}

func (c *kickCore) callCount(p string) int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.calls[p]
}

func (c *kickCore) maxConcurrent(p string) int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.maxInFlight[p]
}

// sleepRec zeichnet die von Kick angeforderten Wartezeiten auf, ohne zu warten.
type sleepRec struct {
	mu sync.Mutex
	d  []time.Duration
}

func (r *sleepRec) sleep(d time.Duration) {
	r.mu.Lock()
	r.d = append(r.d, d)
	r.mu.Unlock()
}

func (r *sleepRec) sum() time.Duration {
	r.mu.Lock()
	defer r.mu.Unlock()
	var s time.Duration
	for _, d := range r.d {
		if d > 0 {
			s += d
		}
	}
	return s
}

func (r *sleepRec) snapshot() []time.Duration {
	r.mu.Lock()
	defer r.mu.Unlock()
	return append([]time.Duration(nil), r.d...)
}

func newKickScheduler(t *testing.T, core *kickCore) (*Scheduler, *sleepRec) {
	t.Helper()
	cfg := &config.Config{PythonCoreURL: core.srv.URL, SchedulerTimezone: "Europe/Vienna"}
	s, err := New(cfg, testStoreWithUsers(t, "alice"))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	rec := &sleepRec{}
	s.kickSleep = rec.sleep
	return s, rec
}

func waitFor(t *testing.T, limit time.Duration, cond func() bool, msg string) {
	t.Helper()
	deadline := time.Now().Add(limit)
	for time.Now().Before(deadline) {
		if cond() {
			return
		}
		time.Sleep(5 * time.Millisecond)
	}
	t.Fatalf("Zeitueberschreitung nach %v: %s", limit, msg)
}

// settle laesst eine eventuell fehlerhaft zusaetzlich startende Kick-Goroutine
// sichtbar werden, bevor "genau N Laeufe" geprueft wird.
func settle() { time.Sleep(300 * time.Millisecond) }

func asInt(t *testing.T, v any) int {
	t.Helper()
	switch n := v.(type) {
	case int:
		return n
	case int32:
		return int(n)
	case int64:
		return int(n)
	case uint64:
		return int(n)
	case float64:
		return int(n)
	}
	t.Fatalf("Zahlenfeld erwartet, bekam %T (%v)", v, v)
	return 0
}

// pushOf liest Status()["jobs"][id]["push"] -- das Feld MUSS existieren.
func pushOf(t *testing.T, s *Scheduler, jobID string) map[string]any {
	t.Helper()
	jobs, ok := s.Status()["jobs"].([]map[string]any)
	if !ok {
		t.Fatalf("Status()[\"jobs\"] hat unerwarteten Typ")
	}
	for _, j := range jobs {
		if j["id"] != jobID {
			continue
		}
		push, ok := j["push"].(map[string]any)
		if !ok {
			t.Fatalf("Job %q: Feld \"push\" fehlt oder ist kein map[string]any: %T", jobID, j["push"])
		}
		for _, f := range []string{"last_received", "received_total", "rejected_total",
			"kicks_coalesced", "missed_total", "last_missed"} {
			if _, ok := push[f]; !ok {
				t.Fatalf("Job %q: push.%s fehlt: %+v", jobID, f, push)
			}
		}
		return push
	}
	t.Fatalf("Job %q nicht in Status()[\"jobs\"]", jobID)
	return nil
}

func kickLastRunStatus(t *testing.T, s *Scheduler, jobID string) any {
	t.Helper()
	jobs := s.Status()["jobs"].([]map[string]any)
	for _, j := range jobs {
		if j["id"] == jobID {
			return j["last_run"]
		}
	}
	t.Fatalf("Job %q nicht im Status", jobID)
	return nil
}

// ---------------------------------------------------------------------------
// Grundverhalten: Kick stoesst den bestehenden Poll-Job an (AC-1/AC-2 Go-Seite)
// ---------------------------------------------------------------------------

func TestKick_SMSStoesstPremiumSmsPollAn(t *testing.T) {
	core := newKickCore(t)
	s, _ := newKickScheduler(t, core)

	s.Kick(jobSMS)

	waitFor(t, 3*time.Second, func() bool { return core.callCount(pfadSMS) >= 1 },
		"Kick(premium_sms_poll) muss POST /api/scheduler/inbound-sms ausloesen")
	settle()
	if core.callCount(pfadMail) != 0 {
		t.Errorf("Kick(premium_sms_poll) darf den Mail-Poll nicht ausloesen, Aufrufe: %d", core.callCount(pfadMail))
	}
	waitFor(t, 2*time.Second, func() bool { return kickLastRunStatus(t, s, jobSMS) != nil },
		"der Kick-Lauf muss ueber recordRun als last_run des Jobs sichtbar werden")
}

func TestKick_MailStoesstInboundCommandPollAn(t *testing.T) {
	core := newKickCore(t)
	s, _ := newKickScheduler(t, core)

	s.Kick(jobMail)

	waitFor(t, 3*time.Second, func() bool { return core.callCount(pfadMail) >= 1 },
		"Kick(inbound_command_poll) muss POST /api/scheduler/inbound-commands ausloesen")
	settle()
	if core.callCount(pfadSMS) != 0 {
		t.Errorf("Kick(inbound_command_poll) darf den SMS-Poll nicht ausloesen, Aufrufe: %d", core.callCount(pfadSMS))
	}
}

// ---------------------------------------------------------------------------
// AC-5: Coalescing, kein verschluckter Weckruf, nie zwei Laeufe gleichzeitig
// ---------------------------------------------------------------------------

// AC-5: 20 parallele Kicks waehrend ein Lauf blockiert -> Kick kehrt sofort
// zurueck, hoechstens 2 Laeufe insgesamt (der laufende + ein Folgelauf),
// nie zwei gleichzeitig, kicks_coalesced zaehlt jeden Kick bei laufender
// Kick-Goroutine (Spec: "laeuft die Goroutine schon -> kicks_coalesced++").
func TestKick_ZwanzigParalleleKicksWaehrendLauf_Coalescing(t *testing.T) {
	core := newKickCore(t)
	release := make(chan struct{})
	core.gate[pfadSMS] = release
	s, _ := newKickScheduler(t, core)

	s.Kick(jobSMS)
	select {
	case <-core.entered:
	case <-time.After(3 * time.Second):
		t.Fatal("der erste Kick startete keinen Lauf")
	}

	const n = 20
	done := make(chan struct{})
	go func() {
		var wg sync.WaitGroup
		for i := 0; i < n; i++ {
			wg.Add(1)
			go func() { defer wg.Done(); s.Kick(jobSMS) }()
		}
		wg.Wait()
		close(done)
	}()
	select {
	case <-done:
	case <-time.After(2 * time.Second):
		close(release)
		t.Fatal("Kick darf nicht auf den laufenden Lauf warten (muss sofort zurueckkehren)")
	}

	close(release)
	waitFor(t, 3*time.Second, func() bool { return core.callCount(pfadSMS) >= 2 },
		"ein Kick WAEHREND des Laufs darf nicht verloren gehen: es muss ein Folgelauf kommen")
	settle()

	if got := core.callCount(pfadSMS); got != 2 {
		t.Errorf("20 Kicks waehrend eines Laufs duerfen hoechstens EINEN weiteren Lauf ausloesen, Laeufe gesamt: %d (erwartet 2)", got)
	}
	if got := core.maxConcurrent(pfadSMS); got != 1 {
		t.Errorf("nie mehr als ein Lauf gleichzeitig, gemessen am Server: %d", got)
	}
	push := pushOf(t, s, jobSMS)
	if got := asInt(t, push["kicks_coalesced"]); got != n {
		t.Errorf("kicks_coalesced erwartet %d (jeder Kick bei laufender Kick-Goroutine), bekam %d", n, got)
	}
}

// AC-5 Gegenprobe: ohne laufenden Lauf entsteht nichts "Verschmolzenes".
func TestKick_EinzelnerKickOhneLaufZaehltNichtAlsCoalesced(t *testing.T) {
	core := newKickCore(t)
	s, _ := newKickScheduler(t, core)

	s.Kick(jobSMS)
	waitFor(t, 3*time.Second, func() bool { return core.callCount(pfadSMS) >= 1 }, "Lauf erwartet")
	settle()

	if got := core.callCount(pfadSMS); got != 1 {
		t.Errorf("ein einzelner Kick (processed=1) loest genau einen Lauf aus, bekam %d", got)
	}
	if got := asInt(t, pushOf(t, s, jobSMS)["kicks_coalesced"]); got != 0 {
		t.Errorf("kicks_coalesced erwartet 0, bekam %d", got)
	}
}

// AC-5: Kick waehrend ein CRON-Lauf (gleicher jobLock) laeuft -> kein zweiter
// gleichzeitiger Aufruf; der Weckruf bleibt erhalten und laeuft danach.
func TestKick_WeckrufWaehrendCronLaufGehtNichtVerloren(t *testing.T) {
	core := newKickCore(t)
	release := make(chan struct{})
	core.gate[pfadSMS] = release
	s, _ := newKickScheduler(t, core)

	cronDone := make(chan struct{})
	go func() { s.premiumSmsPoll(); close(cronDone) }()
	select {
	case <-core.entered:
	case <-time.After(3 * time.Second):
		t.Fatal("der Cron-Lauf kam nicht beim Server an")
	}

	s.Kick(jobSMS)
	time.Sleep(200 * time.Millisecond)
	if got := core.callCount(pfadSMS); got != 1 {
		close(release)
		t.Fatalf("waehrend des Cron-Laufs darf der Kick keinen parallelen Aufruf absetzen, Aufrufe: %d", got)
	}

	close(release)
	<-cronDone
	waitFor(t, 3*time.Second, func() bool { return core.callCount(pfadSMS) >= 2 },
		"der Weckruf muss nach dem Cron-Lauf noch ausgefuehrt werden (nicht verschluckt)")
	settle()
	if got := core.callCount(pfadSMS); got != 2 {
		t.Errorf("erwartet genau 2 Laeufe (Cron + Weckruf), bekam %d", got)
	}
	if got := core.maxConcurrent(pfadSMS); got != 1 {
		t.Errorf("nie mehr als ein Lauf gleichzeitig, gemessen am Server: %d", got)
	}
}

// AC-5/Spec "Mindestabstand ~2 s": zwischen zwei tatsaechlichen Laeufen wird
// ~2 s gewartet (ueber kickSleep angefordert, nicht real gewartet).
func TestKick_MindestabstandZwischenZweiLaeufen(t *testing.T) {
	core := newKickCore(t)
	release := make(chan struct{})
	core.gate[pfadSMS] = release
	s, rec := newKickScheduler(t, core)

	s.Kick(jobSMS)
	select {
	case <-core.entered:
	case <-time.After(3 * time.Second):
		t.Fatal("kein Lauf gestartet")
	}
	s.Kick(jobSMS) // pending waehrend des Laufs
	close(release)
	waitFor(t, 3*time.Second, func() bool { return core.callCount(pfadSMS) >= 2 }, "Folgelauf erwartet")
	settle()

	sum := rec.sum()
	if sum < 1500*time.Millisecond || sum > 3*time.Second {
		t.Errorf("zwischen zwei Laeufen ~2 s Mindestabstand erwartet (angefordert: %v)", rec.snapshot())
	}
}

// ---------------------------------------------------------------------------
// AC-6 (Go-Seite): busy -> Weckruf wird erneut auf pending gesetzt
// ---------------------------------------------------------------------------

func TestKick_BusyAntwortSetztWeckrufErneutAufPending(t *testing.T) {
	core := newKickCore(t)
	// Viermal busy, dann Treffer: ein Nachversuch-Pfad (max. 3 Laeufe) wuerde frueher
	// aufgeben; nur "busy => pending erneut setzen" liefert alle 5 Laeufe.
	busy := `{"status":"busy"}`
	core.script[pfadSMS] = []string{busy, busy, busy, busy, processedBody(1)}
	s, _ := newKickScheduler(t, core)

	s.Kick(jobSMS)

	waitFor(t, 3*time.Second, func() bool { return core.callCount(pfadSMS) >= 5 },
		"Antwort {\"status\":\"busy\"} muss jedes Mal einen spaeteren weiteren Lauf ausloesen")
	settle()
	if got := core.callCount(pfadSMS); got != 5 {
		t.Errorf("4x busy dann processed=1 -> genau 5 Laeufe erwartet, bekam %d", got)
	}
}

func TestKick_BusyAntwortMail_ErneuterLauf(t *testing.T) {
	core := newKickCore(t)
	busy := `{"status":"busy"}`
	core.script[pfadMail] = []string{busy, busy, busy, busy, processedBody(1)}
	s, _ := newKickScheduler(t, core)

	s.Kick(jobMail)

	waitFor(t, 3*time.Second, func() bool { return core.callCount(pfadMail) >= 5 },
		"busy beim Mail-Poll muss jedes Mal einen weiteren Lauf ausloesen")
	settle()
	if got := core.callCount(pfadMail); got != 5 {
		t.Errorf("4x busy dann processed=1 -> genau 5 Laeufe erwartet, bekam %d", got)
	}
}

// ---------------------------------------------------------------------------
// AC-7: Nachversuche gegen Journal-Verzoegerung (SMS 0/3/8 s, Mail ~2 s)
// ---------------------------------------------------------------------------

func TestKick_SMSNachversuch(t *testing.T) {
	faelle := []struct {
		name    string
		script  []string
		laeufe  int
		sumMin  time.Duration
		sumMax  time.Duration
		erklaer string
	}{
		{"0,0,1 -> 3 Laeufe, Abbruch nach Treffer", []string{processedBody(0), processedBody(0), processedBody(1)},
			3, 8 * time.Second, 11 * time.Second, "Laeufe bei 0 s / 3 s / 8 s"},
		{"1 -> 1 Lauf, keine Nachversuche", []string{processedBody(1)},
			1, 0, 1 * time.Second, "findet der erste Lauf die Nachricht, gibt es keine weiteren"},
		{"0,0,0 -> 3 Laeufe und Ende", []string{processedBody(0), processedBody(0), processedBody(0)},
			3, 8 * time.Second, 11 * time.Second, "nach dem dritten Lauf ist Schluss"},
		{"0,1 -> 2 Laeufe, Abbruch nach 3 s", []string{processedBody(0), processedBody(1)},
			2, 3 * time.Second, 6 * time.Second, "Abbruch, sobald ein Lauf processed>0 meldet"},
	}
	for _, f := range faelle {
		t.Run(f.name, func(t *testing.T) {
			core := newKickCore(t)
			core.script[pfadSMS] = f.script
			core.fallback[pfadSMS] = processedBody(0) // ein vierter Lauf waere sichtbar
			s, rec := newKickScheduler(t, core)

			s.Kick(jobSMS)

			waitFor(t, 3*time.Second, func() bool { return core.callCount(pfadSMS) >= f.laeufe },
				fmt.Sprintf("%d Laeufe erwartet (%s)", f.laeufe, f.erklaer))
			settle()
			if got := core.callCount(pfadSMS); got != f.laeufe {
				t.Errorf("erwartet genau %d Laeufe (%s), bekam %d", f.laeufe, f.erklaer, got)
			}
			if sum := rec.sum(); sum < f.sumMin || sum > f.sumMax {
				t.Errorf("angeforderte Wartezeiten %v (Summe %v) ausserhalb [%v, %v]",
					rec.snapshot(), sum, f.sumMin, f.sumMax)
			}
		})
	}
}

func TestKick_MailNachversuch(t *testing.T) {
	faelle := []struct {
		name   string
		script []string
		laeufe int
		sumMin time.Duration
		sumMax time.Duration
	}{
		{"0 -> ein Nachversuch nach ~2 s", []string{processedBody(0), processedBody(0)}, 2, 2 * time.Second, 3500 * time.Millisecond},
		{"1 -> kein Nachversuch", []string{processedBody(1)}, 1, 0, 1 * time.Second},
	}
	for _, f := range faelle {
		t.Run(f.name, func(t *testing.T) {
			core := newKickCore(t)
			core.script[pfadMail] = f.script
			core.fallback[pfadMail] = processedBody(0)
			s, rec := newKickScheduler(t, core)

			s.Kick(jobMail)

			waitFor(t, 3*time.Second, func() bool { return core.callCount(pfadMail) >= f.laeufe },
				fmt.Sprintf("%d Laeufe erwartet", f.laeufe))
			settle()
			if got := core.callCount(pfadMail); got != f.laeufe {
				t.Errorf("erwartet genau %d Laeufe, bekam %d", f.laeufe, got)
			}
			if sum := rec.sum(); sum < f.sumMin || sum > f.sumMax {
				t.Errorf("angeforderte Wartezeiten %v (Summe %v) ausserhalb [%v, %v]",
					rec.snapshot(), sum, f.sumMin, f.sumMax)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// AC-8: Fallback-Poll */5 besteht weiter, kein Push-Lebenszeichen ohne Webhook
// ---------------------------------------------------------------------------

func TestPushEingang_CronFallbackBleibtUndPushLastReceivedFehltOhneWebhook(t *testing.T) {
	core := newKickCore(t)
	s, _ := newKickScheduler(t, core)

	gefunden := map[string]cronSchedule{}
	for _, e := range s.cron.Entries() {
		if meta, ok := s.entryMap[e.ID]; ok && (meta.id == jobSMS || meta.id == jobMail) {
			gefunden[meta.id] = e.Schedule
		}
	}
	base := time.Date(2026, 10, 13, 12, 0, 0, 0, time.UTC)
	for _, id := range []string{jobSMS, jobMail} {
		sch, ok := gefunden[id]
		if !ok {
			t.Fatalf("Cron-Eintrag %s fehlt (Fallback-Poll muss bestehen bleiben)", id)
		}
		first := sch.Next(base)
		if d := sch.Next(first).Sub(first); d != 5*time.Minute {
			t.Errorf("%s: Fallback-Poll erwartet alle 5 min, bekam %v", id, d)
		}
	}

	// Cron-Lauf OHNE jeden Webhook: Job laeuft, aber push.last_received bleibt nil.
	s.premiumSmsPoll()
	s.inboundCommands()
	for _, id := range []string{jobSMS, jobMail} {
		push := pushOf(t, s, id)
		if push["last_received"] != nil {
			t.Errorf("%s: push.last_received muss ohne Webhook nil bleiben, bekam %v", id, push["last_received"])
		}
		if kickLastRunStatus(t, s, id) == nil {
			t.Errorf("%s: der Cron-Lauf ohne Kick muss unveraendert last_run setzen", id)
		}
	}
}

// ---------------------------------------------------------------------------
// AC-9 (Scheduler-Seite): Zaehler je Kanal, nicht global
// ---------------------------------------------------------------------------

func TestPushStatus_ZaehlerJeKanalGetrennt(t *testing.T) {
	core := newKickCore(t)
	s, _ := newKickScheduler(t, core)

	s.RecordPushReceived(jobSMS)
	s.RecordPushReceived(jobSMS)
	s.RecordPushRejected(jobSMS)
	s.RecordPushRejected(jobMail)
	s.RecordPushRejected(jobMail)
	s.RecordPushRejected(jobMail)

	sms := pushOf(t, s, jobSMS)
	mail := pushOf(t, s, jobMail)
	if got := asInt(t, sms["received_total"]); got != 2 {
		t.Errorf("sms.received_total erwartet 2, bekam %d", got)
	}
	if got := asInt(t, sms["rejected_total"]); got != 1 {
		t.Errorf("sms.rejected_total erwartet 1, bekam %d", got)
	}
	if sms["last_received"] == nil {
		t.Error("sms.last_received muss nach RecordPushReceived gesetzt sein")
	} else if str, ok := sms["last_received"].(string); !ok {
		t.Errorf("last_received muss ein RFC3339-String sein, bekam %T", sms["last_received"])
	} else if _, err := time.Parse(time.RFC3339, str); err != nil {
		t.Errorf("last_received ist kein RFC3339: %q (%v)", str, err)
	}
	if got := asInt(t, mail["received_total"]); got != 0 {
		t.Errorf("mail.received_total erwartet 0 (SMS-Zaehler leckt nicht), bekam %d", got)
	}
	if got := asInt(t, mail["rejected_total"]); got != 3 {
		t.Errorf("mail.rejected_total erwartet 3, bekam %d", got)
	}
	if mail["last_received"] != nil {
		t.Errorf("abgewiesene Aufrufe duerfen last_received NICHT setzen, bekam %v", mail["last_received"])
	}
}

// Zaehler leben am Scheduler, nicht in Paket-Globals.
func TestPushStatus_ZaehlerSindProSchedulerInstanz(t *testing.T) {
	core := newKickCore(t)
	a, _ := newKickScheduler(t, core)
	b, _ := newKickScheduler(t, core)

	a.RecordPushReceived(jobSMS)
	a.RecordPushRejected(jobMail)

	if got := asInt(t, pushOf(t, b, jobSMS)["received_total"]); got != 0 {
		t.Errorf("zweite Scheduler-Instanz sieht fremden received_total: %d", got)
	}
	if got := asInt(t, pushOf(t, b, jobMail)["rejected_total"]); got != 0 {
		t.Errorf("zweite Scheduler-Instanz sieht fremden rejected_total: %d", got)
	}
}

// ---------------------------------------------------------------------------
// AC-13: Sichtbarkeit eines ausgefallenen Sofort-Wegs (missed_total)
// ---------------------------------------------------------------------------

// Cron-Lauf mit processed>0, zu dem kein Kick/Webhook vorausging -> missed.
func TestPushMissed_CronLaufMitBefehlenOhneKickZaehltAlsVerpasst(t *testing.T) {
	core := newKickCore(t)
	core.fallback[pfadSMS] = processedBody(1)
	s, _ := newKickScheduler(t, core)

	s.premiumSmsPoll()

	push := pushOf(t, s, jobSMS)
	if got := asInt(t, push["missed_total"]); got != 1 {
		t.Errorf("Cron-Lauf mit processed=1 ohne Kick/Webhook: missed_total erwartet 1, bekam %d", got)
	}
	if push["last_missed"] == nil {
		t.Error("last_missed muss nach einem verpassten Weckruf gesetzt sein")
	}
	if got := asInt(t, pushOf(t, s, jobMail)["missed_total"]); got != 0 {
		t.Errorf("SMS-Ausfall darf den Mail-Zaehler nicht erhoehen, bekam %d", got)
	}
}

// Cron-Lauf ohne verarbeitete Befehle -> nichts verpasst.
func TestPushMissed_CronLaufOhneBefehleZaehltNicht(t *testing.T) {
	core := newKickCore(t)
	core.fallback[pfadSMS] = processedBody(0)
	s, _ := newKickScheduler(t, core)

	s.premiumSmsPoll()

	push := pushOf(t, s, jobSMS)
	if got := asInt(t, push["missed_total"]); got != 0 {
		t.Errorf("processed=0: missed_total erwartet 0, bekam %d", got)
	}
	if push["last_missed"] != nil {
		t.Errorf("last_missed muss nil bleiben, bekam %v", push["last_missed"])
	}
}

// Der Kick-Lauf selbst und ein Cron-Lauf kurz nach einem Kick zaehlen NICHT.
func TestPushMissed_LaufNachKickZaehltNicht(t *testing.T) {
	core := newKickCore(t)
	core.fallback[pfadSMS] = processedBody(1)
	s, _ := newKickScheduler(t, core)

	s.Kick(jobSMS)
	waitFor(t, 3*time.Second, func() bool { return core.callCount(pfadSMS) >= 1 }, "Kick-Lauf erwartet")
	settle()
	if got := asInt(t, pushOf(t, s, jobSMS)["missed_total"]); got != 0 {
		t.Fatalf("der Kick-Lauf selbst (processed=1) ist kein verpasster Weckruf, missed_total=%d", got)
	}

	s.premiumSmsPoll() // Cron-Lauf innerhalb der 5-Minuten-Spanne nach dem Kick
	if got := asInt(t, pushOf(t, s, jobSMS)["missed_total"]); got != 0 {
		t.Errorf("Lauf nach Kick (<5 min): missed_total erwartet 0, bekam %d", got)
	}
}

// Ein gueltiger Webhook (RecordPushReceived) in den letzten 5 Minuten genuegt.
func TestPushMissed_LaufNachGueltigemWebhookZaehltNicht(t *testing.T) {
	core := newKickCore(t)
	core.fallback[pfadSMS] = processedBody(1)
	s, _ := newKickScheduler(t, core)

	s.RecordPushReceived(jobSMS)
	s.premiumSmsPoll()

	if got := asInt(t, pushOf(t, s, jobSMS)["missed_total"]); got != 0 {
		t.Errorf("Lauf nach gueltigem Webhook: missed_total erwartet 0, bekam %d", got)
	}
}

// Ein ABGEWIESENER Webhook ist kein Lebenszeichen des Sofort-Wegs.
func TestPushMissed_AbgewiesenerWebhookVerhindertVerpasstNicht(t *testing.T) {
	core := newKickCore(t)
	core.fallback[pfadSMS] = processedBody(1)
	s, _ := newKickScheduler(t, core)

	s.RecordPushRejected(jobSMS)
	s.premiumSmsPoll()

	if got := asInt(t, pushOf(t, s, jobSMS)["missed_total"]); got != 1 {
		t.Errorf("nur abgewiesene Webhooks: der Cron-Lauf mit processed=1 zaehlt als verpasst, bekam missed_total=%d", got)
	}
}

// Mail-Kanal: gleiche Regel ueber den Cron-Einstieg inboundCommands().
func TestPushMissed_MailCronLaufMitBefehlenOhneKick(t *testing.T) {
	core := newKickCore(t)
	core.fallback[pfadMail] = processedBody(2)
	s, _ := newKickScheduler(t, core)

	s.inboundCommands()

	if got := asInt(t, pushOf(t, s, jobMail)["missed_total"]); got != 1 {
		t.Errorf("Mail: missed_total erwartet 1, bekam %d", got)
	}
	if got := asInt(t, pushOf(t, s, jobSMS)["missed_total"]); got != 0 {
		t.Errorf("Mail-Ausfall darf den SMS-Zaehler nicht erhoehen, bekam %d", got)
	}
}
