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

import type { ActivityProfile, ChannelLayouts, ComparePreset, Corridor } from '../../types.ts';
import type { IdealRange } from './compareMetricDefs.ts';
import { buildComparePresetSavePayload } from './compareEditorSave.ts';
import { rehydrateActiveMetrics } from './compareEditorLoad.ts';
import type { CompareStatus } from './subscriptionHelpers.ts';
import { computePauseToggle } from './subscriptionHelpers.ts';

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
export function hydrateWizardStateFromPreset(preset: ComparePreset): HubWizardFields {
	const displayConfig = (preset.display_config as Record<string, unknown>) ?? {};
	const rehydrated = rehydrateActiveMetrics(displayConfig.active_metrics as string[] | undefined);
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
	metricAlertLevels?: Record<string, string>;
	// Issue #1256 Scheibe 7 (AC-35/AC-36): Versand-Felder, analog Round-Trip-
	// Prinzip — undefined = unangetastet, endDate zusaetzlich null-faehig
	// (Loesch-Sentinel "bis auf Weiteres", #1232-Kontext).
	sendTelegram?: boolean;
	sendSms?: boolean;
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
		channelLayouts: (displayConfig.channel_layouts as ChannelLayouts) ?? null,
		activeMetricKeys: edit.activeMetricKeys ?? (displayConfig.active_metrics as string[] | undefined),
		metricAlertLevels:
			edit.metricAlertLevels ?? (displayConfig.metric_alert_levels as Record<string, string> | undefined),
		corridors: edit.corridors ?? preset.corridors,
		// Issue #1256 Scheibe 7: Versand-Felder 1:1 durchreichen — undefined
		// bleibt undefined (Round-Trip aus `preset` via buildComparePresetSavePayload),
		// endDate: null wird NICHT auf undefined gemappt (Loesch-Sentinel, #1232).
		sendTelegram: edit.sendTelegram,
		sendSms: edit.sendSms,
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
		radarAlertEnabled: edit.radarAlertEnabled
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
}

/**
 * Issue #1258 Scheibe 5 (AC-19, AC-29): Erst-Oeffnungs-Hydration fuer den
 * Hub-Alarme-Tab — mutiert `state` DIREKT (analog dem lazy `alarme`-Effekt in
 * CompareTabs.svelte, H3), OHNE eine vorherige `hydrateWizardStateFromPreset`-
 * oder `hydrateVersandFieldsFromPreset`-Hydration vorauszusetzen. Der Alarme-
 * Tab kann als ERSTER Tab geoeffnet werden (Deep-Link `?tab=alarme`) — deshalb
 * hydriert diese Funktion ALLE alarm-relevanten Felder eigenstaendig, inkl.
 * `corridors` (H4: `notifyCount` braucht Korridore auch ohne vorherigen
 * idealwerte-Effekt).
 *
 * Fallbacks 1:1 analog `AlarmeTab.svelte:80-90` bzw. Trip-Pipeline
 * (trip_alert.py): `officialWarningsEnabled` faellt auf
 * `official_alert_triggers_enabled !== false` zurueck, wenn `official_warnings`
 * fehlt (Legacy-Kompatibilitaet).
 */
export function hydrateAlarmFieldsFromPreset(state: AlarmHydrationTarget, preset: ComparePreset): void {
	const displayConfig = (preset.display_config as Record<string, unknown>) ?? {};
	state.officialAlertsEnabled = preset.official_alerts_enabled ?? true;
	state.officialWarningsEnabled =
		preset.official_warnings?.enabled ?? preset.official_alert_triggers_enabled !== false;
	state.radarAlertEnabled = preset.radar_alert_enabled ?? false;
	state.metricAlertLevels = (displayConfig.metric_alert_levels as Record<string, string>) ?? {};
	state.alertCooldownMinutes = preset.alert_cooldown_minutes;
	state.alertQuietFrom = preset.alert_quiet_from;
	state.alertQuietTo = preset.alert_quiet_to;
	state.corridors = preset.corridors ?? [];
}

/** Plain-Snapshot der 6 persistenzrelevanten Alarme-Tab-Felder (analog
 * `VersandSnapshot`). `corridors` ist bewusst NICHT Teil des Snapshots — die
 * Korridor-Persistenz bleibt exklusiv beim Idealwerte-Tab (`CorridorSnapshot`),
 * der Alarme-Tab liest `corridors` nur lesend fuer `notifyCount` (H4). */
export interface AlarmSnapshot {
	officialAlertsEnabled: boolean;
	officialWarningsEnabled: boolean;
	radarAlertEnabled: boolean;
	metricAlertLevels: Record<string, string>;
	alertCooldownMinutes?: number;
	alertQuietFrom?: string;
	alertQuietTo?: string;
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
		alertQuietTo: current.alertQuietTo
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
		'alertQuietTo'
	];
	const target = state as Record<string, unknown>;
	for (const field of fields) {
		if (JSON.stringify(target[field]) === JSON.stringify(attempted[field])) {
			target[field] = before[field];
		}
	}
}
