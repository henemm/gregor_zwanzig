package scheduler

// Push-Weckruf fuer die Befehls-Poll-Jobs (Issue #2439, ADR-0087).
//
// Ein Webhook (seven.io sms_mo bzw. Stalwart-Mail-Eingang) verarbeitet nichts
// selbst, sondern stoesst den BESTEHENDEN Poll-Job sofort an: Kick(jobID).
// Der Cron-Fallback (*/5) bleibt unveraendert die alleinige Wahrheit.
//
// Coalescing: je Job hoechstens EINE Kick-Goroutine. Ein Kick waehrend sie
// laeuft setzt nur pending (kicks_coalesced++); nach dem Lauf folgt hoechstens
// ein weiterer. Die Kick-Goroutine laeuft ueber den BLOCKIERENDEN jobLock (wie
// der Cron-Tick, der bei Belegung per TryLock ueberspringt), also nie parallel.

import (
	"time"
)

// Job-IDs der beiden Befehls-Poll-Jobs (Webhook-Handler adressieren sie hier).
const (
	JobPremiumSMSPoll     = "premium_sms_poll"
	JobInboundCommandPoll = "inbound_command_poll"
)

const (
	// kickMinGap: Mindestabstand zwischen zwei tatsaechlichen Kick-Runden.
	kickMinGap = 2 * time.Second
	// pushMissedWindow: gueltiger Webhook/Kick in dieser Spanne vor einem
	// Cron-Lauf gilt als Lebenszeichen des Sofort-Wegs (AC-13).
	pushMissedWindow = 5 * time.Minute
)

// kickRetryDelays: Wartezeit VOR dem n-ten Versuch einer Kick-Runde. SMS 0/3/8 s
// (Journal-Verzoegerung), Mail ein Nachversuch nach ~2 s. Nachversuche rufen
// nur Journal/IMAP ab, sie loesen keine zusaetzlichen SMS aus.
var kickRetryDelays = map[string][]time.Duration{
	JobPremiumSMSPoll:     {0, 3 * time.Second, 5 * time.Second},
	JobInboundCommandPoll: {0, 2 * time.Second},
}

// pollResult ist, was Go aus der Python-Antwort eines Poll-Endpunkts braucht.
type pollResult struct {
	Processed int  // in diesem Lauf verarbeitete Befehle
	Busy      bool // Python-flock belegt, nichts verarbeitet
}

// pushState haelt Zaehler und Coalescing-Flags je Poll-Job (pro Scheduler).
type pushState struct {
	pending, running bool
	lastKick         time.Time
	lastReceived     *time.Time
	receivedTotal    int
	rejectedTotal    int
	coalesced        int
	missedTotal      int
	lastMissed       *time.Time
}

// pollRun fuehrt den Poll-Endpunkt des Jobs aus und fuellt res.
func (s *Scheduler) pollRun(jobID string, res *pollResult) error {
	if jobID == JobPremiumSMSPoll {
		return s.triggerPremiumSmsPollEndpointRes(res)
	}
	return s.triggerGlobalEndpointRes("/api/scheduler/inbound-commands", res)
}

func isPollJob(jobID string) bool {
	_, ok := kickRetryDelays[jobID]
	return ok
}

// pushStateLocked liefert den Zustand des Jobs; pushMu muss gehalten werden.
func (s *Scheduler) pushStateLocked(jobID string) *pushState {
	if s.push == nil {
		s.push = make(map[string]*pushState)
	}
	st, ok := s.push[jobID]
	if !ok {
		st = &pushState{}
		s.push[jobID] = st
	}
	return st
}

func (s *Scheduler) sleepFn() func(time.Duration) {
	if s.kickSleep != nil {
		return s.kickSleep
	}
	return time.Sleep
}

// RecordPushReceived verbucht einen Webhook, der die Pruefung bestanden hat.
func (s *Scheduler) RecordPushReceived(jobID string) {
	now := time.Now().In(s.cron.Location())
	s.pushMu.Lock()
	defer s.pushMu.Unlock()
	st := s.pushStateLocked(jobID)
	st.lastReceived = &now
	st.receivedTotal++
}

// RecordPushRejected verbucht einen abgewiesenen Webhook (403). Er ist kein
// Lebenszeichen des Sofort-Wegs und setzt last_received nicht.
func (s *Scheduler) RecordPushRejected(jobID string) {
	s.pushMu.Lock()
	defer s.pushMu.Unlock()
	s.pushStateLocked(jobID).rejectedTotal++
}

// Kick weckt den Poll-Job sofort und kehrt sofort zurueck (asynchron).
func (s *Scheduler) Kick(jobID string) {
	if !isPollJob(jobID) {
		return
	}
	s.pushMu.Lock()
	st := s.pushStateLocked(jobID)
	st.lastKick = time.Now()
	st.pending = true
	if st.running {
		st.coalesced++
		s.pushMu.Unlock()
		return
	}
	st.running = true
	s.pushMu.Unlock()
	go s.kickLoop(jobID)
}

// kickLoop laeuft, solange ein Weckruf pending ist; zwischen zwei Runden
// liegt der Mindestabstand.
func (s *Scheduler) kickLoop(jobID string) {
	first := true
	for {
		s.pushMu.Lock()
		st := s.pushStateLocked(jobID)
		if !st.pending {
			st.running = false
			s.pushMu.Unlock()
			return
		}
		st.pending = false
		s.pushMu.Unlock()
		if !first {
			s.sleepFn()(kickMinGap)
		}
		first = false
		s.kickRound(jobID)
	}
}

// kickRound: eine Runde mit Nachversuchen, Abbruch bei processed>0. Meldet
// Python busy, wird der Weckruf erneut auf pending gesetzt.
func (s *Scheduler) kickRound(jobID string) {
	for i, d := range kickRetryDelays[jobID] {
		if i > 0 {
			s.sleepFn()(d)
		}
		var res pollResult
		s.runJob(jobID, func() error { return s.pollRun(jobID, &res) }, true)
		if res.Busy {
			s.pushMu.Lock()
			s.pushStateLocked(jobID).pending = true
			s.pushMu.Unlock()
			return
		}
		if res.Processed > 0 {
			return
		}
	}
}

// cronPoll ist der Cron-Einstieg der Poll-Jobs (TryLock wie bisher). Hat der
// Lauf Befehle verarbeitet, ohne dass in den letzten 5 min ein gueltiger
// Webhook/Kick vorausging, ist der Sofort-Weg ausgefallen (AC-13).
func (s *Scheduler) cronPoll(jobID string) {
	var res pollResult
	s.recordRun(jobID, func() error { return s.pollRun(jobID, &res) })
	if res.Processed <= 0 {
		return
	}
	now := time.Now().In(s.cron.Location())
	s.pushMu.Lock()
	defer s.pushMu.Unlock()
	st := s.pushStateLocked(jobID)
	recent := func(t time.Time) bool { return !t.IsZero() && time.Since(t) < pushMissedWindow }
	if recent(st.lastKick) || (st.lastReceived != nil && recent(*st.lastReceived)) {
		return
	}
	st.missedTotal++
	st.lastMissed = &now
}

// pushField liefert das "push"-Statusfeld der Poll-Jobs (nil fuer andere Jobs).
func (s *Scheduler) pushField(jobID string) map[string]any {
	if !isPollJob(jobID) {
		return nil
	}
	s.pushMu.Lock()
	defer s.pushMu.Unlock()
	st := s.pushStateLocked(jobID)
	stamp := func(t *time.Time) any {
		if t == nil {
			return nil
		}
		return t.Format(time.RFC3339)
	}
	return map[string]any{
		"last_received":   stamp(st.lastReceived),
		"received_total":  st.receivedTotal,
		"rejected_total":  st.rejectedTotal,
		"kicks_coalesced": st.coalesced,
		"missed_total":    st.missedTotal,
		"last_missed":     stamp(st.lastMissed),
	}
}
