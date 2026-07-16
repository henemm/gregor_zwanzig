package store

// Issue #1280 — Versandzeit-Eingabe auf volle Stunden begrenzen.
// Der Scheduler (Go-Cron, stuendlicher Takt; Faelligkeit ueber .hour) versendet
// Briefings ohnehin nur zur vollen Stunde — Minuten werden serverseitig
// verworfen. Diese Helfer richten die gespeicherte/angezeigte Versandzeit an
// dieser Realitaet aus (Write-Normalisierung + Read-Heilung), OHNE das
// Sendeverhalten zu aendern.
//
// Tech-Lead-Entscheidung (Adversary-Nachtrag, F002-F005): Read-Heilung ist HIER
// im store-Paket zentralisiert (LoadTrip/LoadTrips/LoadComparePreset/
// LoadComparePresets) statt an jedem einzelnen Handler-Serialisierungspfad —
// jeder Aufrufer (TripsHandler, TripHandler, UpdateTripStateHandler,
// ConfirmWaypointHandler, briefing_subscription.go, ...) bekommt automatisch
// geheilte Daten, ohne dass jede neue/uebersehene Encode-Stelle den Heal-Call
// separat einbauen muss (strukturell robuster als "an jedem Handler heilen").
// Write-Normalisierung bleibt an den Schreib-Seams (CreateTripHandler,
// UpdateTripHandler, validateComparePresetSlotTime) — der eingehende NEUE Wert
// muss dort weiterhin gekappt werden, bevor er ueberhaupt auf die Platte kommt.
//
// KRITISCH (#1268-Schutz): Diese Normalisierung fasst AUSSCHLIESSLICH die
// Konfig-Felder morning_time/evening_time an — NIEMALS letzter_versand oder
// andere reale Sende-Zeitstempel.

import (
	"fmt"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

// TruncateTimeStringToHour kappt "HH:MM"/"HH:MM:SS" auf die volle Stunde davor
// (Minuten UND Sekunden -> :00). Truncate, kein Runden — die Realitaet ist die
// volle Stunde davor. Nicht parsebare Werte bleiben unveraendert (Validierung
// findet an anderer Stelle statt).
func TruncateTimeStringToHour(value string) string {
	v := value
	if len(v) == 5 { // "HH:MM" -> Sekunden ergaenzen
		v += ":00"
	}
	t, err := time.Parse("15:04:05", v)
	if err != nil {
		return value
	}
	if t.Minute() == 0 && t.Second() == 0 {
		return value // bereits volle Stunde — Originalformat beibehalten
	}
	return fmt.Sprintf("%02d:00:00", t.Hour())
}

// TruncateTimePtrToHour ist die Pointer-sichere Variante von
// TruncateTimeStringToHour: nil bleibt nil, ein gesetzter Wert wird gekappt
// (neuer Pointer, Original unangetastet).
func TruncateTimePtrToHour(v *string) *string {
	if v == nil {
		return nil
	}
	h := TruncateTimeStringToHour(*v)
	return &h
}

// HealComparePresetSlotTimes kappt die beiden Slot-Zeitfelder eines geladenen
// Presets auf die volle Stunde (Read-Heilung fuer Bestandsdaten). Wird von
// LoadComparePresets/LoadComparePreset aufgerufen — jeder Aufrufer bekommt
// automatisch geheilte Daten, kein Write-Back auf die Platte.
func HealComparePresetSlotTimes(p *model.ComparePreset) {
	p.MorningTime = TruncateTimePtrToHour(p.MorningTime)
	p.EveningTime = TruncateTimePtrToHour(p.EveningTime)
}

// NormalizeReportConfigSlotTimes kappt AUSSCHLIESSLICH report_config.morning_time
// und report_config.evening_time auf die volle Stunde. Alle anderen
// report_config-Keys bleiben unberuehrt (RMW-Merge, kein Replace). Wird sowohl
// von den Trip-Schreib-Seams (CreateTripHandler, UpdateTripHandler) als auch
// von der Read-Heilung (healTripSlotTimes) genutzt.
func NormalizeReportConfigSlotTimes(rc map[string]interface{}) {
	if rc == nil {
		return
	}
	for _, key := range []string{"morning_time", "evening_time"} {
		if v, ok := rc[key].(string); ok && v != "" {
			rc[key] = TruncateTimeStringToHour(v)
		}
	}
}

// healTripSlotTimes kappt sowohl das verschachtelte report_config.morning_time/
// evening_time ALS AUCH die daraus abgeleiteten obersten Flach-Felder
// (trip.MorningTime/EveningTime, s. deriveFlatFields) auf die volle Stunde.
// Muss NACH deriveFlatFields laufen (die Flach-Felder existieren erst danach).
// Aufgerufen ausschliesslich von LoadTrip/LoadTrips (Read-Pfad) — SaveTrip ruft
// dies NICHT, damit roh geseedete Testdaten unnormalisiert auf der Platte
// bleiben und die Heilung beim naechsten Load nachweisbar ist.
func healTripSlotTimes(trip *model.Trip) {
	NormalizeReportConfigSlotTimes(trip.ReportConfig)
	trip.MorningTime = TruncateTimePtrToHour(trip.MorningTime)
	trip.EveningTime = TruncateTimePtrToHour(trip.EveningTime)
}
