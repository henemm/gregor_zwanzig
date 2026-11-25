package handler

// Issue #2988 S2 (Spec rework_2988_ampel_ableitung): POST /api/ampel/aufloesung.
// Vorlage + Abweichungen -> vollstaendige Ampel rechnet allein der Python-Kern
// (app.ampel.resolve_entwurf); Go prueft Anmeldung, Groesse und Form.

import (
	"bytes"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"unicode/utf8"

	"github.com/henemm/gregor-api/internal/middleware"
)

// Grenzen des Endpunkts; die Zahl der Eintraege prueft der Kern ebenso.
const (
	ampelAufloesungMaxBytes     = 256 << 10
	ampelAufloesungMaxEintraege = 32
)

// ampelEintragOk: JSON-Objekt, preset_name/profil Text oder null, metrics Liste
// oder null. Map statt Struct: Schluesselnamen gelten exakt, wie im Kern. Der
// Inhalt von ampel ist kein Formfehler.
func ampelEintragOk(raw json.RawMessage) bool {
	var eintrag map[string]json.RawMessage
	if json.Unmarshal(raw, &eintrag) != nil || eintrag == nil {
		return false
	}
	for _, k := range []string{"preset_name", "profil"} {
		var text *string
		if v, da := eintrag[k]; da && json.Unmarshal(v, &text) != nil {
			return false
		}
	}
	var liste []json.RawMessage
	v, da := eintrag["metrics"]
	return !da || json.Unmarshal(v, &liste) == nil
}

// ampelAufloesungRumpfOk: JSON-Objekt mit hoechstens 32 gueltigen eintraege.
// utf8.Valid, weil json.Unmarshal Fehlbytes still ersetzt, der Kern nicht.
func ampelAufloesungRumpfOk(body []byte) bool {
	var rumpf map[string]json.RawMessage
	var eintraege []json.RawMessage
	if !utf8.Valid(body) || json.Unmarshal(body, &rumpf) != nil ||
		json.Unmarshal(rumpf["eintraege"], &eintraege) != nil || eintraege == nil ||
		len(eintraege) > ampelAufloesungMaxEintraege {
		return false
	}
	for _, e := range eintraege {
		if !ampelEintragOk(e) {
			return false
		}
	}
	return true
}

// AmpelAufloesungHandler reicht den unveraenderten Rumpf mit der user_id der
// Anmeldung an den Kern. Kein Store-Zugriff, kein ETag, nichts wird geschrieben.
func AmpelAufloesungHandler(pythonURL string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if middleware.UserIDFromContext(r.Context()) == "" {
			WriteError(w, r, http.StatusUnauthorized, "unauthorized", nil)
			return
		}
		body, err := io.ReadAll(http.MaxBytesReader(w, r.Body, ampelAufloesungMaxBytes))
		var tooLarge *http.MaxBytesError
		if errors.As(err, &tooLarge) {
			WriteError(w, r, http.StatusRequestEntityTooLarge, "payload_too_large", nil)
			return
		}
		if bailIf(w, r, err != nil || !ampelAufloesungRumpfOk(body), http.StatusBadRequest, "bad_request") {
			return
		}
		r.Body = io.NopCloser(bytes.NewReader(body))
		r.URL.RawQuery = "" // user_id setzt forwardPreview aus der Anmeldung
		forwardPreview(w, r, http.MethodPost, pythonURL+"/api/ampel/aufloesung", previewProxyTimeout)
	}
}
