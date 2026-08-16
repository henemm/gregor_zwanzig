// Package scheduler implements a Go cron-based scheduler that triggers
// Python services via HTTP POST endpoints.
//
// SPEC: docs/specs/modules/go_scheduler.md v1.0
package scheduler

import (
	_ "time/tzdata" // Embed timezone data for portability

	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"sync"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/notify"
	"github.com/henemm/gregor-api/internal/store"
	"github.com/robfig/cron/v3"
)

// Notifier is the function signature for inter-instance message delivery.
// Injectable for tests; defaults to notify.SendMQ.
type Notifier func(sender, recipient, priority, subject, body string) error

// jobResult tracks the last execution of a scheduled job.
type jobResult struct {
	Time   time.Time `json:"time"`
	Status string    `json:"status"` // "ok", "partial" (Issue #1447 S2a) or "error"
	Error  string    `json:"error,omitempty"`
}

// jobOverlapState zaehlt Ticks, die wegen eines noch laufenden Vorgaengers
// uebersprungen wurden — seit dem letzten TATSAECHLICH ausgefuehrten Lauf
// dieses Jobs (Issue #1447 S2a). Waechst mit jedem weiteren Skip, wird bei
// jedem echten Lauf (ok, partial ODER error) auf 0 zurueckgesetzt. Analog zu
// zone_drift in #1434: kumulativer Zaehler + eigener Zeitstempel, damit
// "einmal kurz uebersprungen" von "haengt seit N Ticks" unterscheidbar bleibt.
type jobOverlapState struct {
	SkippedSinceLastRun int        `json:"skipped_since_last_run"`
	LastSkippedAt       *time.Time `json:"last_skipped_at,omitempty"`
}

// partialRunError signalisiert, dass ein Job-Lauf teilweise erfolgreich war
// (status: "partial" ohne failed > 0 aus der Python-Antwort, Issue #1447 S1;
// oder ein Transport-Timeout, Issue #1912) — recordRun verbucht das als
// jobResult.Status "partial", nicht "error".
//
// wrapped haelt (falls vorhanden) den zugrundeliegenden Fehler fuer
// errors.As-Traversal — Issue #1912 braucht das, damit ein Aufrufer per
// errors.As gleichzeitig "ist ein Timeout" (net.Error) UND "ist partial"
// (*partialRunError) am selben err feststellen kann.
type partialRunError struct {
	msg     string
	wrapped error
}

func (e *partialRunError) Error() string { return e.msg }
func (e *partialRunError) Unwrap() error { return e.wrapped }

// isTimeoutTransportError klassifiziert einen Transportfehler aus
// (*http.Client).Post: ein echter Timeout (net.Error mit Timeout()==true,
// bzw. context.DeadlineExceeded) heisst "der Core antwortet nicht
// rechtzeitig" und ist kein Ausfallbeweis (Issue #1912). Alles andere
// (Verbindung verweigert, DNS-Fehler) bleibt ein harter Fehler — ein toter
// Core darf NICHT als "partial" durchgehen, sonst wird der Wachhund blind.
func isTimeoutTransportError(err error) bool {
	var netErr net.Error
	if errors.As(err, &netErr) && netErr.Timeout() {
		return true
	}
	return errors.Is(err, context.DeadlineExceeded)
}

// jobMeta holds the human-readable identity of a cron job.
//
// Issue #1250 Scheibe 7c: subs holds the logical sub-jobs of a unified cron
// entry (e.g. briefing_dispatch fans out to trip_reports_hourly and
// compare_presets_daily). When non-empty, Status() expands this single cron
// entry into one row per sub-job instead of a single parent row — external
// observability (job count, ids, per-job last_run) stays unchanged even
// though only one cron entry actually fires.
type jobMeta struct {
	id   string
	name string
	subs []jobMeta
}

// Scheduler wraps robfig/cron and triggers Python services via HTTP.
type Scheduler struct {
	cron                    *cron.Cron
	pythonURL               string
	heartbeatComparePresets string
	client                  *http.Client
	store                   *store.Store
	mu                      sync.RWMutex
	lastRuns                map[string]*jobResult
	entryMap                map[cron.EntryID]jobMeta // maps cron EntryID → job identity

	// overlapState verzeichnet uebersprungene Ticks je Job GETRENNT von
	// lastRuns (Issue #1447 S2a): ein Skip darf den Zeitpunkt/Ausgang des
	// zuletzt tatsaechlich ausgefuehrten Laufs nicht ueberschreiben, sonst
	// verdeckt ein Dauerhaenger sich selbst hinter einem immer frischen
	// "skipped"-Zeitstempel. Geschuetzt durch s.mu wie lastRuns.
	overlapState map[string]*jobOverlapState

	// lastHardStatus haelt je jobID den zuletzt erreichten NICHT-"partial"-
	// Status ("ok" oder "error"), GETRENNT vom unmittelbaren Vorlauf in
	// lastRuns (Issue #1912 F002/F003). Ein "partial"-Zwischenlauf (Timeout)
	// laesst diesen Wert unangetastet -- die Flankenerkennung in
	// tripReports() fragt lastHardStatus statt lastRuns[...].Status, damit
	// eine fortlaufende Stoerung mit Timeout-Blip (error->partial->error)
	// nicht als zwei getrennte Vorfaelle gezaehlt wird und eine Erholung
	// (error->partial->ok) die Recovery-Notiz weiterhin ausloest. Eine Kette
	// aus lauter "partial" friert den Wert NICHT dauerhaft ein: jeder "ok"-
	// oder "error"-Lauf schreibt ihn frisch, ein neu auftretender Fehler nach
	// "ok" alarmiert also weiterhin sofort. Geschuetzt durch s.mu wie
	// lastRuns.
	lastHardStatus map[string]string

	// jobLocksMu/jobLocks: lazy-initialisierte Sperren je jobID (Issue #1447
	// S2a), analog zum onceMissingHB-Muster unten. TryLock() statt Lock() —
	// ein blockierendes Lock() wuerde die Cron-Goroutine des zweiten Ticks
	// anhalten statt den Tick zu ueberspringen.
	jobLocksMu sync.Mutex
	jobLocks   map[string]*sync.Mutex

	// notifier delivers MQ messages (e.g. heartbeat-URL missing). Defaults to
	// notify.SendMQ; tests inject their own.
	notifier Notifier

	// onceMissingHB ensures the "heartbeat URL empty" warning is sent only once
	// per (process, jobName) — avoids MQ spam on every cron tick.
	onceMissingHB   map[string]*sync.Once
	onceMissingHBmu sync.Mutex
}

// New creates a Scheduler from config and store. Returns error if timezone is invalid.
func New(cfg *config.Config, st *store.Store) (*Scheduler, error) {
	loc, err := time.LoadLocation(cfg.SchedulerTimezone)
	if err != nil {
		return nil, fmt.Errorf("invalid timezone %q: %w", cfg.SchedulerTimezone, err)
	}

	s := &Scheduler{
		cron:                    cron.New(cron.WithLocation(loc)),
		pythonURL:               cfg.PythonCoreURL,
		heartbeatComparePresets: cfg.HeartbeatComparePresets,
		// Issue #1912: 120s reichte fuer den regulaeren Versand nicht mehr
		// (laengster gemessener Einzelversand 319s, briefing_slots.py:48) und
		// riss Laeufe als Timeout ab, die tatsaechlich noch liefen. 3000s (50
		// min) liegt knapp unter dem stuendlichen Cron-Abstand; die
		// Overlap-Sperre in recordRun() verhindert, dass ein langsamer Lauf
		// den Folgetick blockiert.
		client: &http.Client{Timeout: 3000 * time.Second},
		store:                   st,
		lastRuns:                make(map[string]*jobResult),
		entryMap:                make(map[cron.EntryID]jobMeta),
		overlapState:            make(map[string]*jobOverlapState),
		lastHardStatus:          make(map[string]string),
		jobLocks:                make(map[string]*sync.Mutex),
		notifier: func(sender, recipient, priority, subject, body string) error {
			return notify.SendMQ(sender, recipient, priority, subject, body)
		},
		onceMissingHB: make(map[string]*sync.Once),
	}

	// Register jobs and store EntryID → jobMeta mapping
	type jobDef struct {
		expr string
		fn   func()
		id   string
		name string
		subs []jobMeta
	}
	jobs := []jobDef{
		// Issue #1250 Scheibe 7c: trip_reports_hourly und compare_presets_daily
		// liefen zuvor als zwei separate "0 * * * *"-Cron-Einträge; jetzt EIN
		// Eintrag briefing_dispatch, der beide Fan-outs sequenziell auslöst
		// (s. briefingDispatch()). tripReports()/comparePresetsDaily() bleiben
		// unverändert; Status() expandiert diesen Eintrag weiterhin zu 2 Zeilen.
		{"0 * * * *", s.briefingDispatch, "briefing_dispatch", "Briefing Dispatch (hourly)", []jobMeta{
			{id: "trip_reports_hourly", name: "Trip Reports (hourly check)"},
			{id: "compare_presets_daily", name: "Compare Presets Slot-Check (hourly)"},
		}},
		{"*/15 * * * *", s.alertChecks, "alert_checks", "Alert Checks (every 15 min)", nil},
		{"*/5 * * * *", s.inboundCommands, "inbound_command_poll", "Inbound Command Poll (every 5min)", nil},
		// Issue #637: inbound_telegram_poll entfernt — Telegram-Eingang läuft jetzt
		// push-basiert über den Webhook (POST /api/webhooks/telegram/{secret}).
		// Issue #1628 S0: 7/22/37/52 statt */15 (= 0/15/30/45) -- weicht der
		// gemessenen Open-Meteo-Lastspitze auf :00/:30 zeitlich aus. NUR
		// diese zwei Radar-Jobs; alle anderen */15-Jobs bleiben unveraendert.
		{"7,22,37,52 * * * *", s.radarAlertChecks, "radar_alert_checks", "Radar Alert Checks (offset 7/22/37/52 min)", nil},
		{"*/15 * * * *", s.dataWriteSelftest, "data_write_selftest", "Data Write Selftest (every 15 min)", nil},
		{"*/15 * * * *", s.compareAlertChecks, "compare_alert_checks", "Compare Alert Checks (every 15 min)", nil},
		{"7,22,37,52 * * * *", s.compareRadarAlertChecks, "compare_radar_alert_checks", "Compare Radar Alert Checks (offset 7/22/37/52 min)", nil},
		{"*/15 * * * *", s.compareOfficialAlertChecks, "compare_official_alert_checks", "Compare Official Alert Checks (every 15 min)", nil},
		// Issue #1676 Scheibe S1: Premium-SMS-Rueckkanal — pollt das seven.io-
		// Journal auf eingehende Garmin-Nachrichten (globaler Job, kein
		// Nutzer-Fan-out, analog inboundCommands()).
		{"*/5 * * * *", s.premiumSmsPoll, "premium_sms_poll", "Premium SMS Poll (every 5min)", nil},
	}
	for _, j := range jobs {
		eid, _ := s.cron.AddFunc(j.expr, j.fn)
		s.entryMap[eid] = jobMeta{id: j.id, name: j.name, subs: j.subs}
	}

	return s, nil
}

// Start begins cron scheduling.
func (s *Scheduler) Start() {
	s.cron.Start()
	log.Printf("[scheduler] Started: 9 cron entries (10 jobs), timezone %s", s.cron.Location())
}

// Stop gracefully shuts down the scheduler and waits for running jobs.
func (s *Scheduler) Stop() {
	ctx := s.cron.Stop()
	<-ctx.Done()
	log.Println("[scheduler] Stopped")
}

// runForAllUsers iterates over all registered users and triggers the endpoint
// for each. Returns nil only if all users succeeded.
//
// Issue #1265 (Defense-in-Depth): Test-/tdd-Konten werden vor der
// Verarbeitung übersprungen (model.IsTestUserID) — auch wenn ein solches
// Konto künftig wieder in data/users/ leakt, verarbeitet der Scheduler es
// nie. Log-Hinweis einmal je Lauf (nicht pro Job-Tick).
func (s *Scheduler) runForAllUsers(jobID, path string) error {
	allUserIDs, err := s.store.ListUserIDs()
	if err != nil {
		return fmt.Errorf("list users: %w", err)
	}

	userIDs := make([]string, 0, len(allUserIDs))
	var skipped []string
	for _, uid := range allUserIDs {
		if model.IsTestUserID(uid) {
			skipped = append(skipped, uid)
			continue
		}
		userIDs = append(userIDs, uid)
	}
	if len(skipped) > 0 {
		log.Printf("[scheduler] %s: skipping %d test-user account(s): %v", jobID, len(skipped), skipped)
	}

	if len(userIDs) == 0 {
		log.Printf("[scheduler] %s: no users registered, skipping", jobID)
		return nil
	}

	// Issue #1447 S2a: Rangfolge error > partial > ok bei gemischten
	// Nutzer-Ergebnissen — ein einzelner echter Fehler macht den gesamten
	// Job-Lauf "error", auch wenn andere Nutzer nur "partial" waren.
	var firstHardErr, firstPartialErr error
	for _, uid := range userIDs {
		err := s.triggerEndpointForUser(path, uid)
		if err == nil {
			continue
		}
		var pe *partialRunError
		if errors.As(err, &pe) {
			log.Printf("[scheduler] %s: user %s partial: %v", jobID, uid, err)
			if firstPartialErr == nil {
				firstPartialErr = err
			}
			continue
		}
		log.Printf("[scheduler] %s: user %s failed: %v", jobID, uid, err)
		if firstHardErr == nil {
			firstHardErr = err
		}
		// continue — do not stop other users
	}
	if firstHardErr != nil {
		return firstHardErr
	}
	return firstPartialErr // nil, falls kein Nutzer partial war -> "ok"
}

// briefingDispatch ist der vereinheitlichte stündliche Briefing-Einstieg
// (Issue #1250 S7c): EIN Cron-Eintrag, der beide Fan-outs sequenziell auslöst.
// Jeder Teil-Job behält seine eigene recordRun-Buchführung.
//
// Issue #1346: der Heartbeat wird hier zentral konsolidiert (statt allein an
// comparePresetsDaily() zu hängen) — nur wenn BEIDE Teil-Jobs "ok" sind, gilt
// der Briefing-Dispatch als vollständig erfolgreich und pingt.
func (s *Scheduler) briefingDispatch() {
	s.tripReports()
	s.comparePresetsDaily()

	s.mu.RLock()
	tripLR := s.lastRuns["trip_reports_hourly"]
	compareLR := s.lastRuns["compare_presets_daily"]
	s.mu.RUnlock()

	if tripLR != nil && tripLR.Status == "ok" &&
		compareLR != nil && compareLR.Status == "ok" {
		s.pingHeartbeat("briefing_dispatch", s.heartbeatComparePresets)
	}
}

// tripReports triggert den stündlichen Trip-Briefing-Versand.
//
// Issue #1346: edge-getriggerter MQ-Alarm analog dataWriteSelftest() — ein
// Totalausfall (alle Touren scheitern am Wetterabruf) muss aktiv an infra
// gemeldet werden statt still zu bleiben, weil der Heartbeat allein den
// Ausfall nicht mehr sichtbar macht (er hängt jetzt an briefingDispatch()).
//
// Issue #1912 F002/F003: die Flanke wird gegen lastHardStatus statt gegen
// den unmittelbaren Vorlauf geprüft — ein "partial"-Zwischenlauf (Timeout)
// darf eine fortlaufende Störung weder verdoppeln (error->partial->error)
// noch die Recovery-Notiz verschlucken (error->partial->ok).
func (s *Scheduler) tripReports() {
	s.mu.RLock()
	prevHardStatus := s.lastHardStatus["trip_reports_hourly"]
	s.mu.RUnlock()

	s.recordRun("trip_reports_hourly", func() error {
		return s.runForAllUsers("trip_reports_hourly", "/api/scheduler/trip-reports")
	})

	s.mu.Lock()
	cur := s.lastRuns["trip_reports_hourly"]
	if cur != nil && cur.Status != "partial" {
		// "partial" bleibt bewusst aussen vor -- s. Dokumentation an
		// lastHardStatus-Feld weiter oben.
		s.lastHardStatus["trip_reports_hourly"] = cur.Status
	}
	s.mu.Unlock()

	if cur == nil || s.notifier == nil {
		return
	}
	// ok→error (inkl. erster Lauf ohne Vorzustand) → Alarm high
	if cur.Status == "error" && prevHardStatus != "error" {
		subject := "Trip-Briefing-Totalausfall (#1346)"
		body := fmt.Sprintf("Job trip_reports_hourly: Trip-Briefing-Versand fehlgeschlagen.\n%s", cur.Error)
		if err := s.notifier("gregor", "infra", "high", subject, body); err != nil {
			log.Printf("[scheduler] WARN: trip-reports alert notifier failed: %v", err)
		}
	} else if cur.Status == "ok" && prevHardStatus == "error" {
		// error→ok: Recovery-Notiz
		subject := "Trip-Briefing wieder OK (#1346)"
		body := "Job trip_reports_hourly: Trip-Briefing-Versand läuft wieder erfolgreich."
		if err := s.notifier("gregor", "infra", "normal", subject, body); err != nil {
			log.Printf("[scheduler] WARN: trip-reports recovery notifier failed: %v", err)
		}
	}
}

func (s *Scheduler) alertChecks() {
	s.recordRun("alert_checks", func() error {
		return s.runForAllUsers("alert_checks", "/api/scheduler/alert-checks")
	})
}

func (s *Scheduler) radarAlertChecks() {
	s.recordRun("radar_alert_checks", func() error {
		return s.runForAllUsers("radar_alert_checks", "/api/scheduler/radar-alert-checks")
	})
}

// compareAlertChecks triggers Compare-Preset Deviation-Alert-Checks (Issue #1169).
func (s *Scheduler) compareAlertChecks() {
	s.recordRun("compare_alert_checks", func() error {
		return s.runForAllUsers("compare_alert_checks", "/api/scheduler/compare-alert-checks")
	})
}

// compareRadarAlertChecks triggers Compare-Preset Radar-Onset-Alert-Checks
// (Issue #1041 Slice 1b, Epic #1095).
func (s *Scheduler) compareRadarAlertChecks() {
	s.recordRun("compare_radar_alert_checks", func() error {
		return s.runForAllUsers("compare_radar_alert_checks", "/api/scheduler/compare-radar-alert-checks")
	})
}

// compareOfficialAlertChecks triggers Compare-Preset Official-Alert-Checks
// (Issue #1216 Slice 2b) — ruft den bestehenden Slice-2a-Endpoint alle 15 Min
// fuer alle registrierten Nutzer auf.
func (s *Scheduler) compareOfficialAlertChecks() {
	s.recordRun("compare_official_alert_checks", func() error {
		return s.runForAllUsers("compare_official_alert_checks", "/api/scheduler/compare-official-alert-checks")
	})
}

// dataWriteSelftest prüft periodisch, ob data/ noch schreibbar ist (#1120).
// Edge-getriggert: MQ an infra nur beim Statuswechsel ok→error (kein sync.Once,
// das einen späteren Re-Onset im langlebigen Prozess verschlucken würde).
func (s *Scheduler) dataWriteSelftest() {
	s.mu.RLock()
	prevStatus := ""
	if lr := s.lastRuns["data_write_selftest"]; lr != nil {
		prevStatus = lr.Status
	}
	s.mu.RUnlock()

	s.recordRun("data_write_selftest", func() error {
		return probeDataWritable(s.store.DataDir)
	})

	s.mu.RLock()
	cur := s.lastRuns["data_write_selftest"]
	s.mu.RUnlock()
	if cur == nil {
		return
	}
	if s.notifier == nil {
		return
	}
	// ok→error (inkl. erster Lauf ohne Vorzustand) → Alarm high
	if cur.Status == "error" && prevStatus != "error" {
		subject := "Schreib-Selftest data/ FEHLGESCHLAGEN (#1120)"
		body := fmt.Sprintf("Job data_write_selftest: data/ nicht mehr schreibbar.\n%s", cur.Error)
		if err := s.notifier("gregor", "infra", "high", subject, body); err != nil {
			log.Printf("[scheduler] WARN: selftest alert notifier failed: %v", err)
		}
	} else if cur.Status == "ok" && prevStatus == "error" {
		// error→ok: optionale Recovery-Notiz
		subject := "Schreib-Selftest data/ wieder OK (#1120)"
		body := "Job data_write_selftest: data/ ist wieder schreibbar."
		if err := s.notifier("gregor", "infra", "normal", subject, body); err != nil {
			log.Printf("[scheduler] WARN: selftest recovery notifier failed: %v", err)
		}
	}
}

func (s *Scheduler) inboundCommands() {
	s.recordRun("inbound_command_poll", func() error {
		return s.triggerGlobalEndpoint("/api/scheduler/inbound-commands")
	})
}

// premiumSmsPoll triggert den seven.io-Journal-Abruf des Python-Core (Issue
// #1676 S1). Globaler Job (kein Nutzer-Fan-out) — der Python-Reader iteriert
// selbst ueber das Journal, analog inboundCommands().
//
// Fix F002: bewusst NICHT ueber triggerGlobalEndpoint() (das wertet nur den
// HTTP-Statuscode aus) -- der Python-Endpunkt meldet einen Lernfehlschlag
// mit HTTP 200 UND `failed`/`status` im Antwortkoerper (Hausnorm der
// Nachbar-Endpunkte trigger_trip_reports/trigger_compare_presets_daily,
// Issue #766/#1290). triggerPremiumSmsPollEndpoint() wertet diesen Koerper
// aus, damit ein dauerhafter Fehlschlag in /api/scheduler/status sichtbar
// wird -- ein voruebergehender heilt sich durch den Zeiger-Fix (Fix F001,
// Python-Seite) im naechsten Lauf von selbst.
func (s *Scheduler) premiumSmsPoll() {
	s.recordRun("premium_sms_poll", func() error {
		return s.triggerPremiumSmsPollEndpoint()
	})
}

// triggerPremiumSmsPollEndpoint ruft POST /api/scheduler/inbound-sms auf und
// wertet den Antwortkoerper wie triggerEndpointForUser() aus: failed > 0 ist
// ein harter Fehler, status == "partial" (ohne failed) ein Teilerfolg.
// Lokal fuer diesen Job -- triggerGlobalEndpoint() bleibt unveraendert, weil
// inbound_command_poll und weitere Jobs daran haengen, die dieses Verhalten
// nicht wollen.
func (s *Scheduler) triggerPremiumSmsPollEndpoint() error {
	url := s.pythonURL + "/api/scheduler/inbound-sms"
	resp, err := s.client.Post(url, "application/json", nil)
	if err != nil {
		// Issue #1912: Timeout-Klassifikation gilt fuer den geteilten Client
		// s.client an allen drei Aufrufstellen (Spec, Abschnitt "Geteilter
		// Client") — nicht nur fuer triggerEndpointForUser().
		if isTimeoutTransportError(err) {
			return &partialRunError{
				msg:     fmt.Sprintf("/api/scheduler/inbound-sms timed out: %v", err),
				wrapped: err,
			}
		}
		return fmt.Errorf("HTTP error: %w", err)
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)

	if resp.StatusCode >= 400 {
		return fmt.Errorf("HTTP %d: %s", resp.StatusCode, string(body))
	}

	var parsed triggerResponseBody
	if jsonErr := json.Unmarshal(body, &parsed); jsonErr == nil {
		if parsed.Failed > 0 {
			return fmt.Errorf(
				"/api/scheduler/inbound-sms reported %d failed learn call(s) "+
					"(status=%s, count=%d): %s",
				parsed.Failed, parsed.Status, parsed.Count, string(body),
			)
		}
		if parsed.Status == "partial" {
			return &partialRunError{msg: fmt.Sprintf(
				"/api/scheduler/inbound-sms reported partial status (count=%d): %s",
				parsed.Count, string(body),
			)}
		}
	}

	log.Printf("[scheduler] /api/scheduler/inbound-sms → %d", resp.StatusCode)
	return nil
}

// comparePresetsDaily triggert den Ortsvergleich-Slot-Check. Der Heartbeat-
// Ping wurde nach #1346 in briefingDispatch() konsolidiert (dort gated auf
// BEIDE Teil-Jobs statt allein diesen).
func (s *Scheduler) comparePresetsDaily() {
	log.Println("[scheduler] Running compare presets daily...")
	s.recordRun("compare_presets_daily", func() error {
		return s.runForAllUsers("compare_presets_daily", "/api/scheduler/compare-presets-daily")
	})
}

// jobLock returns the lazily-initialized per-jobID mutex (Issue #1447 S2a),
// analog to the onceMissingHB lazy-init pattern above.
func (s *Scheduler) jobLock(jobID string) *sync.Mutex {
	s.jobLocksMu.Lock()
	defer s.jobLocksMu.Unlock()
	l, ok := s.jobLocks[jobID]
	if !ok {
		l = &sync.Mutex{}
		s.jobLocks[jobID] = l
	}
	return l
}

// recordRun executes a job function and stores the result.
//
// Issue #1447 S2a: recordRun is the shared bottleneck of all nine scheduled
// jobs. A per-jobID TryLock() prevents a job from overlapping with its own
// still-running previous execution — a skipped tick is verbucht as a
// separate, cumulative overlapState (NOT written into lastRuns[jobID]), so a
// job that hangs indefinitely never looks "fresh" behind an always-recent
// skip timestamp (#1434 pattern). TryLock (not Lock) is deliberate: a
// blocking Lock() would stall the cron goroutine of the second tick instead
// of skipping it, and robfig/cron would stack goroutines under frequent
// overlap.
func (s *Scheduler) recordRun(jobID string, fn func() error) {
	lock := s.jobLock(jobID)
	if !lock.TryLock() {
		now := time.Now().In(s.cron.Location())
		s.mu.Lock()
		st, ok := s.overlapState[jobID]
		if !ok {
			st = &jobOverlapState{}
			s.overlapState[jobID] = st
		}
		st.SkippedSinceLastRun++
		st.LastSkippedAt = &now
		n := st.SkippedSinceLastRun
		s.mu.Unlock()
		log.Printf("[scheduler] %s: previous run still in progress, "+
			"skipping this tick (%d skipped since last executed run)", jobID, n)
		return // lastRuns[jobID] bewusst NICHT angefasst
	}
	defer lock.Unlock()

	err := fn()

	s.mu.Lock()
	defer s.mu.Unlock()
	// Der Job lief gerade tatsaechlich (egal mit welchem Ausgang) — die
	// Overlap-Zaehlung seit dem letzten ausgefuehrten Lauf beginnt neu.
	if st, ok := s.overlapState[jobID]; ok {
		st.SkippedSinceLastRun = 0
	}

	if err != nil {
		var pe *partialRunError
		status := "error"
		if errors.As(err, &pe) {
			status = "partial"
		} else {
			log.Printf("[scheduler] %s failed: %v", jobID, err)
		}
		s.lastRuns[jobID] = &jobResult{
			Time:   time.Now().In(s.cron.Location()),
			Status: status,
			Error:  err.Error(),
		}
	} else {
		s.lastRuns[jobID] = &jobResult{
			Time:   time.Now().In(s.cron.Location()),
			Status: "ok",
		}
	}
}

// triggerResponseBody mirrors the JSON body returned by Python trigger
// endpoints. Issue #1012 (AC-5): only /api/scheduler/trip-reports currently
// populates "failed" (> 0 on partial send failures); other endpoints omit it
// or leave it at 0, so they are unaffected by the check below. Issue #1447
// S2a: "status" is now also read — "partial" without "failed" (today only
// /api/scheduler/alert-checks, Scheibe S1) is classified as a partialRunError.
type triggerResponseBody struct {
	Status string `json:"status"`
	Count  int    `json:"count"`
	Failed int    `json:"failed"`
}

// triggerEndpointForUser sends a POST to the Python trigger endpoint for a specific user.
func (s *Scheduler) triggerEndpointForUser(path, userID string) error {
	url := s.pythonURL + path + "?user_id=" + userID
	resp, err := s.client.Post(url, "application/json", nil)
	if err != nil {
		// Issue #1912: ein Timeout ist kein Ausfallbeweis — der Core kann
		// dabei erfolgreich weiterarbeiten. Nur eine tatsaechlich verweigerte
		// Verbindung (kein Timeout) bleibt ein harter Fehler.
		if isTimeoutTransportError(err) {
			return &partialRunError{
				msg:     fmt.Sprintf("%s?user_id=%s timed out: %v", path, userID, err),
				wrapped: err,
			}
		}
		return fmt.Errorf("HTTP error: %w", err)
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)

	if resp.StatusCode >= 400 {
		return fmt.Errorf("HTTP %d: %s", resp.StatusCode, string(body))
	}

	// Issue #1012 (AC-5, d): HTTP 200 kann trotzdem einen fachlichen
	// Fehlschlag verbergen (z.B. Wetterdaten-Komplettausfall) — der Body
	// zählt das in "failed". Ohne diese Auswertung meldet recordRun() den
	// Job fälschlich als "ok", obwohl kein Briefing zugestellt wurde.
	var parsed triggerResponseBody
	if jsonErr := json.Unmarshal(body, &parsed); jsonErr == nil {
		if parsed.Failed > 0 {
			return fmt.Errorf(
				"%s?user_id=%s reported %d failed (status=%s, count=%d): %s",
				path, userID, parsed.Failed, parsed.Status, parsed.Count, string(body),
			)
		}
		// Issue #1447 S2a: status="partial" ohne failed (Scheibe S1 —
		// Alarm-Lauf durch die Zeitobergrenze abgebrochen) ist ein
		// Teilerfolg, kein harter Fehler — recordRun() verbucht das als
		// jobResult.Status "partial", nicht "error".
		if parsed.Status == "partial" {
			return &partialRunError{msg: fmt.Sprintf(
				"%s?user_id=%s reported partial status (count=%d): %s",
				path, userID, parsed.Count, string(body),
			)}
		}
	}

	log.Printf("[scheduler] %s?user_id=%s → %d", path, userID, resp.StatusCode)
	return nil
}

// triggerGlobalEndpoint sends a single POST to the Python trigger endpoint
// without iterating over users. Use for global jobs (e.g. inbound polling)
// where the endpoint operates on shared resources.
//
// Issue #200: inbound IMAP polling targets a shared mailbox; one tick must
// produce exactly one IMAP login, not N (one per user).
func (s *Scheduler) triggerGlobalEndpoint(path string) error {
	url := s.pythonURL + path
	resp, err := s.client.Post(url, "application/json", nil)
	if err != nil {
		// Issue #1912: siehe triggerEndpointForUser() — Timeout ist kein
		// Ausfallbeweis, gilt auch fuer den geteilten Client an dieser Stelle.
		if isTimeoutTransportError(err) {
			return &partialRunError{
				msg:     fmt.Sprintf("%s timed out: %v", path, err),
				wrapped: err,
			}
		}
		return fmt.Errorf("HTTP error: %w", err)
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)

	if resp.StatusCode >= 400 {
		return fmt.Errorf("HTTP %d: %s", resp.StatusCode, string(body))
	}
	log.Printf("[scheduler] %s → %d", path, resp.StatusCode)
	return nil
}

// pingHeartbeat sends a GET to BetterStack. Fire-and-forget with logging.
//
// If url is empty (ENV-Var not configured), no HTTP request is made and a
// single MQ-notification is dispatched per (process, jobName) so the missing
// configuration is visible to operators without spamming the MQ on every tick.
func (s *Scheduler) pingHeartbeat(jobName, url string) {
	if url == "" {
		s.warnMissingHeartbeatOnce(jobName)
		return
	}
	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Get(url)
	if err != nil {
		log.Printf("[scheduler] Heartbeat ping failed (%s): %v", jobName, err)
		return
	}
	resp.Body.Close()
	log.Printf("[scheduler] Heartbeat ping OK (%s): ...%s", jobName, url[len(url)-8:])
}

// warnMissingHeartbeatOnce sends an MQ notification to `infra` once per
// jobName for the lifetime of this Scheduler instance.
func (s *Scheduler) warnMissingHeartbeatOnce(jobName string) {
	s.onceMissingHBmu.Lock()
	once, ok := s.onceMissingHB[jobName]
	if !ok {
		once = &sync.Once{}
		s.onceMissingHB[jobName] = once
	}
	s.onceMissingHBmu.Unlock()

	once.Do(func() {
		if s.notifier == nil {
			return
		}
		subject := fmt.Sprintf("Heartbeat-URL für Job %q nicht konfiguriert", jobName)
		body := fmt.Sprintf(
			"ENV-Variable für Heartbeat-Job %q ist leer. Service läuft normal weiter, "+
				"aber externes Monitoring sollte Job-Status anderweitig prüfen.",
			jobName,
		)
		if err := s.notifier("gregor", "infra", "normal", subject, body); err != nil {
			log.Printf("[scheduler] WARN: notifier failed for %s: %v", jobName, err)
		} else {
			log.Printf("[scheduler] WARN: Heartbeat URL empty for %s — MQ sent", jobName)
		}
	})
}

// overlapField builds the "overlap" sibling field for a job (Issue #1447
// S2a), or nil if no tick has been skipped since the last executed run —
// "fehlender Block bedeutet Ruhe", analog zur zone_drift-Konvention aus
// #1434. Caller must already hold s.mu (RLock or Lock).
func (s *Scheduler) overlapField(jobID string) map[string]any {
	st, ok := s.overlapState[jobID]
	if !ok || st.SkippedSinceLastRun <= 0 {
		return nil
	}
	overlap := map[string]any{
		"skipped_since_last_run": st.SkippedSinceLastRun,
	}
	if st.LastSkippedAt != nil {
		overlap["last_skipped_at"] = st.LastSkippedAt.Format(time.RFC3339)
	}
	return overlap
}

// Status returns current scheduler state for API exposure.
func (s *Scheduler) Status() map[string]any {
	s.mu.RLock()
	defer s.mu.RUnlock()

	entries := s.cron.Entries()
	jobs := make([]map[string]any, 0, len(entries))
	for _, e := range entries {
		nextRun := e.Next.Format(time.RFC3339)
		meta, ok := s.entryMap[e.ID]
		if ok && len(meta.subs) > 0 {
			// Issue #1250 Scheibe 7c: ein unified cron entry (z.B.
			// briefing_dispatch) expandiert zu einer Zeile PRO Sub-Job, damit
			// die externe Beobachtbarkeit (Job-Anzahl, ids, last_run je Job)
			// unverändert bleibt.
			for _, sub := range meta.subs {
				subJob := map[string]any{
					"next_run": nextRun,
					"id":       sub.id,
					"name":     sub.name,
				}
				if lr, ok := s.lastRuns[sub.id]; ok {
					subJob["last_run"] = map[string]any{
						"time":   lr.Time.Format(time.RFC3339),
						"status": lr.Status,
						"error":  lr.Error,
					}
				} else {
					subJob["last_run"] = nil
				}
				if overlap := s.overlapField(sub.id); overlap != nil {
					subJob["overlap"] = overlap
				}
				jobs = append(jobs, subJob)
			}
			continue
		}

		job := map[string]any{
			"next_run": nextRun,
		}
		if ok {
			job["id"] = meta.id
			job["name"] = meta.name
			if lr, ok := s.lastRuns[meta.id]; ok {
				job["last_run"] = map[string]any{
					"time":   lr.Time.Format(time.RFC3339),
					"status": lr.Status,
					"error":  lr.Error,
				}
			} else {
				job["last_run"] = nil
			}
			if overlap := s.overlapField(meta.id); overlap != nil {
				job["overlap"] = overlap
			}
		} else {
			job["id"] = int(e.ID)
			job["last_run"] = nil
		}
		jobs = append(jobs, job)
	}
	return map[string]any{
		"running":             true,
		"jobs":                jobs,
		"timezone":            s.cron.Location().String(),
		"briefing_health":     s.BriefingHealth(),
		"warn_service_health": s.WarnServiceHealth(),
		"forecast_budget":     s.ForecastBudgetHealth(),
		"tier_request_health": s.TierRequestHealth(),
	}
}

// Issue #1250 Scheibe 0: BuildCompareSubscriptionsStatus entfernt — Legacy-
// Drittstack CompareSubscription stillgelegt (#1131), model.CompareSubscription
// und store.LoadSubscriptions existieren nicht mehr.
