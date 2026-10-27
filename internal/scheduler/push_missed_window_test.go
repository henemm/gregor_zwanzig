package scheduler

// Issue #2439 AC-13, Adversary-Luecke F003: die 5-Minuten-Spanne
// (pushMissedWindow), in der ein gueltiger Webhook/Kick als Lebenszeichen des
// Sofort-Wegs gilt. Die Zeitpunkte werden im Zustand des Schedulers
// zurueckdatiert; cronPoll misst gegen die echte Uhr (time.Since).

import (
	"testing"
	"time"
)

// zurueckdatieren setzt last_received bzw. lastKick des Jobs auf jetzt-alter.
func zurueckdatieren(s *Scheduler, jobID string, alter time.Duration, kick bool) {
	t := time.Now().Add(-alter)
	s.pushMu.Lock()
	defer s.pushMu.Unlock()
	st := s.pushStateLocked(jobID)
	if kick {
		st.lastKick = t
	} else {
		st.lastReceived = &t
	}
}

func TestPushMissed_Fenster_WebhookVorVierMinutenZaehltNicht(t *testing.T) {
	core := newKickCore(t)
	core.fallback[pfadSMS] = processedBody(1)
	s, _ := newKickScheduler(t, core)

	zurueckdatieren(s, jobSMS, 4*time.Minute, false)
	s.premiumSmsPoll()

	if got := asInt(t, pushOf(t, s, jobSMS)["missed_total"]); got != 0 {
		t.Errorf("gueltiger Webhook vor 4 min (< 5-min-Spanne): missed_total erwartet 0, bekam %d", got)
	}
}

func TestPushMissed_Fenster_WebhookVorSechsMinutenZaehltAlsVerpasst(t *testing.T) {
	core := newKickCore(t)
	core.fallback[pfadSMS] = processedBody(1)
	s, _ := newKickScheduler(t, core)

	zurueckdatieren(s, jobSMS, 6*time.Minute, false)
	s.premiumSmsPoll()

	push := pushOf(t, s, jobSMS)
	if got := asInt(t, push["missed_total"]); got != 1 {
		t.Errorf("letzter gueltiger Webhook vor 6 min (> 5-min-Spanne): missed_total erwartet 1, bekam %d", got)
	}
	if push["last_missed"] == nil {
		t.Error("last_missed muss gesetzt sein")
	}
}

func TestPushMissed_Fenster_KickVorVierMinutenZaehltNicht_VorSechsMinutenSchon(t *testing.T) {
	core := newKickCore(t)
	core.fallback[pfadMail] = processedBody(1)
	s, _ := newKickScheduler(t, core)

	zurueckdatieren(s, jobMail, 4*time.Minute, true)
	s.inboundCommands()
	if got := asInt(t, pushOf(t, s, jobMail)["missed_total"]); got != 0 {
		t.Fatalf("Kick vor 4 min: missed_total erwartet 0, bekam %d", got)
	}

	zurueckdatieren(s, jobMail, 6*time.Minute, true)
	s.inboundCommands()
	if got := asInt(t, pushOf(t, s, jobMail)["missed_total"]); got != 1 {
		t.Errorf("Kick vor 6 min: missed_total erwartet 1, bekam %d", got)
	}
}
