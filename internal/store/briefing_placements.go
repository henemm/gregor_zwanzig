package store

// Issue #3122 B2 (Spec feat_3122_was_steht_wo, Teil A Nr. 1/9, AC-14):
// Schreibweg der Tabelle "Was steht wo". Read-Modify-Write auf den ROHEN
// Bytes der Abo-Datei: nur display_config.placements wird ersetzt, jedes
// andere Feld (auch solche, die nur der Python-Kern kennt) bleibt wertgleich
// stehen. Bewusst nicht ueber LoadTrip/SaveTrip bzw. SaveComparePreset: deren
// Normalisierung (Alarmregeln, Ankunftszeiten, Slot-Heilung) wuerde beim
// Speichern der Tabelle andere Felder mitveraendern.

import (
	"encoding/json"
	"os"
	"path/filepath"
)

// SaveBriefingPlacements ersetzt display_config.placements des Abos id
// (Trip bei vergleich=false, Orte-Abo bei vergleich=true) als Ganzes durch
// placements (ein JSON-Objekt, ungeprueft, ADR-0077). Fehlt die Datei oder ist
// sie von der anderen Art, liefert sie ErrNotFound und schreibt nichts.
// Schreibweg des Tabellen-PUT und der Anlage (Issue #3237).
func (s *Store) SaveBriefingPlacements(id string, vergleich bool, placements json.RawMessage) error {
	if err := s.requireUser(); err != nil {
		return err
	}
	// Issue #2140 Scheibe 2: Segment-Pruefung VOR dem Join.
	if !ValidEntityID(id) {
		return ErrInvalidEntityID
	}
	path := filepath.Join(s.briefingsDir(), id+".json")
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return ErrNotFound
		}
		return err
	}
	var doc map[string]json.RawMessage
	if err := json.Unmarshal(data, &doc); err != nil {
		return err
	}
	if istVergleich(doc) != vergleich {
		return ErrNotFound
	}
	dc := map[string]json.RawMessage{}
	if raw, ok := doc["display_config"]; ok && string(raw) != "null" {
		if err := json.Unmarshal(raw, &dc); err != nil {
			return err
		}
	}
	dc["placements"] = placements
	neu, err := json.Marshal(dc)
	if err != nil {
		return err
	}
	doc["display_config"] = neu
	out, err := json.MarshalIndent(doc, "", "  ")
	if err != nil {
		return err
	}
	if err := pruefeEntityGroesse(out); err != nil {
		return err
	}
	return writeFileLogged(path, out)
}

// istVergleich: dieselbe Regel wie LoadTrip/LoadComparePreset -- nur
// kind=="vergleich" ist ein Orte-Abo, alles andere (auch fehlend) ein Trip.
func istVergleich(doc map[string]json.RawMessage) bool {
	var kind string
	if raw, ok := doc["kind"]; ok {
		_ = json.Unmarshal(raw, &kind)
	}
	return kind == "vergleich"
}
