// mergeReportConfig — Issue #1738 Fix-Loop 1 (Findings F001/F002).
//
// EIN Ort fuer die Read-Modify-Write-Regel des `report_config`-Blobs. Beide
// Schreiber rufen ihn auf: VersandTab.svelte (Kanaele + Zeitplan) und
// EditReportConfigSection.svelte (Mail-Inhalt, dort je nach Props zusaetzlich
// Kanaele/Zeitplan).
//
// Warum ueberhaupt eine eigene Datei: seit /trips/new beide Komponenten
// DAUERHAFT NEBENEINANDER auf dasselbe `bind:reportConfig` mountet
// (TripNewEditor.svelte, Zeitplan-Tab), schreiben zwei $effect-Laeufe
// abwechselnd in denselben Blob. Jeder Lauf, der seine Basis aus einem
// veralteten onMount-Schnappschuss nimmt und das Ergebnis komplett zuweist,
// loescht still alles, was der Nachbar seither gesetzt hat — genau der
// Replace-statt-Merge-Fehler, den CLAUDE.md (Daten-Schema-Reworks,
// BUG-DATALOSS-GR221) verbietet.
//
// Der zweite Grund ist Pruefbarkeit: `$effect` und `onMount` laufen unter
// `svelte/server`s `render()` NIE (im Repo dokumentiert in
// shared/__tests__/weather_metrics_tab_create_mode_callback.test.ts:5), und ein
// DOM-Harness gibt es im Frontend-Test-Setup nicht. Solange die Merge-Regel im
// Effect-Rumpf steht, ist sie nur dort geprueft, wo der Code steht, nicht dort,
// wo er wirkt (Finding F002). Als reine Funktion ist sie ohne Harness direkt
// messbar — inklusive der Reihenfolge zweier aufeinanderfolgende Laeufe.
//
// Pure Funktion, kein Netz-/DOM-Zugriff — node:testbar.

export interface ReportConfigMergeInput {
	/** onMount-Schnappschuss des Blobs. Nur Rueckfall fuer den ersten Lauf,
	 *  bevor `onMount` gelaufen ist — NIE alleinige Basis (siehe Modulkopf). */
	snapshot?: Record<string, unknown> | null;
	/** Der LEBENDE Blob des Parents, im Aufrufer per `untrack` gelesen (kein
	 *  Selbst-Trigger). Absichtlich ein Pflichtfeld der Schnittstelle: laesst ein
	 *  spaeterer Umbau ihn weg, ist das ein Typfehler und kein stiller
	 *  Datenverlust. */
	live: Record<string, unknown> | null | undefined;
	/** Felder, die diese Instanz immer besitzt. */
	own?: Record<string, unknown> | null;
	/** Zeitplan-Felder — nur uebernommen, wenn `showSchedule`. */
	schedule?: Record<string, unknown> | null;
	/** Kanal-Felder — nur uebernommen, wenn `showChannels`. */
	channels?: Record<string, unknown> | null;
	/** Zeigt diese Instanz die Zeitplan-Bedienelemente? Sonst gehoeren die
	 *  Felder dem Nachbarn und duerfen hier nicht geschrieben werden. */
	showSchedule?: boolean;
	/** Zeigt diese Instanz die Kanal-Bedienelemente? Sonst siehe oben. */
	showChannels?: boolean;
}

/**
 * Baut den neuen `report_config`-Blob nach Read-Modify-Write.
 *
 * Reihenfolge (spaeter gewinnt): Schnappschuss -> lebender Blob -> eigene
 * Felder -> Zeitplan-Gruppe (nur mit `showSchedule`) -> Kanal-Gruppe (nur mit
 * `showChannels`). Unbekannte Bestandsfelder (`change_threshold_*`) reisen
 * durch beide Spreads mit und bleiben damit erhalten.
 */
export function mergeReportConfig(input: ReportConfigMergeInput): Record<string, unknown> {
	const merged: Record<string, unknown> = {
		...(input.snapshot ?? {}),
		...(input.live ?? {}),
		...(input.own ?? {})
	};
	if (input.showSchedule) Object.assign(merged, input.schedule ?? {});
	if (input.showChannels) Object.assign(merged, input.channels ?? {});
	return merged;
}
