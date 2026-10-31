package i18n

// errorPrefixes ist die Suchkette fuer Fehlercodes (Konventionen Abschnitt 5).
// Ein Code steht in hoechstens einem dieser Bereiche (Parity).
var errorPrefixes = []string{"fehler.", "auth.fehler.", "konto.fehler.", "fach.fehler."}

// ErrorBody baut das Fehlerobjekt {code, message, error, detail}.
// message: erster Treffer im de-Katalog fuer <praefix><code>_<variante>, dann
// <praefix><code>; sonst fehler.unbekannt mit {code}. error ist ein
// Uebergangsfeld (= code), detail ist args["detail"] oder message.
func (c *Catalog) ErrorBody(lang Lang, code string, args Args) map[string]any {
	msg := c.errorMessage(lang, code, args)
	detail := msg
	if d, ok := args["detail"].(string); ok && d != "" {
		detail = d
	}
	return map[string]any{"code": code, "message": msg, "error": code, "detail": detail}
}

func (c *Catalog) errorMessage(lang Lang, code string, args Args) string {
	var candidates []string
	if v, ok := args["variante"].(string); ok && v != "" {
		for _, p := range errorPrefixes {
			candidates = append(candidates, p+code+"_"+v)
		}
	}
	for _, p := range errorPrefixes {
		candidates = append(candidates, p+code)
	}
	for _, key := range candidates {
		if c.Has(key) {
			return c.T(lang, key, args)
		}
	}
	return c.T(lang, "fehler.unbekannt", Args{"code": code})
}
