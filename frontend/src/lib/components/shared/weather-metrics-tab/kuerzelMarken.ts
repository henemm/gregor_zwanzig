// Issue #2232: EINE Herleitung der Kurzform-Marke für ALLE Editor-Flächen.
//
// Bis #2232 speiste der Trip-Editor seine Marke aus `/api/sms-symbols`, die
// drei Vergleichs-Editoren dagegen aus `sms_code` der Katalogantwort. Ergebnis:
// dieselbe Wettergröße trug je Fläche eine andere Marke (`D` gegen `D+`), und
// die zugestellte Vergleichs-SMS wich von beiden ab. Ab dieser Scheibe lesen
// beide Flächen denselben Endpoint; unterschiedlich ist nur noch die KENNUNG,
// unter der nachgeschlagen wird — und die liefert das Backend mit
// (`kuerzel_metric_id`, sonst `metric_id`).
//
// 🔴 Bewusst KEINE Fallback-Regel im Browser: welche Kennung die Marke trägt,
// entscheidet allein `compare_metric_catalog.kuerzel_metric_id_for()`. Der
// Browser schlägt nur nach. Eine zweite Regel hier wäre die zweite
// Kürzel-Quelle, die diese Scheibe gerade beseitigt.

/** Ein Katalog-Eintrag, soweit für die Marke nötig. */
interface MarkenEintrag {
	/** Kennung, unter der die Marke in `/api/sms-symbols` steht. */
	kuerzel_metric_id?: string;
	metric_id?: string;
}

/**
 * Die Kennung, unter der DIESER Eintrag seine Kurzform-Marke führt.
 * Spiegelt `compare_metric_catalog.kuerzel_metric_id_for()` — das Backend
 * liefert `kuerzel_metric_id` bereits aufgelöst mit, der Rückfall greift nur
 * für ältere Antworten ohne das Feld.
 */
export function markenKennung(eintrag: MarkenEintrag, fallback = ''): string {
	return eintrag.kuerzel_metric_id ?? eintrag.metric_id ?? fallback;
}

/**
 * Anzeige-Schlüssel -> Kurzform-Marken, nachgeschlagen in den Symbolen aus
 * `/api/sms-symbols` (`metricSymbols`: Kennung -> Kürzel-Liste).
 *
 * `zuordnung` nennt je Anzeige-Schlüssel die Kennung, unter der nachzuschlagen
 * ist. Größen ohne Eintrag im Endpoint bekommen KEINE Marke (statt einer
 * leeren) — eine leere Marke wäre ein Bedienelement ohne Aussage.
 */
export function kuerzelMarken(
	zuordnung: Iterable<readonly [string, string]>,
	metricSymbols: Record<string, string[]>
): Record<string, string[]> {
	const marken: Record<string, string[]> = {};
	for (const [schluessel, kennung] of zuordnung) {
		const kuerzel = metricSymbols[kennung];
		if (kuerzel?.length) marken[schluessel] = kuerzel;
	}
	return marken;
}
