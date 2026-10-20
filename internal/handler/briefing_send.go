package handler

// Issue #2280 S2: kind-neutraler Handversand im /api/briefings-Dispatcher
// (ADR-0023, Muster briefing_preview.go). kind ist Pflicht-Query, die ID wird
// vor dem Weiterreichen geprueft, die Besitzpruefung macht der user-scoped
// Python-Loader (fremde ID -> 404). Weiterleitung ueber forwardSend.
//
// Fehlerform des Versandwegs ist Form A {"detail":"<deutscher Text>",
// "code":"<code>"} (api_contract.md 10.1) — bewusst NICHT ueber
// briefingPreviewTarget/writeBriefingKindRequired/bailIf, deren
// {"error":"<code>"}-Form der dokumentierte Vertrag von Vorschau und
// Briefing-CRUD ist.
//
// Spec: docs/specs/modules/feat_2280_handversand_endpoint.md (AC-1 bis AC-3,
// AC-9, AC-13, AC-14).

import (
	"net/http"
	"net/url"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/store"
)

// Go-seitige Versand-Fehlertexte (die fachlichen Codes samt Texten stehen in
// src/services/send_outcomes.py; diese Faelle entstehen, bevor Python
// erreicht wird). kind_required uebernimmt den Python-Wortlaut.
const (
	sendDetailKindRequired      = "Briefing-Art fehlt oder ist ungültig (erlaubt: route, vergleich)"
	sendDetailInvalidID         = "Ungültige Briefing-Kennung"
	sendDetailProxyError        = "Versand konnte nicht gestartet werden — bitte später erneut versuchen"
	sendDetailUpstreamUnreached = "Versanddienst nicht erreichbar — bitte später erneut versuchen"
)

func writeSendError(w http.ResponseWriter, status int, code, detail string) {
	writeJSON(w, status, map[string]string{"detail": detail, "code": code})
}

// POST /api/briefings/{id}/send?kind=route|vergleich[&report_type=]
// Weiter an Python POST /api/briefings/{id}/send?kind=…&user_id=<auth>;
// report_type geht nur bei kind=route mit.
func BriefingSendHandler(pythonURL string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		kind := r.URL.Query().Get("kind")
		if !isValidBriefingKind(kind) {
			writeSendError(w, http.StatusBadRequest, "kind_required", sendDetailKindRequired)
			return
		}
		id := chi.URLParam(r, "id")
		if !store.ValidEntityID(id) {
			writeSendError(w, http.StatusBadRequest, "validation_error", sendDetailInvalidID)
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
