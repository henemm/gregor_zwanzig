package store

// Issue #2050 Scheibe S6 -- AC-13 (D4-Invarianz, PFLICHT mit Gegenprobe).
// SPEC: docs/specs/modules/alarm_protokoll_vorwarnzeit.md (AC-13)
//
// Die Spec verlangt ausdruecklich einen Go-Test statt einer Python-Nachbildung
// des Lesevertrags: geprueft wird die Schicht, die unbekannte Felder verwerfen
// soll (log.go:48-56), nicht der Python-Schreibpfad. Vorbild:
// archive_stats_test.go (writeLogFile-Helper, echtes store.New(t.TempDir())).
//
// Diese Zusicherung ist BEWUSST von Anfang an GRUEN: log.go braucht laut Spec
// KEINE Aenderung ("keine Aenderung noetig") -- Go's encoding/json verwirft
// unbekannte Felder strukturell bereits heute. Der Test ist trotzdem PFLICHT
// als dauerhafter Regressions-Waechter fuer D4 (Cockpit-Kachel/Archiv-
// Statistik duerfen sich fuer Bestandstouren um keine Zahl aendern), samt
// Gegenprobe, dass die Pruefung ueberhaupt etwas MISST.

import (
	"testing"
)

// AC-13: zwei sonst identische alert_log.json-Dateien fuer denselben Nutzer,
// eine MIT den sechs neuen S6-Schluesseln je Eintrag befuellt, eine OHNE --
// AlertCountByEntity() muss fuer dieselbe entity_id EXAKT dieselbe Zahl liefern.
func TestAlertCountByEntity_IgnoresNewS6FieldsInvariantly(t *testing.T) {
	entityID := "trip-2050-s6-ac13"

	mitNeuenFeldern := []map[string]interface{}{
		{
			"entity_id": entityID, "entity_type": "trip",
			"sent_at": "2026-06-10T09:00:00Z", "changes_count": 2, "severity": "MODERATE",
			"lead_time_minutes": 12, "event_at": "2026-06-10T09:12:00Z",
			"event_end_at":      "2026-06-10T09:45:00Z",
			"measurement_point": map[string]interface{}{"segment_id": "1", "km_from": 0.0, "km_to": 3.0},
			"reference_at":      "2026-06-10T08:00:00Z", "source": "Radar (DWD)",
		},
		{
			"entity_id": entityID, "entity_type": "trip",
			"sent_at": "2026-06-11T10:00:00Z", "changes_count": 1, "severity": "LOW",
			"lead_time_minutes": 5, "source": "INCA (GeoSphere AT)",
		},
		{
			"entity_id": entityID, "entity_type": "trip",
			"sent_at": "2026-06-12T11:00:00Z", "changes_count": 3, "severity": "HIGH",
		},
	}
	ohneNeueFelder := []map[string]interface{}{
		{
			"entity_id": entityID, "entity_type": "trip",
			"sent_at": "2026-06-10T09:00:00Z", "changes_count": 2, "severity": "MODERATE",
		},
		{
			"entity_id": entityID, "entity_type": "trip",
			"sent_at": "2026-06-11T10:00:00Z", "changes_count": 1, "severity": "LOW",
		},
		{
			"entity_id": entityID, "entity_type": "trip",
			"sent_at": "2026-06-12T11:00:00Z", "changes_count": 3, "severity": "HIGH",
		},
	}

	dataDirMit := t.TempDir()
	writeLogFile(t, dataDirMit, "s6-mit", "alert_log.json", mitNeuenFeldern)
	dataDirOhne := t.TempDir()
	writeLogFile(t, dataDirOhne, "s6-ohne", "alert_log.json", ohneNeueFelder)

	countsMit, err := New(dataDirMit, "s6-mit").AlertCountByEntity()
	if err != nil {
		t.Fatalf("unexpected error (mit neuen Feldern): %v", err)
	}
	countsOhne, err := New(dataDirOhne, "s6-ohne").AlertCountByEntity()
	if err != nil {
		t.Fatalf("unexpected error (ohne neue Felder): %v", err)
	}

	key := "trip:" + entityID
	if countsMit[key] != countsOhne[key] {
		t.Fatalf(
			"AC-13: die sechs neuen Schluessel duerfen die Zaehlung NICHT veraendern -- mit=%d ohne=%d (erwarte gleiche Zahl)",
			countsMit[key], countsOhne[key],
		)
	}
	if countsMit[key] != 3 {
		t.Fatalf("Vorbedingung: erwarte 3 Eintraege fuer %s, bekam %d", key, countsMit[key])
	}

	// Gegenprobe: eine dritte Fixture mit einem ECHT geaenderten bestehenden
	// Feld (changes_count des ersten Eintrags 2 -> 9) MUSS beim Lesen der
	// EINZELNEN Eintraege eine ANDERE Zahl liefern -- das zeigt, dass der
	// Lesepfad ueberhaupt etwas misst und nicht zufaellig immer gleich zaehlt
	// bzw. blind einen festen Wert zurueckgibt.
	echtGeaendert := []map[string]interface{}{
		{
			"entity_id": entityID, "entity_type": "trip",
			"sent_at": "2026-06-10T09:00:00Z", "changes_count": 9, "severity": "MODERATE",
			"lead_time_minutes": 12,
		},
	}
	dataDirGeaendert := t.TempDir()
	writeLogFile(t, dataDirGeaendert, "s6-geaendert", "alert_log.json", echtGeaendert)

	entriesGeaendert, err := New(dataDirGeaendert, "s6-geaendert").LoadAlertLog()
	if err != nil {
		t.Fatalf("unexpected error (Gegenprobe): %v", err)
	}
	if len(entriesGeaendert) != 1 {
		t.Fatalf("Gegenprobe-Vorbedingung: erwarte genau 1 Eintrag, bekam %d", len(entriesGeaendert))
	}
	if entriesGeaendert[0].ChangesCount != 9 {
		t.Fatalf(
			"Gegenprobe: ein ECHT geaendertes bestehendes Feld (changes_count=9) muss beim Lesen ANKOMMEN (bekam %d) -- sonst waere die Invarianz oben nur ein blind immer-gleiches Ergebnis, kein echter Vergleich",
			entriesGeaendert[0].ChangesCount,
		)
	}
	if entriesGeaendert[0].ChangesCount == 2 {
		t.Fatalf("Gegenprobe-Konstruktion: die Gegenprobe-Fixture muss sich vom changes_count der ersten Fixture (2) UNTERSCHEIDEN, sonst beweist sie nichts")
	}
}
