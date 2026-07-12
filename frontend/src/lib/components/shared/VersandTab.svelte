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

	import { onMount, type Snippet } from 'svelte';
	import { api } from '$lib/api.js';
	import { toHHMMSS } from '$lib/utils/time';
	import { Eyebrow } from '$lib/components/atoms';
	import type { Trip, ReportConfig, AlertRule } from '$lib/types';
	import type { SaveStatus } from '$lib/stores/saveStatusStore.svelte';
	import type { CompareWizardState } from '$lib/components/compare/compareWizardState.svelte';
	import ChannelToggle from '$lib/components/shared/ChannelToggle.svelte';
	import AlertCooldownCard from '$lib/components/alerts-tab/AlertCooldownCard.svelte';
	import AlertQuietHoursCard from '$lib/components/alerts-tab/AlertQuietHoursCard.svelte';
	import AlertPreviewCard from '$lib/components/alerts-tab/AlertPreviewCard.svelte';
	import VTBriefingChannels from './versand-tab/VTBriefingChannels.svelte';
	import VTSchedulePlan from './versand-tab/VTSchedulePlan.svelte';
	import VTLaufzeitRoute from './versand-tab/VTLaufzeitRoute.svelte';
	import VTLaufzeitVergleich from './versand-tab/VTLaufzeitVergleich.svelte';
	import VTAlertSample from './versand-tab/VTAlertSample.svelte';
	import { buildAlertDeliveryPayload } from './versand-tab/alertDeliveryPayload.ts';

	interface Props {
		context?: 'route' | 'vergleich';
		trip?: Trip;
		onTripUpdate?: (updated: Trip) => void;
		saveController?: SaveStatus;
		/** report_config-Blob — bind:reportConfig durchgereicht an den Parent (BriefingScheduleTab). Nur route. */
		reportConfig?: ReportConfig;
		/** Issue #736: display_config.channels-Sync bei Kanal-Toggle (Parent-Callback). Nur route. */
		onChannelChange?: (channel: 'email' | 'telegram' | 'sms', value: boolean) => void;
		/** Tab-Wechsel (analog HubOverview onJump) — "Etappen öffnen →" springt in 'stages'. Nur route. */
		onJump?: (tab: string) => void;
		/** Issue #1232 Scheibe 2b: geteilter Compare-Wizard-State (context="vergleich").
		 * KEIN Self-Save — alle Controls binden direkt an wiz.*, Persistenz bleibt
		 * zentral in CompareEditor.handleSave()/wiz.saveNewPreset() (Doppel-Mount
		 * Desktop+Mobile, Create ohne Preset-ID). */
		wiz?: CompareWizardState;
		/** Issue #1232 Scheibe 2b: Create-Aktivierungs-Banner (1:1 JSX-Slot), nur vergleich. */
		activation?: Snippet;
	}
	let {
		context = 'route',
		trip,
		onTripUpdate,
		saveController,
		reportConfig = $bindable(),
		onChannelChange,
		onJump,
		wiz,
		activation
	}: Props = $props();

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

	// Issue #1232 Scheibe 2b: vergleich-Zweig — Kanal-Zähler direkt aus wiz.*
	// (kein lokaler $state, kein Self-Save).
	const vergleichActiveChannelCount = $derived(
		wiz ? [wiz.sendEmail, wiz.sendTelegram, wiz.sendSms].filter(Boolean).length : 0
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
	// Issue #1232 Scheibe 2b: vergleich-Zweig — schreibt direkt in wiz.* statt
	// in lokale $state-Variablen (kein Self-Save, siehe Modul-Kommentar oben).
	function makeWizChannelHandler(field: 'sendEmail' | 'sendTelegram' | 'sendSms') {
		return function doChange(e: Event) {
			if (!wiz) return;
			wiz[field] = (e.target as HTMLInputElement).checked;
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
	// t optional: im vergleich-Zweig wird trip nie gesetzt (Laufzeit-Sektion
	// dort ist VTLaufzeitVergleich, nicht VTLaufzeitRoute) — computeTripEnd
	// wird nur fuer den route-Zweig ausgewertet, defensiv trotzdem null-sicher.
	function computeTripEnd(t: Trip | undefined): string | null {
		if (!t) return null;
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
	// (Issue #864/#859/#1087/#1088), nur der Tab hat sich geändert. Nur route:
	// im vergleich-Zweig binden AlertCooldownCard/AlertQuietHoursCard direkt an
	// wiz.* (kein trip-Objekt vorhanden) — trip? defensiv, damit die Initialisierung
	// im vergleich-Zweig (trip=undefined) nicht wirft. ─────────────────────────
	let officialAlertsEnabled = $state<boolean>(trip?.official_alerts_enabled ?? true);
	let officialAlertTriggersEnabled = $state<boolean>(trip?.official_alert_triggers_enabled ?? true);
	let cooldownMinutes = $state<number | undefined>(trip?.alert_cooldown_minutes ?? undefined);
	let quietFrom = $state<string | undefined>(trip?.alert_quiet_from ?? undefined);
	let quietTo = $state<string | undefined>(trip?.alert_quiet_to ?? undefined);
	let alertRules = $state<AlertRule[]>(trip?.alert_rules ?? []);

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
			// Nur im route-Zweig erreichbar (die vergleich-Handler mutieren
			// officialAlertsEnabled/cooldownMinutes/etc. nie, siehe Kommentar oben).
			const updated = await api.put<Trip>(`/api/trips/${trip!.id}`, payload);
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
			<AlertPreviewCard trip={trip!} {alertRules} />
		</div>
	</div>
{:else if context === 'vergleich'}
	<div class="versand-tab" data-testid="versand-tab">
		<VTBriefingChannels
			{context}
			channels={{
				email: wiz?.sendEmail ?? false,
				telegram: wiz?.sendTelegram ?? false,
				sms: wiz?.sendSms ?? false
			}}
			onEmailChange={makeWizChannelHandler('sendEmail')}
			onTelegramChange={makeWizChannelHandler('sendTelegram')}
			onSmsChange={makeWizChannelHandler('sendSms')}
			emailTestid="compare-step5-channel-email"
			telegramTestid="compare-step5-channel-telegram"
			smsTestid="compare-step5-channel-sms"
		/>

		<VTSchedulePlan
			context="vergleich"
			hasActiveChannel={vergleichActiveChannelCount > 0}
			morning_enabled={wiz?.morningEnabled ?? true}
			morning_time={wiz?.morningTime ?? '07:00'}
			evening_enabled={wiz?.eveningEnabled ?? false}
			evening_time={wiz?.eveningTime ?? '18:00'}
			onMorningToggle={makeToggleHandler((v) => {
				if (wiz) wiz.morningEnabled = v;
			})}
			onEveningToggle={makeToggleHandler((v) => {
				if (wiz) wiz.eveningEnabled = v;
			})}
			onMorningTime={makeTimeHandler((v) => {
				if (wiz) wiz.morningTime = v;
			})}
			onEveningTime={makeTimeHandler((v) => {
				if (wiz) wiz.eveningTime = v;
			})}
		/>

		<VTLaufzeitVergleich
			value={wiz?.endDate ?? null}
			onChange={(v) => {
				if (wiz) wiz.endDate = v;
			}}
		/>

		<div class="vt-alert-delivery">
			<Eyebrow style="margin-bottom: 10px;">Wann Warnungen rausgehen</Eyebrow>
			<div class="vt-alert-cards">
				<AlertCooldownCard bind:cooldown_minutes={wiz!.alertCooldownMinutes} />
				<AlertQuietHoursCard bind:quiet_from={wiz!.alertQuietFrom} bind:quiet_to={wiz!.alertQuietTo} />
			</div>
			<VTAlertSample context="vergleich" />
		</div>

		{#if activation}
			<div class="vt-activation-slot">{@render activation()}</div>
		{/if}
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
