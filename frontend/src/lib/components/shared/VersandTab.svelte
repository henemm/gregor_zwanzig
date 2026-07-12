<script lang="ts">
	// VersandTab — Issue #1232 Scheibe 1: geteilter Versand-Organism
	// (Epic #29/#1230, Phase 4 Editor-Konsolidierung).
	//
	// EIN Organism für Trip-Editor (context="route") und Compare-Editor
	// (context="vergleich", folgt Scheibe 2 — KL-3). Buendelt alles was
	// rausgeht: Briefing-Kanaele, Briefing-Zeitplan, Laufzeit und die
	// komplette Alert-Zustellung (bisher im Alerts-Tab).
	//
	// Design-Quelle (1:1): claude-code-handoff/current/jsx/versand-tab.jsx
	// Spec: docs/specs/modules/versand_tab_route.md

	import { onMount } from 'svelte';
	import { api } from '$lib/api.js';
	import { toHHMMSS } from '$lib/utils/time';
	import { Eyebrow } from '$lib/components/atoms';
	import type { Trip, ReportConfig, AlertRule } from '$lib/types';
	import type { SaveStatus } from '$lib/stores/saveStatusStore.svelte';
	import ChannelToggle from '$lib/components/shared/ChannelToggle.svelte';
	import AlertCooldownCard from '$lib/components/alerts-tab/AlertCooldownCard.svelte';
	import AlertQuietHoursCard from '$lib/components/alerts-tab/AlertQuietHoursCard.svelte';
	import AlertPreviewCard from '$lib/components/alerts-tab/AlertPreviewCard.svelte';
	import VTBriefingChannels from './versand-tab/VTBriefingChannels.svelte';
	import VTSchedulePlan from './versand-tab/VTSchedulePlan.svelte';
	import VTLaufzeitRoute from './versand-tab/VTLaufzeitRoute.svelte';
	import { buildAlertDeliveryPayload } from './versand-tab/alertDeliveryPayload.ts';

	interface Props {
		context?: 'route' | 'vergleich';
		trip: Trip;
		onTripUpdate?: (updated: Trip) => void;
		saveController?: SaveStatus;
		/** report_config-Blob — bind:reportConfig durchgereicht an den Parent (BriefingScheduleTab). */
		reportConfig: ReportConfig;
		/** Issue #736: display_config.channels-Sync bei Kanal-Toggle (Parent-Callback). */
		onChannelChange?: (channel: 'email' | 'telegram' | 'sms', value: boolean) => void;
		/** Tab-Wechsel (analog HubOverview onJump) — "Etappen öffnen →" springt in 'stages'. */
		onJump?: (tab: string) => void;
	}
	let { context = 'route', trip, onTripUpdate, saveController, reportConfig = $bindable(), onChannelChange, onJump }: Props =
		$props();

	// ── Sektion 1+2: Briefing-Kanäle + Zeitplan (report_config) ────────────────
	let originalReportConfig: ReportConfig = {};
	let morning_enabled = $state(true);
	let evening_enabled = $state(true);
	let morning_time = $state('07:00');
	let evening_time = $state('18:00');
	let multi_day_trend_morning = $state(false);
	let multi_day_trend_evening = $state(false);
	let send_email = $state(true);
	let send_telegram = $state(false);
	let send_sms = $state(false);

	onMount(() => {
		if (reportConfig) {
			originalReportConfig = { ...reportConfig };
			const c = originalReportConfig;
			const globallyEnabled = typeof c.enabled === 'boolean' ? c.enabled : true;
			morning_enabled =
				typeof c.morning_enabled === 'boolean'
					? c.morning_enabled
					: globallyEnabled && typeof c.morning_time === 'string';
			evening_enabled =
				typeof c.evening_enabled === 'boolean'
					? c.evening_enabled
					: globallyEnabled && typeof c.evening_time === 'string';
			if (typeof c.morning_time === 'string') morning_time = c.morning_time.slice(0, 5);
			if (typeof c.evening_time === 'string') evening_time = c.evening_time.slice(0, 5);
			if (typeof c.send_email === 'boolean') send_email = c.send_email;
			if (typeof c.send_telegram === 'boolean') send_telegram = c.send_telegram;
			if (typeof c.send_sms === 'boolean') send_sms = c.send_sms;
			if (typeof c.multi_day_trend_morning === 'boolean') {
				multi_day_trend_morning = c.multi_day_trend_morning;
			} else if (Array.isArray(c.multi_day_trend_reports)) {
				multi_day_trend_morning = c.multi_day_trend_reports.includes('morning');
			}
			if (typeof c.multi_day_trend_evening === 'boolean') {
				multi_day_trend_evening = c.multi_day_trend_evening;
			} else if (Array.isArray(c.multi_day_trend_reports)) {
				multi_day_trend_evening = c.multi_day_trend_reports.includes('evening');
			}
		}
	});

	$effect(() => {
		const multi_day_trend_reports: string[] = [];
		if (multi_day_trend_morning) multi_day_trend_reports.push('morning');
		if (multi_day_trend_evening) multi_day_trend_reports.push('evening');
		const merged: Record<string, unknown> = {
			...originalReportConfig,
			enabled: morning_enabled || evening_enabled,
			morning_enabled,
			evening_enabled,
			morning_time: toHHMMSS(morning_time),
			evening_time: toHHMMSS(evening_time),
			send_email,
			send_telegram,
			send_sms,
			multi_day_trend_morning,
			multi_day_trend_evening,
			multi_day_trend_reports
		};
		reportConfig = merged as ReportConfig;
	});

	const activeChannelCount = $derived(
		[send_email, send_telegram, send_sms].filter(Boolean).length
	);

	// Factory-Pattern (Safari-Closure-Schutz, CLAUDE.md).
	function makeChannelChangeHandler(channel: 'email' | 'telegram' | 'sms') {
		return function doChange(e: Event) {
			const v = (e.target as HTMLInputElement).checked;
			if (channel === 'email') send_email = v;
			else if (channel === 'telegram') send_telegram = v;
			else send_sms = v;
			onChannelChange?.(channel, v);
		};
	}
	function makeToggleHandler(setter: (v: boolean) => void) {
		return function doToggle(e: Event) {
			setter((e.target as HTMLInputElement).checked);
		};
	}
	function makeTimeHandler(setter: (v: string) => void) {
		return function doSetTime(e: Event) {
			setter((e.target as HTMLInputElement).value);
		};
	}

	// ── Sektion 3: Laufzeit (route = read-only aus Etappen) ────────────────────
	function computeTripEnd(t: Trip): string | null {
		const dates = (t.stages ?? [])
			.map((s) => s.date)
			.filter((d): d is string => !!d)
			.slice()
			.sort();
		if (dates.length === 0) return null;
		const clean = dates[dates.length - 1].split('T')[0];
		const [y, m, d] = clean.split('-');
		if (!y || !m || !d) return null;
		return `${d}.${m}.${y}`;
	}
	const tripEnd = $derived(computeTripEnd(trip));

	function handleOpenStages() {
		onJump?.('stages');
	}

	// ── Sektion 4: Alert-Zustellung — Speicherpfad funktionsgleich zu AlertsTab
	// (Issue #864/#859/#1087/#1088), nur der Tab hat sich geändert. ────────────
	let officialAlertsEnabled = $state<boolean>(trip.official_alerts_enabled ?? true);
	let officialAlertTriggersEnabled = $state<boolean>(trip.official_alert_triggers_enabled ?? true);
	let cooldownMinutes = $state<number | undefined>(trip.alert_cooldown_minutes ?? undefined);
	let quietFrom = $state<string | undefined>(trip.alert_quiet_from ?? undefined);
	let quietTo = $state<string | undefined>(trip.alert_quiet_to ?? undefined);
	let alertRules = $state<AlertRule[]>(trip.alert_rules ?? []);

	// Adversary-Fund F002 (Issue #1232 Scheibe 1): EIN gemeinsamer Debounce-Slot
	// für die gesamte Alert-Zustellung. `saveController.schedule()` kennt nur
	// EINEN pending Save (`_pendingFn` wird bei jedem Aufruf komplett ersetzt,
	// siehe saveStatusStore.svelte.ts) — drei unabhängige schedule()-Aufrufe
	// (officialAlerts, officialAlertTriggers, cooldown/quiet) würden sich
	// gegenseitig verwerfen, wenn sie innerhalb der 700ms kollidieren. Fix:
	// EIN $effect beobachtet alle 5 Felder und plant GENAU EINEN Save, dessen
	// Payload immer den vollständigen aktuellen Zustand enthält (kein Feld
	// geht verloren, egal wie viele Änderungen im Debounce-Fenster passieren).
	function buildAlertDeliverySaveFn() {
		const payload = buildAlertDeliveryPayload({
			officialAlertsEnabled,
			officialAlertTriggersEnabled,
			cooldownMinutes,
			quietFrom,
			quietTo
		});
		return async () => {
			const updated = await api.put<Trip>(`/api/trips/${trip.id}`, payload);
			onTripUpdate?.(updated);
		};
	}

	// Factory-Pattern (Safari-Closure-Schutz) — die Handler setzen NUR den
	// lokalen State; das Speichern übernimmt der gemeinsame $effect unten.
	function makeOfficialAlertsToggleHandler() {
		return (checked: boolean) => {
			officialAlertsEnabled = checked;
		};
	}
	function makeOfficialAlertTriggersToggleHandler() {
		return (checked: boolean) => {
			officialAlertTriggersEnabled = checked;
		};
	}

	// Cooldown/Stille-Stunden sind $bindable in den wiederverwendeten Cards
	// (kein onchange-Callback) — Auto-Save analog zum reportConfig-Muster
	// (JSON-Diff-Guard), aber für ALLE 5 Alert-Zustellungsfelder gemeinsam.
	let _prevAlertDeliveryJson = JSON.stringify({
		officialAlertsEnabled,
		officialAlertTriggersEnabled,
		cooldownMinutes,
		quietFrom,
		quietTo
	});
	$effect(() => {
		const currentJson = JSON.stringify({
			officialAlertsEnabled,
			officialAlertTriggersEnabled,
			cooldownMinutes,
			quietFrom,
			quietTo
		});
		if (currentJson === _prevAlertDeliveryJson) return;
		_prevAlertDeliveryJson = currentJson;
		if (saveController) saveController.schedule(buildAlertDeliverySaveFn());
		else void buildAlertDeliverySaveFn()();
	});
</script>

{#if context === 'route'}
	<div class="versand-tab" data-testid="versand-tab">
		<VTBriefingChannels
			{context}
			channels={{ email: send_email, telegram: send_telegram, sms: send_sms }}
			onEmailChange={makeChannelChangeHandler('email')}
			onTelegramChange={makeChannelChangeHandler('telegram')}
			onSmsChange={makeChannelChangeHandler('sms')}
		/>

		<VTSchedulePlan
			hasActiveChannel={activeChannelCount > 0}
			{morning_enabled}
			{morning_time}
			{evening_enabled}
			{evening_time}
			{multi_day_trend_morning}
			{multi_day_trend_evening}
			onMorningToggle={makeToggleHandler((v) => (morning_enabled = v))}
			onEveningToggle={makeToggleHandler((v) => (evening_enabled = v))}
			onMorningTime={makeTimeHandler((v) => (morning_time = v))}
			onEveningTime={makeTimeHandler((v) => (evening_time = v))}
			onTrendMorningToggle={makeToggleHandler((v) => (multi_day_trend_morning = v))}
			onTrendEveningToggle={makeToggleHandler((v) => (multi_day_trend_evening = v))}
		/>

		<VTLaufzeitRoute {tripEnd} onOpenStages={handleOpenStages} />

		<div class="vt-alert-delivery">
			<Eyebrow style="margin-bottom: 10px;">Wann Warnungen rausgehen</Eyebrow>
			<div class="vt-alert-toggles">
				<ChannelToggle
					label="Amtliche Warnungen"
					checked={officialAlertsEnabled}
					onchange={makeOfficialAlertsToggleHandler()}
					testid="alerts-tab-official-alerts-toggle"
				/>
				<ChannelToggle
					label="Amtliche Warnungen lösen Alert aus"
					checked={officialAlertTriggersEnabled}
					onchange={makeOfficialAlertTriggersToggleHandler()}
					testid="alerts-tab-official-alert-triggers-toggle"
				/>
			</div>
			<div class="vt-alert-cards">
				<AlertCooldownCard bind:cooldown_minutes={cooldownMinutes} />
				<AlertQuietHoursCard bind:quiet_from={quietFrom} bind:quiet_to={quietTo} />
			</div>
			<Eyebrow style="margin: 4px 0 10px;">Beispiel-Warnung</Eyebrow>
			<AlertPreviewCard {trip} {alertRules} />
		</div>
	</div>
{/if}

<style>
	.versand-tab {
		position: relative;
		padding: 28px 40px 60px;
		display: flex;
		flex-direction: column;
		gap: 30px;
		max-width: 900px;
	}
	.vt-alert-delivery {
		display: flex;
		flex-direction: column;
		gap: 18px;
		max-width: 620px;
	}
	.vt-alert-toggles {
		display: flex;
		flex-direction: column;
		gap: 10px;
	}
	.vt-alert-cards {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 16px;
	}

	@media (max-width: 899px) {
		.versand-tab {
			padding: 20px 16px 48px;
			gap: 22px;
		}
		.vt-alert-cards {
			grid-template-columns: 1fr;
		}
	}
</style>
