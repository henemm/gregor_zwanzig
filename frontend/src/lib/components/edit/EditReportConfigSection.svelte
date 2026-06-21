<script lang="ts">
	import { onMount } from 'svelte';
	import type { ReportConfig } from '$lib/types';
	import { toHHMMSS } from '$lib/utils/time';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import * as Card from '$lib/components/ui/card/index.js';
	import {
		DEFAULT_DAILY_SUMMARY_METRICS,
		CONTENT_MODULE_DESCRIPTIONS,
	} from './reportConfigWrite.ts';
	import {
		visibleChannels,
		activeChannelLabels,
		hasNoActiveChannel,
		syncSendFlags,
		type ChannelConfig,
	} from '../trip-detail/briefingChannelGating.ts';

	interface Props {
		reportConfig: ReportConfig | undefined;
		mode?: 'create' | 'edit';
		/** Wetter-aktive Kanäle aus display_config.channels (#617).
		 *  Wenn nicht gesetzt: Altverhalten (alle drei Kanäle sichtbar, kein Banner). */
		weatherChannels?: ChannelConfig;
		/** Issue #736: Steuert ob die E-Mail-Inhalt-Card gerendert wird (Default: true). */
		showMailContent?: boolean;
		/** Issue #736: Steuert ob die Kanal-Checkboxen gerendert werden (Default: true). */
		showChannels?: boolean;
		/** Issue #736: Callback bei Kanal-Toggle — für Auto-Save von display_config.channels. */
		onChannelChange?: (channel: 'email' | 'telegram' | 'sms', value: boolean) => void;
	}
	let { reportConfig = $bindable(), mode = 'create', weatherChannels, showMailContent = true, showChannels = true, onChannelChange }: Props = $props();

	// --- Original-Blob fuer Read-Modify-Write -----------------------------------
	// Alle nicht UI-gepflegten Felder (insb. change_threshold_*, custom_unknown_*)
	// muessen byte-identisch erhalten bleiben. Wir bewahren den initial geladenen
	// Blob auf und mergen unsere UI-Felder beim Schreiben darueber.
	// Issue #207: ReportConfig statt Record<string, unknown> — die zusaetzlichen
	// unbekannten Felder (change_threshold_*) bleiben durch Spread erhalten,
	// auch wenn der Compiler sie nicht im Interface kennt (forward-compatible).
	let originalReportConfig: ReportConfig = {};

	// --- UI-State pro Sektion ---------------------------------------------------
	let morning_enabled = $state(true);
	let evening_enabled = $state(true);
	let morning_time = $state('07:00');
	let evening_time = $state('18:00');
	let multi_day_trend_morning = $state(false);
	let multi_day_trend_evening = $state(true);

	// Channels
	let send_email = $state(true);
	let send_telegram = $state(false);
	let send_sms = $state(false);

	// Bestandsdaten-Erhalt: diese States werden nicht mehr im UI gezeigt,
	// aber weiterhin für den Read-Modify-Write im merged-Objekt benötigt.
	let show_compact_summary = $state(true);
	let show_daylight = $state(true);
	let wind_exposition_min_elevation_m: number | null = $state(null);

	// E-Mail-Elemente (Issue #619 — Backend seit #621 live)
	let show_stage_stats = $state(true);
	let show_quick_take_tags = $state(true);
	let show_stability = $state(true);
	let show_highlights = $state(true);
	let dailySummaryMetrics = $state<string[]>([...DEFAULT_DAILY_SUMMARY_METRICS]);
	// Issue #664: Metriken-Überblick (ersetzt Quick-Take + Tages-Summe)
	let show_metrics_summary = $state(false);
	// Issue #721/#723: Ausblick-Block (Großwetterlage + nächste Etappen + Sicherheit%)
	let show_outlook = $state(true);

	// Issue #722: E-Mail-Format
	let email_format = $state<'full' | 'compact'>('full');

	// Issue #785: Vortag-Vergleich
	let show_yesterday_comparison = $state(true);

	// --- Profile (Channel-Verfuegbarkeit) --------------------------------------
	interface Profile {
		mail_to?: string;
		telegram_chat_id?: string;
		sms_to?: string;
	}
	let profile = $state<Profile | null>(null);

	let availableChannels = $derived({
		email: !!profile?.mail_to,
		telegram: !!profile?.telegram_chat_id,
		sms: !!profile?.sms_to
	});

	// Issue #617: Wetter-Kanal-Gating (nur wenn weatherChannels gesetzt)
	let weatherVisible = $derived(visibleChannels(weatherChannels));
	let weatherLabels = $derived(
		weatherChannels !== undefined ? activeChannelLabels(weatherChannels) : []
	);
	let weatherEmpty = $derived(hasNoActiveChannel(weatherChannels));

	// --- Initial-Load ----------------------------------------------------------
	onMount(() => {
		if (reportConfig) {
			originalReportConfig = { ...reportConfig };
			const c = originalReportConfig;

			// Master-Switch-Migration: bevorzugt morning_enabled/evening_enabled,
			// sonst Fallback auf enabled + gesetzte Zeit.
			const globallyEnabled = typeof c.enabled === 'boolean' ? c.enabled : true;
			if (typeof c.morning_enabled === 'boolean') {
				morning_enabled = c.morning_enabled;
			} else {
				morning_enabled = globallyEnabled && typeof c.morning_time === 'string';
			}
			if (typeof c.evening_enabled === 'boolean') {
				evening_enabled = c.evening_enabled;
			} else {
				evening_enabled = globallyEnabled && typeof c.evening_time === 'string';
			}

			if (typeof c.morning_time === 'string') morning_time = c.morning_time.slice(0, 5);
			if (typeof c.evening_time === 'string') evening_time = c.evening_time.slice(0, 5);

			if (typeof c.send_email === 'boolean') send_email = c.send_email;
			if (typeof c.send_telegram === 'boolean') send_telegram = c.send_telegram;
			if (typeof c.send_sms === 'boolean') send_sms = c.send_sms;

			if (typeof c.show_compact_summary === 'boolean') show_compact_summary = c.show_compact_summary;
			if (typeof c.show_daylight === 'boolean') show_daylight = c.show_daylight;
			wind_exposition_min_elevation_m = typeof c.wind_exposition_min_elevation_m === 'number'
				? c.wind_exposition_min_elevation_m
				: null;

			// Trend-Migration: erst neue Bool-Felder, dann Legacy-Array
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

			// Issue #619: E-Mail-Elemente
			if (typeof c.show_stage_stats === 'boolean') show_stage_stats = c.show_stage_stats;
			if (typeof c.show_quick_take_tags === 'boolean') show_quick_take_tags = c.show_quick_take_tags;
			if (typeof c.show_stability === 'boolean') show_stability = c.show_stability;
			if (typeof c.show_highlights === 'boolean') show_highlights = c.show_highlights;
			dailySummaryMetrics = [...(c.daily_summary_metrics ?? DEFAULT_DAILY_SUMMARY_METRICS)];
			// Issue #664: Metriken-Überblick
			if (typeof c.show_metrics_summary === 'boolean') show_metrics_summary = c.show_metrics_summary;
			// Issue #721/#723: Ausblick (Default true wenn fehlt)
			if (typeof c.show_outlook === 'boolean') show_outlook = c.show_outlook;
			// Issue #722: E-Mail-Format
			if (c.email_format === 'compact' || c.email_format === 'full') email_format = c.email_format;
			// Issue #785: Vortag-Vergleich (Default true wenn Feld fehlt — Altdaten-Kompatibilität)
			if (typeof c.show_yesterday_comparison === 'boolean')
				show_yesterday_comparison = c.show_yesterday_comparison;
		}

		// Profile laden (Channel-Verfuegbarkeit). Fail-soft: bei Fehler bleiben
		// alle Channels disabled (mit Account-Link-Hinweis).
		fetch('/api/auth/profile', { credentials: 'same-origin' })
			.then((r) => (r.ok ? r.json() : null))
			.then((p) => { profile = p as Profile | null; })
			.catch(() => { profile = null; });
	});

	// --- Write-Back: Read-Modify-Write -----------------------------------------
	$effect(() => {
		const multi_day_trend_reports: string[] = [];
		if (multi_day_trend_morning) multi_day_trend_reports.push('morning');
		if (multi_day_trend_evening) multi_day_trend_reports.push('evening');

		// Original-Blob als Basis -> UI-Felder darueber mergen.
		// So bleiben change_threshold_* und alle anderen unbekannten Felder erhalten.
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
			multi_day_trend_reports,
			show_compact_summary,
			show_daylight,
			wind_exposition_min_elevation_m,
			// Issue #619: E-Mail-Elemente
			show_stage_stats,
			show_quick_take_tags,
			show_stability,
			show_highlights,
			daily_summary_metrics: [...dailySummaryMetrics],
			// Issue #664: Metriken-Überblick
			show_metrics_summary,
			// Issue #721/#723: Ausblick-Block
			show_outlook,
			// Issue #722: E-Mail-Format
			email_format,
			// Issue #785: Vortag-Vergleich
			show_yesterday_comparison,
		};

		// Issue #617: verwaiste Kanäle (nicht Wetter-aktiv) auf false synchronisieren.
		// syncSendFlags gibt merged unverändert zurück wenn weatherChannels undefined.
		reportConfig = syncSendFlags(merged, weatherChannels) as ReportConfig;
	});

	// --- Quick-Pick-Handler (Factory Pattern fuer Safari-Closure-Schutz) -------
	function makeMorningTimeHandler(time: string) {
		return function doSetMorningTime() {
			morning_time = time;
		};
	}
	function makeEveningTimeHandler(time: string) {
		return function doSetEveningTime() {
			evening_time = time;
		};
	}
</script>

<div class="space-y-6">
	<!-- ====================================================================== -->
	<!-- Morgen-Report                                                          -->
	<!-- ====================================================================== -->
	<Card.Root class="p-3 space-y-3 hover:translate-y-0 hover:shadow-none">
		<div class="text-sm font-semibold">
			<span data-testid="morning-master-switch" class="inline-flex items-center gap-2">
				<Checkbox
					checked={morning_enabled}
					onchange={(e) => { morning_enabled = (e.target as HTMLInputElement).checked; }}
				>Morgen-Report aktivieren</Checkbox>
			</span>
		</div>

		<div class="flex flex-wrap items-center gap-2 pl-6">
			<label class="flex items-center gap-2 text-sm">
				<span>Uhrzeit:</span>
				<input
					type="time"
					data-testid="report-morning-time"
					class="g-num-input rounded-md border border-input bg-background px-2 py-1 text-sm disabled:opacity-50"
					bind:value={morning_time}
					disabled={!morning_enabled}
				/>
			</label>
			<button
				type="button"
				data-testid="report-morning-quickpick-07"
				class="g-quick-chip disabled:opacity-50"
				onclick={makeMorningTimeHandler('07:00')}
				disabled={!morning_enabled}
			>
				Morgens 07:00
			</button>
			<button
				type="button"
				data-testid="report-morning-quickpick-18"
				class="g-quick-chip disabled:opacity-50"
				onclick={makeMorningTimeHandler('18:00')}
				disabled={!morning_enabled}
			>
				Abends 18:00
			</button>
		</div>

		<div class="pl-6 text-sm">
			<span data-testid="report-morning-trend" class="inline-flex items-center gap-2">
				<Checkbox
					checked={multi_day_trend_morning}
					disabled={!morning_enabled}
					onchange={(e) => { multi_day_trend_morning = (e.target as HTMLInputElement).checked; }}
				>Trend über mehrere Tage zeigen</Checkbox>
			</span>
		</div>
	</Card.Root>

	<!-- ====================================================================== -->
	<!-- Abend-Report                                                            -->
	<!-- ====================================================================== -->
	<Card.Root class="p-3 space-y-3 hover:translate-y-0 hover:shadow-none">
		<div class="text-sm font-semibold">
			<span data-testid="evening-master-switch" class="inline-flex items-center gap-2">
				<Checkbox
					checked={evening_enabled}
					onchange={(e) => { evening_enabled = (e.target as HTMLInputElement).checked; }}
				>Abend-Report aktivieren</Checkbox>
			</span>
		</div>

		<div class="flex flex-wrap items-center gap-2 pl-6">
			<label class="flex items-center gap-2 text-sm">
				<span>Uhrzeit:</span>
				<input
					type="time"
					data-testid="report-evening-time"
					class="g-num-input rounded-md border border-input bg-background px-2 py-1 text-sm disabled:opacity-50"
					bind:value={evening_time}
					disabled={!evening_enabled}
				/>
			</label>
			<button
				type="button"
				data-testid="report-evening-quickpick-07"
				class="g-quick-chip disabled:opacity-50"
				onclick={makeEveningTimeHandler('07:00')}
				disabled={!evening_enabled}
			>
				Morgens 07:00
			</button>
			<button
				type="button"
				data-testid="report-evening-quickpick-18"
				class="g-quick-chip disabled:opacity-50"
				onclick={makeEveningTimeHandler('18:00')}
				disabled={!evening_enabled}
			>
				Abends 18:00
			</button>
		</div>

		<div class="pl-6 text-sm">
			<span data-testid="report-evening-trend" class="inline-flex items-center gap-2">
				<Checkbox
					checked={multi_day_trend_evening}
					disabled={!evening_enabled}
					onchange={(e) => { multi_day_trend_evening = (e.target as HTMLInputElement).checked; }}
				>Trend über mehrere Tage zeigen</Checkbox>
			</span>
		</div>
	</Card.Root>

	<!-- ====================================================================== -->
	<!-- Kanaele — Issue #736: nur wenn showChannels=true                      -->
	<!-- ====================================================================== -->
	{#if showChannels}
	<Card.Root class="p-3 space-y-2 hover:translate-y-0 hover:shadow-none">
		<h3 class="text-sm font-semibold">Kanäle</h3>

		{#if weatherChannels !== undefined && weatherEmpty}
			<!-- AC-3: Kein Kanal aktiv → Warnzustand -->
			<div data-testid="briefings-channel-empty" style="padding: 8px 10px; background: var(--g-surface-warn, #fff8e1); border: 1px solid var(--g-warn, #f9a825); border-radius: 6px; font-size: 13px; color: var(--g-ink);">
				Kein Kanal aktiv. Aktiviere zuerst mindestens einen Kanal im Tab Wetter-Metriken.
				<a
					data-testid="briefings-channel-empty-link"
					href="?tab=weather"
					style="display: inline-block; margin-top: 4px; color: var(--g-accent); text-decoration: underline; text-underline-offset: 2px;"
				>Zu Wetter-Metriken wechseln</a>
			</div>
		{:else}
			{#if weatherChannels !== undefined}
				<!-- AC-2: Hinweis-Banner (≥1 aktiver Kanal) -->
				<div data-testid="briefings-channel-hint" style="padding: 6px 10px; background: var(--g-surface-2, #f6f4ee); border: 1px solid var(--g-ink-faint, #e0ddd5); border-radius: 6px; font-size: 12px; color: var(--g-ink-muted);">
					Nur Kanäle, die du in Wetter-Metriken aktiviert hast, stehen hier zur Auswahl:
					{weatherLabels.join(' · ')}
				</div>
			{/if}

			<!-- E-Mail (nur wenn Wetter-aktiv oder kein Gating) -->
			{#if weatherVisible.email}
				<div class="text-sm">
					<span data-testid="channel-email" class="inline-flex items-center gap-2">
						<Checkbox
							checked={send_email}
							disabled={!availableChannels.email}
							onchange={(e) => { const v = (e.target as HTMLInputElement).checked; send_email = v; onChannelChange?.('email', v); }}
						>E-Mail{profile?.mail_to ? ` (${profile.mail_to})` : ''}</Checkbox>
					</span>
				</div>
				{#if !availableChannels.email}
					<div data-testid="channel-email-hint" class="pl-6 text-xs text-muted-foreground">
						E-Mail-Adresse fehlt — <a href="/account" style="color:var(--g-accent);text-decoration:underline;text-underline-offset:2px">im Account einrichten</a>
					</div>
				{/if}
			{/if}

			<!-- Telegram (nur wenn Wetter-aktiv oder kein Gating) -->
			{#if weatherVisible.telegram}
				<div class="text-sm">
					<span data-testid="channel-telegram" class="inline-flex items-center gap-2">
						<Checkbox
							checked={send_telegram}
							disabled={!availableChannels.telegram}
							onchange={(e) => { const v = (e.target as HTMLInputElement).checked; send_telegram = v; onChannelChange?.('telegram', v); }}
						>Telegram{profile?.telegram_chat_id ? ` (${profile.telegram_chat_id})` : ''}</Checkbox>
					</span>
				</div>
				{#if !availableChannels.telegram}
					<div data-testid="channel-telegram-hint" class="pl-6 text-xs text-muted-foreground">
						Telegram-Chat-ID fehlt — <a href="/account" style="color:var(--g-accent);text-decoration:underline;text-underline-offset:2px">im Account einrichten</a>
					</div>
				{/if}
			{/if}

			<!-- SMS (nur wenn Wetter-aktiv oder kein Gating) -->
			{#if weatherVisible.sms}
				<div class="text-sm">
					<span data-testid="channel-sms" class="inline-flex items-center gap-2">
						<Checkbox
							checked={send_sms}
							disabled={!availableChannels.sms}
							onchange={(e) => { const v = (e.target as HTMLInputElement).checked; send_sms = v; onChannelChange?.('sms', v); }}
						>SMS{profile?.sms_to ? ` (${profile.sms_to})` : ''}</Checkbox>
					</span>
				</div>
				{#if !availableChannels.sms}
					<div data-testid="channel-sms-hint" class="pl-6 text-xs text-muted-foreground">
						Handynummer fehlt — <a href="/account" style="color:var(--g-accent);text-decoration:underline;text-underline-offset:2px">im Account einrichten</a>
					</div>
				{/if}
			{/if}
		{/if}
	</Card.Root>
	{/if}

	<!-- ====================================================================== -->
	<!-- E-Mail-Inhalt (Issue #619, #693, #722) — Issue #736: konditionell    -->
	<!-- ====================================================================== -->
	{#if showMailContent}
	<Card.Root class="p-3 space-y-2 hover:translate-y-0 hover:shadow-none" data-testid="report-mail-content">
		<h3 class="text-sm font-semibold">E-Mail-Inhalt</h3>

		<!-- Issue #722: Format-Schalter (full/compact) -->
		<div class="space-y-1">
			<p class="text-xs text-muted-foreground font-medium">Format</p>
			<div class="flex gap-2" data-testid="report-email-format-switcher">
				<label class="flex items-center gap-1.5 text-sm cursor-pointer">
					<input
						type="radio"
						data-testid="report-email-format-full"
						name="email_format"
						value="full"
						checked={email_format === 'full'}
						onchange={() => { email_format = 'full'; }}
					/>
					Ausführlich (HTML)
				</label>
				<label class="flex items-center gap-1.5 text-sm cursor-pointer">
					<input
						type="radio"
						data-testid="report-email-format-compact"
						name="email_format"
						value="compact"
						checked={email_format === 'compact'}
						onchange={() => { email_format = 'compact'; }}
					/>
					Kompakt (Nur-Text)
				</label>
			</div>
			{#if email_format === 'compact'}
				<p class="text-xs text-muted-foreground" data-testid="report-compact-hint">
					Im Kompakt-Modus werden fix Metriken-Überblick + Ausblick gezeigt. Die Inhalts-Bausteine unten sind deaktiviert.
				</p>
			{/if}
		</div>

		<!-- Gruppe A: Inhalts-Bausteine (Issue #723: genau 3, Issue #774: direkt ohne Einklapp-Toggle) -->
		<div class="space-y-1" style={email_format === 'compact' ? 'opacity:0.45;pointer-events:none' : ''}>
			<div data-testid="report-content-modules-body" class="space-y-2 pl-2">
				<div class="text-sm">
					<span data-testid="report-show-metrics-summary" class="inline-flex items-center gap-2">
						<Checkbox
							checked={show_metrics_summary}
							disabled={email_format === 'compact'}
							onchange={(e) => { show_metrics_summary = (e.target as HTMLInputElement).checked; }}
						>{CONTENT_MODULE_DESCRIPTIONS.show_metrics_summary.label}</Checkbox>
					</span>
					<p class="pl-6 text-xs text-muted-foreground mt-0.5">{CONTENT_MODULE_DESCRIPTIONS.show_metrics_summary.description}</p>
				</div>
				<div class="text-sm">
					<span data-testid="report-show-outlook" class="inline-flex items-center gap-2">
						<Checkbox
							checked={show_outlook}
							disabled={email_format === 'compact'}
							onchange={(e) => { show_outlook = (e.target as HTMLInputElement).checked; }}
						>{CONTENT_MODULE_DESCRIPTIONS.show_outlook.label}</Checkbox>
					</span>
					<p class="pl-6 text-xs text-muted-foreground mt-0.5">{CONTENT_MODULE_DESCRIPTIONS.show_outlook.description}</p>
				</div>
				<div class="text-sm">
					<span data-testid="report-show-stage-stats" class="inline-flex items-center gap-2">
						<Checkbox
							checked={show_stage_stats}
							disabled={email_format === 'compact'}
							onchange={(e) => { show_stage_stats = (e.target as HTMLInputElement).checked; }}
						>{CONTENT_MODULE_DESCRIPTIONS.show_stage_stats.label}</Checkbox>
					</span>
					<p class="pl-6 text-xs text-muted-foreground mt-0.5">{CONTENT_MODULE_DESCRIPTIONS.show_stage_stats.description}</p>
				</div>
				<div class="text-sm">
					<span data-testid="report-show-yesterday-comparison" class="inline-flex items-center gap-2">
						<Checkbox
							checked={show_yesterday_comparison}
							disabled={email_format === 'compact'}
							onchange={(e) => { show_yesterday_comparison = (e.target as HTMLInputElement).checked; }}
						>{CONTENT_MODULE_DESCRIPTIONS.show_yesterday_comparison.label}</Checkbox>
					</span>
					<p class="pl-6 text-xs text-muted-foreground mt-0.5">
						{CONTENT_MODULE_DESCRIPTIONS.show_yesterday_comparison.description}
					</p>
				</div>
			</div>
		</div>
	</Card.Root>
	{/if}
</div>

<style>
	.g-quick-chip {
		border: 1px solid var(--g-ink-faint);
		border-radius: var(--g-radius-pill);
		font-family: var(--g-font-data);
		font-size: 11px;
		color: var(--g-ink-muted);
		padding: 2px 8px;
		background: transparent;
		cursor: pointer;
	}
	.g-quick-chip:hover {
		background: var(--g-surface-2);
		color: var(--g-ink);
	}

</style>
