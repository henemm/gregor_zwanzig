package handler

// Issue #2280 S2: kind-neutraler Handversand im /api/briefings-Dispatcher
// (ADR-0023, Muster briefing_preview.go). kind ist Pflicht-Query, die ID wird
// vor dem Weiterreichen geprueft, die Besitzpruefung macht der user-scoped
// Python-Loader (fremde ID -> 404). Weiterleitung ueber forwardSend.
//
// Fehlerform des Versandwegs ist Form A {"detail","code"} (api_contract.md
// 10.1); seit Issue #2677 liefert WriteError sie mit (detail = message in der
// Sprache des Nutzers, Texte in fach.fehler.*_versand/_kennung).
//
// Spec: docs/specs/modules/feat_2280_handversand_endpoint.md (AC-1 bis AC-3,
// AC-9, AC-13, AC-14).

import (
	"net/http"
	"net/url"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/i18n"
	"github.com/henemm/gregor-api/internal/store"
)

// Go-seitige Versand-Fehler (die fachlichen Codes samt Texten stehen in
// src/services/send_outcomes.py; diese Faelle entstehen, bevor Python
// erreicht wird). Variante waehlt fach.fehler.<code>_<variante>.
var (
	sendVarianteKennung = i18n.Args{"variante": "kennung"}
	sendVarianteVersand = i18n.Args{"variante": "versand"}
)

// POST /api/briefings/{id}/send?kind=route|vergleich[&report_type=]
// Weiter an Python POST /api/briefings/{id}/send?kind=…&user_id=<auth>;
// report_type geht nur bei kind=route mit.
func BriefingSendHandler(pythonURL string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		kind := r.URL.Query().Get("kind")
		if !isValidBriefingKind(kind) {
			WriteError(w, r, http.StatusBadRequest, "kind_required", nil)
			return
		}
		id := chi.URLParam(r, "id")
		if !store.ValidEntityID(id) {
			WriteError(w, r, http.StatusBadRequest, "validation_error", sendVarianteKennung)
			return
		}
		q := url.Values{}
		q.Set("kind", kind)
		if rt := r.URL.Query().Get("report_type"); kind == briefingKindRoute && rt != "" {
			q.Set("report_type", rt)
		}
		forwardSend(w, r, pythonURL+"/api/briefings/"+id+"/send", q.Encode())
	}
}
