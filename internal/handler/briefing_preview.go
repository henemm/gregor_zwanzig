package handler

// Issue #2283 S1/S4 (Epic #2345 P3): kind-neutrale Alarm-Vorschau im
// /api/briefings-Dispatcher (Muster briefing_subscription.go, ADR-0023):
// kind ist Pflicht-Query, die ID wird vor dem Weiterreichen geprueft, die
// Besitzpruefung macht der user-scoped Python-Loader (fremde ID -> 404).
// Die Route laeuft durch dieselbe Proxy-Behandlung wie die Alt-Route
// (forwardPreview). Die kind-neutrale Briefing-Vorschau (alle Kanaele in
// einem Abruf) ist mit #1743 entfallen (Reiter Vorschau abgebaut).
//
// Spec: docs/specs/modules/shared_preview_tab.md (AC-1 bis AC-5, AC-16).

import (
	"net/http"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/store"
)

// briefingPreviewTarget prueft kind und ID und liefert den Python-Pfad
// /api/briefings/{id}/<suffix>; false heisst: Antwort (400) ist geschrieben,
// Python wird nicht erreicht.
func briefingPreviewTarget(w http.ResponseWriter, r *http.Request, pythonURL, suffix string) (string, string, bool) {
	kind := r.URL.Query().Get("kind")
	if !isValidBriefingKind(kind) {
		writeBriefingKindRequired(w)
		return "", "", false
	}
	id := chi.URLParam(r, "id")
	if bailIf(w, r, !store.ValidEntityID(id), http.StatusBadRequest, "validation_error") {
		return "", "", false
	}
	return pythonURL + "/api/briefings/" + id + "/" + suffix, kind, true
}

// POST /api/briefings/{id}/alert-preview?kind=route|vergleich
// Alarm-Koerper geht unveraendert durch; Zeitlimit 30 s wie die Alt-Route
// POST /api/trips/{id}/alert-preview.
func BriefingAlertPreviewHandler(pythonURL string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		target, _, ok := briefingPreviewTarget(w, r, pythonURL, "alert-preview")
		if !ok {
			return
		}
		forwardPreview(w, r, http.MethodPost, target, previewProxyTimeout)
	}
}
