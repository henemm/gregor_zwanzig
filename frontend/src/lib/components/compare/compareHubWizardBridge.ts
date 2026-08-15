// Issue #1256 Scheibe 6 — Hub-Wizard-Bridge fuer den eingebetteten
// CorridorEditor (context="vergleich") im Hub-Idealwerte-Tab.
//
// Spec: docs/specs/modules/issue_1256_compare_ui_rewire.md § Scheibe 6
//   (AC-16, AC-33, AC-34), Edge Case Z.1020 (PUT-Fehler -> Rollback).
// Context: docs/context/feat-1256-s6-hub-idealwerte-inline.md § Entscheidung 1+3.
//
// `CorridorEditor.svelte` liest im vergleich-Kontext GENAU 6 Felder aus
// `getContext('compare-wizard-state')` (Z.41-113). Diese Datei extrahiert die
// Teil-Hydration + Persistenz-Uebersetzung, die bislang nur inline in
// routes/compare/[id]/edit/+page.svelte existierte — 0 Zeilen Diff im
// Organism selbst (C0).
//
// Kein Browser-/SvelteKit-Import — lauffaehig unter node --experimental-strip-types.

import type { ActivityProfile, ComparePreset, Corridor } from '../../types.ts';
import type { IdealRange } from '../shared/corridor-editor/corridorEditorState.ts';
import { buildComparePresetSavePayload } from './compareEditorSave.ts';
import { rehydrateActiveMetrics } from './compareEditorLoad.ts';
// Issue #1703 Scheibe 8: kanal-eigene Auswahl der Uebersichtstabelle.
import type { CompareChannelActiveMetrics } from '../shared/weather-metrics-tab/compareChannelMetricLayouts.ts';
// Issue #1373 (S2 Scheibe B, AC-12): dieselbe Lesenormalisierung wie im
// Lade-Pfad — Alt- UND Neuformat der gespeicherten Metrik-Auswahl.
import {
	normalizeStoredActiveMetrics,
	registeredCompareMetricCatalog,
	type CompareSelectionEntry
} from '../shared/weather-metrics-tab/compareMetricSelection.ts';
import type { CompareStatus } from './subscriptionHelpers.ts';
import { computePauseToggle } from './subscriptionHelpers.ts';
import { hydrateWeatherMetricsFromPreset } from '../shared/weather-metrics-tab/weatherMetricsCompareSave.ts';

/** Plain-Objekt mit GENAU den 6 Feldern, die CorridorEditor.svelte im
 * vergleich-Kontext aus dem Wizard-State liest. Die Bridge-Komponente
 * (CompareTabs.svelte) uebertraegt dies auf eine echte CompareWizardState-
 * Instanz und ruft setContext(...). */
export interface HubWizardFields {
	isEditMode: true;
	corridors: Corridor[];
	activityProfile: ActivityProfile | null;
	idealRanges: Record<string, IdealRange>;
	// #1191-Semantik (rehydrateActiveMetrics): null = "Feld fehlte im Preset"
	// (Signal fuer Profil-Default-Pfad), NIEMALS still als [] getarnt.
	activeMetricKeys: string[] | null;
	metricAlertLevels: Record<string, string>;
}

/**
 * Teil-Hydration der 6 CorridorEditor-Felder aus einem ComparePreset.
 * isEditMode ist immer true — der Hub mountet den Organism wie den Editor.
 */
export function hydrateWizardStateFromPreset(
	preset: ComparePreset,
	// Issue #1373 (S2 Scheibe B, Fix-Runde 1): geladene Katalogantwort — ohne sie
	// bliebe eine im Format Größe + Auswertung gespeicherte Auswahl unaufgelöst,
	// und das ✕-Entfernen einer Metrik-Zeile im Idealwerte-Reiter träfe sie nicht
	// mehr (`activeSet.delete(key)` in buildCompareCorridorSavePayload).
	catalog: CompareSelectionEntry[] = registeredCompareMetricCatalog()
): HubWizardFields {
	const displayConfig = (preset.display_config as Record<string, unknown>) ?? {};
	const rehydrated = rehydrateActiveMetrics(displayConfig.active_metrics, catalog);
	return {
		isEditMode: true,
		corridors: preset.corridors ?? [],
		activityProfile: (preset.profil as ActivityProfile) ?? null,
		idealRanges: (displayConfig.ideal_ranges as Record<string, IdealRange>) ?? {},
		activeMetricKeys: rehydrated ? rehydrated.activeMetricKeys : null,
		metricAlertLevels: (displayConfig.metric_alert_levels as Record<string, string>) ?? {}
	};
}

/** Teil-Edit fuer den Hub: nur die Felder, die eine Nutzeraktion tatsaechlich
 * veraendert hat, werden geliefert — alle anderen kommen per Read-Modify-Write
 * unveraendert aus `preset` (#1257/#1234-Kontext: metric_alert_levels und
 * active_metrics duerfen nie stillschweigend verloren gehen). */
export interface HubEdit {
	corridors?: Corridor[];
	pickedIds?: string[];
	idealRanges?: Record<string, IdealRange>;
	activeMetricKeys?: string[];
	// Issue #1703 Scheibe 8: kanal-eigene Auswahl der Uebersichtstabelle.
	// undefined = nicht editiert -> Round-Trip via `preset.display_config`
	// (der RMW-Merge in buildComparePresetSavePayload laeuft dann gar nicht).
	channelActiveMetricKeys?: CompareChannelActiveMetrics;
	metricAlertLevels?: Record<string, string>;
	// Issue #1256 Scheibe 7 (AC-35/AC-36): Versand-Felder, analog Round-Trip-
	// Prinzip — undefined = unangetastet, endDate zusaetzlich null-faehig
	// (Loesch-Sentinel "bis auf Weiteres", #1232-Kontext).
	sendTelegram?: boolean;
	sendSms?: boolean;
	// Issue #1745 A (Landmine 3): DIESE Feldliste ist die zweite Kodierung neben
	// buildComparePresetSavePayload — fehlt der Kanal hier, geht der Haken beim
	// naechsten Hub-Speichern verloren.
	sendPremiumSms?: boolean;
	morningEnabled?: boolean;
	morningTime?: string;
	eveningEnabled?: boolean;
	eveningTime?: string;
	endDate?: string | null;
	alertCooldownMinutes?: number;
	alertQuietFrom?: string;
	alertQuietTo?: string;
	// Issue #1258 S5 (AC-19/AC-29): S4-Known-Gap geschlossen — bislang kannte
	// die Hub-Bridge nur metricAlertLevels/Cooldown/Quiet, nicht die drei
	// amtliche-Warnungen-/Radar-Felder. officialWarnings NUR {enabled} — `sources`
	// wird vom FE NIEMALS gesendet (F001-Lehre aus S4, Context Zeile 32).
	officialAlertsEnabled?: boolean;
	officialWarnings?: { enabled: boolean };
	radarAlertEnabled?: boolean;
	// Issue #1260: Telegram-Kurzstil (display_config.telegram_style). undefined =
	// nicht editiert → Round-Trip via `preset.display_config`.
	telegramStyle?: 'rich' | 'kurzform';
	// Issue #1299/C2: Stundenverlauf-Felder, bisher NIE über den Hub-Pfad
	// geschrieben (nur über den weggeleiteten wizardState.saveComparePreset()).
	// Issue #1366 F001: `null` = „nie eingestellt" (Editor-Zustand unangetastet).
	hourlyMetricKeys?: string[] | null;
	hourlyEnabled?: boolean;
	// Issue #1361/#1372 S1b: gemeinsames Tagesfenster. undefined = nicht
	// editiert -> Round-Trip via `preset.day_window_start_hour/_end_hour`.
	dayWindowStartHour?: number;
	dayWindowEndHour?: number;
	// Issue #1361 Befund 2/#1368: Ausblick-Auswahl + Schalter.
	outlookMetricKeys?: string[] | null;
	outlookEnabled?: boolean;
	// Issue #1461 S3b-2b: Kanal-Schwelle, TOP-LEVEL Feld (Go-Model
	// ComparePreset.AlertChannelThresholds), analog metricAlertLevels.
	channelThresholds?: Record<string, string>;
}

/**
 * Duenner Adapter um `buildComparePresetSavePayload`: hydratisiert die
 * required-Felder der Editor-Edits aus `preset`, ueberschreibt sie nur dort,
 * wo `edit` tatsaechlich einen neuen Wert liefert.
 */
export function buildHubPutPayload(
	preset: ComparePreset,
	edit: HubEdit
): { url: string; body: ComparePreset } {
	const displayConfig = (preset.display_config as Record<string, unknown>) ?? {};
	return buildComparePresetSavePayload(preset, {
		name: preset.name,
		activityProfile: (preset.profil as ActivityProfile) ?? null,
		pickedIds: edit.pickedIds ?? preset.location_ids ?? [],
		region: (displayConfig.region as string) ?? '',
		idealRanges: edit.idealRanges ?? (displayConfig.ideal_ranges as Record<string, IdealRange>) ?? {},
		// Issue #1373 (S2 Scheibe B, AC-12 — Datenverlust-Pfad): der
		// Bestandsrueckfall (Nutzer bearbeitet einen ANDEREN Reiter, also ist
		// edit.activeMetricKeys undefined) reichte bisher den ROHEN gespeicherten
		// Wert weiter. Seit dem Formatwechsel sind das Objekte, die als string[]
		// deklariert in die Schreibfunktion laufen wuerden — Ergebnis: beschaedigte
		// Metrik-Auswahl beim Speichern eines voellig anderen Reiters. Der Rueckfall
		// laeuft deshalb durch DIESELBE Lesenormalisierung wie rehydrateActiveMetrics();
		// `null` (kein Array / Feld fehlt) wird zu undefined, damit
		// buildComparePresetSavePayload den Key wie bisher unangetastet
		// round-trippt (#1191: fehlend != []).
		activeMetricKeys: edit.activeMetricKeys ?? normalizeStoredActiveMetrics(displayConfig.active_metrics) ?? undefined,
		// Issue #1703 Scheibe 8: KEIN Bestandsrueckfall wie bei activeMetricKeys —
		// undefined bleibt undefined. Der gespeicherte Stand round-trippt dann
		// unangetastet ueber `...restDisplayConfig`; ein hier gebauter Rueckfall
		// wuerde denselben Wert nur unnoetig durch die Schreibuebersetzung jagen.
		channelActiveMetricKeys: edit.channelActiveMetricKeys,
		metricAlertLevels:
			edit.metricAlertLevels ?? (displayConfig.metric_alert_levels as Record<string, string> | undefined),
		// Issue #1461 S3b-2b: 1:1 Round-Trip wie alle anderen HubEdit-Felder,
		// TOP-LEVEL (nicht in display_config), undefined bleibt undefined.
		channelThresholds:
			edit.channelThresholds ??
			(preset.alert_channel_thresholds as Record<string, string> | undefined),
		corridors: edit.corridors ?? preset.corridors,
		// Issue #1256 Scheibe 7: Versand-Felder 1:1 durchreichen — undefined
		// bleibt undefined (Round-Trip aus `preset` via buildComparePresetSavePayload),
		// endDate: null wird NICHT auf undefined gemappt (Loesch-Sentinel, #1232).
		sendTelegram: edit.sendTelegram,
		sendSms: edit.sendSms,
		// Issue #1745 A (Landmine 3): 1:1 durchreichen wie die Geschwister —
		// undefined bleibt undefined (Round-Trip aus `preset`).
		sendPremiumSms: edit.sendPremiumSms,
		morningEnabled: edit.morningEnabled,
		morningTime: edit.morningTime,
		eveningEnabled: edit.eveningEnabled,
		eveningTime: edit.eveningTime,
		endDate: edit.endDate,
		alertCooldownMinutes: edit.alertCooldownMinutes,
		alertQuietFrom: edit.alertQuietFrom,
		alertQuietTo: edit.alertQuietTo,
		// Issue #1258 S5: S4-Known-Gap geschlossen — 1:1 Round-Trip wie alle
		// anderen HubEdit-Felder, undefined bleibt undefined.
		officialAlertsEnabled: edit.officialAlertsEnabled,
		officialWarnings: edit.officialWarnings,
		radarAlertEnabled: edit.radarAlertEnabled,
		// Issue #1260: 1:1 Round-Trip wie alle anderen HubEdit-Felder, undefined
		// bleibt undefined (kein Datenverlust am telegram_style).
		telegramStyle: edit.telegramStyle,
		// Issue #1299/C2: Lücke geschlossen — bislang kannte buildHubPutPayload
		// diese beiden Felder nicht, obwohl buildComparePresetSavePayload sie
		// laengst verarbeitet (compareEditorSave.ts:104-111,142).
		hourlyMetricKeys:
			edit.hourlyMetricKeys ?? (displayConfig.hourly_metrics as string[] | null | undefined),
		hourlyEnabled: edit.hourlyEnabled ?? preset.hourly_enabled,
		// Issue #1361/#1368: analog hourlyMetricKeys — der Bestandsrueckfall
		// (anderer Reiter bearbeitet) laeuft durch DIESELBE Lesenormalisierung,
		// sonst liefen die gespeicherten Groesse-Auswertung-Objekte als
		// string[] deklariert in die Schreibfunktion (#1373-Datenverlustpfad).
		// `null` -> undefined, damit der Key unangetastet round-trippt.
		outlookMetricKeys:
			edit.outlookMetricKeys ??
			normalizeStoredActiveMetrics(displayConfig.outlook_metrics) ??
			undefined,
		outlookEnabled: edit.outlookEnabled ?? preset.outlook_enabled,
		// Issue #1361/#1372 S1b: 1:1 Round-Trip wie alle anderen HubEdit-Felder.
		dayWindowStartHour: edit.dayWindowStartHour ?? preset.day_window_start_hour ?? undefined,
		dayWindowEndHour: edit.dayWindowEndHour ?? preset.day_window_end_hour ?? undefined
	});
}

/**
 * Deep-Copy-Helfer fuer den Prae-Aktions-Zustand (Edge Case Z.1020, Rollback
 * bei PUT-Fehler). JSON-Rundreise statt structuredClone, damit Svelte-$state-
 * Proxies zuverlaessig in ein reines, unabhaengiges Objekt entpackt werden.
 */
export function snapshotForRollback<T>(value: T): T {
	return JSON.parse(JSON.stringify(value)) as T;
}

/** Plain-Snapshot der 4 persistenzrelevanten CorridorEditor-Felder (Teilmenge
 * von HubWizardFields ohne isEditMode/activityProfile, die der Idealwerte-Tab
 * nicht schreibt). */
export interface CorridorSnapshot {
	corridors: Corridor[];
	idealRanges: Record<string, IdealRange>;
	activeMetricKeys: string[];
	metricAlertLevels: Record<string, string>;
}

/**
 * Issue #1256 Scheibe 6 Fix-Loop 1 (F002, Adversary HIGH): reine
 * Diff-/Payload-Entscheidung fuer den Idealwerte-Tab-Commit, entkoppelt vom
 * DOM-Event, das ihn ausloest (Wrapper-Bubbling ODER Fenster-Ebene) — beide
 * Aufrufer rufen dieselbe Funktion, damit ein Pointer-Release ausserhalb des
 * Wrapper-Subtrees (z. B. bei einem Band-Handle-Drag) nicht mehr zu einem
 * uebersehenen Commit fuehrt.
 * Liefert `null`, wenn sich der persistenzrelevante Ausschnitt seit dem
 * letzten persistierten Snapshot NICHT veraendert hat (Waechter gegen
 * unnoetige PUTs, #1234-Kontext) — sonst den fertigen PUT-Payload.
 */
export function flushPendingCorridorSave(
	preset: ComparePreset,
	current: CorridorSnapshot,
	before: CorridorSnapshot | null
): { url: string; body: ComparePreset } | null {
	const baseline = before ?? current;
	if (JSON.stringify(current) === JSON.stringify(baseline)) return null;
	return buildHubPutPayload(preset, {
		corridors: current.corridors,
		idealRanges: current.idealRanges,
		activeMetricKeys: current.activeMetricKeys,
		metricAlertLevels: current.metricAlertLevels
	});
}

/**
 * Issue #1256 Scheibe 6 Fix-Loop 2 (F006, Adversary MEDIUM): reine
 * Entscheidungslogik fuer den fenster-weiten Pointerup-Flush-Guard
 * (`<svelte:window onpointerup>` in CompareTabs.svelte, F002-Fix aus Fix-Loop 1)
 * — herausgezogen aus dem Svelte-Handler, damit sie ohne DOM/Browser testbar
 * ist. Der Svelte-Handler `handleWindowPointerUp` wird dadurch zu einer
 * 1-Zeilen-Delegation; die untestbare Flaeche schrumpft auf diese Zeile.
 * Flush nur, wenn der Idealwerte-Tab aktiv UND bereits hydratisiert ist
 * (sonst gibt es keinen sinnvollen `wizardState`-Stand zum Speichern).
 */
export function shouldFlushOnWindowPointerUp(activeTab: string, idealwerteHydrated: boolean): boolean {
	return activeTab === 'idealwerte' && idealwerteHydrated;
}

/**
 * Issue #1256 Scheibe 6 Fix-Loop 3 (F007, Adversary CRITICAL): reine
 * Payload-Konstruktion fuer den Uebersicht-Tab-Pausieren/Aktivieren-Pfad
 * (`handleToggleActive` in CompareTabs.svelte) — bislang der einzige der
 * drei Hub-PUT-Pfade, der noch die eingefrorene `preset`-Prop statt der
 * laufend aktuellen `currentPreset`-Baseline spread'te (identischer Bug wie
 * F005 fuer die Orte-/Idealwerte-Pfade, hier fuer einen dritten,
 * vorbestehenden Pfad). Analog `flushPendingCorridorSave`: reine Funktion,
 * kein DOM/Browser-Bezug, der Svelte-Handler bleibt eine duenne Delegation.
 */
export function buildToggleActivePutPayload(
	preset: ComparePreset,
	schedule: string,
	previousSchedule: string
): { url: string; body: ComparePreset } {
	return {
		url: `/api/compare/presets/${preset.id}`,
		body: { ...preset, schedule, previous_schedule: previousSchedule }
	};
}

/**
 * Issue #1259 (Read-Modify-Write): Payload-Bau fuer den Vergleichs-LISTEN-
 * Kebab "Pausieren/Aktivieren" — analog `buildToggleActivePutPayload`, aber
 * mit frisch via `getPreset` geladenem Server-Stand statt der eingefrorenen
 * Listen-Prop. Verhindert stillen Server-Datenverlust, wenn Liste und
 * Detail-Hub desselben Vergleichs gleichzeitig offen sind (Multi-Tab).
 * `getPreset` ist injizierbar (kein hartcodiertes `fetch`) fuer
 * DOM-/Browser-freie Kern-Tests.
 */
export async function buildFreshTogglePutPayload(
	presetId: string,
	getPreset: (id: string) => Promise<ComparePreset>
): Promise<{ url: string; body: ComparePreset }> {
	const fresh = await getPreset(presetId);
	const next = computePauseToggle(fresh);
	return buildToggleActivePutPayload(
		fresh,
		next.schedule,
		next.previous_schedule ?? (fresh.schedule !== 'manual' ? fresh.schedule : 'daily')
	);
}

/** Plain-Snapshot der 10 persistenzrelevanten Versand-Felder (OHNE sendEmail —
 * `ComparePreset` kennt kein `send_email`-Feld, s. `hydrateVersandFieldsFromPreset`). */
export interface VersandSnapshot {
	sendTelegram: boolean;
	sendSms: boolean;
	morningEnabled: boolean;
	morningTime: string;
	eveningEnabled: boolean;
	eveningTime: string;
	endDate: string | null;
	alertCooldownMinutes?: number;
	alertQuietFrom?: string;
	alertQuietTo?: string;
}

/**
 * Issue #1256 Scheibe 7 (AC-35/36): Hydration der Versand-Felder, die der
 * eingebettete `VersandTab context="vergleich"` im Hub aus `wizardState.*`
 * liest. Defaults identisch zur Edit-Routen-Hydration
 * (routes/compare/[id]/edit/+page.svelte:44-61). `sendEmail` ist IMMER true —
 * ComparePreset hat kein `send_email`-Feld (vorbestehende Luecke, Known
 * Limitation der S7-Freigabe).
 */
export function hydrateVersandFieldsFromPreset(preset: ComparePreset): VersandSnapshot & { sendEmail: true } {
	return {
		sendEmail: true,
		sendTelegram: preset.send_telegram ?? false,
		sendSms: preset.send_sms ?? false,
		morningEnabled: preset.morning_enabled ?? true,
		morningTime: (preset.morning_time ?? '06:00').slice(0, 5),
		eveningEnabled: preset.evening_enabled ?? false,
		eveningTime: (preset.evening_time ?? '18:00').slice(0, 5),
		endDate: preset.end_date ?? null,
		alertCooldownMinutes: preset.alert_cooldown_minutes ?? undefined,
		alertQuietFrom: preset.alert_quiet_from ?? undefined,
		alertQuietTo: preset.alert_quiet_to ?? undefined
	};
}

/**
 * Issue #1256 Scheibe 7 (AC-35/36): Event-diskretisierte PUT-Persistenz fuer
 * den Hub-Versand-Tab, analog `flushPendingCorridorSave` — liefert `null`,
 * wenn sich der Versand-Snapshot seit dem letzten persistierten Stand NICHT
 * veraendert hat (Waechter gegen unnoetige PUTs, #1234-Kontext), sonst den
 * fertigen PUT-Payload via `buildHubPutPayload` (Read-Modify-Write: alle
 * nicht-Versand-Felder unveraendert aus `preset`, #1257-Kontext).
 */
export function flushPendingVersandSave(
	preset: ComparePreset,
	current: VersandSnapshot,
	before: VersandSnapshot | null
): { url: string; body: ComparePreset } | null {
	const baseline = before ?? current;
	if (JSON.stringify(current) === JSON.stringify(baseline)) return null;
	return buildHubPutPayload(preset, {
		sendTelegram: current.sendTelegram,
		sendSms: current.sendSms,
		morningEnabled: current.morningEnabled,
		morningTime: current.morningTime,
		eveningEnabled: current.eveningEnabled,
		eveningTime: current.eveningTime,
		endDate: current.endDate,
		alertCooldownMinutes: current.alertCooldownMinutes,
		alertQuietFrom: current.alertQuietFrom,
		alertQuietTo: current.alertQuietTo
	});
}

/** Modell der Hub-Aktivierungs-Karte (Soll: `screen-compare-detail.jsx:273-277`
 * + `:313-325`). Die JSX-active-Copy "im konfigurierten Rhythmus" ist eine
 * timeWindow-Stale-Spur (Spec § Umsetzungsregel) und wird NICHT mitkopiert —
 * ersetzt durch "zu den konfigurierten Zeiten". */
export function hubActivationBanner(status: CompareStatus): {
	statusLabel: string;
	text: string;
	cta: string;
	border: string;
	dotTone: 'good' | 'neutral';
} {
	if (status === 'active') {
		return {
			statusLabel: 'Aktiv',
			text: 'Läuft automatisch — unbegrenzt, bis du pausierst. Das Briefing geht zu den konfigurierten Zeiten in die Kanäle.',
			cta: 'Pausieren',
			border: 'var(--g-good)',
			dotTone: 'good'
		};
	}
	if (status === 'paused') {
		return {
			statusLabel: 'Pausiert',
			text: 'Pausiert. Es geht aktuell kein Briefing raus.',
			cta: 'Aktivieren',
			border: 'var(--g-rule)',
			dotTone: 'neutral'
		};
	}
	return {
		statusLabel: 'Entwurf',
		text: 'Noch nicht aktiv. Sobald Orte, Idealwerte und mindestens ein Kanal stehen, kannst du den Vergleich aktivieren.',
		cta: 'Aktivieren',
		border: 'var(--g-accent)',
		dotTone: 'neutral'
	};
}

export interface PutQueue {
	enqueue<T>(fn: () => Promise<T>): Promise<T>;
}

/**
 * Issue #1256 Scheibe 7 Fix-Loop 1 (F002, Adversary CRITICAL): serialisiert
 * ALLE Hub-PUT-Pfade (Orte/Idealwerte/Versand/Toggle-Active) auf EINE
 * gemeinsame Kette, damit zwei schnell aufeinanderfolgende Nutzeraktionen
 * (z. B. Versand-Aenderung + Aktivieren-Klick im selben Versand-Tab) nie
 * zwei parallele, unsynchronisierte `api.put()`-Aufrufe auf dieselbe
 * Ressource ausloesen — der zweite wuerde sonst mit einer veralteten
 * `currentPreset`-Baseline die Aenderung des ersten still ueberschreiben.
 * Payload-Bau MUSS innerhalb des enqueueten `fn` passieren (nicht davor) —
 * nur so liest ein zweiter, spaeter ausgefuehrter Aufruf den frischen
 * `currentPreset`-Stand aus der PUT-Response des ersten. Ein Fehler in `fn`
 * bricht die Kette NICHT ab (die Kette resettet in jedem Fall auf einen
 * aufgeloesten Zustand), sodass nachfolgende Aufrufe trotzdem laufen.
 */
export function createPutQueue(): PutQueue {
	let tail: Promise<void> = Promise.resolve();
	return {
		enqueue<T>(fn: () => Promise<T>): Promise<T> {
			const run = tail.then(fn);
			tail = run.then(
				() => undefined,
				() => undefined
			);
			return run;
		}
	};
}

/** Ziel-Objekt fuer `hydrateAlarmFieldsFromPreset`: ALLE Felder optional, damit
 * sowohl ein frischer Plain-Objekt-Stub (Kern-Test) als auch die reale
 * `CompareWizardState`-Instanz (CompareTabs.svelte) strukturell passen —
 * eine `Record<string, unknown>`-Signatur waere fuer die Klasseninstanz NICHT
 * zuweisbar (kein Index-Signature), waehrend optionale benannte Felder in
 * beide Richtungen kompatibel sind. */
export interface AlarmHydrationTarget {
	officialAlertsEnabled?: boolean;
	officialWarningsEnabled?: boolean;
	radarAlertEnabled?: boolean;
	metricAlertLevels?: Record<string, string>;
	alertCooldownMinutes?: number;
	alertQuietFrom?: string;
	alertQuietTo?: string;
	corridors?: Corridor[];
	// Issue #1260: Telegram-Kurzstil-Toggle im Hub-Alarme-Tab
	// (display_config.telegram_style). Default "rich".
	telegramStyle?: 'rich' | 'kurzform';
	// Issue #1461 S3b-2b (bestaetigter Speicher-Fehler, s. Spec „Implementation
	// Details"): sendTelegram/sendSms fehlten hier bisher komplett -- eine
	// Kanal-Umschaltung im Alarme-Reiter war deshalb weder als Snapshot-Differenz
	// erkennbar noch im PUT-Body enthalten (der Server-Bestand wurde beim
	// naechsten Alarme-Save aktiv zurueckgeschrieben). Analog channelThresholds.
	sendTelegram?: boolean;
	sendSms?: boolean;
	// Issue #1745 A: der vierte Kanal muss aus demselben Grund mit-hydriert
	// werden — sonst ist eine Aenderung im Alarme-Reiter weder als
	// Snapshot-Differenz erkennbar noch im PUT-Body enthalten.
	sendPremiumSms?: boolean;
	channelThresholds?: Record<string, string>;
	// Issue #1320: activeMetricKeys wird sonst nur von den Hydrations-Effekten
	// der Tabs "wetter-metriken"/"idealwerte" befuellt — fehlt Alarme als
	// Erst-Tab (Deep-Link), zeigt AlarmeTab.svelte faelschlich "keine Metriken".
	// Issue #1366 F002: `string[] | null`, damit `wizardState` (jetzt nullable)
	// strukturell zuweisbar bleibt -- hydrateAlarmFieldsFromPreset schreibt hier
	// ohnehin immer einen konkreten Wert (Zeile unten), nie `null`.
	activeMetricKeys?: string[] | null;
}

/**
 * Issue #1258 Scheibe 5 (AC-19, AC-29): Erst-Oeffnungs-Hydration fuer den
 * Hub-Alarme-Tab — mutiert `state` DIREKT (analog dem lazy `alarme`-Effekt in
 * CompareTabs.svelte, H3), OHNE eine vorherige `hydrateWizardStateFromPreset`-
 * oder `hydrateVersandFieldsFromPreset`-Hydration vorauszusetzen. Der Alarme-
 * Tab kann als ERSTER Tab geoeffnet werden (Deep-Link `?tab=alarme`) — deshalb
 * hydriert diese Funktion ALLE alarm-relevanten Felder eigenstaendig, inkl.
 * `corridors` (H4: der Idealwerte-Tab braucht bereits geladene Korridore,
 * falls er NACH Alarme als zweiter Tab geoeffnet wird).
 *
 * Fallbacks 1:1 analog `AlarmeTab.svelte:80-90` bzw. Trip-Pipeline
 * (trip_alert.py): `officialWarningsEnabled` faellt auf
 * `official_alert_triggers_enabled !== false` zurueck, wenn `official_warnings`
 * fehlt (Legacy-Kompatibilitaet).
 */
export function hydrateAlarmFieldsFromPreset(
	state: AlarmHydrationTarget,
	preset: ComparePreset,
	// Issue #1373 (S2 Scheibe B, Fix-Runde 1): geladene Katalogantwort, nötig zum
	// Auflösen des Speicherformats der Metrik-Auswahl (Größe + Auswertung) in
	// der Zeile unten. Default = bereits registrierter Katalog.
	catalog: CompareSelectionEntry[] = registeredCompareMetricCatalog()
): void {
	const displayConfig = (preset.display_config as Record<string, unknown>) ?? {};
	state.officialAlertsEnabled = preset.official_alerts_enabled ?? true;
	state.officialWarningsEnabled =
		preset.official_warnings?.enabled ?? preset.official_alert_triggers_enabled !== false;
	state.radarAlertEnabled = preset.radar_alert_enabled ?? false;
	state.metricAlertLevels = (displayConfig.metric_alert_levels as Record<string, string>) ?? {};
	// Issue #1461 S3b-2b (Speicher-Bugfix): sendTelegram/sendSms UND die
	// Kanal-Schwelle mit-hydrieren, damit eine Aenderung im Alarme-Reiter als
	// Snapshot-Differenz erkennbar wird (s. AlarmHydrationTarget-Kommentar).
	state.sendTelegram = preset.send_telegram ?? false;
	state.sendSms = preset.send_sms ?? false;
	// Issue #1745 A (D1): fehlt das Feld im Preset, ist der Kostenkanal AUS.
	state.sendPremiumSms = preset.send_premium_sms ?? false;
	state.channelThresholds = (preset.alert_channel_thresholds as Record<string, string>) ?? {};
	state.alertCooldownMinutes = preset.alert_cooldown_minutes;
	state.alertQuietFrom = preset.alert_quiet_from;
	state.alertQuietTo = preset.alert_quiet_to;
	state.corridors = preset.corridors ?? [];
	// Issue #1320: Alarme kann als ERSTER Tab geoeffnet werden — dann hat
	// activeMetricKeys noch keinen Hydrations-Durchlauf vom Wetter-Metriken-/
	// Idealwerte-Tab gesehen. Ohne diese Zeile zeigt die Empfindlichkeits-
	// Tabelle faelschlich "keine Metriken", obwohl das Preset aktive Metriken hat.
	state.activeMetricKeys = hydrateWeatherMetricsFromPreset(preset, catalog);
	// Issue #1260: Kurzstil-Toggle aus display_config.telegram_style hydrieren,
	// Default "rich" (analog CompareEditor). Ohne diese Zeile bliebe der Toggle
	// im Hub-Alarme-Tab dauerhaft auf dem Klasse-Default stehen und ein
	// gespeicherter "kurzform"-Wert waere unsichtbar.
	state.telegramStyle = (displayConfig.telegram_style as 'rich' | 'kurzform') ?? 'rich';
}

/** Plain-Snapshot der 6 persistenzrelevanten Alarme-Tab-Felder (analog
 * `VersandSnapshot`). `corridors` ist bewusst NICHT Teil des Snapshots — die
 * Korridor-Persistenz bleibt exklusiv beim Idealwerte-Tab (`CorridorSnapshot`),
 * der Alarme-Tab liest `corridors` seit #1371 gar nicht mehr (kein
 * "Korridor-Auslöser"-Block mehr). */
export interface AlarmSnapshot {
	officialAlertsEnabled: boolean;
	officialWarningsEnabled: boolean;
	radarAlertEnabled: boolean;
	metricAlertLevels: Record<string, string>;
	alertCooldownMinutes?: number;
	alertQuietFrom?: string;
	alertQuietTo?: string;
	// Issue #1260: Teil des Snapshots, damit ein reiner Kurzstil-Toggle-Klick im
	// Hub-Alarme-Tab als "dirty" erkannt wird und einen PUT ausloest.
	telegramStyle?: 'rich' | 'kurzform';
	// Issue #1461 S3b-2b (Speicher-Bugfix): sendTelegram/sendSms UND die
	// Kanal-Schwelle sind Teil DIESES Snapshots -- der Alarme-Reiter zeigt seit
	// dieser Scheibe den Kanal-Picker (inkl. Telegram/SMS-Schalter), eine dort
	// vorgenommene Aenderung muss deshalb wie jede andere Alarme-Aenderung als
	// Snapshot-Differenz erkennbar sein UND im PUT-Body landen. Optional (wie
	// alertCooldownMinutes u.a.) -- bestehende Snapshot-Fixtures ohne diese
	// Felder bleiben gueltig, `undefined` bedeutet "nicht editiert" (Round-Trip).
	sendTelegram?: boolean;
	sendSms?: boolean;
	// Issue #1745 A: vierter Kanal im Snapshot — ein reiner Premium-SMS-Klick
	// muss als Snapshot-Differenz erkannt werden und einen PUT ausloesen.
	sendPremiumSms?: boolean;
	channelThresholds?: Record<string, string>;
}

/**
 * Issue #1258 Scheibe 5 (AC-19, AC-29): Event-diskretisierte PUT-Persistenz
 * fuer den Hub-Alarme-Tab, analog `flushPendingVersandSave` — liefert `null`,
 * wenn sich der Alarm-Snapshot seit dem letzten persistierten Stand NICHT
 * veraendert hat (Waechter gegen unnoetige PUTs, #1234-Kontext), sonst den
 * fertigen PUT-Payload via `buildHubPutPayload` (Read-Modify-Write: alle
 * nicht-Alarm-Felder unveraendert aus `preset`, #1257-Kontext).
 *
 * `officialWarnings` im Body traegt NIEMALS `sources` (F001-Lehre aus S4,
 * Context Zeile 32) — nur `{ enabled }`, unabhaengig vom Preset-Bestand.
 *
 * Hinweis (H3, Snapshot-Kreuzeffekte): `metricAlertLevels`/`alertCooldown*`/
 * `alertQuiet*` werden auch vom Idealwerte- (`CorridorSnapshot`) bzw.
 * Versand-Snapshot (`VersandSnapshot`) getrackt — der Alarme-Tab ist die
 * ERSTE Ueberlappung zwischen zwei Hub-Snapshots (S5 fuehrt sie ein, es gibt
 * KEIN "vorbestehendes Muster" dafuer). Fuer den ERFOLGS-Pfad ist das
 * unkritisch: jeder Commit-Handler liest `current` IMMER frisch aus dem
 * gemeinsamen `wizardState` (nie aus dem stale `before`) — ein bereits von
 * einem Nachbar-Tab persistiertes Feld wird beim naechsten Flush korrekt
 * mitgesendet, hoechstens ein redundanter Echo-PUT. Fuer den FEHLER-Pfad
 * (Rollback) ist ein pauschales "alles auf `before` zuruecksetzen" dagegen
 * gefaehrlich, weil es einen zwischenzeitlichen Edit eines Nachbar-Tabs im
 * geteilten Feld stumm ueberschreiben wuerde (S5 Fix-Loop 1, F001) — deshalb
 * `rollbackAlarmSnapshot` (diff-basiert, s. u.) statt direkter Feldzuweisung.
 */
export function flushPendingAlarmSave(
	preset: ComparePreset,
	current: AlarmSnapshot,
	before: AlarmSnapshot | null
): { url: string; body: ComparePreset } | null {
	const baseline = before ?? current;
	if (JSON.stringify(current) === JSON.stringify(baseline)) return null;
	return buildHubPutPayload(preset, {
		officialAlertsEnabled: current.officialAlertsEnabled,
		officialWarnings: { enabled: current.officialWarningsEnabled },
		radarAlertEnabled: current.radarAlertEnabled,
		metricAlertLevels: current.metricAlertLevels,
		alertCooldownMinutes: current.alertCooldownMinutes,
		alertQuietFrom: current.alertQuietFrom,
		alertQuietTo: current.alertQuietTo,
		// Issue #1260: Kurzstil in den PUT-Payload — landet via
		// buildComparePresetSavePayload in display_config.telegram_style (RMW).
		telegramStyle: current.telegramStyle,
		// Issue #1461 S3b-2b (Speicher-Bugfix): ohne diese beiden Zeilen wurden
		// die Server-Werte bei jedem Alarme-Save aktiv zurueckgeschrieben (s.
		// AlarmSnapshot-Kommentar).
		sendTelegram: current.sendTelegram,
		sendSms: current.sendSms,
		// Issue #1745 A: ohne diese Zeile schriebe jeder andere Alarme-Save den
		// Server-Bestand des vierten Kanals still zurueck.
		sendPremiumSms: current.sendPremiumSms,
		channelThresholds: current.channelThresholds
	});
}

/**
 * Issue #1258 Scheibe 5 Fix-Loop 1 (F001, Adversary CRITICAL): diff-basierter
 * Rollback fuer den Hub-Alarme-Commit-Fehlerpfad. `AlarmSnapshot` teilt sich
 * drei Felder (`metricAlertLevels`, `alertCooldownMinutes`, `alertQuietFrom/To`)
 * mit dem Idealwerte- bzw. Versand-Snapshot (H3) — ein pauschales
 * `state[f] = before[f]` fuer ALLE Felder wuerde einen Edit, den ein
 * Nachbar-Tab WAEHREND des in-flight PUTs an genau diesem geteilten Feld
 * vorgenommen hat, stumm mit dem alten Wert ueberschreiben (der Nachbar-Edit
 * ging nie ins Netz, es gab keinen fehlgeschlagenen PUT dafuer — trotzdem
 * waere er weg).
 *
 * Deshalb pro Feld: nur zuruecksetzen, wenn der AKTUELLE `state`-Wert noch
 * exakt dem Wert entspricht, den DIESER gescheiterte Commit gesendet hat
 * (`attempted[f]` = der `current`-Snapshot des Commits). Hat ein Nachbar-Tab
 * das Feld zwischenzeitlich veraendert (aktuell !== attempted), bleibt es
 * unangetastet — der fremde Edit ueberlebt, der eigene, gescheiterte Edit
 * wird ehrlich zurueckgerollt (UI wieder deckungsgleich mit Server-Stand).
 * Wertvergleich JSON-stabil (wie der No-Op-Guard oben) fuer `metricAlertLevels`.
 */
export function rollbackAlarmSnapshot(
	state: AlarmHydrationTarget,
	before: AlarmSnapshot,
	attempted: AlarmSnapshot
): void {
	const fields: (keyof AlarmSnapshot)[] = [
		'officialAlertsEnabled',
		'officialWarningsEnabled',
		'radarAlertEnabled',
		'metricAlertLevels',
		'alertCooldownMinutes',
		'alertQuietFrom',
		'alertQuietTo',
		// Issue #1260: der Kurzstil-Toggle rollt bei PUT-Fehler diff-basiert
		// zurueck wie die uebrigen Alarme-Snapshot-Felder.
		'telegramStyle',
		// Issue #1461 S3b-2b (Speicher-Bugfix): rollen bei PUT-Fehler diff-basiert
		// zurueck wie die uebrigen Alarme-Snapshot-Felder.
		'sendTelegram',
		'sendSms',
		// Issue #1745 A: rollt diff-basiert zurueck wie die uebrigen Kanal-Felder.
		'sendPremiumSms',
		'channelThresholds'
	];
	const target = state as Record<string, unknown>;
	for (const field of fields) {
		if (JSON.stringify(target[field]) === JSON.stringify(attempted[field])) {
			target[field] = before[field];
		}
	}
}

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
		// Issue #1361/#1368: `outlook_metrics` liegt im NEUFORMAT (Groesse +
		// Auswertung) -- dieselbe Lesenormalisierung wie `active_metrics`
		// (#1373), damit die Bedienflaeche Auswahl-Schluessel sieht. Der
		// Aufrufer muss die Katalogantwort abwarten (sonst Rohform, s.
		// hydrateWeatherMetricsFromPreset).
		outlookMetricKeys: normalizeStoredActiveMetrics(displayConfig.outlook_metrics, catalog),
		outlookEnabled: preset.outlook_enabled ?? true
	};
}

/**
 * Issue #1299/C2: Event-diskretisierte PUT-Persistenz fuer den Hub-Layout-Tab,
 * analog `flushPendingVersandSave` — liefert `null`, wenn sich der Snapshot
 * seit dem letzten persistierten Stand NICHT veraendert hat (Waechter gegen
 * unnoetige PUTs), sonst den fertigen PUT-Payload via `buildHubPutPayload`
 * (Read-Modify-Write: alle nicht-Layout-Felder unveraendert aus `preset`).
 *
 * Issue #1361 (S1-Rest von Epic #1372, Adversary-Fund BROKEN, loest die
 * #1299-Altregel ab): `hourlyMetricKeys` wurde HIER frueher sortiert
 * verglichen ("Array-Reihenfolge darf den Diff-Waechter nicht faelschlich
 * dirty melden"). Das war richtig, SOLANGE die Reihenfolge bedeutungslos war.
 * Seit #1335 Scheibe 1 folgt der Renderer (`_visible_hour_metrics`,
 * compare_html.py:610-623) exakt der gespeicherten Reihenfolge — eine reine
 * Ziehgeste (gleiche Menge an Keys, neue Reihenfolge) MUSS also als Aenderung
 * zaehlen. Mit sortiertem Vergleich lieferte diese Funktion bei einer
 * Umsortierung `null`, `CompareTabs.svelte` sendete keinen PUT, meldete aber
 * trotzdem "gespeichert" — die neue Reihenfolge ging beim naechsten Reload
 * verloren. Deshalb jetzt positionssensitiver Vergleich (KEIN `sort()` mehr
 * auf `hourlyMetricKeys`); "identischer Snapshot -> null" bleibt fuer echte
 * Identitaet richtig, nur die Gleichsetzung "umsortiert = identisch" entfaellt.
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
		// Issue #1361/#1368: MUSS im Diff stehen — ein Waechter, der die neuen
		// Felder nicht kennt, meldet "nichts geaendert" und der Ausblick bliebe
		// unspeicherbar (bekannte Falle, s. Dirty-Check-Erfahrung #1373).
		outlookMetricKeys: s.outlookMetricKeys == null ? null : [...s.outlookMetricKeys],
		outlookEnabled: s.outlookEnabled
	});
	if (JSON.stringify(norm(current)) === JSON.stringify(norm(baseline))) return null;
	return buildHubPutPayload(preset, {
		hourlyMetricKeys: current.hourlyMetricKeys,
		hourlyEnabled: current.hourlyEnabled,
		outlookMetricKeys: current.outlookMetricKeys,
		outlookEnabled: current.outlookEnabled
	});
}

/**
 * Issue #1299/C2 (AC-6): Rollback fuer den Hub-Layout-Commit-Fehlerpfad.
 * `hourlyMetricKeys`/`hourlyEnabled` sind EXKLUSIV Layout-Tab-Eigentum (anders
 * als die H3-Kreuzeffekt-Felder im Alarme-Snapshot) — direkte Zuweisung
 * genuegt, kein diff-basierter Rollback noetig.
 */
export function rollbackLayoutSnapshot(
	state: {
		hourlyMetricKeys?: string[] | null;
		hourlyEnabled?: boolean;
		outlookMetricKeys?: string[] | null;
		outlookEnabled?: boolean;
	},
	before: LayoutSnapshot
): void {
	state.hourlyMetricKeys = before.hourlyMetricKeys;
	state.hourlyEnabled = before.hourlyEnabled;
	state.outlookMetricKeys = before.outlookMetricKeys ?? null;
	state.outlookEnabled = before.outlookEnabled ?? true;
}
