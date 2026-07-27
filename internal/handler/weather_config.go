package handler

import (
	"encoding/json"
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// --- Trip Weather Config ---

// Issue #1395 S2: ":=" statt "=" beim WithUser-Aufruf — anfragelokale Variable
// statt geteilter Closure-Variable. Begruendung ausfuehrlich in trip.go
// (Kommentar ueber TripsHandler). Gilt hier fuer die beiden TRIP-Handler; die
// Location-Handler weiter unten tragen dasselbe Muster noch und bleiben in
// dieser Scheibe unberuehrt (andere Datei-Ebene, nicht im Scope).
func GetTripWeatherConfigHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s := s.WithUser(middleware.UserIDFromContext(r.Context()))
		id := chi.URLParam(r, "id")
		// Issue #1395 S2: Sperre auch beim Lesen, damit der ausgelieferte ETag
		// zur ausgelieferten Fassung gehoert (analog TripHandler).
		defer s.LockBriefing(id)()

		trip, err := s.LoadTrip(id)
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}
		if trip == nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(404)
			w.Write([]byte(`{"error":"not_found"}`))
			return
		}
		// Issue #1395 S2: Der Stempel gilt fuer die GANZE Briefing-Datei, nicht
		// nur fuer display_config — beide Schreibpfade (PUT /api/trips/{id} und
		// dieser hier) fassen dieselbe Datei an, also braucht es denselben
		// Bezugspunkt.
		fp, fpErr := s.BriefingFingerprint(id)
		setETagHeader(w, fp, fpErr)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(trip.DisplayConfig)
	}
}

func PutTripWeatherConfigHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s := s.WithUser(middleware.UserIDFromContext(r.Context()))
		id := chi.URLParam(r, "id")
		// Issue #1395 S2: Sperre + Vorbedingung, identisch zu UpdateTripHandler.
		// Dieser Pfad schreibt dieselbe Datei UND synchronisiert dabei
		// alert_rules (model.SyncAlertRules) — ein verlorener Schreibvorgang
		// zieht hier also mehr nach sich als nur display_config.
		defer s.LockBriefing(id)()

		oldFp, fpErr := s.BriefingFingerprint(id)
		if fpErr != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}

		trip, err := s.LoadTrip(id)
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}
		if trip == nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(404)
			w.Write([]byte(`{"error":"not_found"}`))
			return
		}
		// Vorbedingung VOR dem Dekodieren des Rumpfes (AC-5).
		if !ifMatchAllows(r.Header.Get("If-Match"), oldFp) {
			writePreconditionFailed(w, preconditionFailedDetail)
			return
		}
		var cfg map[string]interface{}
		if err := json.NewDecoder(r.Body).Decode(&cfg); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"bad_request"}`))
			return
		}
		// Issue #1151: Feld-Level-Merge statt Blind-Replace, analog #1129/#1103.
		// Teil-Updates (nur `metrics` gesendet) duerfen andere zuvor gespeicherte
		// display_config-Keys (z.B. `theme`) nicht loeschen.
		// Issue #1159: konsolidiert auf den gemeinsamen mergeConfigMap-Helfer.
		trip.DisplayConfig = mergeConfigMap(trip.DisplayConfig, cfg)
		// Sync alert_rules with active weather metrics (Issue #701)
		activeIDs := model.ActiveAlertableMetricIDs(trip.DisplayConfig)
		trip.AlertRules = model.SyncAlertRules(trip.AlertRules, activeIDs)
		// Issue #1395 S2 (Adversary F002): Kennung auf den URL-Parameter setzen,
		// exakt wie UpdateTripHandler es seit #99/#103 tut. SaveTrip schreibt
		// nach trip.ID — weicht die INNERE Kennung der Datei vom Dateinamen ab,
		// landete die Aenderung sonst in einer fremden Tour, waehrend die
		// angefragte unveraendert blieb. Der Nutzer bekam trotzdem 200 samt
		// gueltigem ETag (der zur unveraenderten Datei gehoerte) und hielt sich
		// fuer gespeichert — ein Vertrauensanker, den es vor S2 nicht gab.
		trip.ID = id
		if err := s.SaveTrip(trip); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}
		// Issue #1395 S2: neuer Stempel fuer den Folge-Schreibvorgang; fail-soft,
		// ein geglueckter Schreibvorgang wird nicht nachtraeglich zum Fehler.
		newFp, newFpErr := s.BriefingFingerprint(id)
		setETagHeader(w, newFp, newFpErr)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(trip.DisplayConfig)
	}
}

// --- Location Weather Config ---

func GetLocationWeatherConfigHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s = s.WithUser(middleware.UserIDFromContext(r.Context()))
		id := chi.URLParam(r, "id")
		loc, err := s.LoadLocation(id)
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}
		if loc == nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(404)
			w.Write([]byte(`{"error":"not_found"}`))
			return
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(loc.DisplayConfig)
	}
}

func PutLocationWeatherConfigHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s = s.WithUser(middleware.UserIDFromContext(r.Context()))
		id := chi.URLParam(r, "id")
		loc, err := s.LoadLocation(id)
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}
		if loc == nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(404)
			w.Write([]byte(`{"error":"not_found"}`))
			return
		}
		var cfg map[string]interface{}
		if err := json.NewDecoder(r.Body).Decode(&cfg); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"bad_request"}`))
			return
		}
		// Issue #1159: Feld-Level-Merge statt Blind-Replace — behebt aktiven
		// Datenverlust (BUG-DATALOSS-GR221, s. mergeConfigMap-Doku).
		loc.DisplayConfig = mergeConfigMap(loc.DisplayConfig, cfg)
		if err := s.SaveLocation(*loc); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(loc.DisplayConfig)
	}
}

// Issue #1257: extractActiveMetricIDs entfernt — dupliziertes, kaputtes
// zweites Mapping (roher Katalog-ID-Vergleich gegen AlertMetric-Vokabular,
// matchte nie). PutTripWeatherConfigHandler nutzt jetzt zentral
// model.ActiveAlertableMetricIDs (dieselbe Stelle wie store.SaveTrip/LoadTrip).

// Issue #1250 Scheibe 0: Subscription Weather Config (GetSubscriptionWeatherConfigHandler,
// PutSubscriptionWeatherConfigHandler) entfernt — Legacy-Drittstack CompareSubscription
// stillgelegt (#1131), store.LoadSubscription/SaveSubscription existieren nicht mehr.
