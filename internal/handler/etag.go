package handler

import (
	"encoding/json"
	"net/http"
	"strings"
)

// Nebenlaeufigkeitsschutz fuer die Briefing-Schreibpfade (Issue #1395 Scheibe S2).
//
// Zwei gleichzeitige Speichervorgaenge auf dieselbe Tour ueberschreiben sich
// heute gegenseitig: es gewinnt der, der ZULETZT ANKOMMT — nicht der, der
// zuletzt abgeschickt wurde. Die Bausteine dafuer liegen seit S1 im store-Paket
// (BriefingFingerprint = Inhalts-Stempel der Datei, LockBriefing = Sperre je
// Nutzer+Briefing). Hier werden sie als HTTP-Vertrag sichtbar:
//
//   - GET liefert den aktuellen Stand als ETag-Header
//   - PUT prueft optional If-Match und lehnt einen veralteten Schreibvorgang
//     mit 412 ab, statt ihn kommentarlos anzunehmen
//
// Bewusst NICHT scharf geschaltet: ohne If-Match-Header verhaelt sich jeder
// Aufruf exakt wie bisher. Das Erzwingen kommt erst mit dem Frontend (S3).

// preconditionFailedDetail ist der nutzerlesbare Text der 412-Antwort. Er sagt,
// was passiert ist UND was der Nutzer tun kann — eine reine Statuszahl waere
// im Frontend nicht uebersetzbar.
const preconditionFailedDetail = "Der Stand wurde zwischenzeitlich an anderer Stelle geaendert. " +
	"Bitte neu laden und die Aenderung erneut vornehmen."

// ifMatchAllows prueft den If-Match-Header gegen den aktuellen Fingerabdruck.
//
// Rueckgabe true bedeutet "Schreibvorgang darf weiterlaufen":
//   - fehlender oder leerer Header -> angenommen (Rollout-Politik: Bestands-
//     Clients ohne ETag-Kenntnis duerfen nicht ausgesperrt werden; r.Header.Get
//     unterscheidet "fehlt" und "leer" ohnehin nicht)
//   - "*" -> angenommen, sofern die Ressource existiert; das prueft der
//     Aufrufer VOR diesem Aufruf (LoadTrip != nil)
//   - sonst: RFC-7232-Liste, ein Treffer genuegt. Anfuehrungszeichen werden
//     abgestreift, damit ein Client, der sie weglaesst, nicht faelschlich
//     scheitert.
//
// Issue #2317 Fix-Loop 1 (AC-11): ein vorangestelltes `W/` (schwacher
// Validator) wird VOR dem Anfuehrungszeichen-Trim entfernt. Ein gzip-faehiger
// Proxy vor dem Server schwaecht den selbst erzeugten starken Fingerabdruck
// beim Komprimieren automatisch ab (RFC 7232 §2.1) — jeder echte Client
// (Browser, SvelteKit-SSR-`fetch`) bekommt also `ETag: W/"<fp>"` und reicht
// genau das, wie vom Standard verlangt, unveraendert als `If-Match` zurueck.
// Ohne dieses Abstreifen blieb ein passender Fingerabdruck durch den `W/`-
// Rest ununterscheidbar von einem veralteten — jeder zweite Schreibvorgang
// hinter einem gzip-Proxy scheiterte an einem FALSCHEN 412 (gemessen gegen
// Staging: `Accept-Encoding: identity` -> `"<fp>"`, `gzip` -> `W/"<fp>"`).
func ifMatchAllows(header, current string) bool {
	header = strings.TrimSpace(header)
	if header == "" || header == "*" {
		return true
	}
	for _, part := range strings.Split(header, ",") {
		part = strings.TrimSpace(part)
		part = strings.TrimPrefix(part, "W/")
		if strings.Trim(part, `"`) == current {
			return true
		}
	}
	return false
}

// setETagHeader setzt den ETag-Header in RFC-7232-Form ("<hex>").
//
// Fail-soft: ist der Fingerabdruck nicht lesbar (err != nil) oder leer (Datei
// existiert nicht), bleibt der Header schlicht weg. Ein geglueckter Schreib-
// oder Lesevorgang darf nicht nachtraeglich am Stempel scheitern — der Client
// faehrt dann ohne Vorbedingung weiter, also genau wie vor dieser Scheibe.
func setETagHeader(w http.ResponseWriter, fingerprint string, err error) {
	if err != nil || fingerprint == "" {
		return
	}
	w.Header().Set("ETag", `"`+fingerprint+`"`)
}

// writePreconditionFailed beantwortet einen abgelehnten Schreibvorgang mit 412.
// Die Antwort traegt bewusst KEINEN ETag: der Client soll neu laden und dabei
// den Stempel zusammen mit dem Inhalt holen, statt blind mit einem Stempel
// weiterzuschreiben, dessen Inhalt er nie gesehen hat.
func writePreconditionFailed(w http.ResponseWriter, detail string) {
	w.Header().Del("ETag")
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusPreconditionFailed)
	json.NewEncoder(w).Encode(map[string]string{
		"error":  "precondition_failed",
		"detail": detail,
	})
}
