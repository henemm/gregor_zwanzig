<script lang="ts">
	// AlarmeTab — Issue #1258 Scheibe S2: geteilter Alarme-Organism (Trip UND
	// Compare), EIN Baustein fuer context="route"|"vergleich". Buendelt die
	// gesamte Alert-Zustellung, die bisher im Versand-Tab (route) bzw. in
	// CompareAlarmSection (vergleich) lag. Vorbild: shared/VersandTab.svelte
	// (context-Prop + Persistenz-Weiche, buildAlertDeliverySaveFn()-Muster
	// :209-260).
	//
	// UNGEWIRED in dieser Scheibe (S2) — keine Flaeche bindet AlarmeTab ein.
	// Wiring folgt in S3 (Trip) und S4/S5 (Compare).
	//
	// Abschnittsreihenfolge kommt aus alarmeTabSections(context) und wird
	// tatsaechlich zum Rendern genutzt (kein Duplikat der Reihenfolge im
	// Markup) — das garantiert AC-9 strukturell.
	//
	// Spec: docs/specs/modules/issue_1258_alarme_tab_official_warnings.md
	//   (AC-9 .. AC-12, Implementation Details Abschnitt 4/5)

	import { onMount, untrack } from 'svelte';
	import { api } from '$lib/api';
	import { baueTripSpeicherung } from './tripSpeicherung.ts';
	// Issue #2276 S2: Speicherweg des vergleich-Zweigs (kein Laufzeit-Import aus compare/, AC-9).
	import {
		alarmSnapshotAus,
		alarmZustandsBruecke,
		erstelleAlarmeVergleichSpeicherung
	} from './alarmeVergleichSpeicherung.ts';
	import { Eyebrow } from '$lib/components/atoms';
	import type { Trip, AlertMetric, SensLevel, ComparePreset } from '$lib/types';
	import type { SaveStatus } from '$lib/stores/saveStatusStore.svelte';
	import ChannelToggle from '$lib/components/shared/ChannelToggle.svelte';
	import TelegramKurzstilToggle from '$lib/components/shared/TelegramKurzstilToggle.svelte';
	import AlertCooldownCard from '$lib/components/alerts-tab/AlertCooldownCard.svelte';
	import AlertQuietHoursCard from '$lib/components/alerts-tab/AlertQuietHoursCard.svelte';
	import AlertPreviewCard from '$lib/components/alerts-tab/AlertPreviewCard.svelte';
	import AlertMetricLevelTable from '$lib/components/alerts-tab/AlertMetricLevelTable.svelte';
	import VTAlertSample from './versand-tab/VTAlertSample.svelte';
	import AlertChannelPicker from './AlertChannelPicker.svelte';
	import {
		alarmeTabSections,
		triggerGroupHeading,
		type AlarmeContext
	} from './alarme-tab/alarmeTabSections.ts';
	import {
		resolveAlertChannels,
		type AlertChannelState,
		type ChannelKind
	} from './alarme-tab/alertChannelState.ts';
	import {
		applyThresholdChange,
		resolveAlertChannelThresholds,
		type AlertChannelThresholdState,
		type ChannelThreshold
	} from './alarme-tab/alertChannelState.ts';
	import { buildAlarmeDeliveryPayload } from './alarme-tab/alarmeDeliveryPayload.ts';
	import { derivePremiumSmsAlarmGate } from './alarme-tab/premiumSmsAlarmGate.ts';
	// Feature #1435 E1a-2: die Alarm-Zeilen kommen aus dem zentralen Register
	// (Katalog-Feld `alertMetric`), nicht mehr aus der geloeschten Frontend-
	// Liste compareMetricMapping.ts.
	// Feature #1435 E1b: gewaehlte Groessen ohne Alarm werden benannt statt
	// kommentarlos weggelassen — dieselbe Quelle, derselbe Katalog-Prop.
	import {
		deriveActiveAlertMetricsFromCatalog,
		deriveUnalertableSelectedMetricNames
	} from './alarme-tab/activeAlertMetricsFromCatalog.ts';
	import type { CompareSelectionEntry } from './weather-metrics-tab/compareMetricSelection.ts';
	// Issue #1366 F002 Fix-Loop 2: EINZIGE Materialisierungs-Quelle „nie
	// eingestellt" (null) -> Vorgabemenge, geteilt mit WeatherMetricsTab.svelte/
	// CorridorEditor(Mobile) -- sonst weicht die Empfindlichkeits-Tabelle vom
	// Wetter-Metriken-Bereich desselben, frisch angelegten Vergleichs ab.
	import { materializeActiveMetricKeys } from './weather-metrics-tab/compareMetricOrder.ts';

	interface Props {
		context?: AlarmeContext;
		// route
		trip?: Trip;
		onTripUpdate?: (updated: Trip) => void;
		saveController?: SaveStatus;
		activeMetrics?: AlertMetric[];
		metricLevels?: Record<AlertMetric, SensLevel>;
		onMetricLevelChange?: (metric: AlertMetric, level: SensLevel) => void;
		// vergleich — Issue #2276 S6c: reine Wertprops + Rueckrufe. Das Buendel
		// baut `compare/alarmePropsAus.ts`, alle drei Vergleichs-Mounts speisen
		// es identisch ein; der Wizard-Zustand liegt beim Elternteil.
		//
		// 🔴 EINE Diskriminator-Regel fuer alle Felder: unterschieden wird an
		// etwas, das das Buendel IMMER liefert und der Trip-Mount NIE uebergibt.
		// Wo `undefined` kein gueltiger Wert ist, entscheidet der WERT; bei
		// Cooldown und Stillen Stunden ist `undefined` gueltig („nicht
		// gesetzt") — dort entscheidet die Anwesenheit des RUECKRUFS.
		/** Persistenzwert OHNE Bedienelement hier: der Schalter „Amtliche
		 *  Warnungen im Bericht" steht im Inhalt-Bereich (#1301 D2). Der Wert
		 *  laeuft nur durch, damit er beim naechsten Alarm-PUT nicht aus der
		 *  Nutzlast faellt. */
		amtlicheWarnungenImBericht?: boolean;
		officialWarningsEnabled?: boolean;
		onOfficialWarningsChange?: (an: boolean) => void;
		metricAlertLevels?: Record<string, string>;
		activeMetricKeys?: string[] | null;
		sendTelegram?: boolean;
		sendSms?: boolean;
		sendPremiumSms?: boolean;
		channelThresholds?: Record<string, string>;
		onThresholdChange?: (kind: ChannelKind, level: ChannelThreshold) => void;
		telegramStyle?: 'rich' | 'kurzform';
		onTelegramStyleChange?: (stil: 'rich' | 'kurzform') => void;
		cooldownMinutes?: number;
		onCooldownChange?: (minuten: number | undefined) => void;
		quietFrom?: string;
		quietTo?: string;
		onQuietHoursChange?: (von: string | undefined, bis: string | undefined) => void;
		radarAlertEnabled?: boolean;
		onRadarAlertChange?: (an: boolean) => void;
		/** Bezugsgroesse der Ortszeit in den Stillen Stunden (#1726/#1378 AC-4).
		 *  Der Vorgabewert deckt den Trip-Mount vollstaendig ab, der nichts
		 *  uebergibt; die drei Vergleichs-Mounts liefern „des ersten Orts". */
		zonenBezug?: string;
		/** Rollback-Senke des UNVERAENDERTEN Vergleichs-Speicherwegs:
		 *  `rollbackAlarmSnapshot` setzt nach einem gescheiterten PUT feldweise
		 *  zurueck. KEIN Bedienelement schreibt hierueber. */
		onAlarmFeldSetzen?: (feld: string, wert: unknown) => void;
		// #1435 E1a-2: geladener Compare-Katalog als UEBERGABEWERT — der
		// Modul-Getter registeredCompareMetricCatalog() ist nicht reaktiv und
		// wuerde ein $derived nach spaeterem Laden nicht neu rechnen lassen.
		catalog?: CompareSelectionEntry[];
		// Issue #2276 S2: der vergleich-Zweig speichert selbst (Hub). Ohne `preset`
		// oder `saveController` (Anlege-Seite) bleibt der Speicherzweig inaktiv.
		preset?: ComparePreset;
		onCompareUpdate?: (updated: ComparePreset) => void;
		enqueueHubWrite?: <T>(fn: () => Promise<T>) => Promise<T>;
		// beide Kontexte
		existingChannels?: Partial<AlertChannelState> | null;
		onChannelToggle?: (kind: ChannelKind) => void;
		// Issue #1461 S3b-2a (route): route liest den Bestand ueber diese Prop
		// (Trip-Speicherweg). Der Vergleich liest/schreibt seit S6c ueber die
		// Wertprop `channelThresholds` + `onThresholdChange` (kein zweiter
		// Speicherweg noetig).
		existingChannelThresholds?: Partial<Record<ChannelKind, string | null>> | null;
		// Issue #1745 A: Testhaken fuer den Tarif-Zustand (Muster
		// VTBriefingChannels.svelte:60,74,82). Ohne Uebergabe (`undefined`)
		// unveraendertes Verhalten (Fetch in onMount); mit Uebergabe (auch
		// explizit `null`) wird der Fetch uebersprungen — SSR-Tests koennen den
		// Tarif-Zustand so steuern, ohne dass `onMount` je laeuft (#1717).
		profileOverride?: { premium_sms_allowed?: boolean } | null;
	}
	let {
		context = 'route',
		trip,
		onTripUpdate,
		saveController,
		activeMetrics,
		metricLevels,
		onMetricLevelChange,
		amtlicheWarnungenImBericht,
		officialWarningsEnabled,
		onOfficialWarningsChange,
		metricAlertLevels,
		activeMetricKeys,
		sendTelegram,
		sendSms,
		sendPremiumSms,
		channelThresholds,
		onThresholdChange,
		telegramStyle,
		onTelegramStyleChange,
		cooldownMinutes,
		onCooldownChange,
		quietFrom,
		quietTo,
		onQuietHoursChange,
		radarAlertEnabled,
		onRadarAlertChange,
		zonenBezug = 'der Tour',
		onAlarmFeldSetzen,
		catalog,
		preset,
		onCompareUpdate,
		enqueueHubWrite,
		existingChannels,
		onChannelToggle,
		existingChannelThresholds,
		profileOverride
	}: Props = $props();

	// ── Tarif-Zustand fuer das Premium-SMS-Gate (AC-5/AC-13) ───────────────────
	// EIN Fetch-Ort fuer alle vier Mount-Punkte (Trip-Alarme-Reiter,
	// Vergleichs-Hub, beide Compare-Anlege-Masken) — AlertChannelPicker wird
	// ausschliesslich von AlarmeTab eingebunden.
	let alarmProfile = $state<{ premium_sms_allowed?: boolean } | null>(
		untrack(() => (profileOverride !== undefined ? profileOverride : null))
	);
	onMount(() => {
		if (profileOverride !== undefined) return;
		fetch('/api/auth/profile', { credentials: 'same-origin' })
			.then((r) => (r.ok ? r.json() : null))
			.then((p) => {
				alarmProfile = p as { premium_sms_allowed?: boolean } | null;
			})
			.catch(() => {
				alarmProfile = null;
			});
	});
	const premiumSmsAlarmGate = $derived(derivePremiumSmsAlarmGate(alarmProfile));
	const channelDisabled = $derived(
		premiumSmsAlarmGate.disabled && premiumSmsAlarmGate.hint
			? { premium_sms: premiumSmsAlarmGate.hint }
			: undefined
	);

	const sections = $derived(alarmeTabSections(context));

	// ── (b) Amtliche Warnungen — scharfer Trigger (S1; Inhalt-Schalter s.u.) ───
	// route: lokaler State (Grundlage fuer den EINEN $effect unten).
	// vergleich: kein lokaler State — Anzeige aus der Wertprop, Aenderung ueber
	// den Rueckruf nach oben (Issue #2276 S6c).
	//
	// D2 (#1301, #1292 P4): der Inhalt-Schalter (official_alerts_enabled)
	// wurde HIER ENTFERNT — er war ein doppelter Schreibpfad neben dem
	// Inhalt-Bereich (WeatherMetricsTab / CompareInhaltSection), der per
	// Last-Writer-Wins einen dort gesetzten Wert ueberschreiben konnte.
	// Alleiniger Schreiber ist jetzt der Inhalt-Bereich.
	// Trigger bindet fachlich auf official_warnings.enabled (S1, scharf).
	// Legacy-Fallback identisch zur Pipeline (trip_alert.py): nil -> Ist-Verhalten.
	let routeOfficialWarningsEnabled = $state<boolean>(
		trip?.official_warnings?.enabled ?? trip?.official_alert_triggers_enabled !== false
	);
	const displayOfficialWarningsEnabled = $derived(
		officialWarningsEnabled ?? routeOfficialWarningsEnabled
	);
	function handleOfficialWarningsToggle(checked: boolean) {
		if (officialWarningsEnabled === undefined) {
			routeOfficialWarningsEnabled = checked;
			return;
		}
		onOfficialWarningsChange?.(checked);
	}

	// ── (c) Metrik-Level-Tabelle ────────────────────────────────────────────────
	// vergleich: Ableitung aus der Wertprop `activeMetricKeys` (Compare-Metrik-
	// Namensraum) gegen den durchgereichten Register-Katalog (#1435 E1a-2).
	// route: aus `activeMetrics` (Ermittlung aus trip ist S3-Aufgabe).
	const effectiveActiveMetrics = $derived(
		activeMetricKeys !== undefined
			? deriveActiveAlertMetricsFromCatalog(
					materializeActiveMetricKeys(activeMetricKeys ?? null),
					catalog ?? []
				)
			: (activeMetrics ?? [])
	);
	// #1435 E1b: die gewaehlten Groessen, die keinen Alarm ausloesen koennen —
	// DIESELBE Materialisierung wie oben, damit die Leerauswahl-Kante (`null` =
	// nie geoeffnet = Vorgabemenge, `[]` = bewusst leer) konsistent bleibt.
	// route liefert strukturell immer [] (dort gibt es keine Metrik-Auswahl,
	// jeder daraus gebildete Satz waere sachlich falsch — AC-7).
	const unalertableSelectedMetricNames = $derived(
		context === 'vergleich'
			? deriveUnalertableSelectedMetricNames(
					materializeActiveMetricKeys(activeMetricKeys ?? null),
					catalog ?? []
				)
			: []
	);
	// route: lokaler State (Adversary Fix-Loop 1, F001) — Initialwert aus der
	// metricLevels-Prop (Container leitet sie aus trip.display_config her),
	// danach editierbar hier und Teil des EINEN konsolidierten Saves unten.
	// onMetricLevelChange bleibt als informativer Callback erhalten (API-
	// Kompatibilitaet), die PERSISTENZ laeuft ausschliesslich ueber
	// buildAlarmeSaveFn.
	let routeMetricLevels = $state<Record<AlertMetric, SensLevel>>(
		metricLevels ?? ({} as Record<AlertMetric, SensLevel>)
	);
	const effectiveMetricLevels = $derived(
		(metricAlertLevels as Record<AlertMetric, SensLevel> | undefined) ?? routeMetricLevels
	);
	function handleMetricLevelChange(metric: AlertMetric, level: SensLevel) {
		if (metricAlertLevels === undefined) {
			routeMetricLevels = { ...routeMetricLevels, [metric]: level };
		}
		onMetricLevelChange?.(metric, level);
	}

	// ── (d) Kanaele ───────────────────────────────────────────────────────────
	// route: lokaler State, Bestand kommt ueber existingChannels-Prop (S3
	// rekonstruiert Ist-Zustand, AC-15) — ohne Prop greift der Neuanlage-
	// Default (AC-11). vergleich: bindet an bestehende send_telegram/send_sms
	// (Implementation Details Abschnitt 5) — E-Mail bleibt implizit
	// (compare_official_alert.py:161-169), daher hier kein Toggle fuer E-Mail.
	//
	// Adversary Fix-Loop 1, F001: onChannelToggle ist nur noch ein
	// informativer Callback (API-Kompatibilitaet fuer AlarmeScheduleTab) —
	// die PERSISTENZ laeuft ausschliesslich ueber den EINEN konsolidierten
	// Save unten (buildAlarmeSaveFn), NICHT mehr ueber einen eigenen
	// schedule()-Aufruf im Container.
	let routeChannelState = $state<AlertChannelState>(resolveAlertChannels(existingChannels));
	const displayChannelState = $derived<AlertChannelState>(
		sendTelegram === undefined
			? routeChannelState
			: {
					telegram: sendTelegram,
					sms: sendSms ?? false,
					premium_sms: sendPremiumSms ?? false,
					// E-Mail bleibt implizit — kein Toggle im vergleich-Zweig.
					email: true
				}
	);
	function handleChannelToggle(kind: ChannelKind) {
		if (sendTelegram === undefined) {
			routeChannelState = { ...routeChannelState, [kind]: !routeChannelState[kind] };
		}
		onChannelToggle?.(kind);
	}

	// ── (d2) Kanal-Schwellen — Issue #1461 S3b-2a (route) + S3b-2b (vergleich) ─
	// route: lokaler State, Bestand kommt ueber existingChannelThresholds-Prop.
	// vergleich: liest die Wertprop `channelThresholds` (Muster metricAlertLevels
	// oben) — kein eigener lokaler State, keine eigene Persistenz-Logik hier.
	// 🔴 Auflage (Spec „Implementation Details"): die Sichtbarkeit der
	// Stufen-Auswahl darf NICHT vom WERT dieses Zustands abhaengen (Regress auf
	// AC-10 aus S3b-2a) — `resolveAlertChannelThresholds()` liefert immer ein
	// vollstaendiges Objekt (Startwert „gering" je Kanal), die Prop `thresholds`
	// im Markup unten ist deshalb IMMER gesetzt, unabhaengig von `context`.
	// svelte-ignore state_referenced_locally -- Prop wird bewusst nur einmal
	// zur Initialisierung gelesen (Muster routeChannelState oben).
	let routeChannelThresholds = $state<AlertChannelThresholdState>(
		resolveAlertChannelThresholds(existingChannelThresholds)
	);
	// Die Vorgabe „gering" fuellt nur die Kanaele, fuer die noch nichts
	// gespeichert ist — ein gehaltener Wert ueberlebt unveraendert
	// (`resolveAlertChannelThresholds` allein drehte jeden ihm unbekannten Wert
	// auf „gering" zurueck).
	const displayChannelThresholds = $derived<AlertChannelThresholdState>(
		channelThresholds === undefined
			? routeChannelThresholds
			: ({
					...resolveAlertChannelThresholds(channelThresholds),
					...channelThresholds
				} as AlertChannelThresholdState)
	);
	function handleThresholdChange(kind: ChannelKind, level: ChannelThreshold) {
		if (channelThresholds === undefined) {
			routeChannelThresholds = applyThresholdChange(routeChannelThresholds, kind, level);
		}
		onThresholdChange?.(kind, level);
	}

	// ── (e)/(f) Cooldown/Stille Stunden ───────────────────────────────────────
	// `undefined` heisst hier „nicht gesetzt" und ist ein gueltiger Wert —
	// deshalb entscheidet an DIESEN beiden Stellen als einzigen der RUECKRUF
	// darueber, ob die Aenderung nach oben gemeldet oder lokal gehalten wird.
	let routeCooldownMinutes = $state<number | undefined>(trip?.alert_cooldown_minutes ?? undefined);
	let routeQuietFrom = $state<string | undefined>(trip?.alert_quiet_from ?? undefined);
	let routeQuietTo = $state<string | undefined>(trip?.alert_quiet_to ?? undefined);
	const displayCooldownMinutes = $derived(cooldownMinutes ?? routeCooldownMinutes);
	const displayQuietFrom = $derived(quietFrom ?? routeQuietFrom);
	const displayQuietTo = $derived(quietTo ?? routeQuietTo);
	function handleCooldownChange(minuten: number | undefined) {
		if (onCooldownChange) {
			onCooldownChange(minuten);
			return;
		}
		routeCooldownMinutes = minuten;
	}
	function handleQuietFromChange(von: string | undefined) {
		if (onQuietHoursChange) {
			onQuietHoursChange(von, displayQuietTo);
			return;
		}
		routeQuietFrom = von;
	}
	function handleQuietToChange(bis: string | undefined) {
		if (onQuietHoursChange) {
			onQuietHoursChange(displayQuietFrom, bis);
			return;
		}
		routeQuietTo = bis;
	}

	// ── AC-12/F001: EIN $effect, EINE konsolidierte Payload-Funktion (nur route) ─
	// Vorbild: VersandTab.svelte:209-260 (buildAlertDeliverySaveFn, JSON-Diff-
	// Guard). Kanaele (routeChannelState) UND Metrik-Level (routeMetricLevels)
	// sind seit Adversary Fix-Loop 1 (F001) Teil DIESER EINEN Payload —
	// AlarmeScheduleTab.svelte hat keine eigenen schedule()-Aufrufer mehr
	// (die haetten sich mit diesem $effect denselben Ein-Slot-Debounce
	// geteilt und eine der beiden Aenderungen still verworfen).
	function buildAlarmeSaveFn() {
		const payload = buildAlarmeDeliveryPayload(
			{
				officialWarningsEnabled: routeOfficialWarningsEnabled,
				cooldownMinutes: routeCooldownMinutes,
				quietFrom: routeQuietFrom,
				quietTo: routeQuietTo,
				channels: routeChannelState,
				channelThresholds: routeChannelThresholds,
				metricLevels: routeMetricLevels
			},
			trip?.display_config as Record<string, unknown> | undefined
		);
		// #2317 Baustein 1: die Entlade-Option (keepalive) erreicht den PUT.
		return baueTripSpeicherung<Trip>(api, trip!.id, payload, (updated) => onTripUpdate?.(updated));
	}

	// svelte-ignore state_referenced_locally -- Initialwert des Dirty-Check-
	// Snapshots liest bewusst nur einmal (Issue #1461 S3b-2a fuegt
	// routeChannelThresholds zur bestehenden Liste hinzu).
	let _prevAlarmeJson = JSON.stringify({
		routeOfficialWarningsEnabled,
		routeCooldownMinutes,
		routeQuietFrom,
		routeQuietTo,
		routeChannelState,
		routeChannelThresholds,
		routeMetricLevels
	});
	$effect(() => {
		if (!trip) return;
		const currentJson = JSON.stringify({
			routeOfficialWarningsEnabled,
			routeCooldownMinutes,
			routeQuietFrom,
			routeQuietTo,
			routeChannelState,
			routeChannelThresholds,
			routeMetricLevels
		});
		if (currentJson === _prevAlarmeJson) return;
		_prevAlarmeJson = currentJson;
		if (saveController) saveController.schedule(buildAlarmeSaveFn());
		else void buildAlarmeSaveFn()();
	});

	// ── Issue #2276 S2: vergleich-Zweig speichert selbst (analog Trip-Zweig) ───
	// Diff-Gate gegen die zuletzt gespeicherte Baseline, Queue, Basis-Rueckmeldung
	// und Rollback liegen in alarmeVergleichSpeicherung.ts; der $effect delegiert.
	// Die Baseline entsteht beim Mount — CompareTabs mountet erst nach der
	// Hydration. Anlege-Seite (ohne preset/saveController): Zweig inaktiv (AC-7).
	// Der Speicherweg bleibt unveraendert; er bekommt den Alarmstand ueber die
	// Bruecke aus den Wertprops (Namenszuordnung und Frisch-Lesen liegen in
	// alarmeVergleichSpeicherung.ts, EINE Stelle fuer beide Namensraeume).
	const alarmZustand = alarmZustandsBruecke(
		() => ({
			amtlicheWarnungenImBericht,
			officialWarningsEnabled,
			radarAlertEnabled,
			metricAlertLevels,
			cooldownMinutes,
			quietFrom,
			quietTo,
			telegramStyle,
			sendTelegram,
			sendSms,
			sendPremiumSms,
			channelThresholds
		}),
		(feld, wert) => onAlarmFeldSetzen?.(feld, wert)
	);
	const vergleichSpeicherung = untrack(() =>
		preset && saveController
			? erstelleAlarmeVergleichSpeicherung({
					client: api,
					zustand: alarmZustand,
					preset: () => preset!,
					enqueueHubWrite: (fn) => (enqueueHubWrite ? enqueueHubWrite(fn) : fn()),
					onCompareUpdate: (updated) => onCompareUpdate?.(updated),
					saveController
				})
			: null
	);
	$effect(() => {
		if (!vergleichSpeicherung) return;
		// Liest alle Alarmfelder (Abhaengigkeiten); das Melden selbst ohne
		// Tracking, damit Zustandswechsel des Controllers keinen Neulauf ausloesen.
		alarmSnapshotAus(alarmZustand);
		untrack(() => vergleichSpeicherung.aenderungMelden());
	});
</script>

<div class="alarme-tab" data-testid="alarme-tab">
	{#each sections as id (id)}
		<div
			class="alarme-section{id === 'radar' ? ' alarme-section--tight' : ''}"
			data-testid="alarme-section-{id}"
		>
			{#if id === 'official-warnings'}
				<div class="alarme-official-warnings">
					<Eyebrow style="margin-bottom: 10px;">{triggerGroupHeading(context)}</Eyebrow>
					<div class="alarme-official-toggles">
						<ChannelToggle
							label="Amtliche Warnungen lösen Alert aus"
							checked={displayOfficialWarningsEnabled}
							onchange={handleOfficialWarningsToggle}
							testid="alerts-tab-official-alert-triggers-toggle"
						/>
					</div>
				</div>
			{:else if id === 'metric-levels'}
				{#if effectiveActiveMetrics.length === 0 && unalertableSelectedMetricNames.length === 0}
					<p class="alarme-no-metrics-hint" data-testid="alarme-no-metrics">
						Wähle im Tab „Wetter-Metriken" Metriken aus, um Alarm-Schwellen zu konfigurieren.
					</p>
				{:else if effectiveActiveMetrics.length === 0}
					<!-- #1435 E1b: der Nutzer HAT gewaehlt, nur eben nichts Alarmfaehiges —
					     „nichts gewaehlt" waere hier sachlich falsch (AC-9). -->
					<p class="alarme-no-metrics-hint" data-testid="alarme-only-unalertable-hint">
						Keine der gewählten Größen kann einen Alarm auslösen: {unalertableSelectedMetricNames.join(
							', '
						)}. Sie erscheinen weiterhin im Briefing, lösen aber keine Warnung aus.
					</p>
				{:else}
					<AlertMetricLevelTable
						activeMetrics={effectiveActiveMetrics}
						levels={effectiveMetricLevels}
						onLevelChange={handleMetricLevelChange}
					/>
					{#if context === 'vergleich' && unalertableSelectedMetricNames.length > 0}
						<p class="option-hint alarme-unalertable-hint" data-testid="alarme-unalertable-metrics-hint">
							Für diese Größen gibt es keinen Alarm: {unalertableSelectedMetricNames.join(', ')}. Sie
							erscheinen weiterhin im Briefing, lösen aber keine Warnung aus.
						</p>
					{/if}
				{/if}
			{:else if id === 'channels'}
				<!-- Issue #1461 S3b-2b: `thresholds`/`onThresholdChange` sind jetzt in
				     BEIDEN Kontexten gesetzt -- alle vier Flaechen (Trip-Alarm-Reiter,
				     Vergleichs-Hub, beide Compare-Anlege-Masken) zeigen die
				     Stufen-Auswahl (PO-Entscheid 2026-08-06, Spec v1.3). -->
				<AlertChannelPicker
					channels={displayChannelState}
					onToggle={handleChannelToggle}
					thresholds={displayChannelThresholds}
					onThresholdChange={handleThresholdChange}
					disabledChannels={channelDisabled}
				/>
				{#if context === 'vergleich'}
					<!-- Issue #1260 S5: geteilter Kurzstil-Schalter (DIESELBE Komponente
					     wie im Trip-Versand-Tab). Bindet an display_config.telegram_style;
					     nur aktiv, wenn der Telegram-Kanal an ist. -->
					<div class="alarme-telegram-style">
						<TelegramKurzstilToggle
							context="vergleich"
							style={telegramStyle ?? 'rich'}
							disabled={!(sendTelegram ?? false)}
							onchange={(s) => onTelegramStyleChange?.(s)}
						/>
					</div>
				{/if}
			{:else if id === 'cooldown'}
				<AlertCooldownCard
					bind:cooldown_minutes={() => displayCooldownMinutes, handleCooldownChange}
				/>
			{:else if id === 'quiet-hours'}
				<!-- Issue #1726: EIN geteilter Baustein, zwei Bezugsgrössen — beim
				     Vergleich gilt die Zone des erstgenannten Orts (#1378 AC-4). -->
				<AlertQuietHoursCard
					bind:quiet_from={() => displayQuietFrom, handleQuietFromChange}
					bind:quiet_to={() => displayQuietTo, handleQuietToChange}
					zonen_bezug={zonenBezug}
				/>
			{:else if id === 'radar'}
				<ChannelToggle
					label="Radar-Alarm"
					checked={radarAlertEnabled ?? false}
					onchange={(checked) => onRadarAlertChange?.(checked)}
					testid="alarme-radar-toggle"
				/>
			{:else if id === 'sample'}
				{#if context === 'vergleich'}
					<VTAlertSample context="vergleich" />
				{:else}
					<Eyebrow style="margin: 4px 0 10px;">Beispiel-Warnung</Eyebrow>
					<AlertPreviewCard trip={trip!} alertRules={trip?.alert_rules ?? []} />
				{/if}
			{/if}
		</div>
	{/each}
</div>

<style>
	.alarme-tab {
		position: relative;
		padding: 28px 40px 60px;
		display: flex;
		flex-direction: column;
		gap: 24px;
		max-width: 900px;
	}
	.alarme-section {
		display: flex;
		flex-direction: column;
		max-width: 620px;
	}
	/* Epic #1301 D3: Radar-Schalter visuell dicht unter dem
	   Amtliche-Warnungen-Schalter halten (eine Ausloeser-Gruppe unter einer
	   Ueberschrift), ohne den regulaeren Section-Abstand fuer alle Blöcke
	   zu aendern. */
	.alarme-section--tight {
		margin-top: -14px;
	}
	.alarme-official-toggles {
		display: flex;
		flex-direction: column;
		gap: 10px;
	}
	.alarme-telegram-style {
		margin-top: 12px;
	}
	/* #1435 E1b: Fussnote unter der Empfindlichkeits-Tabelle — Vorbild
	   WeatherMetricsTab.svelte `.option-hint` (gleiche Gattung Hinweis). */
	.alarme-unalertable-hint {
		margin: var(--g-s-3) 0 0;
		font-size: var(--g-text-sm);
		color: var(--g-ink-muted);
		line-height: 1.5;
	}

	.alarme-no-metrics-hint {
		margin: 0;
		padding: 24px;
		background: var(--g-card, #ffffff);
		border: 1px solid var(--g-line, #e2ddd2);
		border-radius: 12px;
		color: var(--g-ink);
		font-size: 16px;
	}

	@media (max-width: 899px) {
		.alarme-tab {
			padding: 20px 16px 48px;
			gap: 18px;
		}
	}
</style>
