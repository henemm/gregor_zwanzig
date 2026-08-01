// Reine Auswahl-/Reihenfolge-Funktionen des Ortsvergleich-Stundenverlaufs.
// Issue #1106, umgestellt mit Issue #1406 Scheibe B.
// Spec: docs/specs/modules/feat_1406b_stundenverlauf_katalog.md
//
// WAS HIER NICHT MEHR STEHT (#1406 B): die frühere Zehnerliste
// `ALL_HOURLY_METRICS` und die Vorgabemenge `DEFAULT_HOURLY_METRIC_KEYS`. Der
// Vorrat der wählbaren Größen, ihre Namen, die Vorgabemenge und die Merge-only-
// Eigenschaft kommen jetzt aus derselben Katalogantwort wie bei Übersicht und
// Ausblick (GET /api/compare/metrics, Felder `hourlyDefault`/`hourlyMergeOnly`/
// `hourlySelectable`/`hourly_legacy_keys`). Die einzige Zuordnung
// Stundenverlaufs-Schlüssel → Wettergröße lebt in
// src/output/renderers/compare_hourly_metric_ids.py — hier keine zweite
// (Ratsche: compare_hourly_vocabulary_single_source.test.ts).
//
// Was bleibt: die reine Umschalt-/Materialisierungs-/Reihenfolge-Mechanik. Sie
// ist Zustandslogik, kein Vokabular, und wird von Hub UND Anlege-Seite über
// CompareHourlyLayoutControls.svelte geteilt.

/**
 * Reine Toggle-Funktion für die Stundenverlauf-Metrikauswahl. Arbeitet direkt
 * auf der uebergebenen (ggf. leeren) Liste -- eine leere Auswahl ist seit
 * Issue #1366 (AC-8) eine bewusste Nutzerwahl und wird NICHT mehr durch die
 * volle Default-Menge ersetzt, bevor der Toggle greift (sonst erzeugt ein
 * Klick aus "nichts" "Vorgabe minus eins" statt "genau die eine Spalte").
 *
 * `aliases` (#1406 B): die historischen Kurzschlüssel derselben Größe. Beim
 * Abwählen müssen sie mit verschwinden — sonst bliebe ein gespeichertes
 * `temp_c` stehen, während der Editor die Zeile als abgewählt zeigt, und die
 * Mail zeigte die Spalte weiter.
 */
export function applyHourlyMetricToggle(
	currentKeys: string[],
	key: string,
	checked: boolean,
	aliases: string[] = []
): string[] {
	const entfernen = new Set([key, ...aliases]);
	if (!checked) return currentKeys.filter((k) => !entfernen.has(k));
	if (currentKeys.some((k) => entfernen.has(k))) return [...currentKeys];
	return [...currentKeys, key];
}

/**
 * Issue #1366 Adversary-Fund F001: EINZIGE Materialisierungs-Stelle fuer
 * "nie eingestellt" (`null`) -> Vorgabemenge. Eine bewusst geleerte Auswahl
 * (`[]`) bleibt unveraendert leer -- nur `null` loest die Vorgabemenge aus.
 * Anzeige (isHourlyMetricActive) UND Umschalt-Handler muessen ZWINGEND dieselbe
 * Funktion nutzen -- vorher wichen beide Stellen in
 * CompareHourlyLayoutControls.svelte voneinander ab (Anzeige materialisierte,
 * der Handler arbeitete auf der rohen Liste), was aus "eine von neun Spalten
 * abwaehlen" faelschlich eine komplette Leerauswahl machte.
 *
 * `defaultKeys` (#1406 B): die Vorgabemenge kommt jetzt vom Server
 * (`hourlyDefault` je Katalogzeile) statt aus einer Frontend-Liste — so haben
 * Renderer und Bedienfläche nachweisbar dieselbe Vorgabe.
 */
export function materializeHourlyMetricKeys(
	keys: string[] | null,
	defaultKeys: string[] = []
): string[] {
	return keys === null ? defaultKeys : keys;
}

/**
 * Issue #1366 F001: der Umschalt-Handler-Pfad, wie ihn
 * CompareHourlyLayoutControls.svelte tatsaechlich aufruft -- materialisiert
 * zuerst (analog Anzeige), toggelt danach auf der materialisierten Liste.
 * Ohne diesen Umweg erzeugte ein Klick aus "nie eingestellt" (Anzeige zeigt
 * alle neun an) die leere Liste statt "8 von 9".
 */
export function applyHourlyMetricToggleFromState(
	currentKeys: string[] | null,
	key: string,
	checked: boolean,
	defaultKeys: string[] = [],
	aliases: string[] = []
): string[] {
	return applyHourlyMetricToggle(
		materializeHourlyMetricKeys(currentKeys, defaultKeys),
		key,
		checked,
		aliases
	);
}

/**
 * Issue #1361 Befund 4/5: filtert reine Merge-Signale (Windrichtung) aus einer
 * Liste aktiver Stundenverlauf-Keys heraus. Merge-Signale erzeugen NIE eine
 * eigene Mail-Spalte (`_should_merge_wind_dir` prueft nur Mitgliedschaft,
 * nicht Position) -- eine Listenposition in der Reihenfolge-Ansicht waere fuer
 * sie also eine Falschaussage. Sie bleiben in der An/Aus-Auswahl unveraendert
 * sichtbar (keine Regression).
 *
 * `mergeOnlyKeys` (#1406 B): welche Größen Merge-Signale sind, sagt die
 * Katalogantwort (`hourlyMergeOnly`) — inklusive ihrer historischen
 * Kurzschlüssel, damit auch Altbestand richtig gefiltert wird.
 */
export function orderableHourlyMetricKeys(
	keys: string[],
	mergeOnlyKeys: string[] = []
): string[] {
	const mergeOnly = new Set(mergeOnlyKeys);
	return keys.filter((k) => !mergeOnly.has(k));
}

/**
 * Issue #1361 Befund 4: baut die neue vollstaendige `hourlyMetricKeys`-Liste
 * nach einer Ziehgeste in der Reihenfolge-Ansicht. `newOrder` ist die neue
 * Reihenfolge der SORTIERBAREN Teilmenge -- Merge-only Keys (falls aktiv)
 * werden unveraendert uebernommen und ans Ende gestellt, da ihre Position fuer
 * den Renderer wirkungslos ist.
 */
export function applyHourlyReorder(
	materializedKeys: string[],
	newOrder: string[],
	mergeOnlyKeys: string[] = []
): string[] {
	const orderable = new Set(orderableHourlyMetricKeys(materializedKeys, mergeOnlyKeys));
	const mergeOnlyActive = materializedKeys.filter((k) => !orderable.has(k));
	return [...newOrder, ...mergeOnlyActive];
}
