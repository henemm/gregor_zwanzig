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

	import { api } from '$lib/api';
	import { Eyebrow } from '$lib/components/atoms';
	import type { Trip, AlertMetric, SensLevel } from '$lib/types';
	import type { SaveStatus } from '$lib/stores/saveStatusStore.svelte';
	import type { CompareWizardState } from '$lib/components/compare/compareWizardState.svelte';
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
	import { resolveAlertChannels, type AlertChannelState } from './alarme-tab/alertChannelState.ts';
	import {
		applyThresholdChange,
		resolveAlertChannelThresholds,
		type AlertChannelThresholdState,
		type ChannelThreshold
	} from './alarme-tab/alertChannelState.ts';
	import { buildAlarmeDeliveryPayload } from './alarme-tab/alarmeDeliveryPayload.ts';
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
		// vergleich
		wiz?: CompareWizardState;
		// #1435 E1a-2: geladener Compare-Katalog als UEBERGABEWERT — der
		// Modul-Getter registeredCompareMetricCatalog() ist nicht reaktiv und
		// wuerde ein $derived nach spaeterem Laden nicht neu rechnen lassen.
		catalog?: CompareSelectionEntry[];
		// beide Kontexte
		existingChannels?: Partial<AlertChannelState> | null;
		onChannelToggle?: (kind: 'telegram' | 'sms' | 'email') => void;
		// Issue #1461 S3b-2a (route) + S3b-2b (vergleich): route liest den
		// Bestand ueber diese Prop (Trip-Speicherweg); vergleich liest/schreibt
		// stattdessen direkt gegen `wiz.channelThresholds` (Muster
		// metricAlertLevels/sendTelegram — kein zweiter Speicherweg noetig).
		existingChannelThresholds?: Partial<Record<'telegram' | 'sms' | 'email', string | null>> | null;
	}
	let {
		context = 'route',
		trip,
		onTripUpdate,
		saveController,
		activeMetrics,
		metricLevels,
		onMetricLevelChange,
		wiz,
		catalog,
		existingChannels,
		onChannelToggle,
		existingChannelThresholds
	}: Props = $props();

	const sections = $derived(alarmeTabSections(context));

	// ── (b) Amtliche Warnungen — scharfer Trigger (S1; Inhalt-Schalter s.u.) ───
	// route: lokaler State (Grundlage fuer den EINEN $effect unten).
	// vergleich: kein lokaler State — Anzeige/Aenderung direkt gegen wiz.*
	// (kein Self-Save, Persistenz macht CompareEditor/Hub-Bridge, s. Modul-
	// Kommentar VersandTab.svelte:42-46).
	//
	// D2 (#1301, #1292 P4): der Inhalt-Schalter (official_alerts_enabled)
	// wurde HIER ENTFERNT — er war ein doppelter Schreibpfad neben dem
	// Inhalt-Bereich (WeatherMetricsTab / CompareInhaltSection), der per
	// Last-Writer-Wins einen dort gesetzten Wert ueberschreiben konnte.
	// Alleiniger Schreiber ist jetzt der Inhalt-Bereich.
	// Trigger bindet fachlich auf official_warnings.enabled (S1, scharf).
	// Legacy-Fallback identisch zur Pipeline (trip_alert.py): nil -> Ist-Verhalten.
	let officialWarningsEnabled = $state<boolean>(
		trip?.official_warnings?.enabled ?? trip?.official_alert_triggers_enabled !== false
	);
	const displayOfficialWarningsEnabled = $derived(
		context === 'vergleich' ? (wiz?.officialWarningsEnabled ?? false) : officialWarningsEnabled
	);
	function handleOfficialWarningsToggle(checked: boolean) {
		if (context === 'vergleich') {
			if (wiz) wiz.officialWarningsEnabled = checked;
			return;
		}
		officialWarningsEnabled = checked;
	}

	// ── (c) Metrik-Level-Tabelle ────────────────────────────────────────────────
	// vergleich: Ableitung aus wiz.activeMetricKeys (Compare-Metrik-Namensraum)
	// gegen den durchgereichten Register-Katalog (#1435 E1a-2). route: aus Props
	// (Ermittlung aus trip ist S3-Aufgabe, s. Context-Doc).
	const effectiveActiveMetrics = $derived(
		context === 'vergleich'
			? deriveActiveAlertMetricsFromCatalog(
					materializeActiveMetricKeys(wiz?.activeMetricKeys ?? null),
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
					materializeActiveMetricKeys(wiz?.activeMetricKeys ?? null),
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
		context === 'vergleich'
			? ((wiz?.metricAlertLevels ?? {}) as Record<AlertMetric, SensLevel>)
			: routeMetricLevels
	);
	function handleMetricLevelChange(metric: AlertMetric, level: SensLevel) {
		if (context === 'vergleich') {
			if (wiz) wiz.metricAlertLevels = { ...wiz.metricAlertLevels, [metric]: level };
			return;
		}
		routeMetricLevels = { ...routeMetricLevels, [metric]: level };
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
		context === 'vergleich'
			? { telegram: wiz?.sendTelegram ?? false, sms: wiz?.sendSms ?? false, email: true }
			: routeChannelState
	);
	function handleChannelToggle(kind: 'telegram' | 'sms' | 'email') {
		if (context === 'vergleich') {
			if (!wiz) return;
			if (kind === 'telegram') wiz.sendTelegram = !wiz.sendTelegram;
			else if (kind === 'sms') wiz.sendSms = !wiz.sendSms;
			// E-Mail bleibt implizit — kein Toggle im vergleich-Zweig.
			return;
		}
		routeChannelState = { ...routeChannelState, [kind]: !routeChannelState[kind] };
		onChannelToggle?.(kind);
	}

	// ── (d2) Kanal-Schwellen — Issue #1461 S3b-2a (route) + S3b-2b (vergleich) ─
	// route: lokaler State, Bestand kommt ueber existingChannelThresholds-Prop.
	// vergleich: bindet direkt an wiz.channelThresholds (Muster metricAlertLevels
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
	const displayChannelThresholds = $derived<AlertChannelThresholdState>(
		context === 'vergleich'
			? resolveAlertChannelThresholds(wiz?.channelThresholds ?? null)
			: routeChannelThresholds
	);
	function handleThresholdChange(kind: 'telegram' | 'sms' | 'email', level: ChannelThreshold) {
		if (context === 'vergleich') {
			if (wiz) {
				const updated = applyThresholdChange(
					resolveAlertChannelThresholds(wiz.channelThresholds ?? null),
					kind,
					level
				);
				wiz.channelThresholds = {
					telegram: updated.telegram,
					sms: updated.sms,
					email: updated.email
				};
			}
			return;
		}
		routeChannelThresholds = applyThresholdChange(routeChannelThresholds, kind, level);
	}

	// ── (e)/(f) Cooldown/Stille Stunden — route: lokaler State, vergleich: wiz.* ─
	let cooldownMinutes = $state<number | undefined>(trip?.alert_cooldown_minutes ?? undefined);
	let quietFrom = $state<string | undefined>(trip?.alert_quiet_from ?? undefined);
	let quietTo = $state<string | undefined>(trip?.alert_quiet_to ?? undefined);

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
				officialWarningsEnabled,
				cooldownMinutes,
				quietFrom,
				quietTo,
				channels: routeChannelState,
				channelThresholds: routeChannelThresholds,
				metricLevels: routeMetricLevels
			},
			trip?.display_config as Record<string, unknown> | undefined
		);
		return async () => {
			const updated = await api.put<Trip>(`/api/trips/${trip!.id}`, payload);
			onTripUpdate?.(updated);
		};
	}

	// svelte-ignore state_referenced_locally -- Initialwert des Dirty-Check-
	// Snapshots liest bewusst nur einmal (Issue #1461 S3b-2a fuegt
	// routeChannelThresholds zur bestehenden Liste hinzu).
	let _prevAlarmeJson = JSON.stringify({
		officialWarningsEnabled,
		cooldownMinutes,
		quietFrom,
		quietTo,
		routeChannelState,
		routeChannelThresholds,
		routeMetricLevels
	});
	$effect(() => {
		if (context !== 'route') return;
		const currentJson = JSON.stringify({
			officialWarningsEnabled,
			cooldownMinutes,
			quietFrom,
			quietTo,
			routeChannelState,
			routeChannelThresholds,
			routeMetricLevels
		});
		if (currentJson === _prevAlarmeJson) return;
		_prevAlarmeJson = currentJson;
		if (saveController) saveController.schedule(buildAlarmeSaveFn());
		else void buildAlarmeSaveFn()();
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
				/>
				{#if context === 'vergleich'}
					<!-- Issue #1260 S5: geteilter Kurzstil-Schalter (DIESELBE Komponente
					     wie im Trip-Versand-Tab). Bindet an display_config.telegram_style
					     via wiz.telegramStyle; nur aktiv, wenn Telegram-Kanal an ist. -->
					<div class="alarme-telegram-style">
						<TelegramKurzstilToggle
							context="vergleich"
							style={wiz?.telegramStyle ?? 'rich'}
							disabled={!(wiz?.sendTelegram ?? false)}
							onchange={(s) => {
								if (wiz) wiz.telegramStyle = s;
							}}
						/>
					</div>
				{/if}
			{:else if id === 'cooldown'}
				{#if context === 'vergleich'}
					<AlertCooldownCard bind:cooldown_minutes={wiz!.alertCooldownMinutes} />
				{:else}
					<AlertCooldownCard bind:cooldown_minutes={cooldownMinutes} />
				{/if}
			{:else if id === 'quiet-hours'}
				{#if context === 'vergleich'}
					<AlertQuietHoursCard bind:quiet_from={wiz!.alertQuietFrom} bind:quiet_to={wiz!.alertQuietTo} />
				{:else}
					<AlertQuietHoursCard bind:quiet_from={quietFrom} bind:quiet_to={quietTo} />
				{/if}
			{:else if id === 'radar'}
				<ChannelToggle
					label="Radar-Alarm"
					checked={wiz?.radarAlertEnabled ?? false}
					onchange={(checked) => {
						if (wiz) wiz.radarAlertEnabled = checked;
					}}
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
