// channelMetricLayouts.ts — Issue #1575 Scheibe 3: kanal-eigene Metrik-Auswahl
// im Trip-Editor (context="route").
//
// Spec: docs/specs/modules/fix_1575_channel_metric_selection.md (Teil 2)

import type { ChannelLayouts, WeatherConfigMetric } from '$lib/types';
import type { ChannelId } from '$lib/components/shared/layout-tab/ltChannels';
import { deriveMissingChildMetrics, moveWithDerivedChildren, type Buckets } from '$lib/components/trip-detail/metricsEditor';

export interface ChannelOverride {
	buckets: Buckets;
	friendlyMap: Record<string, boolean>;
}

/**
 * Setzt den Kanal-Eintrag von `channel` auf `metrics` und laesst alle anderen
 * Kanaele unberuehrt.
 *
 * `internal/handler/config_merge.go` mergt `display_config` nur shallow auf
 * oberster Schluesselebene — wer beim Speichern nur den aktiven Kanal sendet,
 * loescht die uebrigen lautlos (BUG-DATALOSS-GR221-Muster). `metrics === null`
 * bedeutet: dieser Kanal wurde nie editiert und bekommt keinen eigenen
 * Eintrag, damit die Backend-Kaskade weiter auf die globale Auswahl faellt.
 */
export function mergeChannelLayoutsForSave(
	prevLayouts: ChannelLayouts | undefined,
	channel: ChannelId,
	metrics: WeatherConfigMetric[] | null
): ChannelLayouts {
	const next: ChannelLayouts = { ...(prevLayouts ?? {}) };
	if (metrics === null) return next;
	next[channel] = metrics;
	return next;
}

/**
 * Baut den Kanal-Eintrag aus einer gespeicherten `channel_layouts[kanal]`-Liste
 * zurueck, damit ein editierter Reiter nach dem Reload seine eigene Auswahl
 * zeigt (AC-4/AC-5). Der Trip-Editor kennt kein Detail-Bucket (#587) — alles
 * Aktive landet in `primary`.
 */
export function channelOverrideFromMetrics(
	metrics: WeatherConfigMetric[],
	catalogIds: string[],
	fallbackFriendly: Record<string, boolean>
): ChannelOverride {
	// Bug #2454 Abschnitt 1: fehlende Kind-Eintraege VOR dem Bucket-Aufbau
	// ableiten — Elter-Referenz ist der Elter-Eintrag in DIESER Kanal-Liste,
	// nicht die globale (mirrort loader.py::_append_derived_metrics je Kanal).
	const derived = deriveMissingChildMetrics(metrics);
	const active = derived
		.filter((m) => m.enabled)
		.slice()
		.sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
	const activeIds = new Set(active.map((m) => m.metric_id));
	const friendlyMap = { ...fallbackFriendly };
	for (const m of derived) {
		if (m.use_friendly_format !== undefined) friendlyMap[m.metric_id] = m.use_friendly_format;
	}
	return {
		buckets: {
			primary: active.map((m) => m.metric_id),
			secondary: [],
			off: catalogIds.filter((id) => !activeIds.has(id))
		},
		friendlyMap
	};
}

/** Startpunkt eines Kanal-Eintrags: tiefe Kopie der globalen Auswahl (AC-2). */
export function startChannelOverride(
	buckets: Buckets,
	friendlyMap: Record<string, boolean>
): ChannelOverride {
	return {
		buckets: {
			primary: [...buckets.primary],
			secondary: [...buckets.secondary],
			off: [...buckets.off]
		},
		friendlyMap: { ...friendlyMap }
	};
}

/**
 * Bug #2454 Fix-Loop 1 (Finding F001, Abschnitt 2/AC-2): globales Ein-/
 * Ausschalten von `id` (`temperature`/`wind_chill` nehmen ihre mitgelaufenen
 * Kinder mit — fuer alle anderen IDs ist `moveWithDerivedChildren` deckungs-
 * gleich mit einem einfachen Verschieben, da ihr Kind-Set leer ist) UND, bei
 * einer Abwahl (`wasOn=true`), der bestehenden Durchschreibung in alle Kanal-
 * Overrides, die `id` aktiv fuehren (Issue #1719 S3 / ADR-0050 Regel 3) — die
 * Kind-Mitnahme greift dort identisch, sonst blieben Kind-Zeilen im Kanal-
 * Override aktiv stehen, waehrend der Elter global gerade abgewaehlt wurde.
 * #3047 T3 (AC-10, Konzept einstellungen_neu.md §5 Punkt 6/8): bei einer
 * EINWAHL (`wasOn=false`) landen `id` und seine mitgenommenen Kinder in JEDER
 * bereits bearbeiteten Kanal-Liste hinten, eingeschaltet; die bestehende Folge
 * und kanal-lokale Abwahlen anderer Metriken bleiben. Nie bearbeitete Kanaele
 * (`null`) folgen ohnehin der Grundauswahl und bekommen keinen Eintrag.
 * DIESELBE Funktion wird von `WeatherMetricsTab.svelte::onToggleMetric()` UND
 * vom Test-Nachbau aufgerufen (kein zweiter Nachbau der Verdrahtung, F001).
 * Referenz-Identitaet: `from === to` (No-Op) liefert exakt `buckets`/
 * `channelBuckets` unveraendert zurueck (Aufrufer erkennt No-Op daran).
 */
export function toggleGlobalMetric(
	buckets: Buckets,
	channelBuckets: Record<ChannelId, ChannelOverride | null>,
	id: string,
	wasOn: boolean
): { buckets: Buckets; channelBuckets: Record<ChannelId, ChannelOverride | null> } {
	const from: keyof Buckets = buckets.primary.includes(id) ? 'primary' : 'off';
	const to: keyof Buckets = wasOn ? 'off' : 'primary';
	if (from === to) return { buckets, channelBuckets };

	const newBuckets = moveWithDerivedChildren(buckets, id, from, to);
	if (!wasOn) return { buckets: newBuckets, channelBuckets: appendToChannelOverrides(buckets, newBuckets, channelBuckets) };

	const newChannelBuckets = { ...channelBuckets };
	// ADR-0049: nur Metrik-/Layout-Kanäle — Premium-SMS hat keine eigene Auswahl, sie sendet den SMS-Text
	for (const ch of ['email', 'telegram', 'sms'] as ChannelId[]) {
		const override = newChannelBuckets[ch];
		if (override === null || !override.buckets.primary.includes(id)) continue;
		newChannelBuckets[ch] = {
			buckets: moveWithDerivedChildren(override.buckets, id, 'primary', 'off'),
			friendlyMap: override.friendlyMap
		};
	}
	return { buckets: newBuckets, channelBuckets: newChannelBuckets };
}

/** #3047 T3: die durch eine Einwahl neu in die Grundauswahl gekommenen IDs
 *  (Elter samt Kindern, in ihrer Folge) hinten an jede bearbeitete Kanal-Liste. */
function appendToChannelOverrides(
	before: Buckets,
	after: Buckets,
	channelBuckets: Record<ChannelId, ChannelOverride | null>
): Record<ChannelId, ChannelOverride | null> {
	const neu = after.primary.filter((m) => !before.primary.includes(m));
	if (neu.length === 0) return channelBuckets;
	const next = { ...channelBuckets };
	// ADR-0049: nur Metrik-/Layout-Kanäle — Premium-SMS hat keine eigene Auswahl, sie sendet den SMS-Text
	for (const ch of ['email', 'telegram', 'sms'] as ChannelId[]) {
		const override = next[ch];
		if (override === null || override === undefined) continue;
		const fehlend = neu.filter((m) => !override.buckets.primary.includes(m));
		if (fehlend.length === 0) continue;
		next[ch] = {
			buckets: {
				primary: [...override.buckets.primary, ...fehlend],
				secondary: override.buckets.secondary.filter((m) => !fehlend.includes(m)),
				off: override.buckets.off.filter((m) => !fehlend.includes(m))
			},
			friendlyMap: override.friendlyMap
		};
	}
	return next;
}

/**
 * #3047 T3 (AC-10): haengt die durch eine Einwahl neu in die Grundauswahl
 * gekommenen Metriken (`ids`, Trip-Katalog-IDs) hinten an eine GESPEICHERTE
 * Ausblick-Liste (`outlook_metrics`, Kennungen) an. Uebersetzung ID -> Kennung
 * ueber denselben Vergleichs-Katalog wie OutlookLayoutControls.svelte; eine ID
 * ohne Ausblick-Zeile (kein Tageswert, z. B. Kind-Kennungen) faellt heraus.
 * `null` (nie eingestellt) folgt ohnehin der Grundauswahl und bleibt `null`.
 */
export function appendNewMetricsToOutlook(
	outlookKeys: string[] | null,
	ids: readonly string[],
	catalog: ReadonlyArray<{ metric: string; metric_id?: string }>
): string[] | null {
	if (outlookKeys === null) return null;
	const kennungen = new Set(catalog.map((e) => e.metric_id ?? e.metric));
	const next = [...outlookKeys];
	for (const id of ids) {
		const kennung = catalog.find((e) => e.metric === id)?.metric_id ?? id;
		if (kennungen.has(kennung) && !next.includes(kennung)) next.push(kennung);
	}
	return next.length === outlookKeys.length ? outlookKeys : next;
}

/**
 * Issue #1719 Scheibe S3 (AC-8/AC-12, ADR-0050 Regel 1/2): teilt die
 * Kanal-Reihenfolge in "aktiv" (sortierbar) und "aus" (wieder einschaltbar).
 *
 * `active` wird defensiv gegen `globalPrimary` gefiltert — eine Metrik, die
 * global nicht (mehr) aktiv ist, darf über einen stale Kanal-Override nicht
 * als "aktiv" zurückkommen. `off` = `globalPrimary` MINUS `active`
 * (Reihenfolge wie in `globalPrimary`). Eine global abgewählte Metrik
 * erscheint damit in KEINER der beiden Listen — ein Kanal kann sie nicht
 * zurückholen, es gibt für sie gar keinen Kanal-Eintrag.
 */
export function splitChannelMetricsForDisplay(
	globalPrimary: string[],
	channelPrimary: string[]
): { active: string[]; off: string[] } {
	const globalSet = new Set(globalPrimary);
	const active = channelPrimary.filter((id) => globalSet.has(id));
	const activeSet = new Set(active);
	const off = globalPrimary.filter((id) => !activeSet.has(id));
	return { active, off };
}

/**
 * Issue #1719 Scheibe S3 (AC-10, Persistenz-Fix — "der wichtigste Test der
 * Scheibe"): serialisiert JEDEN nicht-`null`-Eintrag aus `channelBuckets`,
 * nicht nur einen ausgezeichneten "aktiven" Kanal. Ohne diesen Fix geht eine
 * Durchschreibung (globale Abwahl -> alle Kanal-Overrides) beim Speichern
 * verloren, sobald der Nutzer nicht im editierten Kanal-Reiter steht
 * (Kontext-Dokument Abschnitt 10.1) — eine neue ADR-0050-Regel-3-Verletzung,
 * eingebaut von der Scheibe, die sie beheben soll.
 *
 * `channelBuckets[ch] === null` (nie editierter Kanal) lässt den Wert aus
 * `prevLayouts` unverändert — der Datenverlust-Schutz aus #1575 bleibt
 * gewahrt (`config_merge.go` ersetzt `channel_layouts` als GANZES, es gehen
 * also MEHR Kanäle mit, nie weniger). Mutiert `prevLayouts` nicht.
 */
export function mergeAllChannelLayoutsForSave(
	prevLayouts: ChannelLayouts | undefined,
	channelBuckets: Record<ChannelId, ChannelOverride | null>,
	buildMetrics: (override: ChannelOverride, channel: ChannelId) => WeatherConfigMetric[]
): ChannelLayouts {
	let next: ChannelLayouts = { ...(prevLayouts ?? {}) };
	// ADR-0049: nur Metrik-/Layout-Kanäle — Premium-SMS hat keine eigene Auswahl, sie sendet den SMS-Text
	for (const ch of ['email', 'telegram', 'sms'] as ChannelId[]) {
		const override = channelBuckets[ch];
		if (override === null) continue;
		next = { ...next, [ch]: buildMetrics(override, ch) };
	}
	return next;
}
