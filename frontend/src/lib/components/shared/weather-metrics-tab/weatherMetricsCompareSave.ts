// Issue #1311, Scheibe C1 von Epic #1301 — Vergleich-Save-Zweig fuer den
// geteilten Wetter-Metriken-Tab: schlankes an/aus, kein Zwei-PUT-Trip-Muster.
//
// Issue #2276 Scheibe S4 (Epic #2345): Die Layout-Haelfte (Stundenverlauf/
// Ausblick) ist aus `compare/compareHubWizardBridge.ts` hierher umgezogen und
// beide Domaenen sind zu EINER kombinierten Orchestrierung zusammengefuehrt
// (Design-Entscheidung 1 — zwei unabhaengige Selbst-Speicherer auf demselben
// Reiter wuerden sich in derselben Event-Tick gegenseitig ueberschreiben,
// Kontext-Dokument Abschnitt 1.7). `flushPendingWeatherMetricsSave` ist auf
// `buildComparePresetSavePayload` (Voll-Spread, Go-Merge-Kernel mergt
// display_config nur auf Ebene 1) umgestellt — der Laufzeit-Import der
// Hub-PUT-Erzeugerin aus `compare/compareHubWizardBridge.ts` entfaellt
// (AC-9: dieses Modul laedt zur Laufzeit KEIN Modul aus `compare/` mehr,
// ausser Typen).
//
// Spec: docs/specs/modules/rework_2276_s4_wetter_metriken.md
//   (Implementation Details Abschnitt 2, AC-1 .. AC-13)
//
// Kein Browser-/SvelteKit-Import — lauffaehig unter node --experimental-strip-types.

import type { ActivityProfile, ComparePreset } from '../../../types.ts';
import type { SaveFn, SaveStatus } from '../../../stores/saveStatusStore.svelte.ts';
import type { PutClient } from '../tripSpeicherung.ts';
import { buildComparePresetSavePayload } from '../../compare/compareEditorSave.ts';
import { rehydrateActiveMetrics } from '../../compare/compareEditorLoad.ts';
import { COMPARE_METRIC_KEYS } from '../corridor-editor/corridorEditorState.ts';
// Issue #1373 (S2 Scheibe B): Übersetzungsquelle für das Speicherformat der
// Metrik-Auswahl (Größe + Auswertung) — die geladene Katalogantwort.
import {
	normalizeStoredOutlookMetrics,
	registeredCompareMetricCatalog,
	type CompareSelectionEntry,
	type StoredActiveMetric
} from './compareMetricSelection.ts';
// Issue #1703 Scheibe 8: kanal-eigene Auswahl DERSELBEN Uebersichtstabelle —
// Erweiterung dieser Domaene, KEIN dritter Commit-Wrapper.
import {
	compareChannelActiveMetricsFromStored,
	type CompareChannelActiveMetrics
} from './compareChannelMetricLayouts.ts';
import { materializeActiveMetricKeys } from './compareMetricOrder.ts';

// Issue #1361/#1372 S1b — Trip-Default (day_window.py DAY_WINDOW_START_HOUR/
// _END_HOUR), geteilt zwischen Hydration und Neuanlage.
const DEFAULT_DAY_WINDOW_START_HOUR = 4;
const DEFAULT_DAY_WINDOW_END_HOUR = 19;

/** Tagesfenster-Hydration aus dem Preset — undefined/null (Alt-Preset) fällt
 * auf denselben Default (4/19) zurück wie der Renderer
 * (day_window.resolve_configured_window()), AC-4. */
export function hydrateDayWindowFromPreset(preset: ComparePreset): {
	dayWindowStartHour: number;
	dayWindowEndHour: number;
} {
	return {
		dayWindowStartHour: preset.day_window_start_hour ?? DEFAULT_DAY_WINDOW_START_HOUR,
		dayWindowEndHour: preset.day_window_end_hour ?? DEFAULT_DAY_WINDOW_END_HOUR
	};
}

/**
 * Erst-Oeffnungs-Hydration fuer den Vergleichs-Zweig: ein zuvor NIE
 * gespeichertes `active_metrics`-Feld (Legacy, AC-4) zeigt sich im Tab als
 * "alle Metriken aktiv" (deckt sich mit `resolve_enabled_metrics(None)` im
 * Renderpfad, der ohne Filter ALLE Metriken zeigt) — ohne das direkt zu
 * schreiben. Ein explizit gespeichertes (auch leeres) Array wird 1:1
 * uebernommen (#1191-Semantik, kein Legacy-Fallback fuer bewusste Leerauswahl).
 *
 * Issue #1373 (S2 Scheibe B, Fix-Runde 1): `catalog` ist die geladene Antwort
 * von GET /api/compare/metrics — nur damit kann eine im neuen Format
 * (Größe + Auswertung) gespeicherte Auswahl auf Auswahl-Schlüssel
 * zurückgeführt werden. Der Aufrufer MUSS die Antwort abwarten, bevor er
 * hydriert und den Dirty-Check-Grundzustand aufnimmt (sonst Scheindiff und
 * Rücksetzen auf die Rohform, Adversary-Befund F001). Default = der bereits
 * registrierte Katalog, damit bestehende Aufrufer unverändert funktionieren.
 */
export function hydrateWeatherMetricsFromPreset(
	preset: ComparePreset,
	catalog: CompareSelectionEntry[] = registeredCompareMetricCatalog()
): string[] {
	const displayConfig = (preset.display_config as Record<string, unknown>) ?? {};
	const rehydrated = rehydrateActiveMetrics(displayConfig.active_metrics, catalog);
	return rehydrated ? rehydrated.activeMetricKeys : [...COMPARE_METRIC_KEYS];
}

/**
 * Issue #1703 Scheibe 8: Kanal-Ebene derselben Uebersichtstabelle. Ein Preset
 * OHNE `channel_active_metrics` (jedes heute gespeicherte, AC-S8-15) liefert
 * dreimal `null` — alle Kanaele folgen dann der Grundauswahl, genau wie heute.
 */
export function hydrateChannelActiveMetricsFromPreset(
	preset: ComparePreset,
	catalog: CompareSelectionEntry[] = registeredCompareMetricCatalog()
): CompareChannelActiveMetrics {
	const displayConfig = (preset.display_config as Record<string, unknown>) ?? {};
	return compareChannelActiveMetricsFromStored(
		displayConfig.channel_active_metrics as Record<string, StoredActiveMetric[]> | undefined,
		catalog
	);
}

/**
 * D2-Fix-Loop 2 (AC-6, Staging-Befund BROKEN): der Amtliche-Warnungen-Toggle
 * ist fuer bestehende Vergleiche nur noch ueber diesen Hub-Tab erreichbar
 * (der Alarm-Tab-Toggle entfaellt mit D2) — der Snapshot traegt ihn neben
 * `activeMetricKeys`, damit ein reiner Toggle-Klick (ohne Metrik-Aenderung)
 * ebenfalls als dirty erkannt wird.
 * Spec: d2_1301_official_alerts_single_control.md § Punkt 6, AC-6.
 *
 * Bleibt als eigenstaendiger Typ bestehen (Legacy-Zusicherung,
 * compare_hub_wizard_bridge.test.ts) — die PRODUKTIVE Verdrahtung nutzt seit
 * Scheibe S4 ausschliesslich `WetterMetrikenLayoutSnapshot` weiter unten.
 */
export interface WeatherMetricsSnapshot {
	activeMetricKeys: string[];
	// Issue #1703 Scheibe 8: die Kanal-Ebene derselben Uebersichtstabelle gehoert
	// in DENSELBEN Snapshot — ein reiner Kanal-Edit (Grundauswahl unveraendert)
	// waere sonst kein Diff und wuerde nie gespeichert.
	channelActiveMetricKeys: CompareChannelActiveMetrics;
	officialAlertsEnabled: boolean;
	// Issue #1361/#1372 S1b: Tagesfenster — Teil desselben Snapshots, damit ein
	// reiner Von/Bis-Wechsel (ohne Metrik-/Toggle-Aenderung) ebenfalls als dirty
	// erkannt wird (analog officialAlertsEnabled oben).
	dayWindowStartHour: number;
	dayWindowEndHour: number;
}

/**
 * Diff-Guard analog `flushPendingVersandSave` (compareHubWizardBridge.ts):
 * liefert `null`, wenn sich weder Metrik-Auswahl noch Amtliche-Warnungen-
 * Toggle noch Tagesfenster seit dem letzten persistierten Stand veraendert
 * haben (kein Schreiben ohne Nutzer-Geste, AC-4) — sonst den fertigen
 * PUT-Payload ueber `buildComparePresetSavePayload` (Voll-Spread, Issue
 * #2276 S4: die Hub-PUT-Erzeugerin entfaellt, `region` wird deshalb explizit
 * aus dem Bestand zurueckgelesen, damit der unbedingte Region-Schreibpfad von
 * `buildComparePresetSavePayload` den Bestand nicht auf "" zuruecksetzt).
 */
export function flushPendingWeatherMetricsSave(
	preset: ComparePreset,
	current: WeatherMetricsSnapshot,
	before: WeatherMetricsSnapshot | null
): { url: string; body: ComparePreset } | null {
	const baseline = before ?? current;
	// Issue #1359 Scheibe 1: KEIN `.sort()` mehr. Die Listenposition IST die
	// Metrik-Reihenfolge (kein eigenes order-Feld) — sortiert verglichen galten
	// zwei Listen mit derselben MENGE in anderer Reihenfolge als identisch,
	// `flushPendingWeatherMetricsSave` lieferte `null` und eine reine
	// Umsortierung wurde nie gespeichert. Die AC-4-Zusage "kein Schreiben ohne
	// Nutzer-Geste" bleibt gewahrt: der Guard entscheidet nur, OB ein
	// Unterschied vorliegt — ausgeloest wird weiterhin nur von einer echten
	// Geste (Checkbox-Toggle bzw. Drag-Ende).
	const norm = (s: WeatherMetricsSnapshot) => ({
		activeMetricKeys: [...s.activeMetricKeys],
		// Issue #1703 Scheibe 8: feste Kanalfolge statt Objekt-Spread — der
		// JSON.stringify-Vergleich ist schluesselreihenfolge-abhaengig, und ein
		// per Copy-on-write neu gebautes Objekt kann eine andere Folge haben als
		// der Grundzustand (Scheindiff bei jeder Geste).
		channelActiveMetricKeys: [
			s.channelActiveMetricKeys?.email ?? null,
			s.channelActiveMetricKeys?.telegram ?? null,
			s.channelActiveMetricKeys?.sms ?? null
		],
		officialAlertsEnabled: s.officialAlertsEnabled,
		dayWindowStartHour: s.dayWindowStartHour,
		dayWindowEndHour: s.dayWindowEndHour
	});
	if (JSON.stringify(norm(current)) === JSON.stringify(norm(baseline))) return null;
	const displayConfig = (preset.display_config as Record<string, unknown>) ?? {};
	return buildComparePresetSavePayload(preset, {
		name: preset.name,
		activityProfile: (preset.profil as ActivityProfile) ?? null,
		pickedIds: preset.location_ids ?? [],
		region: (displayConfig.region as string) ?? '',
		idealRanges: {},
		activeMetricKeys: current.activeMetricKeys,
		channelActiveMetricKeys: current.channelActiveMetricKeys,
		officialAlertsEnabled: current.officialAlertsEnabled,
		dayWindowStartHour: current.dayWindowStartHour,
		dayWindowEndHour: current.dayWindowEndHour
	});
}

// ─── Issue #2276 S4: Layout-Haelfte (Stundenverlauf/Ausblick) — umgezogen aus
// compare/compareHubWizardBridge.ts, auf buildComparePresetSavePayload umgestellt ──

/** Plain-Snapshot der beiden persistenzrelevanten Layout-Tab-Felder (analog
 * `VersandSnapshot`). Issue #1299/#1291/#1287 (Scheibe C2 von Epic #1301). */
export interface LayoutSnapshot {
	// Issue #1366 F001: `null` = „nie eingestellt" (Feld fehlt im Preset),
	// `[]` = bewusste Leerauswahl -- beide muessen unterscheidbar bleiben
	// (vorher kollabierte `?? []` beides zu derselben leeren Liste).
	hourlyMetricKeys: string[] | null;
	hourlyEnabled: boolean;
	// Issue #1361 Befund 2/#1368: der 3-Tages-Ausblick teilt sich diesen
	// Speicherpfad mit dem Stundenverlauf (beide liegen im Reiter
	// "Wetter-Metriken", derselbe Commit-Wrapper). `null`/`[]` tragen dieselbe
	// Unterscheidung wie oben.
	outlookMetricKeys: string[] | null;
	// Issue #2049: Roh/Einfach je Ausblick-Groesse -- `null` = nie eingestellt.
	outlookMetricFormats?: Record<string, boolean> | null;
	outlookEnabled: boolean;
}

/**
 * Issue #1299/C2: Erst-Oeffnungs-Hydration fuer den Hub-Layout-Tab, analog
 * `hydrateVersandFieldsFromPreset` — liest die Stundenverlauf-Felder aus
 * `preset.display_config.hourly_metrics` bzw. `preset.hourly_enabled`.
 */
export function hydrateLayoutFieldsFromPreset(
	preset: ComparePreset,
	catalog: CompareSelectionEntry[] = registeredCompareMetricCatalog()
): LayoutSnapshot {
	const displayConfig = (preset.display_config as Record<string, unknown>) ?? {};
	return {
		hourlyMetricKeys: (displayConfig.hourly_metrics as string[] | null | undefined) ?? null,
		hourlyEnabled: preset.hourly_enabled ?? true,
		outlookMetricKeys: normalizeStoredOutlookMetrics(displayConfig.outlook_metrics, catalog),
		outlookMetricFormats:
			(displayConfig.outlook_metric_formats as Record<string, boolean> | undefined) ?? null,
		outlookEnabled: preset.outlook_enabled ?? true
	};
}

/**
 * Issue #1299/C2 (AC-6): Event-diskretisierte PUT-Persistenz fuer den
 * Hub-Layout-Tab — liefert `null`, wenn sich der Snapshot seit dem letzten
 * persistierten Stand NICHT veraendert hat, sonst den fertigen PUT-Payload
 * via `buildComparePresetSavePayload` (Issue #2276 S4: die Hub-PUT-Erzeugerin
 * entfaellt, `region` wird deshalb explizit zurueckgelesen).
 */
export function flushPendingLayoutSave(
	preset: ComparePreset,
	current: LayoutSnapshot,
	before: LayoutSnapshot | null
): { url: string; body: ComparePreset } | null {
	const baseline = before ?? current;
	const norm = (s: LayoutSnapshot) => ({
		hourlyMetricKeys: s.hourlyMetricKeys === null ? null : [...s.hourlyMetricKeys],
		hourlyEnabled: s.hourlyEnabled,
		outlookMetricKeys: s.outlookMetricKeys == null ? null : [...s.outlookMetricKeys],
		outlookMetricFormats: s.outlookMetricFormats == null ? null : { ...s.outlookMetricFormats },
		outlookEnabled: s.outlookEnabled
	});
	if (JSON.stringify(norm(current)) === JSON.stringify(norm(baseline))) return null;
	const displayConfig = (preset.display_config as Record<string, unknown>) ?? {};
	return buildComparePresetSavePayload(preset, {
		name: preset.name,
		activityProfile: (preset.profil as ActivityProfile) ?? null,
		pickedIds: preset.location_ids ?? [],
		region: (displayConfig.region as string) ?? '',
		idealRanges: {},
		hourlyMetricKeys: current.hourlyMetricKeys,
		hourlyEnabled: current.hourlyEnabled,
		outlookMetricKeys: current.outlookMetricKeys,
		outlookMetricFormats: current.outlookMetricFormats,
		outlookEnabled: current.outlookEnabled
	});
}

/**
 * Issue #1299/C2 (AC-6): Rollback fuer den Hub-Layout-Commit-Fehlerpfad.
 * `hourlyMetricKeys`/`hourlyEnabled` sind EXKLUSIV Layout-Tab-Eigentum —
 * direkte Zuweisung genuegt, kein diff-basierter Rollback noetig.
 */
export function rollbackLayoutSnapshot(
	state: {
		hourlyMetricKeys?: string[] | null;
		hourlyEnabled?: boolean;
		outlookMetricKeys?: string[] | null;
		outlookMetricFormats?: Record<string, boolean> | null;
		outlookEnabled?: boolean;
	},
	before: LayoutSnapshot
): void {
	state.hourlyMetricKeys = before.hourlyMetricKeys;
	state.hourlyEnabled = before.hourlyEnabled;
	state.outlookMetricKeys = before.outlookMetricKeys ?? null;
	state.outlookMetricFormats = before.outlookMetricFormats ?? null;
	state.outlookEnabled = before.outlookEnabled ?? true;
}

// ─── Issue #2276 S4: EINE kombinierte Orchestrierung ueber BEIDE Domaenen ──
//
// Design-Entscheidung 1 (Spec): zwei unabhaengige Selbst-Speicherer auf
// demselben Reiter, von derselben Geste ausgeloest, ueberschreiben sich in
// derselben Event-Tick den `_pendingFn`-Einzel-Slot des Speicher-Controllers
// (saveStatusStore.svelte.ts:184-189) — deshalb EIN Snapshot-Typ, EINE
// `aenderungMelden()`, EIN `schedule()`-Aufruf pro Geste.

/** Kombinierter Snapshot ueber Wetter-Metriken- UND Layout-Domaene (9 Felder). */
export interface WetterMetrikenLayoutSnapshot {
	activeMetricKeys: string[];
	channelActiveMetricKeys: CompareChannelActiveMetrics;
	officialAlertsEnabled: boolean;
	dayWindowStartHour: number;
	dayWindowEndHour: number;
	hourlyMetricKeys: string[] | null;
	hourlyEnabled: boolean;
	outlookMetricKeys: string[] | null;
	outlookMetricFormats: Record<string, boolean> | null;
	outlookEnabled: boolean;
}

/** Wizard-Zustand, den der Wetter-Metriken/Layout-Reiter liest/schreibt
 *  (bewusst locker typisiert, kein Laufzeit-Import einer Compare-Klasse). */
export type WetterMetrikenZustand = object;

function felder(wiz: WetterMetrikenZustand): Record<string, unknown> {
	return wiz as Record<string, unknown>;
}

/** Aktueller Wetter-Metriken/Layout-Stand von `wiz` als entkoppelte Kopie —
 *  `activeMetricKeys` materialisiert (#1366), alle Felder LIVE gelesen
 *  (E3-Pflicht, AC-4: `activeMetricKeys` teilt sich `display_config.
 *  active_metrics` mit dem Wertebereiche-Reiter — nur ein Live-Read beider
 *  Schreiber macht die Ueberschneidung sicher). */
export function wetterMetrikenSnapshotAus(wiz: WetterMetrikenZustand): WetterMetrikenLayoutSnapshot {
	const f = felder(wiz);
	return JSON.parse(
		JSON.stringify({
			activeMetricKeys: materializeActiveMetricKeys(
				(f.activeMetricKeys as string[] | null | undefined) ?? null
			),
			channelActiveMetricKeys: f.channelActiveMetricKeys ?? { email: null, telegram: null, sms: null },
			officialAlertsEnabled: f.officialAlertsEnabled ?? true,
			dayWindowStartHour: (f.dayWindowStartHour as number | undefined) ?? DEFAULT_DAY_WINDOW_START_HOUR,
			dayWindowEndHour: (f.dayWindowEndHour as number | undefined) ?? DEFAULT_DAY_WINDOW_END_HOUR,
			hourlyMetricKeys: (f.hourlyMetricKeys as string[] | null | undefined) ?? null,
			hourlyEnabled: (f.hourlyEnabled as boolean | undefined) ?? true,
			outlookMetricKeys: (f.outlookMetricKeys as string[] | null | undefined) ?? null,
			outlookMetricFormats: (f.outlookMetricFormats as Record<string, boolean> | null | undefined) ?? null,
			outlookEnabled: (f.outlookEnabled as boolean | undefined) ?? true
		})
	) as WetterMetrikenLayoutSnapshot;
}

/**
 * EINZIGE Erzeugerin der kombinierten Nutzlast: Voll-Spread über `preset`
 * (Go-Merge mergt `display_config` nur auf Ebene 1), die neun eigenen Felder
 * aus `current` — `activeMetricKeys` LIVE aus dem Zustand (AC-4), nie aus
 * einer eingefrorenen Preset-Kopie. `hourlyMetricKeys`/`outlookMetricKeys`/
 * `outlookMetricFormats` fallen bei `null` ("nie eingestellt") auf den
 * bereits gespeicherten Preset-Stand zurueck (Rundlauf-Sicherung, analog dem
 * fruehreren Hub-PUT-Bestandsrueckfall) — eine bewusste
 * Leerauswahl (`[]`) bleibt davon unberuehrt (nur `??`, kein `||`).
 */
export function baueWetterMetrikenNutzlast(
	preset: ComparePreset,
	current: WetterMetrikenLayoutSnapshot
): { url: string; body: ComparePreset } {
	const displayConfig = (preset.display_config as Record<string, unknown>) ?? {};
	return buildComparePresetSavePayload(preset, {
		name: preset.name,
		activityProfile: (preset.profil as ActivityProfile) ?? null,
		pickedIds: preset.location_ids ?? [],
		region: (displayConfig.region as string) ?? '',
		idealRanges: {},
		activeMetricKeys: current.activeMetricKeys,
		channelActiveMetricKeys: current.channelActiveMetricKeys,
		officialAlertsEnabled: current.officialAlertsEnabled,
		hourlyMetricKeys: current.hourlyMetricKeys ?? (displayConfig.hourly_metrics as string[] | null | undefined),
		hourlyEnabled: current.hourlyEnabled,
		outlookMetricKeys:
			current.outlookMetricKeys ?? normalizeStoredOutlookMetrics(displayConfig.outlook_metrics) ?? undefined,
		outlookMetricFormats:
			current.outlookMetricFormats ?? (displayConfig.outlook_metric_formats as Record<string, boolean> | undefined),
		outlookEnabled: current.outlookEnabled,
		dayWindowStartHour: current.dayWindowStartHour,
		dayWindowEndHour: current.dayWindowEndHour
	});
}

/**
 * Liefert `null`, wenn sich der kombinierte Snapshot seit dem letzten
 * gespeicherten Stand NICHT veraendert hat (kein unnoetiger PUT), sonst die
 * fertige Nutzlast. `before === null` ⇒ der aktuelle Stand ist die Baseline.
 * Design-Entscheidung 6: `outlookMetricFormats` behaelt die
 * `== null ? null : {...}`-Semantik — sonst Scheindiff zwischen „Schluessel
 * fehlt" und „Schluessel ist null".
 */
export function flushPendingWetterMetrikenSave(
	preset: ComparePreset,
	current: WetterMetrikenLayoutSnapshot,
	before: WetterMetrikenLayoutSnapshot | null
): { url: string; body: ComparePreset } | null {
	const baseline = before ?? current;
	const norm = (s: WetterMetrikenLayoutSnapshot) => ({
		activeMetricKeys: [...s.activeMetricKeys],
		channelActiveMetricKeys: [
			s.channelActiveMetricKeys?.email ?? null,
			s.channelActiveMetricKeys?.telegram ?? null,
			s.channelActiveMetricKeys?.sms ?? null
		],
		officialAlertsEnabled: s.officialAlertsEnabled,
		dayWindowStartHour: s.dayWindowStartHour,
		dayWindowEndHour: s.dayWindowEndHour,
		hourlyMetricKeys: s.hourlyMetricKeys === null ? null : [...s.hourlyMetricKeys],
		hourlyEnabled: s.hourlyEnabled,
		outlookMetricKeys: s.outlookMetricKeys == null ? null : [...s.outlookMetricKeys],
		outlookMetricFormats: s.outlookMetricFormats == null ? null : { ...s.outlookMetricFormats },
		outlookEnabled: s.outlookEnabled
	});
	if (JSON.stringify(norm(current)) === JSON.stringify(norm(baseline))) return null;
	return baueWetterMetrikenNutzlast(preset, current);
}

/**
 * Diff-basierter Rollback (Design Punkt 7, analog Wertebereiche S3): ein Feld
 * wird nur zurueckgesetzt, wenn `wiz` noch exakt den Wert traegt, den DIESER
 * gescheiterte Vorgang gesendet hat.
 */
export function rollbackWetterMetrikenSnapshot(
	wiz: WetterMetrikenZustand,
	before: WetterMetrikenLayoutSnapshot,
	attempted: WetterMetrikenLayoutSnapshot
): void {
	const target = felder(wiz);
	const aktuell = wetterMetrikenSnapshotAus(wiz);
	const felderListe = [
		'activeMetricKeys',
		'channelActiveMetricKeys',
		'officialAlertsEnabled',
		'dayWindowStartHour',
		'dayWindowEndHour',
		'hourlyMetricKeys',
		'hourlyEnabled',
		'outlookMetricKeys',
		'outlookMetricFormats',
		'outlookEnabled'
	] as const;
	for (const field of felderListe) {
		if (JSON.stringify(aktuell[field]) === JSON.stringify(attempted[field])) {
			target[field] = before[field];
		}
	}
}

export interface WetterMetrikenVergleichSpeicherungOptionen {
	client: PutClient;
	wiz: WetterMetrikenZustand;
	/** Basis — als Getter, damit sie ERST bei Ausführung in der Queue gelesen wird. */
	preset: () => ComparePreset;
	/** Hub-Queue (`hubPutQueue.enqueue`) — Serialisierung mit den Nachbar-Reitern. */
	enqueueHubWrite: <T>(fn: () => Promise<T>) => Promise<T>;
	/** Basis-Rückmeldung nach Erfolg (`currentPreset` im Hub). */
	onCompareUpdate: (antwort: ComparePreset) => void;
	saveController: SaveStatus;
}

/**
 * Orchestrierung des Wetter-Metriken/Layout-Speicherns im Ortsvergleich
 * (Muster `erstelleAlarmeVergleichSpeicherung`/`erstelleWertebereicheVergleichSpeicherung`,
 * S2/S3) — anders als dort ueber EINEN kombinierten Snapshot beider Domaenen
 * (Design-Entscheidung 1). Anfangs-Baseline = Stand von `wiz` beim Erzeugen
 * (nach BEIDEN Hydrationen, AC-3 — der Aufrufer MUSS erst nach
 * `wetterMetrikenHydrationAbgeschlossen()` erzeugen).
 *
 * `aenderungMelden()`: ohne Unterschied zur Baseline wird ein eigener, noch
 * ausstehender Vorgang verworfen — sonst `schedule(SaveFn)`. Die SaveFn liest
 * Basis und Stand erst bei Ausführung in der Queue (AC-4), reicht `init`
 * (keepalive) an den PUT durch (AC-11), rollt nur bei Nicht-412 zurück
 * (AC-7) und wirft den Fehler weiter, damit der Controller `conflict`/`error`
 * anzeigt.
 */
export function erstelleWetterMetrikenVergleichSpeicherung(
	opt: WetterMetrikenVergleichSpeicherungOptionen
): { aenderungMelden(): void } {
	const { client, wiz, enqueueHubWrite, saveController } = opt;
	let zuletztGespeichert: WetterMetrikenLayoutSnapshot = wetterMetrikenSnapshotAus(wiz);
	let eigenerVorgangAussteht = false;

	const saveFn: SaveFn = async (init) => {
		eigenerVorgangAussteht = false;
		await enqueueHubWrite(async () => {
			for (;;) {
				const current = wetterMetrikenSnapshotAus(wiz);
				const before = zuletztGespeichert;
				const payload = flushPendingWetterMetrikenSave(opt.preset(), current, before);
				if (!payload) return;
				try {
					const antwort = await client.put<ComparePreset>(payload.url, payload.body, init);
					zuletztGespeichert = current;
					opt.onCompareUpdate(antwort);
				} catch (e) {
					if ((e as { status?: number })?.status !== 412) {
						rollbackWetterMetrikenSnapshot(wiz, before, current);
					}
					throw e;
				}
			}
		});
	};

	return {
		aenderungMelden(): void {
			const current = wetterMetrikenSnapshotAus(wiz);
			if (JSON.stringify(current) === JSON.stringify(zuletztGespeichert)) {
				if (eigenerVorgangAussteht) {
					eigenerVorgangAussteht = false;
					saveController.cancel();
					saveController.markPristine();
				}
				return;
			}
			eigenerVorgangAussteht = true;
			saveController.schedule(saveFn);
		}
	};
}

/** AC-3-Gate: die kombinierte Orchestrierung darf erst erzeugt werden, wenn
 *  BEIDE Katalog-Ladevorgaenge (Wetter-Metriken-Auswahl, Stundenverlauf/
 *  Ausblick) abgeschlossen sind — sonst diffed sie gegen eine unvollstaendige
 *  Baseline und die spaeter eintreffende zweite Hydration loest einen PUT
 *  OHNE Nutzergeste aus (Kontext-Dokument Abschnitt 1.2/4.2). */
export function wetterMetrikenHydrationAbgeschlossen(p: {
	wetterMetrikenHydrated: boolean;
	layoutHydrated: boolean;
}): boolean {
	return p.wetterMetrikenHydrated && p.layoutHydrated;
}

/** Erzeugungs-Bedingung der kombinierten Vergleichs-Speicherung im Editor
 *  (AC-10, AC-13): nur im Ortsvergleich-Hub (vergleich + Wizard-Zustand +
 *  Basis + Controller) — die Anlege-Seite mountet ohne `preset`/
 *  `saveController`, der Trip-Zweig (`route`) speichert ueber
 *  `scheduleAutoSave`/`scheduleReportConfigOnlySave`. */
export function wetterMetrikenVergleichSpeicherungAktiv(p: {
	context: string;
	wiz: unknown;
	preset: unknown;
	saveController: unknown;
}): boolean {
	return p.context === 'vergleich' && !!p.wiz && !!p.preset && !!p.saveController;
}
