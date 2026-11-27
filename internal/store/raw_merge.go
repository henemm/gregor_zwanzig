package store

import (
	"encoding/json"
	"log"
	"os"
	"reflect"
	"strings"
)

// jsonKeysOf liefert die JSON-Schluessel aller Top-Level-Felder des
// Struct-Typs t ("-" wird ignoriert, Tag-Name vor dem Komma). Eingebettete
// anonyme Structs ohne eigenen Tag werden aufgeloest (Issue #3092).
func jsonKeysOf(t reflect.Type) []string {
	for t.Kind() == reflect.Ptr {
		t = t.Elem()
	}
	keys := make([]string, 0, t.NumField())
	for i := 0; i < t.NumField(); i++ {
		f := t.Field(i)
		tag := f.Tag.Get("json")
		if tag == "-" {
			continue
		}
		name, _, _ := strings.Cut(tag, ",")
		if f.Anonymous && name == "" {
			ft := f.Type
			for ft.Kind() == reflect.Ptr {
				ft = ft.Elem()
			}
			if ft.Kind() == reflect.Struct {
				keys = append(keys, jsonKeysOf(ft)...)
				continue
			}
		}
		if !f.IsExported() {
			continue
		}
		if name == "" {
			name = f.Name
		}
		keys = append(keys, name)
	}
	return keys
}

// mergeUnknownTopLevel serialisiert model und uebernimmt dem Modell
// unbekannte Top-Level-Schluessel der vorhandenen Datei path (ADR-0101,
// Issue #3092). Bekannte Schluessel werden zuerst aus dem Altstand
// geloescht, damit geleerte omitempty-Felder nicht wiederaufleben. Fehlt
// die Datei, ist sie nicht lesbar oder kein JSON-Objekt: nur Modellstand.
func mergeUnknownTopLevel(path string, model interface{}, known []string) ([]byte, error) {
	data, err := json.MarshalIndent(model, "", "  ")
	if err != nil {
		return nil, err
	}
	existing, err := os.ReadFile(path)
	if err != nil {
		if !os.IsNotExist(err) {
			log.Printf("mergeUnknownTopLevel %s: Altdatei nicht lesbar, schreibe Modellstand: %v", path, err)
		}
		return data, nil
	}
	var raw map[string]json.RawMessage
	if err := json.Unmarshal(existing, &raw); err != nil || raw == nil {
		return data, nil
	}
	var modelMap map[string]json.RawMessage
	if err := json.Unmarshal(data, &modelMap); err != nil {
		return nil, err
	}
	for _, key := range known {
		delete(raw, key)
	}
	for k, v := range modelMap {
		raw[k] = v
	}
	return json.MarshalIndent(raw, "", "  ")
}
