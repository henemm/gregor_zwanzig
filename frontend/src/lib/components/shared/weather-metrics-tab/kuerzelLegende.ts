// Issue #1888 (Etappe E6, Scheibe B): Ableitung der Kuerzel-Legende im Reiter
// „Wetter-Metriken" — EIN Datenfluss fuer Trip UND Ortsvergleich.
// Spec: docs/specs/modules/fix_1888_e6b_kuerzel_legende.md (AC-1..AC-4)
//
// Warum ein eigenes Modul und nicht nur ein Snippet: AC-1/AC-2/AC-2a sind
// Aussagen ueber MENGEN und TEXTE („kein Kuerzel ohne Bedeutung", „`D` genau
// zweimal"). An der .svelte-Datei sind sie in der Kern-Schicht nicht messbar —
// WeatherMetricsTab holt seine Kataloge in $effect/onMount, und SSR fuehrt
// beides nie aus (ein SSR-Test waere strukturell immer gruen, #1717). Die
// Legende SELBST bleibt ein Snippet in WeatherMetricsTab.svelte (AC-5).
//
// Hier steht bewusst KEIN Kuerzel und KEINE Bedeutung: die Funktion verknuepft
// nur die beiden Katalog-Objekte, die der Aufrufer ohnehin an den
// Reihenfolge-Block reicht. Eine eigene Zuordnung waere die zweite Liste im
// Frontend, die AC-3 (und der Waechter officialAlertLegend.test.ts:395-415)
// verbietet.

/** Eine Legenden-Zeile: das Kuerzel, wie die Marke daneben es zeigt, und sein
 *  Klartext. Das Kuerzel bleibt roh — im Ortsvergleich also `D`, nicht `D+`;
 *  das Auswertungszeichen haengt erst die zugestellte SMS an
 *  (src/output/renderers/comparison.py:647-650, Messung M2b). Eindeutig wird
 *  die Zeile durch die mitgezeigte Auswertung, nicht durch ein Vorzeichen. */
export interface KuerzelLegendeEintrag {
	kuerzel: string;
	bedeutung: string;
}

/** Bedeutungs-Seite: `label` immer, `aggregation_label` nur im Ortsvergleich
 *  (GET /api/metrics liefert es nicht, GET /api/compare/metrics schon). */
interface BedeutungsQuelle {
	label?: string;
	aggregation_label?: string;
}

/** Ergebnis der Ableitung. `unaufloesbar` ist der LAUTE Ausgang fuer den Fall,
 *  den frueher ein stummes `continue` verschluckt hat: eine gerenderte Groesse
 *  traegt ein Kuerzel, aber keine aufloesbare Bedeutung.
 *
 *  Warum kein `throw`: AC-4 verlangt fail-soft — ein Ladefehler darf den Reiter
 *  nicht unbedienbar machen. Warum trotzdem nicht stumm: eine Luecke, die
 *  niemand sehen kann, faellt auch keinem Test auf (genau so ist der
 *  Staging-Befund entstanden). Der Fall verlaesst die Funktion deshalb als
 *  eigenes Feld, das die Tests bewachen — und die Zeile bekommt trotzdem
 *  KEINEN erfundenen Erklaertext (AC-1). */
export interface KuerzelLegende {
	eintraege: KuerzelLegendeEintrag[];
	unaufloesbar: string[];
}

/**
 * Verknuepft die im Reihenfolge-Block gerenderten Groessen mit Kuerzel- und
 * Bedeutungs-Katalog zu den Zeilen der Legende.
 *
 * Massgeblich ist `gerenderteIds` — die Liste, die der Block tatsaechlich
 * zeigt (aktive Zeilen UND die Aus-Gruppe), NICHT der volle Backend-Katalog:
 *
 *   * Adversary F001: von 29 Katalog-Groessen stehen in einer frischen Tour
 *     nur 9 im Block. Eine Legende aus dem vollen Katalog erklaerte 20
 *     Zeichen, die nirgends auf dem Schirm stehen — Rauschen in einem
 *     Werkzeug, das unter Zeitdruck gelesen wird.
 *   * Messung M1: `cape` traegt das Kuerzel `CP`, ist aber `selectable=False`
 *     und im Reiter nirgends eine Marke. Aus dem rohen Kuerzel-Katalog
 *     gespeist entstuende dort ein Kuerzel ohne jede Bedeutung.
 *
 * Es wird NICHT nach Kuerzel entdoppelt: im Ortsvergleich steht `D` auf zwei
 * Katalogzeilen (Temperatur Maximum/Minimum) und die Marken zeigen es an
 * beiden — eine Entdopplung braeche die Zusicherung „dieselbe Quelle wie die
 * Marken" (AC-2a/AC-3).
 *
 * Fail-soft (AC-4): fehlt eine der drei Seiten, entstehen gar keine Zeilen —
 * lieber keine Legende als eine mit leeren Feldern.
 *
 * KEIN stummes Ueberspringen: traegt eine gerenderte Groesse ein Kuerzel, laesst
 * sich ihre Bedeutung aber nicht aufloesen, landet ihre Id in `unaufloesbar`.
 * Frueher verschwand genau dieser Fall spurlos (`if (!label) continue`) — eine
 * Luecke, die niemand sehen kann, faellt auch keinem Test auf.
 *
 * @param gerenderteIds Die Groessen des Blocks, in seiner Reihenfolge
 *                      (`primaryColumns` + `offColumns` der Marken-Komponente)
 * @param kuerzelById   Kuerzel je Groesse — DIESELBE Prop, die die Marken speist
 * @param metricById    Bedeutung je Groesse — DIESELBE Prop, die die Zeilen beschriftet
 */
export function buildKuerzelLegende(
	gerenderteIds: string[] | null | undefined,
	kuerzelById: Record<string, string[]> | null | undefined,
	metricById: Record<string, BedeutungsQuelle> | null | undefined
): KuerzelLegende {
	const eintraege: KuerzelLegendeEintrag[] = [];
	const unaufloesbar: string[] = [];
	const gesehen = new Set<string>();
	for (const id of gerenderteIds ?? []) {
		if (typeof id !== 'string' || gesehen.has(id)) continue;
		gesehen.add(id);
		const kuerzel = (kuerzelById?.[id] ?? []).filter((k) => !!k);
		const quelle = metricById?.[id];
		const label = (quelle?.label ?? '').trim();
		if (!label) {
			// Ohne Bedeutung kein Eintrag — aber auch kein stilles Verschwinden.
			// Traegt die Groesse ein Kuerzel, ist das eine echte Luecke: die
			// Marken-Komponente zeigt dann eine Marke, die niemand aufloesen kann.
			if (kuerzel.length > 0) unaufloesbar.push(id);
			continue;
		}
		const auswertung = (quelle?.aggregation_label ?? '').trim();
		const bedeutung = auswertung ? `${label} (${auswertung})` : label;
		for (const k of kuerzel) eintraege.push({ kuerzel: k, bedeutung });
	}
	return { eintraege, unaufloesbar };
}
