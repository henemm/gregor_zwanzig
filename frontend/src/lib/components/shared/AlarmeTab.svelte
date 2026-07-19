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
		notifySummaryLabel,
		triggerGroupHeading,
		type AlarmeContext
	} from './alarme-tab/alarmeTabSections.ts';
	import { resolveAlertChannels, type AlertChannelState } from './alarme-tab/alertChannelState.ts';
	import { buildAlarmeDeliveryPayload } from './alarme-tab/alarmeDeliveryPayload.ts';
	import { deriveActiveAlertMetrics } from './alarme-tab/compareMetricMapping.ts';

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
		// beide Kontexte
		notifyCount?: number;
		onJumpToWertebereiche?: () => void;
		existingChannels?: Partial<AlertChannelState> | null;
		onChannelToggle?: (kind: 'telegram' | 'sms' | 'email') => void;
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
		notifyCount = 0,
		onJumpToWertebereiche,
		existingChannels,
		onChannelToggle
	}: Props = $props();

	const sections = $derived(alarmeTabSections(context));
	const summaryLabel = $derived(notifySummaryLabel(notifyCount));

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
	// vergleich: Ableitung aus wiz.activeMetricKeys (Compare-Metrik-Namensraum,
	// Mapping-Modul compareMetricMapping.ts). route: aus Props (Ermittlung aus
	// trip ist S3-Aufgabe, s. Context-Doc).
	const effectiveActiveMetrics = $derived(
		context === 'vergleich' ? deriveActiveAlertMetrics(wiz?.activeMetricKeys ?? []) : (activeMetrics ?? [])
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
				metricLevels: routeMetricLevels
			},
			trip?.display_config as Record<string, unknown> | undefined
		);
		return async () => {
			const updated = await api.put<Trip>(`/api/trips/${trip!.id}`, payload);
			onTripUpdate?.(updated);
		};
	}

	let _prevAlarmeJson = JSON.stringify({
		officialWarningsEnabled,
		cooldownMinutes,
		quietFrom,
		quietTo,
		routeChannelState,
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
			{#if id === 'korridor-summary'}
				<div class="alarme-korridor-summary">
					<Eyebrow style="margin-bottom: 6px;">Korridor-Auslöser</Eyebrow>
					<p class="alarme-korridor-text">{summaryLabel ?? 'Keine Warn-Schwellen aktiv'}</p>
					<button
						type="button"
						class="alarme-korridor-jump"
						data-testid="alarme-korridor-jump"
						onclick={() => onJumpToWertebereiche?.()}
					>
						Wertebereiche öffnen →
					</button>
				</div>
			{:else if id === 'official-warnings'}
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
				{#if effectiveActiveMetrics.length === 0}
					<p class="alarme-no-metrics-hint" data-testid="alarme-no-metrics">
						Wähle im Tab „Wertebereiche" Metriken aus, um Alarm-Schwellen zu konfigurieren.
					</p>
				{:else}
					<AlertMetricLevelTable
						activeMetrics={effectiveActiveMetrics}
						levels={effectiveMetricLevels}
						onLevelChange={handleMetricLevelChange}
					/>
				{/if}
			{:else if id === 'channels'}
				<AlertChannelPicker channels={displayChannelState} onToggle={handleChannelToggle} />
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
	.alarme-korridor-summary {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}
	.alarme-korridor-text {
		margin: 0;
		font-size: 14px;
		color: var(--g-ink);
	}
	.alarme-korridor-jump {
		align-self: flex-start;
		background: none;
		border: none;
		padding: 0;
		cursor: pointer;
		font-size: 12px;
		font-weight: 600;
		color: var(--g-accent-deep);
		font-family: var(--g-font-sans);
	}
	.alarme-official-toggles {
		display: flex;
		flex-direction: column;
		gap: 10px;
	}
	.alarme-telegram-style {
		margin-top: 12px;
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
