// _editor_kette.ts -- geteilter TS-Kette-Nachbau fuer Issue #2422 S2a.
//
// SPEC: docs/specs/modules/fix_2422_s2a_editor_gleich_gespeichert.md
// ("Drei Beine + E2E", "Vierter Baustein: Aenderungspfad").
//
// Kein Test-Modul (fuehrender Unterstrich -> node:test sammelt es nicht ein,
// Konvention aus tests/tdd/_einstellung_auslieferung_fixtures.py). Bündelt
// den Nachbau von `WeatherMetricsTab.svelte::initFromTrip()` (Laden,
// Zeilen ~452-486) und `buildWeatherPayload()` (Speichern, Zeilen ~930-970)
// UEBER DIE ECHTEN Helfer (`bucketsToColumns`, `channelOverrideFromMetrics`,
// `splitChannelMetricsForDisplay`, `buildWeatherConfigMetrics`,
// `mergeAllChannelLayoutsForSave`) -- DAMIT Anzeige-Test (AC-3), No-Op-
// Speichern-Test (AC-4) und Aenderungspfad-Test (AC-14) sowie der
// Erwartungsdatei-Generator dieselbe Nachbau-Logik teilen, statt sie mehrfach
// leicht abweichend zu duplizieren (Drift-Risiko).
//
// Cast-Pattern (wie in feld_erhalt_ohne_ausnahme.test.ts): `buildWeatherConfigMetrics`
// bekommt einen 5. Parameter `bestand`, `mergeAllChannelLayoutsForSave`s
// `buildMetrics`-Callback einen 2. Parameter `channel` -- BEIDE Signaturen
// existieren heute noch nicht (K8-Fix-Ort fuer /50), deshalb Aufruf per Cast.

import {
	bucketsToColumns,
	buildWeatherConfigMetrics,
	type Buckets,
	type Horizons,
} from '../../../trip-detail/metricsEditor.ts';
import {
	channelOverrideFromMetrics,
	mergeAllChannelLayoutsForSave,
	splitChannelMetricsForDisplay,
	type ChannelOverride,
} from '../channelMetricLayouts.ts';
import type { ChannelId } from '../../layout-tab/ltChannels.ts';

export interface GoldenMetric {
	metric_id: string;
	enabled?: boolean;
	bucket?: string;
	order?: number;
	use_friendly_format?: boolean;
	[key: string]: unknown;
}
export interface GoldenTrip {
	display_config: {
		metrics: GoldenMetric[];
		channel_layouts: Record<string, GoldenMetric[]>;
		[key: string]: unknown;
	};
}

const REITER: ChannelId[] = ['email', 'telegram', 'sms'];

/** Katalog-Form wie `/api/metrics` (kategorie-geschluesselt) -- ECHTE
 * Fidelity-Pflicht: `buildWeatherConfigMetrics` emittiert einen Eintrag pro
 * `allCatalogIds(catalog)`-ID (metricsEditor.ts:366), NICHT nur pro Golden-
 * eigener Metrik -- ein leerer/unvollstaendiger Katalog wuerde die
 * gebaute `metrics`-Liste strukturell verkleinern und jeden Datenvergleich
 * gegen einen echten (29 waehlbare Metriken) Katalog verfaelschen. Reale
 * Snapshot-Quelle: `fixtures/metric_catalog_selectable.json`
 * (aus `app.metric_catalog.get_all_metrics()`, dieselbe Funktion hinter
 * `GET /api/metrics`). */
export type MinimalCatalog = Record<string, Array<{ id: string }>>;

/** Nachbau von metricsEditor.ts::allCatalogIds() (dort nicht exportiert) --
 * flache Liste aller Katalog-IDs in Kategorie-Einfuegereihenfolge. */
export function alleCatalogIds(catalog: MinimalCatalog): string[] {
	const ids: string[] = [];
	for (const gruppe of Object.values(catalog)) {
		for (const m of gruppe) ids.push(m.id);
	}
	return ids;
}

export interface EditorState {
	buckets: Buckets;
	friendlyMap: Record<string, boolean>;
	horizonsMap: Record<string, Horizons>;
	channelBuckets: Record<ChannelId, ChannelOverride | null>;
}

/** Nachbau von initFromTrip() (WeatherMetricsTab.svelte:452-486): globale
 * Bucket-Zerlegung nach ROHEM `enabled` (Editor ist NICHT report-typ-
 * gesplittet -- morning_enabled/evening_enabled wirken erst bei der
 * AUSLIEFERUNG, siehe erwartungsdateien_erzeugen.py-Docstring), #587-
 * Migration (secondary -> primary via bucketsToColumns), sowie je Reiter
 * `channelOverrideFromMetrics`, falls ein eigenes Kanal-Layout existiert. */
export function ladeInEditorState(golden: GoldenTrip, catalog: MinimalCatalog): EditorState {
	const saved = golden.display_config.metrics ?? [];
	const prim = saved
		.filter((m) => m.enabled && m.bucket === 'primary')
		.slice()
		.sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
		.map((m) => m.metric_id);
	const sec = saved
		.filter((m) => m.enabled && m.bucket === 'secondary')
		.slice()
		.sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
		.map((m) => m.metric_id);
	// looseActive: aktive Metriken ohne bucket-Feld (Alt-Bestand) -- wie
	// initFromTrip() haengt WeatherMetricsTab sie ans Ende von secondary an,
	// bevor bucketsToColumns() migriert.
	const looseActive = saved
		.filter((m) => m.enabled && m.bucket !== 'primary' && m.bucket !== 'secondary')
		.map((m) => m.metric_id);
	// off = ALLE Katalog-IDs minus aktive (nicht nur Golden-eigene IDs) --
	// exakt initFromTrip() (WeatherMetricsTab.svelte:463-466).
	const activeIds = new Set([...prim, ...sec, ...looseActive]);
	const off = alleCatalogIds(catalog).filter((id) => !activeIds.has(id));

	const mergedPrimary = bucketsToColumns({ primary: prim, secondary: [...sec, ...looseActive], off });
	const buckets: Buckets = { primary: mergedPrimary, secondary: [], off };

	const friendlyMap: Record<string, boolean> = {};
	const horizonsMap: Record<string, Horizons> = {};
	for (const m of saved) {
		friendlyMap[m.metric_id] = m.use_friendly_format ?? true;
		horizonsMap[m.metric_id] = { today: true, tomorrow: true, day_after: true };
	}

	const channelBuckets = {} as Record<ChannelId, ChannelOverride | null>;
	for (const ch of REITER) {
		const layout = golden.display_config.channel_layouts[ch];
		channelBuckets[ch] = layout
			? channelOverrideFromMetrics(layout as never, alleCatalogIds(catalog), friendlyMap)
			: null;
	}

	return { buckets, friendlyMap, horizonsMap, channelBuckets };
}

/** Displayed Auswahl+Reihenfolge+Roh/Einfach je Reiter -- reiner Datenbau,
 * KEINE Kaskaden-Logik (Memory: Orakel bleibt Python-exklusiv). */
export function berechneAnzeige(
	state: EditorState,
): Record<ChannelId, Array<{ metric_id: string; friendly: boolean }>> {
	const out = {} as Record<ChannelId, Array<{ metric_id: string; friendly: boolean }>>;
	for (const ch of REITER) {
		const override = state.channelBuckets[ch];
		let aktiveReihenfolge: string[];
		let friendlyMap = state.friendlyMap;
		if (override) {
			const { active } = splitChannelMetricsForDisplay(state.buckets.primary, override.buckets.primary);
			aktiveReihenfolge = active;
			friendlyMap = override.friendlyMap;
		} else {
			aktiveReihenfolge = state.buckets.primary;
		}
		out[ch] = aktiveReihenfolge.map((mid) => ({ metric_id: mid, friendly: friendlyMap[mid] ?? true }));
	}
	return out;
}

type BuildMitBestand = (
	buckets: Buckets,
	friendlyMap: Record<string, boolean>,
	horizonsMap: Record<string, Horizons>,
	catalog: MinimalCatalog,
	bestand: ReadonlyArray<Record<string, unknown>>,
) => Array<Record<string, unknown>>;
type BuildMetricsMitKanal = (override: ChannelOverride, channel: ChannelId) => Array<Record<string, unknown>>;
type MergeMitKanal = (
	prevLayouts: Record<string, ReadonlyArray<Record<string, unknown>>> | undefined,
	channelBuckets: Record<ChannelId, ChannelOverride | null>,
	buildMetrics: BuildMetricsMitKanal,
) => Record<string, Array<Record<string, unknown>>>;

const buildMitBestand = buildWeatherConfigMetrics as unknown as BuildMitBestand;
const mergeMitKanal = mergeAllChannelLayoutsForSave as unknown as MergeMitKanal;

/** Nachbau von buildWeatherPayload() (WeatherMetricsTab.svelte:930-970),
 * REDUZIERT auf die K8-relevanten Felder (`metrics`, `channel_layouts`) --
 * andere Payload-Felder (preset_name, outlook_metrics, ...) sind fuer diese
 * Kette nicht Pruefgegenstand. `bestand` = die Original-Eintraege aus
 * `golden.display_config.metrics` (5. Parameter, K8-Fix-Signatur). */
export function baueSpeichernPayload(
	golden: GoldenTrip,
	state: EditorState,
	catalog: MinimalCatalog,
): { metrics: Array<Record<string, unknown>>; channel_layouts: Record<string, Array<Record<string, unknown>>> } {
	const bestand = golden.display_config.metrics ?? [];
	const metrics = buildMitBestand(state.buckets, state.friendlyMap, state.horizonsMap, catalog, bestand);

	const prevLayouts = golden.display_config.channel_layouts as unknown as Record<
		string,
		ReadonlyArray<Record<string, unknown>>
	>;
	const buildMetrics: BuildMetricsMitKanal = (override, channel) => {
		const kanalBestand = prevLayouts?.[channel] ?? [];
		return buildMitBestand(override.buckets, override.friendlyMap, state.horizonsMap, catalog, kanalBestand);
	};
	const channel_layouts = mergeMitKanal(prevLayouts, state.channelBuckets, buildMetrics);

	return { metrics, channel_layouts };
}

/** Flacher Merge wie `config_merge.go::mergeConfigMap`, angewendet auf
 * `display_config` -- Keys aus `payload` ueberschreiben
 * `golden.display_config`, nicht gesendete Keys bleiben. Gibt den
 * VOLLSTAENDIGEN Trip-Zustand zurueck (Spec: "der vollstaendige Trip-
 * Zustand, den die TS-Helferkette erzeugt") -- dieselbe Form wie
 * `golden_*.json` selbst, damit Python (`erwartete_kaskade(nach, ...)`
 * erwartet `nach["display_config"]`) und die E2E-GET-Antwort
 * (`{..., display_config: {...}}`) dieselbe Datei ohne Sonderfall lesen
 * koennen. */
export function flacherMerge(
	golden: GoldenTrip,
	payload: { metrics: unknown; channel_layouts: unknown },
): Record<string, unknown> {
	return { ...golden, display_config: { ...golden.display_config, ...payload } };
}

/** Speichern OHNE Aenderung: laden, unveraendert speichern, flach mergen --
 * Ergebnis ist der vollstaendige `nach_speichern_<golden>.json`-Kandidat
 * (vollstaendiger Trip-Zustand, siehe `flacherMerge`). */
export function speichernOhneAenderung(golden: GoldenTrip, catalog: MinimalCatalog): Record<string, unknown> {
	const state = ladeInEditorState(golden, catalog);
	const payload = baueSpeichernPayload(golden, state, catalog);
	return flacherMerge(golden, payload);
}

// ---------------------------------------------------------------------------
// Aenderungsfaelle (aenderungsfaelle.json) -- vier definierte Bedienungen
// ---------------------------------------------------------------------------

export interface AenderungsfallDeselect { kind: 'deselect'; channel: ChannelId; metric_id: string }
export interface AenderungsfallSwap { kind: 'swap'; channel: ChannelId; metric_a: string; metric_b: string }
export interface AenderungsfallFormatToggle {
	kind: 'format_toggle'; channel: ChannelId; metric_id: string; from_friendly: boolean; to_friendly: boolean;
}
export interface AenderungsfallDeselectAndSwap {
	kind: 'deselect_and_swap'; channel: ChannelId; deselect_metric_id: string; metric_a: string; metric_b: string;
}
export type Aenderungsfall =
	| AenderungsfallDeselect | AenderungsfallSwap | AenderungsfallFormatToggle | AenderungsfallDeselectAndSwap;

function tauscheInListe(liste: string[], a: string, b: string): string[] {
	const next = [...liste];
	const ia = next.indexOf(a);
	const ib = next.indexOf(b);
	[next[ia], next[ib]] = [next[ib], next[ia]];
	return next;
}

/** Wendet einen der vier Aenderungsfaelle auf einen frisch geladenen
 * EditorState an -- reiner State-Umbau, KEINE Speicherung. Fall 4
 * (deselect_and_swap, Golden C SMS-Reiter) nutzt `startChannelOverride`-
 * Semantik: existiert noch kein Kanal-Override, wird die globale Auswahl als
 * Startpunkt kopiert (tiefe Kopie, ADR-0050 AC-2) -- exakt was
 * `startChannelOverride()` (channelMetricLayouts.ts:67-79) tut. */
export function wendeAenderungAn(state: EditorState, fall: Aenderungsfall): EditorState {
	const next: EditorState = {
		buckets: { primary: [...state.buckets.primary], secondary: [...state.buckets.secondary], off: [...state.buckets.off] },
		friendlyMap: { ...state.friendlyMap },
		horizonsMap: { ...state.horizonsMap },
		channelBuckets: { ...state.channelBuckets },
	};

	const ch = fall.channel;
	const override: ChannelOverride = next.channelBuckets[ch]
		? {
			buckets: {
				primary: [...next.channelBuckets[ch]!.buckets.primary],
				secondary: [...next.channelBuckets[ch]!.buckets.secondary],
				off: [...next.channelBuckets[ch]!.buckets.off],
			},
			friendlyMap: { ...next.channelBuckets[ch]!.friendlyMap },
		}
		: { buckets: { primary: [...next.buckets.primary], secondary: [], off: [...next.buckets.off] }, friendlyMap: { ...next.friendlyMap } };

	switch (fall.kind) {
		case 'deselect':
			override.buckets.primary = override.buckets.primary.filter((id) => id !== fall.metric_id);
			override.buckets.off = [...override.buckets.off, fall.metric_id];
			break;
		case 'swap':
			override.buckets.primary = tauscheInListe(override.buckets.primary, fall.metric_a, fall.metric_b);
			break;
		case 'format_toggle':
			override.friendlyMap[fall.metric_id] = fall.to_friendly;
			break;
		case 'deselect_and_swap':
			override.buckets.primary = tauscheInListe(
				override.buckets.primary.filter((id) => id !== fall.deselect_metric_id),
				fall.metric_a,
				fall.metric_b,
			);
			override.buckets.off = [...override.buckets.off, fall.deselect_metric_id];
			break;
	}
	next.channelBuckets[ch] = override;
	return next;
}
