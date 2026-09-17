package scheduler

// Fix #2149 Scheibe A — Buchführung je (jobID, userID), getrennt von
// lastRuns/overlapState (analog zum Muster aus #1447 S2a). Persistiert unter
// store.DataDir als Geschwisterdatei von users/, siehe Spec Abschnitt 6.
//
// Spec: docs/specs/modules/fix_2149_scheduler_nutzer_sichtbarkeit.md

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"sync"
	"time"
)

// schedulerUserStateFileName ist die Geschwisterdatei von users/ unter
// store.DataDir (Spec Abschnitt 6 — bewusst NICHT darunter, s. dort für die
// Begründung). Der Name deckt sich mit der lokalen Testkonstante
// userStateFileName in user_partial_and_persistence_test.go.
const schedulerUserStateFileName = "scheduler_user_state.json"

// Schwellenwerte (Tech-Lead-Entscheidung, Spec Abschnitt 1/2).
const (
	failureAlertThreshold = 3
	partialAlertThreshold = 8
)

// userJobRecord ist der Zustand eines einzelnen (jobID, userID)-Paars.
type userJobRecord struct {
	LastRun             time.Time `json:"last_run"`
	LastStatus          string    `json:"last_status"` // ok|partial|error|budget|skipped_in_flight|not_reached
	LastError           string    `json:"last_error,omitempty"`
	ConsecutiveFailures int       `json:"consecutive_failures"`
	ConsecutivePartial  int       `json:"consecutive_partial"`
	FailureAlertSent    bool      `json:"failure_alert_sent"`
	PartialAlertSent    bool      `json:"partial_alert_sent"`
}

// userRunState haelt den Zustand aller (jobID, userID)-Paare mit einem
// EIGENEN Mutex (getrennt von Scheduler.mu, s. Spec Abschnitt 6 fuer die
// Begruendung: mehrere Fan-out-Jobs koennen gleichzeitig schreiben wollen).
type userRunState struct {
	mu    sync.Mutex
	path  string
	state map[string]map[string]*userJobRecord // [jobID][userID]
}

// newUserRunState erstellt den Zustand und laedt eine vorhandene
// Zustandsdatei. Eine fehlende Datei ist kein Fehler (leerer Zustand); eine
// defekte Datei fuehrt zu einem leeren Zustand plus Log-Warnung, niemals zu
// einem Fehler-Return (Spec Abschnitt 6).
func newUserRunState(dataDir string) *userRunState {
	u := &userRunState{
		path:  filepath.Join(dataDir, schedulerUserStateFileName),
		state: make(map[string]map[string]*userJobRecord),
	}
	u.load()
	return u
}

// load liest die persistierte Zustandsdatei ein. Fehlend -> leerer Zustand,
// defekt -> leerer Zustand + Log-Warnung, kein Absturz.
func (u *userRunState) load() {
	raw, err := os.ReadFile(u.path)
	if err != nil {
		if !os.IsNotExist(err) {
			log.Printf("[scheduler] user-run-state: read %s failed: %v (starting empty)", u.path, err)
		}
		return
	}
	var parsed map[string]map[string]*userJobRecord
	if err := json.Unmarshal(raw, &parsed); err != nil {
		log.Printf("[scheduler] user-run-state: corrupt state file %s: %v (starting empty)", u.path, err)
		return
	}
	if parsed == nil {
		// Valides JSON `null` deserialisiert fehlerfrei zu einer nil-Map --
		// ohne diesen Zweig wuerde der naechste recordLocked()-Aufruf mit
		// "assignment to entry in nil map" abstuerzen (F-ADV1).
		log.Printf("[scheduler] user-run-state: state file %s parsed to null (starting empty)", u.path)
		return
	}
	// Dieselbe Falle gilt geschachtelt: ein einzelner Job-Eintrag kann `null`
	// sein (nil innere Map), oder ein einzelner Nutzer-Eintrag kann `null`
	// sein (nil *userJobRecord) -- beides deserialisiert fehlerfrei und
	// panickt sonst erst beim naechsten Schreibzugriff bzw. Lesezugriff
	// (F-ADV1).
	for jobID, byUser := range parsed {
		if byUser == nil {
			parsed[jobID] = make(map[string]*userJobRecord)
			continue
		}
		for uid, rec := range byUser {
			if rec == nil {
				byUser[uid] = &userJobRecord{}
				continue
			}
			// F-ADV5: negative Zaehler aus einer manuell/fehlerhaft
			// veraenderten Zustandsdatei wuerden den Alarm unbemerkt
			// verzoegern (bei -5 braeuchte es 8 statt 3 echte Fehler bis
			// zur Schwelle) -- auf 0 klammern.
			if rec.ConsecutiveFailures < 0 {
				rec.ConsecutiveFailures = 0
			}
			if rec.ConsecutivePartial < 0 {
				rec.ConsecutivePartial = 0
			}
		}
	}
	u.state = parsed
}

// persistLocked schreibt den aktuellen Zustand atomar (tmp + os.Rename,
// analog store/write.go, hier lokal nachgebaut, da dort unexported).
// Aufrufer haelt bereits u.mu.
func (u *userRunState) persistLocked() {
	data, err := json.Marshal(u.state)
	if err != nil {
		log.Printf("[scheduler] user-run-state: marshal failed: %v", err)
		return
	}
	f, err := os.CreateTemp(filepath.Dir(u.path), "."+filepath.Base(u.path)+".tmp-*")
	if err != nil {
		log.Printf("[scheduler] user-run-state: write %s failed: %v", u.path, err)
		return
	}
	tmp := f.Name()
	if _, err := f.Write(data); err != nil {
		f.Close()
		os.Remove(tmp)
		log.Printf("[scheduler] user-run-state: write %s failed: %v", u.path, err)
		return
	}
	if err := f.Close(); err != nil {
		os.Remove(tmp)
		log.Printf("[scheduler] user-run-state: write %s failed: %v", u.path, err)
		return
	}
	if err := os.Chmod(tmp, 0644); err != nil {
		os.Remove(tmp)
		log.Printf("[scheduler] user-run-state: write %s failed: %v", u.path, err)
		return
	}
	if err := os.Rename(tmp, u.path); err != nil {
		os.Remove(tmp)
		log.Printf("[scheduler] user-run-state: write %s failed: %v", u.path, err)
	}
}

// recordLocked aktualisiert den Zaehler eines einzelnen (jobID, userID)-Paars
// nach der Zaehlerregel aus Spec Abschnitt 1 und meldet zurueck, ob dabei eine
// Fehler-, Teilerfolgs- oder Erholungs-Flanke gefeuert hat. Aufrufer haelt
// bereits u.mu.
func (u *userRunState) recordLocked(jobID, userID, outcome, errText string) (failureEdge, partialEdge, recoveryEdge bool) {
	byUser, ok := u.state[jobID]
	if !ok {
		byUser = make(map[string]*userJobRecord)
		u.state[jobID] = byUser
	}
	rec, ok := byUser[userID]
	if !ok {
		rec = &userJobRecord{}
		byUser[userID] = rec
	}

	rec.LastRun = time.Now()
	rec.LastStatus = outcome
	rec.LastError = errText

	switch outcome {
	case "ok":
		rec.ConsecutiveFailures = 0
		rec.ConsecutivePartial = 0
		if rec.FailureAlertSent || rec.PartialAlertSent {
			recoveryEdge = true
			rec.FailureAlertSent = false
			rec.PartialAlertSent = false
		}
	case "error":
		rec.ConsecutiveFailures++
		rec.ConsecutivePartial = 0
		if rec.ConsecutiveFailures >= failureAlertThreshold && !rec.FailureAlertSent {
			failureEdge = true
			rec.FailureAlertSent = true
		}
	case "budget", "skipped_in_flight":
		// Fix #2149 Scheibe B (Spec Abschnitt 5): ein haengender Nutzer soll
		// nach spaetestens drei Laeufen den high-Alarm ausloesen --
		// ConsecutivePartial bleibt unveraendert.
		rec.ConsecutiveFailures++
		if rec.ConsecutiveFailures >= failureAlertThreshold && !rec.FailureAlertSent {
			failureEdge = true
			rec.FailureAlertSent = true
		}
	case "partial", "not_reached":
		// "not_reached" (Scheibe B): Laufbudget vor diesem Nutzer erschoepft --
		// keine eigene Schuld, zaehlt wie ein Teilerfolg.
		rec.ConsecutivePartial++
		if rec.ConsecutivePartial >= partialAlertThreshold && !rec.PartialAlertSent {
			partialEdge = true
			rec.PartialAlertSent = true
		}
	}
	return failureEdge, partialEdge, recoveryEdge
}

// pruneLocked entfernt aus state[jobID] alle Nutzer, die nicht (mehr) in
// keepUserIDs enthalten sind (geloeschte Konten, geleakte Testkonten). Nur
// state[jobID] wird angefasst -- andere Jobs bleiben unberuehrt. Aufrufer
// haelt bereits u.mu.
func (u *userRunState) pruneLocked(jobID string, keepUserIDs []string) {
	byUser, ok := u.state[jobID]
	if !ok {
		return
	}
	keep := make(map[string]bool, len(keepUserIDs))
	for _, id := range keepUserIDs {
		keep[id] = true
	}
	for uid := range byUser {
		if !keep[uid] {
			delete(byUser, uid)
		}
	}
}

// aggregateLocked liefert total/failing/partial fuer job ID -- NUR Zahlen,
// keine IDs (Spec Abschnitt 5). Aufrufer haelt bereits u.mu.
func (u *userRunState) aggregateLocked(jobID string) (total, failing, partial int) {
	byUser, ok := u.state[jobID]
	if !ok {
		return 0, 0, 0
	}
	for _, rec := range byUser {
		total++
		if rec.ConsecutiveFailures >= 1 {
			failing++
		}
		if rec.ConsecutivePartial >= 1 {
			partial++
		}
	}
	return total, failing, partial
}

// Record verbucht das Ergebnis eines einzelnen Nutzer-Aufrufs innerhalb eines
// Job-Laufs. Rueckgabe: die betroffene userID + welche Flanken feuerten --
// der Aufrufer (runForAllUsers) sammelt diese ueber alle Nutzer eines Laufs
// und buendelt sie zu hoechstens einer Nachricht je Art (Spec Abschnitt 2).
func (u *userRunState) Record(jobID, userID, outcome, errText string) (failureEdge, partialEdge, recoveryEdge bool) {
	u.mu.Lock()
	defer u.mu.Unlock()
	return u.recordLocked(jobID, userID, outcome, errText)
}

// RecordLate uebernimmt ein spaet geerntetes Ergebnis (Fix #2149 Scheibe B,
// Spec Abschnitt 6) rein informativ in LastRun/LastStatus/LastError -- ohne
// Zaehler, Alarm-Merker oder Flanken anzufassen. Ein spaetes "ok" darf die
// Fehlerserie NICHT zuruecksetzen (AC-4).
func (u *userRunState) RecordLate(jobID, userID, outcome, errText string) {
	u.mu.Lock()
	defer u.mu.Unlock()
	byUser, ok := u.state[jobID]
	if !ok {
		byUser = make(map[string]*userJobRecord)
		u.state[jobID] = byUser
	}
	rec, ok := byUser[userID]
	if !ok {
		rec = &userJobRecord{}
		byUser[userID] = rec
	}
	rec.LastRun = time.Now()
	rec.LastStatus = outcome
	rec.LastError = errText
}

// Prune entfernt geloeschte/Test-Nutzer aus dem Zustand des Jobs und
// persistiert danach.
func (u *userRunState) Prune(jobID string, keepUserIDs []string) {
	u.mu.Lock()
	defer u.mu.Unlock()
	u.pruneLocked(jobID, keepUserIDs)
	u.persistLocked()
}

// Aggregate liefert das oeffentliche users{total,failing,partial}-Feld fuer
// einen Fan-out-Job als map[string]any, passend fuer Status().
func (u *userRunState) Aggregate(jobID string) map[string]any {
	u.mu.Lock()
	defer u.mu.Unlock()
	total, failing, partial := u.aggregateLocked(jobID)
	return map[string]any{
		"total":   total,
		"failing": failing,
		"partial": partial,
	}
}

// fanOutJobIDs sind die sieben Jobs, die ueber runForAllUsers laufen (Spec
// Abschnitt 1) -- die einzigen, die ein users-Aggregat in Status() tragen.
// Die drei globalen Jobs (inbound_command_poll, data_write_selftest,
// premium_sms_poll) sind bewusst NICHT enthalten.
var fanOutJobIDs = map[string]bool{
	"trip_reports_hourly":           true,
	"alert_checks":                  true,
	"radar_alert_checks":            true,
	"compare_alert_checks":          true,
	"compare_radar_alert_checks":    true,
	"compare_official_alert_checks": true,
	"compare_presets_daily":         true,
}

// formatUserAlertBody baut den Nachrichtentext einer gebuendelten Alarm-/
// Entwarnungs-Nachricht. jobID identifiziert den Job, userIDs die betroffenen
// Nutzer (in Aufrufreihenfolge), detail ergaenzt optional den letzten
// Fehlertext (leer bei Entwarnung).
func formatUserAlertBody(jobID string, userIDs []string, detail string) string {
	body := fmt.Sprintf("Job %s: %d Nutzer betroffen: %v.", jobID, len(userIDs), userIDs)
	if detail != "" {
		body += " Letzter Fehler: " + detail
	}
	return body
}
