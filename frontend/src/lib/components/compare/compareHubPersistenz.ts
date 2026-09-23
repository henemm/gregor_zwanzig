// Issue #2276 Scheibe S6f (Epic #2345) — Persistenz-Haelfte der aufgeloesten
// Compare-Hub-Klebeschicht (Issue #1256 Scheibe 6/7). Alles, was einen
// Hub-PUT baut oder serialisiert: Orte-/Idealwerte-Teil-Edit
// (`buildHubPutPayload`), Toggle-Active (Hub UND Liste), Rollback-Snapshot,
// Aktivierungs-Banner-Text und die geteilte Schreibschlange `hubPutQueue`
// (F1: Payload-Bau bleibt im `enqueue()`-Closure, s. Spec
// Design-Entscheidung 4).
//
// Spec: docs/specs/modules/rework_2276_s6f_bridge_umzug.md — AC-1
//
// Funktionskoerper/JSDoc byte-identisch aus der aufgeloesten Bridge
// uebernommen — reiner Umzug, kein Verhalten geaendert.
//
// Kein Browser-/SvelteKit-Import — lauffaehig unter node --experimental-strip-types.
//
// gz-eigenstaendig: Compare-Hub-Orchestrierung (ComparePreset-PUT/-Hydration fuer CompareTabs.svelte), reiner Umzug der aufgeloesten Compare-Klebeschicht; kein Trip-Pendant (Spec rework_2276_s6f_bridge_umzug.md)

import type { ActivityProfile, ComparePreset, Corridor } from '../../types.ts';
import type { IdealRange } from '../shared/corridor-editor/corridorEditorState.ts';
import { buildComparePresetSavePayload } from './compareEditorSave.ts';
// Issue #1703 Scheibe 8: kanal-eigene Auswahl der Uebersichtstabelle.
import type { CompareChannelActiveMetrics } from '../shared/weather-metrics-tab/compareChannelMetricLayouts.ts';
// Issue #1373 (S2 Scheibe B, AC-12): dieselbe Lesenormalisierung wie im
// Lade-Pfad — Alt- UND Neuformat der gespeicherten Metrik-Auswahl.
import {
	normalizeStoredActiveMetrics,
	normalizeStoredOutlookMetrics
} from '../shared/weather-metrics-tab/compareMetricSelection.ts';
import type { CompareStatus } from './subscriptionHelpers.ts';
import { computePauseToggle } from './subscriptionHelpers.ts';

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
	// Issue #2049: Roh/Einfach je Ausblick-Groesse.
	outlookMetricFormats?: Record<string, boolean> | null;
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
			normalizeStoredOutlookMetrics(displayConfig.outlook_metrics) ??
			undefined,
		// Issue #2049: analog outlookMetricKeys -- `null` -> undefined, damit
		// der Schluessel bei "nie eingestellt" unangetastet round-trippt.
		outlookMetricFormats:
			edit.outlookMetricFormats ??
			(displayConfig.outlook_metric_formats as Record<string, boolean> | undefined) ??
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

/**
 * Issue #1256 Scheibe 6 Fix-Loop 3 (F007, Adversary CRITICAL): reine
 * Payload-Konstruktion fuer den Uebersicht-Tab-Pausieren/Aktivieren-Pfad
 * (`handleToggleActive` in CompareTabs.svelte) — bislang der einzige der
 * drei Hub-PUT-Pfade, der noch die eingefrorene `preset`-Prop statt der
 * laufend aktuellen `currentPreset`-Baseline spread'te (identischer Bug wie
 * F005 fuer die Orte-/Idealwerte-Pfade, hier fuer einen dritten,
 * vorbestehenden Pfad). Reine Funktion,
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
