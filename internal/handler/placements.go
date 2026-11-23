package handler

// Issue #3122 B2 (Spec feat_3122_was_steht_wo, Teil A Nr. 9, ADR-0124):
// Tabelle "Was steht wo" unter der Briefing-Route, fuer Trip (kind=route) und
// Orte (kind=vergleich) EIN Code-Pfad.
//
//   GET /api/briefings/{id}/placements?kind=route|vergleich
//       Nutzer aus der Anmeldung, Abo DIESES Nutzers laden (fremd/unbekannt =
//       404 wie bei GET /api/briefings/{id}), dann an den Python-Kern
//       weiterreichen (Beispielwerte, SMS-Beispiel, Marken baut der Kern aus
//       dem echten Renderer). ETag = Stempel des Abos, Grundlage fuer If-Match.
//   PUT /api/briefings/{id}/placements?kind=route|vergleich
//       Rumpf = vollstaendiger Stand von display_config.placements (JSON-
//       Objekt, Inhalt ungeprueft, ADR-0077). Read-Modify-Write schreibt nur
//       dieses Feld (store.SaveBriefingPlacements). If-Match wie beim Abo:
//       veralteter Stand -> 412 precondition_failed, nichts wird geschrieben.
//       Issue #3237: der PUT fragt den Kern nicht (frueheres Begleitfeld
//       show_stability_off entfallen); report_config bleibt unveraendert.
//   Anlage (POST Trip/Orte, anlageTabelle): nach dem Speichern fragt Go den
//       Kern (GET .../placements/erstanlage) nach der vollen Tabelle aus der
//       Grundauswahl und schreibt sie per Read-Modify-Write (#3275/#3237).
//
// Die Rumpfgrenze setzt die globale LimitBody-Middleware wie fuer alle Routen.

import (
	"bytes"
	"encoding/json"
	"errors"
	"io"
	"log"
	"net/http"
	"net/url"
	"time"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/store"
)

// placementsZiel prueft Anmeldung, kind und Kennung und liefert Nutzer,
// kind und Kennung; false heisst: die Antwort ist geschrieben. Die Bindung
// des Stores (WithUser) macht jeder Handler selbst, sichtbar fuer den
// Waechter store_scope_call_guard.
func placementsZiel(w http.ResponseWriter, r *http.Request) (string, string, string, bool) {
	userID := middleware.UserIDFromContext(r.Context())
	if userID == "" {
		WriteError(w, r, http.StatusUnauthorized, "unauthorized", nil)
		return "", "", "", false
	}
	kind := r.URL.Query().Get("kind")
	if !isValidBriefingKind(kind) {
		WriteError(w, r, http.StatusBadRequest, "kind_required", nil)
		return "", "", "", false
	}
	id := chi.URLParam(r, "id")
	if bailIf(w, r, !store.ValidEntityID(id), http.StatusBadRequest, "validation_error") {
		return "", "", "", false
	}
	return userID, kind, id, true
}

// placementsAboVorhanden laedt das Abo der Art kind aus dem Bestand des
// gebundenen Nutzers; fremd, unbekannt oder andere Art -> 404.
func placementsAboVorhanden(w http.ResponseWriter, r *http.Request, s *store.Store, kind, id string) bool {
	var vorhanden bool
	var err error
	if kind == briefingKindRoute {
		// gz-store-scope-call: Hilfsfunktion, beide Aufrufer reichen den per WithUser gebundenen Store durch
		trip, e := s.LoadTrip(id)
		vorhanden, err = trip != nil, e
	} else {
		// gz-store-scope-call: Hilfsfunktion, beide Aufrufer reichen den per WithUser gebundenen Store durch
		preset, e := s.LoadComparePreset(id)
		vorhanden, err = preset != nil, e
	}
	if bailIf(w, r, err != nil, http.StatusInternalServerError, "store_error") {
		return false
	}
	return !bailIf(w, r, !vorhanden, http.StatusNotFound, "not_found")
}

// BriefingPlacementsGetHandler: GET /api/briefings/{id}/placements.
func BriefingPlacementsGetHandler(s *store.Store, pythonURL string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userID, kind, id, ok := placementsZiel(w, r)
		if !ok {
			return
		}
		s := s.WithUser(userID)
		// Sperre wie beim Lesen des Abos: der Stempel gehoert zum Stand, den
		// der Kern liest (kein Go-Schreibweg dazwischen).
		unlock, okB := lockBriefingOr503(w, r, s, id)
		if !okB {
			return
		}
		defer unlock()
		if !placementsAboVorhanden(w, r, s, kind, id) {
			return
		}
		fp, fpErr := s.BriefingFingerprint(id)
		setETagHeader(w, fp, fpErr)
		// Nur kind geht weiter; user_id setzt forwardPreview aus der Anmeldung.
		r.URL.RawQuery = url.Values{"kind": {kind}}.Encode()
		forwardPreview(w, r, http.MethodGet,
			pythonURL+"/api/briefings/"+url.PathEscape(id)+"/placements", previewProxyTimeout)
	}
}

// placementsErstanlageTimeout: Zeitgrenze der Tabellen-Abfrage (Paket-`var`).
// Kurz (5 s), weil anlageTabelle unter dem nutzerweiten Quoten-Lock laeuft
// (trip.go/compare_preset.go `defer s.LockQuota()()`): ein haengender Kern
// blockiert sonst jede weitere Anlage/Loeschung des Nutzers. Fail-soft: ohne
// Antwort bleibt die Anlage gueltig (Grundauswahl-Tabelle beim Lesen).
var placementsErstanlageTimeout = 5 * time.Second

// tabelleMitZeilen: display_config traegt schon placements.rows.
func tabelleMitZeilen(dc map[string]interface{}) bool {
	tab, ok := dc["placements"].(map[string]interface{})
	if !ok {
		return false
	}
	_, hatRows := tab["rows"].([]interface{})
	return hatRows
}

// anlageTabelle (#3275/#3237): nach der Anlage berechnet der Kern die volle
// Tabelle aus der Grundauswahl DIESES Nutzers, Go schreibt sie per Read-
// Modify-Write (unter der Briefing-Sperre, s per WithUser gebunden). Keine
// Zeilen in Go; mitgeschickte rows bleiben; Kern-Fehler: Anlage bleibt
// gueltig (ohne rows gilt dieselbe Grundauswahl-Tabelle). *dc (Antwort) folgt.
func anlageTabelle(r *http.Request, s *store.Store, pythonURL, kind, id string, dc *map[string]interface{}) {
	if pythonURL == "" || tabelleMitZeilen(*dc) {
		return
	}
	query := appendUserID(url.Values{"kind": {kind}}.Encode(), middleware.UserIDFromContext(r.Context()))
	ziel := pythonURL + "/api/briefings/" + url.PathEscape(id) + "/placements/erstanlage?" + query
	req, err := http.NewRequestWithContext(r.Context(), http.MethodGet, ziel, nil)
	var resp *http.Response
	if err == nil {
		resp, err = (&http.Client{Timeout: placementsErstanlageTimeout}).Do(req)
	}
	if err != nil {
		log.Printf("[anlage] Tabelle %s: Kern nicht erreichbar: %v", id, err)
		return
	}
	defer resp.Body.Close()
	var antwort struct {
		Placements json.RawMessage `json:"placements"`
	}
	var tabelle map[string]interface{}
	if resp.StatusCode != http.StatusOK || json.NewDecoder(resp.Body).Decode(&antwort) != nil ||
		json.Unmarshal(antwort.Placements, &tabelle) != nil || tabelle == nil {
		log.Printf("[anlage] Tabelle %s: Kern-Antwort unbrauchbar (Status %d)", id, resp.StatusCode)
		return
	}
	// gz-store-scope-call: Hilfsfunktion, beide Anlage-Handler reichen den per WithUser gebundenen Store durch
	if err := s.SaveBriefingPlacements(id, kind == briefingKindVergleich, antwort.Placements); err != nil {
		log.Printf("[anlage] Tabelle %s: Speichern fehlgeschlagen: %v", id, err)
		return
	}
	if *dc == nil {
		*dc = map[string]interface{}{}
	}
	(*dc)["placements"] = tabelle
}

// BriefingPlacementsPutHandler: PUT /api/briefings/{id}/placements.
func BriefingPlacementsPutHandler(s *store.Store, pythonURL string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userID, kind, id, ok := placementsZiel(w, r)
		if !ok {
			return
		}
		s := s.WithUser(userID)
		unlock, okB := lockBriefingOr503(w, r, s, id)
		if !okB {
			return
		}
		defer unlock()
		oldFp, fpErr := s.BriefingFingerprint(id)
		if bailIf(w, r, fpErr != nil, http.StatusInternalServerError, "store_error") {
			return
		}
		if !placementsAboVorhanden(w, r, s, kind, id) {
			return
		}
		// Vorbedingung VOR dem Lesen des Rumpfes: stimmt sie nicht, wird nichts geschrieben.
		if !ifMatchAllows(r.Header.Get("If-Match"), oldFp) {
			writePreconditionFailed(w, r)
			return
		}
		placements, ok := placementsRumpf(w, r)
		if !ok {
			return
		}
		if err := s.SaveBriefingPlacements(id, kind == briefingKindVergleich, placements); err != nil {
			if errors.Is(err, store.ErrNotFound) {
				WriteError(w, r, http.StatusNotFound, "not_found", nil)
				return
			}
			writeSaveError(w, r, err)
			return
		}
		newFp, newFpErr := s.BriefingFingerprint(id)
		setETagHeader(w, newFp, newFpErr)
		writeJSON(w, http.StatusOK, map[string]json.RawMessage{"placements": placements})
	}
}

// placementsRumpf liest den Rumpf; nur ein JSON-Objekt ist zulaessig (Inhalt
// ungeprueft, ADR-0077). Zurueck kommt die kompakte Form.
func placementsRumpf(w http.ResponseWriter, r *http.Request) (json.RawMessage, bool) {
	body, err := io.ReadAll(r.Body)
	if bailIf(w, r, err != nil, http.StatusBadRequest, "bad_request") {
		return nil, false
	}
	var objekt map[string]json.RawMessage
	if err := json.Unmarshal(body, &objekt); bailIf(w, r, err != nil || objekt == nil, http.StatusBadRequest, "bad_request") {
		return nil, false
	}
	var kompakt bytes.Buffer
	if err := json.Compact(&kompakt, body); bailIf(w, r, err != nil, http.StatusBadRequest, "bad_request") {
		return nil, false
	}
	return json.RawMessage(kompakt.Bytes()), true
}

// placementsVorschauMaxBytes: Grenze des Entwurfs der Vorschau (#3304, AC-8).
const placementsVorschauMaxBytes = 256 << 10

// BriefingPlacementsPreviewHandler: POST /api/briefings/placements/vorschau
// (#3304). Tabelle "Was steht wo" fuer einen noch nicht angelegten Entwurf:
// Anmeldung, kind, Groesse und JSON-Objekt pruefen, dann den unveraenderten
// Entwurf an den Kern reichen. Kein Store-Zugriff, kein ETag, nichts wird
// geschrieben; die Orte liest der Kern im Bestand des angemeldeten Nutzers.
func BriefingPlacementsPreviewHandler(pythonURL string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if middleware.UserIDFromContext(r.Context()) == "" {
			WriteError(w, r, http.StatusUnauthorized, "unauthorized", nil)
			return
		}
		kind := r.URL.Query().Get("kind")
		if !isValidBriefingKind(kind) {
			WriteError(w, r, http.StatusBadRequest, "kind_required", nil)
			return
		}
		body, err := io.ReadAll(http.MaxBytesReader(w, r.Body, placementsVorschauMaxBytes))
		var tooLarge *http.MaxBytesError
		if errors.As(err, &tooLarge) {
			WriteError(w, r, http.StatusRequestEntityTooLarge, "payload_too_large", nil)
			return
		}
		var objekt map[string]json.RawMessage
		if bailIf(w, r, err != nil || json.Unmarshal(body, &objekt) != nil || objekt == nil,
			http.StatusBadRequest, "bad_request") {
			return
		}
		r.Body = io.NopCloser(bytes.NewReader(body))
		// Nur kind geht weiter; user_id setzt forwardPreview aus der Anmeldung.
		r.URL.RawQuery = url.Values{"kind": {kind}}.Encode()
		forwardPreview(w, r, http.MethodPost, pythonURL+"/api/briefings/placements/vorschau", previewProxyTimeout)
	}
}
