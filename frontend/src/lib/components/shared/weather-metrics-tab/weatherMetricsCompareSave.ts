// Issue #1311, Scheibe C1 von Epic #1301 — Vergleich-Save-Zweig fuer den
// geteilten Wetter-Metriken-Tab: schlankes an/aus, kein Zwei-PUT-Trip-Muster.
//
// Issue #2276 Scheibe S4 (Epic #2345): Die Layout-Haelfte (Stundenverlauf/
// Ausblick) ist aus der ehemaligen Compare-Hub-Klebeschicht hierher umgezogen und
// beide Domaenen sind zu EINER kombinierten Orchestrierung zusammengefuehrt
// (Design-Entscheidung 1 — zwei unabhaengige Selbst-Speicherer auf demselben
// Reiter wuerden sich in derselben Event-Tick gegenseitig ueberschreiben,
// Kontext-Dokument Abschnitt 1.7). #3276 (F005): `flushPendingWeatherMetricsSave`
// (ohne Produktions-Aufrufer) ist entfernt.
//
// Spec: docs/specs/modules/rework_2276_s4_wetter_metriken.md
//   (Implementation Details Abschnitt 2, AC-1 .. AC-13)
//
// Kein Browser-/SvelteKit-Import — lauffaehig unter node --experimental-strip-types.

import type { ActivityProfile, ComparePreset } from '../../../types.ts';
import type { SaveFn, SaveStatus } from '../../../stores/saveStatusStore.svelte.ts';
import { merkeNutzlast } from '../../../stores/nutzlastStand.ts';
import type { PutClient } from '../tripSpeicherung.ts';
import { buildComparePresetSavePayload, waehleEigenfelder } from '../../compare/compareEditorSave.ts';
import { rehydrateActiveMetrics } from '../../compare/compareEditorLoad.ts';
// Issue #1373 (S2 Scheibe B): Übersetzungsquelle für das Speicherformat der
// Metrik-Auswahl (Größe + Auswertung) — die geladene Katalogantwort.
import { registeredCompareMetricCatalog, type CompareSelectionEntry } from './compareMetricSelection.ts';
// Issue #1703 Scheibe 8: kanal-eigene Auswahl DERSELBEN Uebersichtstabelle —
// Erweiterung dieser Domaene, KEIN dritter Commit-Wrapper. #3298: die Lese-Naht entfaellt.
import type { CompareChannelActiveMetrics } from './compareChannelMetricLayouts.ts';
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
 * #3047 J1/#3061 (AC-13): fehlendes `active_metrics` -> `null` („nie eingestellt"), nie die Vorgabeliste.
 */
export function hydrateWeatherMetricsFromPreset(
	preset: ComparePreset,
	catalog: CompareSelectionEntry[] = registeredCompareMetricCatalog()
): string[] | null {
	const displayConfig = (preset.display_config as Record<string, unknown>) ?? {};
	const rehydrated = rehydrateActiveMetrics(displayConfig.active_metrics, catalog);
	return rehydrated ? rehydrated.activeMetricKeys : null;
}

// Issue #3298: die Lese-Naht der Kanal-Auswahl (`hydrateChannelActiveMetricsFromPreset`)
// ist entfallen — das Backend liefert den Altschluessel nicht mehr (ADR-0124).

// ─── Issue #2276 S4: Layout-Haelfte (Stundenverlauf) — umgezogen aus der
// ehemaligen Compare-Hub-Klebeschicht, auf buildComparePresetSavePayload umgestellt ──

/** Plain-Snapshot des persistenzrelevanten Layout-Felds (analog `VersandSnapshot`).
 * Issue #1299/#1291/#1287 (Scheibe C2 von Epic #1301). Issue #3298: Stundenverlauf-/
 * Ausblick-Auswahl und Ausblick-Schalter entfallen (ADR-0124, `placements`). */
export interface LayoutSnapshot {
	hourlyEnabled: boolean;
}

/**
 * Issue #1299/C2: Erst-Oeffnungs-Hydration fuer den Hub-Layout-Tab, analog
 * `hydrateVersandFieldsFromPreset` — liest nur noch `preset.hourly_enabled`
 * (#3298: keine Altfelder).
 */
export function hydrateLayoutFieldsFromPreset(preset: ComparePreset): LayoutSnapshot {
	return { hourlyEnabled: preset.hourly_enabled ?? true };
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
	// #3276: nur die gesendeten Felder zaehlen — eine Aenderung an Altfeldern loest keinen PUT aus.
	if (current.hourlyEnabled === baseline.hourlyEnabled) return null;
	const displayConfig = (preset.display_config as Record<string, unknown>) ?? {};
	const voll = buildComparePresetSavePayload(preset, {
		name: preset.name,
		activityProfile: (preset.profil as ActivityProfile) ?? null,
		pickedIds: preset.location_ids ?? [],
		region: (displayConfig.region as string) ?? '',
		idealRanges: {},
		hourlyEnabled: current.hourlyEnabled
	});
	// Issue #2375: nur die Layout-Eigenfelder. #3276/#3298: ohne Altschluessel.
	return waehleEigenfelder(voll, ['hourly_enabled']);
}

/**
 * Issue #1299/C2 (AC-6): Rollback fuer den Hub-Layout-Commit-Fehlerpfad.
 * `hourlyEnabled` ist EXKLUSIV Layout-Tab-Eigentum — direkte Zuweisung genuegt.
 */
export function rollbackLayoutSnapshot(state: { hourlyEnabled?: boolean }, before: LayoutSnapshot): void {
	state.hourlyEnabled = before.hourlyEnabled;
}

// ─── Issue #2276 S4: EINE kombinierte Orchestrierung ueber BEIDE Domaenen ──
//
// Design-Entscheidung 1 (Spec): zwei unabhaengige Selbst-Speicherer auf
// demselben Reiter, von derselben Geste ausgeloest, ueberschreiben sich in
// derselben Event-Tick den `_pendingFn`-Einzel-Slot des Speicher-Controllers
// (saveStatusStore.svelte.ts:184-189) — deshalb EIN Snapshot-Typ, EINE
// `aenderungMelden()`, EIN `schedule()`-Aufruf pro Geste.

/** Kombinierter Snapshot ueber Wetter-Metriken- UND Layout-Domaene. #3298: die
 *  Stundenverlauf-/Ausblick-Altfelder und der Ausblick-Schalter entfallen. */
export interface WetterMetrikenLayoutSnapshot {
	activeMetricKeys: string[];
	channelActiveMetricKeys: CompareChannelActiveMetrics;
	officialAlertsEnabled: boolean;
	dayWindowStartHour: number;
	dayWindowEndHour: number;
	hourlyEnabled: boolean;
}

/** Wizard-Zustand, den der Wetter-Metriken/Layout-Reiter liest/schreibt
 *  (bewusst locker typisiert, kein Laufzeit-Import einer Compare-Klasse). */
export type WetterMetrikenZustand = object;

function felder(zustand: WetterMetrikenZustand): Record<string, unknown> {
	return zustand as Record<string, unknown>;
}

/** Aktueller Wetter-Metriken/Layout-Stand von `zustand` als entkoppelte Kopie —
 *  `activeMetricKeys` materialisiert (#1366), alle Felder LIVE gelesen
 *  (E3-Pflicht, AC-4: `activeMetricKeys` teilt sich `display_config.
 *  active_metrics` mit dem Wertebereiche-Reiter — nur ein Live-Read beider
 *  Schreiber macht die Ueberschneidung sicher). */
export function wetterMetrikenSnapshotAus(zustand: WetterMetrikenZustand): WetterMetrikenLayoutSnapshot {
	const f = felder(zustand);
	return JSON.parse(
		JSON.stringify({
			activeMetricKeys: materializeActiveMetricKeys(
				(f.activeMetricKeys as string[] | null | undefined) ?? null
			),
			channelActiveMetricKeys: f.channelActiveMetricKeys ?? { email: null, telegram: null, sms: null },
			officialAlertsEnabled: f.officialAlertsEnabled ?? true,
			dayWindowStartHour: (f.dayWindowStartHour as number | undefined) ?? DEFAULT_DAY_WINDOW_START_HOUR,
			dayWindowEndHour: (f.dayWindowEndHour as number | undefined) ?? DEFAULT_DAY_WINDOW_END_HOUR,
			hourlyEnabled: (f.hourlyEnabled as boolean | undefined) ?? true
		})
	) as WetterMetrikenLayoutSnapshot;
}

// Issue #2375: Feld-Besitz des Wetter-Metriken-Reiters (Spec
// compare_konfliktschutz_teilfelder.md §2) — inklusive `official_alerts_enabled`
// (Bedienelement sitzt hier, nicht im Alarme-Reiter).
// Issue #2794 S3a Teil-PR 3 (AC-38, Fix-Loop F006): der Reiter ist nur noch Zustellung —
// die Felder des Reiters Wetter (`active_metrics`, `ampel`, `official_alerts_enabled`,
// `official_warnings`, `radar_alert_enabled`, `day_window_*`) schreibt allein der
// WetterTab-Speicherer; hier stehen sie weder im Rumpf noch im Aenderungs-Vergleich.
// Issue #3276 (Spec-AC-38): die display_config-Eigenfelder (`channel_active_metrics`,
// `hourly_metrics`, `outlook_metrics`, `outlook_metric_formats`, `hourly_metric_formats`)
// sind Altschluessel und entfallen ersatzlos; die Tabelle „Was steht wo" ist die Quelle.
// Issue #3298: auch der Ausblick-Schalter entfaellt (`placements.outlook_reports`, ADR-0124 Nr. 6).
const WETTER_TOP = ['hourly_enabled'] as const;

/**
 * EINZIGE Erzeugerin der kombinierten Nutzlast (Issue #2375: Teilfeld-Nutzlast):
 * die eigenen Felder aus `current` — `activeMetricKeys` LIVE aus dem
 * Zustand (AC-4), nie aus einer eingefrorenen Preset-Kopie; gesendet werden nur
 * diese Eigenfelder, der Server mergt fehlende Felder als „unverändert".
 * Issue #3276/#3298: seit dem Wegfall der Altschluessel ist das nur noch `hourly_enabled`.
 */
export function baueWetterMetrikenNutzlast(
	preset: ComparePreset,
	current: WetterMetrikenLayoutSnapshot
): { url: string; body: ComparePreset } {
	const displayConfig = (preset.display_config as Record<string, unknown>) ?? {};
	const voll = buildComparePresetSavePayload(preset, {
		name: preset.name,
		activityProfile: (preset.profil as ActivityProfile) ?? null,
		pickedIds: preset.location_ids ?? [],
		region: (displayConfig.region as string) ?? '',
		idealRanges: {},
		activeMetricKeys: current.activeMetricKeys,
		officialAlertsEnabled: current.officialAlertsEnabled,
		hourlyEnabled: current.hourlyEnabled,
		dayWindowStartHour: current.dayWindowStartHour,
		dayWindowEndHour: current.dayWindowEndHour
	});
	// Issue #2375: nur die Wetter-Metriken-Eigenfelder (Feld-Besitz-Tabelle).
	return waehleEigenfelder(voll, WETTER_TOP);
}

/** Die Felder, die dieser Speicherer besitzt, normiert fuer den Vergleich. #2794 F006: Felder
 *  des Reiters Wetter zaehlen hier nicht als Aenderung (AC-38). */
function zustellungsStand(s: WetterMetrikenLayoutSnapshot) {
	// #3276: nur noch die gesendeten Felder -- eine Aenderung an Altfeldern loest keinen PUT aus.
	return { hourlyEnabled: s.hourlyEnabled };
}

/**
 * Liefert `null`, wenn sich der kombinierte Snapshot seit dem letzten
 * gespeicherten Stand NICHT veraendert hat (kein unnoetiger PUT), sonst die
 * fertige Nutzlast. `before === null` ⇒ der aktuelle Stand ist die Baseline.
 */
export function flushPendingWetterMetrikenSave(
	preset: ComparePreset,
	current: WetterMetrikenLayoutSnapshot,
	before: WetterMetrikenLayoutSnapshot | null
): { url: string; body: ComparePreset } | null {
	const baseline = before ?? current;
	if (JSON.stringify(zustellungsStand(current)) === JSON.stringify(zustellungsStand(baseline))) return null;
	return baueWetterMetrikenNutzlast(preset, current);
}

/**
 * Diff-basierter Rollback (Design Punkt 7, analog Wertebereiche S3): ein Feld
 * wird nur zurueckgesetzt, wenn `zustand` noch exakt den Wert traegt, den
 * DIESER gescheiterte Vorgang gesendet hat.
 */
export function rollbackWetterMetrikenSnapshot(
	zustand: WetterMetrikenZustand,
	before: WetterMetrikenLayoutSnapshot,
	attempted: WetterMetrikenLayoutSnapshot
): void {
	const target = felder(zustand);
	const aktuell = wetterMetrikenSnapshotAus(zustand);
	// #2794 F006: nur die Felder, die dieser Speicherer sendet (Wetter-Felder gehoeren dem WetterTab).
	// #3276: Altfelder werden nicht mehr gesendet, also auch nicht zurueckgerollt.
	const felderListe = ['hourlyEnabled'] as const;
	for (const field of felderListe) {
		if (JSON.stringify(aktuell[field]) === JSON.stringify(attempted[field])) {
			target[field] = before[field];
		}
	}
}

export interface WetterMetrikenVergleichSpeicherungOptionen {
	client: PutClient;
	zustand: WetterMetrikenZustand;
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
 * (Design-Entscheidung 1). Anfangs-Baseline = Stand von `zustand` beim
 * Erzeugen (nach BEIDEN Hydrationen, AC-3 — der Aufrufer MUSS erst nach
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
	const { client, zustand, enqueueHubWrite, saveController } = opt;
	let zuletztGespeichert: WetterMetrikenLayoutSnapshot = wetterMetrikenSnapshotAus(zustand);
	let eigenerVorgangAussteht = false;

	const saveFn: SaveFn = async (init) => {
		eigenerVorgangAussteht = false;
		await enqueueHubWrite(async () => {
			for (;;) {
				const current = wetterMetrikenSnapshotAus(zustand);
				const before = zuletztGespeichert;
				const payload = flushPendingWetterMetrikenSave(opt.preset(), current, before);
				if (!payload) return;
				try {
					// Fix-Loop 3 (F201): die GESENDETE Nutzlast bleibt am Funktionsobjekt (Seitenstand-Fortschreibung bei 412).
					merkeNutzlast(saveFn, payload.body);
					const antwort = await client.put<ComparePreset>(payload.url, payload.body, init);
					zuletztGespeichert = current;
					opt.onCompareUpdate(antwort);
				} catch (e) {
					if ((e as { status?: number })?.status !== 412 && !saveController.imWiederholen) {
						rollbackWetterMetrikenSnapshot(zustand, before, current);
					}
					throw e;
				}
			}
		});
	};

	return {
		aenderungMelden(): void {
			const current = wetterMetrikenSnapshotAus(zustand);
			if (JSON.stringify(zustellungsStand(current)) === JSON.stringify(zustellungsStand(zuletztGespeichert))) {
				if (eigenerVorgangAussteht) {
					eigenerVorgangAussteht = false;
					saveController.cancel('wetter-metriken');
					saveController.markPristine();
				}
				return;
			}
			eigenerVorgangAussteht = true;
			saveController.schedule(saveFn, 700, 'wetter-metriken');
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
	zustand: unknown;
	preset: unknown;
	saveController: unknown;
}): boolean {
	return p.context === 'vergleich' && !!p.zustand && !!p.preset && !!p.saveController;
}

/**
 * Issue #2276 S6g: Bruecke zwischen den WERTPROPS des Wetter-Metriken-
 * Organismus und diesem (unveraenderten) Speicherweg. Seit S6g haelt
 * `WeatherMetricsTab.svelte` keine Wizard-Referenz mehr — der Baustein reicht
 * seine Props herein, und HIER, an genau einer Stelle, treffen Wertprops und
 * Speicherweg aufeinander.
 *
 * Gelesen wird IMMER frisch (`werte()` je Zugriff): ein einmal gebautes Objekt
 * saehe nach der ersten Aenderung veraltete Werte, und der Diff-Gate-Vergleich
 * fiele dann stumm aus — der Hub speicherte die vorletzte Fassung.
 * Geschrieben wird ausschliesslich vom diff-basierten Rollback
 * (`rollbackWetterMetrikenSnapshot`) — `setzen` meldet das an den Halter des
 * Zustands weiter; kein Bedienelement schreibt hierueber.
 *
 * Wie `corridorZustandsBruecke`/`versandZustandsBruecke` braucht es hier KEINE
 * Namensumleitung: die zehn Felder heissen im Speicherweg genauso wie die
 * Wertprops.
 *
 * PLATZIERUNG unterhalb Zeile 534 ist Pflicht, keine Vorliebe (Spec, Auflage
 * A1): weiter oben verschoebe sie den eingefrorenen Ratschen-Eintrag
 * `weather-metrics-tab/weatherMetricsCompareSave.ts:534` nach unten.
 */
export function wetterMetrikenZustandsBruecke(
	werte: () => Record<string, unknown>,
	setzen?: (feld: string, wert: unknown) => void
): WetterMetrikenZustand {
	return new Proxy({} as WetterMetrikenZustand, {
		get: (_ziel, feld) => werte()[feld as string],
		set: (_ziel, feld, wert) => {
			setzen?.(feld as string, wert);
			return true;
		}
	});
}
