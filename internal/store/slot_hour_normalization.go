package store

// Issue #2795 — seit S3b Teil 1a gilt das VIERTELSTUNDEN-Raster statt der
// vollen Stunde (siehe Block unten); der folgende Text beschreibt die
// Herkunft (#1280) und die unveraenderte Aufteilung Schreiben/Lesen.
//
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

// Issue #2795 (Viertelstunden-Raster, PO 2026-11-12): Briefing-Zeiten sind
// nicht mehr auf die volle Stunde gekappt. Zulaessig sind die Minuten
// 00/15/30/45 (der Go-Cron `briefing_dispatch` laeuft alle 15 Minuten, Python
// vergleicht die Faelligkeit in Minuten).
//   - Schreiben: ValidateQuarterHourSlotTime / ValidateReportConfigSlotTimes —
//     eine Minute ausserhalb des Rasters wird mit Fehler (HTTP 400) abgelehnt,
//     NICHT still gerundet; Sekunden werden zu :00.
//   - Lesen: TruncateTimeStringToQuarterHour rundet einen (theoretisch) nicht
//     rasterkonformen Altwert auf die VORHERIGE Viertelstunde ab, ohne
//     Rueckschreiben. Rasterkonforme Werte bleiben unveraendert.

// parseSlotTime liest "HH:MM" oder "HH:MM:SS" (Stunde 0..23, Minute/Sekunde
// 0..59).
func parseSlotTime(value string) (time.Time, bool) {
	v := value
	if len(v) == 5 { // "HH:MM" -> Sekunden ergaenzen
		v += ":00"
	}
	if len(v) != 8 {
		return time.Time{}, false
	}
	t, err := time.Parse("15:04:05", v)
	if err != nil {
		return time.Time{}, false
	}
	return t, true
}

// ValidateQuarterHourSlotTime prueft eine Briefing-Uhrzeit beim Schreiben:
// Format "HH:MM" oder "HH:MM:SS", Minute 00/15/30/45. Liefert den Wert als
// "HH:MM:SS" mit Sekunden :00 (z. B. "06:45:30" -> "06:45:00"). Eine
// unzulaessige Minute (z. B. 06:50) ist ein Fehler — keine stille Rundung.
func ValidateQuarterHourSlotTime(fieldName, value string) (string, error) {
	t, ok := parseSlotTime(value)
	if !ok {
		return "", fmt.Errorf("%s must match HH:MM or HH:MM:SS", fieldName)
	}
	if t.Minute()%15 != 0 {
		return "", fmt.Errorf("%s must be on the quarter hour (minutes 00, 15, 30, 45), got %q", fieldName, value)
	}
	return fmt.Sprintf("%02d:%02d:00", t.Hour(), t.Minute()), nil
}

// TruncateTimeStringToQuarterHour rundet "HH:MM"/"HH:MM:SS" auf die
// vorherige Viertelstunde ab (Lese-Heilung fuer Altwerte, 07:20 -> 07:15:00).
// Rasterkonforme Werte ohne Sekunden bleiben im Originalformat unveraendert;
// nicht parsebare Werte ebenfalls (Validierung findet beim Schreiben statt).
func TruncateTimeStringToQuarterHour(value string) string {
	t, ok := parseSlotTime(value)
	if !ok {
		return value
	}
	if t.Minute()%15 == 0 && t.Second() == 0 {
		return value // bereits im Raster — Originalformat beibehalten
	}
	return fmt.Sprintf("%02d:%02d:00", t.Hour(), t.Minute()-t.Minute()%15)
}

// TruncateTimePtrToQuarterHour ist die Pointer-sichere Variante von
// TruncateTimeStringToQuarterHour: nil bleibt nil, ein gesetzter Wert wird
// abgerundet (neuer Pointer, Original unangetastet).
func TruncateTimePtrToQuarterHour(v *string) *string {
	if v == nil {
		return nil
	}
	h := TruncateTimeStringToQuarterHour(*v)
	return &h
}

// HealComparePresetSlotTimes rundet die beiden Slot-Zeitfelder eines
// geladenen Presets auf das Viertelstunden-Raster ab (Read-Heilung fuer
// Bestandsdaten, #2795). Wird von LoadComparePresets/LoadComparePreset
// aufgerufen — kein Write-Back auf die Platte.
func HealComparePresetSlotTimes(p *model.ComparePreset) {
	p.MorningTime = TruncateTimePtrToQuarterHour(p.MorningTime)
	p.EveningTime = TruncateTimePtrToQuarterHour(p.EveningTime)
}

// NormalizeReportConfigSlotTimes rundet AUSSCHLIESSLICH report_config.morning_time
// und report_config.evening_time auf das Viertelstunden-Raster ab (Read-Heilung,
// healTripSlotTimes). Alle anderen report_config-Keys bleiben unberuehrt.
func NormalizeReportConfigSlotTimes(rc map[string]interface{}) {
	if rc == nil {
		return
	}
	for _, key := range []string{"morning_time", "evening_time"} {
		if v, ok := rc[key].(string); ok && v != "" {
			rc[key] = TruncateTimeStringToQuarterHour(v)
		}
	}
}

// ValidateReportConfigSlotTimes ist die Schreib-Pruefung (CreateTripHandler,
// UpdateTripHandler, #2795): report_config.morning_time/evening_time muessen
// im Viertelstunden-Raster liegen; Sekunden werden zu :00. Bei einem Fehler
// bleibt die Map unveraendert und der Aufrufer antwortet mit 400. Alle
// anderen report_config-Keys bleiben unberuehrt.
func ValidateReportConfigSlotTimes(rc map[string]interface{}) error {
	if rc == nil {
		return nil
	}
	normalized := map[string]string{}
	for _, key := range []string{"morning_time", "evening_time"} {
		if v, ok := rc[key].(string); ok && v != "" {
			n, err := ValidateQuarterHourSlotTime("report_config."+key, v)
			if err != nil {
				return err
			}
			normalized[key] = n
		}
	}
	for key, n := range normalized {
		if t, _ := parseSlotTime(rc[key].(string)); t.Second() != 0 {
			rc[key] = n // nur Sekunden -> :00; rasterkonforme Werte behalten ihr Format
		}
	}
	return nil
}

// ClampReportConfigDayWindow validiert/klemmt report_config.day_window_start_hour
// und _end_hour (Epic #1319 Scheibe B, DEC-2 Defense-in-Depth; erweitert
// Issue #1361/#1372 S1b, PO-Entscheidung 2026-07-25): liegt einer der beiden
// Werte ausserhalb 0-23 oder ist start == end, werden BEIDE Keys aus der Map
// entfernt (-> Python-seitiger Default 4/19 beim naechsten Lesen). start > end
// ist seit #1361/#1372 S1b ein GUELTIGES Fenster ueber Mitternacht (z. B.
// 22-2 Uhr), keine Klemmung mehr -- dieselbe Regel wie
// day_window.resolve_configured_window() auf der Python-Seite. Ein gueltiges
// Paar bleibt unangetastet. Alle anderen report_config-Keys bleiben unberuehrt
// (kein Replace).
func ClampReportConfigDayWindow(rc map[string]interface{}) {
	if rc == nil {
		return
	}
	start, startOk := toIntHour(rc["day_window_start_hour"])
	end, endOk := toIntHour(rc["day_window_end_hour"])
	if !startOk && !endOk {
		return // kein Feld-Paar gesetzt -- nichts zu tun
	}
	valid := startOk && endOk &&
		start >= 0 && start <= 23 &&
		end >= 0 && end <= 23 &&
		start != end
	if !valid {
		delete(rc, "day_window_start_hour")
		delete(rc, "day_window_end_hour")
	}
}

// ClampComparePresetDayWindow validiert/klemmt ComparePreset.DayWindowStartHour/
// DayWindowEndHour (Issue #1361/#1372 S1b, analog ClampReportConfigDayWindow
// fuer den Trip): liegt einer der beiden Werte ausserhalb 0-23 oder ist
// start == end, werden BEIDE Pointer auf nil gesetzt (-> Python-seitiger
// Default 4/19 beim naechsten Lesen). start > end ist ein GUELTIGES Fenster
// ueber Mitternacht (PO-Entscheidung 2026-07-25), keine Klemmung mehr. Ist
// nur EINER der beiden Pointer gesetzt (Teil-Input), gilt das ebenfalls als
// ungueltiges Paar -> beide nil. Ein gueltiges Paar bleibt unangetastet.
// Alle anderen Preset-Felder bleiben unberuehrt.
func ClampComparePresetDayWindow(p *model.ComparePreset) {
	if p.DayWindowStartHour == nil && p.DayWindowEndHour == nil {
		return // kein Feld-Paar gesetzt -- nichts zu tun
	}
	valid := p.DayWindowStartHour != nil && p.DayWindowEndHour != nil &&
		*p.DayWindowStartHour >= 0 && *p.DayWindowStartHour <= 23 &&
		*p.DayWindowEndHour >= 0 && *p.DayWindowEndHour <= 23 &&
		*p.DayWindowStartHour != *p.DayWindowEndHour
	if !valid {
		p.DayWindowStartHour = nil
		p.DayWindowEndHour = nil
	}
}

// toIntHour liest einen Stunden-Wert aus einer JSON-dekodierten map[string]interface{}
// (Zahlen kommen aus encoding/json typischerweise als float64 an).
func toIntHour(v interface{}) (int, bool) {
	switch n := v.(type) {
	case float64:
		return int(n), true
	case int:
		return n, true
	default:
		return 0, false
	}
}

// healTripSlotTimes rundet sowohl das verschachtelte report_config.morning_time/
// evening_time ALS AUCH die daraus abgeleiteten obersten Flach-Felder
// (trip.MorningTime/EveningTime, s. deriveFlatFields) auf das
// Viertelstunden-Raster ab (#2795; vorher volle Stunde, #1280).
// Muss NACH deriveFlatFields laufen (die Flach-Felder existieren erst danach).
// Aufgerufen ausschliesslich von LoadTrip/LoadTrips (Read-Pfad) — SaveTrip ruft
// dies NICHT, damit roh geseedete Testdaten unnormalisiert auf der Platte
// bleiben und die Heilung beim naechsten Load nachweisbar ist.
func healTripSlotTimes(trip *model.Trip) {
	NormalizeReportConfigSlotTimes(trip.ReportConfig)
	ClampReportConfigDayWindow(trip.ReportConfig)
	trip.MorningTime = TruncateTimePtrToQuarterHour(trip.MorningTime)
	trip.EveningTime = TruncateTimePtrToQuarterHour(trip.EveningTime)
}
