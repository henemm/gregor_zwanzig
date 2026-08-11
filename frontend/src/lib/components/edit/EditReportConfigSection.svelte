<script lang="ts">
	import { onMount, untrack } from 'svelte';
	import type { ReportConfig } from '$lib/types';
	import { toHHMMSS } from '$lib/utils/time';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import * as Card from '$lib/components/ui/card/index.js';
	import VTSchedulePlan from '../shared/versand-tab/VTSchedulePlan.svelte';
	import {
		channelConnectionStatus,
		type ConnectionProfile
	} from '../shared/versand-tab/channelConnectionStatus';
	import { channelContactLabel } from '../shared/versand-tab/channelContactLabel';
	import { premiumSmsChannelState } from '../shared/versand-tab/premiumSmsChannelState';
	import { Dot } from '$lib/components/atoms';
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
		/** Issue #1047: Steuert ob die Morgen-/Abend-Report-Zeitplan-Karten gerendert werden (Default: true). */
		showSchedule?: boolean;
		/** Issue #736: Callback bei Kanal-Toggle — für Auto-Save von display_config.channels. */
		onChannelChange?: (channel: 'email' | 'telegram' | 'sms', value: boolean) => void;
		/** RED-Infrastruktur (#1510): optionaler SSR-Test-Override fuer `profile`.
		 * Falls gesetzt (auch explizit `null`) wird `profile` daraus initialisiert
		 * und der `onMount`-Fetch uebersprungen — `svelte/server`s `render()` fuehrt
		 * `onMount` nicht aus, ohne diesen Override bliebe `profile` in SSR-Tests
		 * immer `null`. Ohne Uebergabe unveraendertes Verhalten (Fetch in onMount). */
		profileOverride?: Profile | null;
	}
	let { reportConfig = $bindable(), mode = 'create', weatherChannels, showMailContent = true, showChannels = true, showSchedule = true, onChannelChange, profileOverride }: Props = $props();

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

	// Channels — Issue #1717 S3: alle vier BEIM ERZEUGEN aus der Prop
	// initialisiert (untrack, wie `profile` unten) und nicht erst in onMount.
	// onMount laeuft serverseitig nie, und ein Wert, der erst nach der ersten
	// Ausgabe erscheint, ist einen Wimpernschlag falsch; ausserdem waere der
	// Zeitplan-Leerzustand (hasActiveChannel unten) beim Rendern sonst nicht
	// erreichbar und damit nicht pruefbar. Semantik wie in onMount: E-Mail
	// Default an, alles andere Default aus.
	let send_email = $state(untrack(() => reportConfig?.send_email !== false));
	let send_telegram = $state(untrack(() => reportConfig?.send_telegram === true));
	let send_sms = $state(untrack(() => reportConfig?.send_sms === true));
	// Der gespeicherte Anhak-Zustand von Premium-SMS muss schon beim Rendern
	// stehen (AC-10).
	let send_premium_sms = $state(untrack(() => reportConfig?.send_premium_sms === true));

	// Bestandsdaten-Erhalt: diese States werden nicht mehr im UI gezeigt,
	// aber weiterhin für den Read-Modify-Write im merged-Objekt benötigt.
	let show_compact_summary = $state(true);
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
	/** Issue #1717 S3: EINE kanonische Profilform (channelConnectionStatus.ts)
	 * statt einer lokalen Kopie je Komponente — sonst muesste jedes neue
	 * Profilfeld an drei Stellen nachgezogen werden. */
	type Profile = ConnectionProfile;
	let profile = $state<Profile | null>(
		untrack(() => (profileOverride !== undefined ? profileOverride : null))
	);

	let availableChannels = $derived({
		email: !!profile?.mail_to,
		telegram: !!profile?.telegram_chat_id,
		sms: !!profile?.sms_to && profile?.sms_allowed !== false
	});

	// Issue #1510: ehrlicher Verbindungsstatus + geteilte Kontakt-Beschriftung
	// (analog VTBriefingChannels.svelte).
	let connectionStatus = $derived(channelConnectionStatus(profile));
	let contactLabel = $derived(channelContactLabel(profile));
	// Issue #1717 S3: derselbe geteilte Zustands-Helfer wie in
	// VTBriefingChannels.svelte — keine zweite Kopie der Logik (AC-2).
	let premiumSms = $derived(premiumSmsChannelState(profile));

	// Issue #617: Wetter-Kanal-Gating (nur wenn weatherChannels gesetzt)
	let weatherVisible = $derived(visibleChannels(weatherChannels));
	let weatherLabels = $derived(
		weatherChannels !== undefined ? activeChannelLabels(weatherChannels) : []
	);
	let weatherEmpty = $derived(hasNoActiveChannel(weatherChannels));
	// Issue #1286 KL-1: VTSchedulePlan bringt einen eigenen "Kein Kanal aktiv"-
	// Leerzustand (hasActiveChannel-basiert) mit demselben Testid
	// briefings-channel-empty wie der Kanal-Gating-Leerzustand unten
	// (weatherChannels-basiert). Um im Assistenten nie zwei Elemente mit
	// identischem Testid gleichzeitig sichtbar zu haben, wird VTSchedulePlan
	// gar nicht erst gerendert, solange der Kanal-Gating-Leerzustand aktiv ist
	// — die beiden Leerzustände schließen sich dadurch gegenseitig aus (AC-9).
	let scheduleGatingEmpty = $derived(weatherChannels !== undefined && weatherEmpty);
	// Issue #1717 S3: Premium-SMS zaehlt mit — wer nur diesen Kanal einschaltet,
	// bekommt ein echtes Briefing, und ein Leerzustand "Kein Kanal aktiv" waere
	// eine Anzeige, die der Wirklichkeit widerspricht. Zweite Fassung derselben
	// Zaehlung: VersandTab.svelte (activeChannelCount, /trips/[id]) — beide
	// werden im selben Testfall gegeneinander gemessen
	// (shared/versand-tab/__tests__/channel_checkbox_dedupe_render.test.ts).
	let hasActiveChannel = $derived(send_email || send_telegram || send_sms || send_premium_sms);

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
			// Issue #1717 S3: zusaetzlich zur Initialisierung beim Erzeugen (oben) —
			// deckt den Fall ab, dass reportConfig erst nach dem Erzeugen der
			// Komponente eintrifft.
			if (typeof c.send_premium_sms === 'boolean') send_premium_sms = c.send_premium_sms;

			if (typeof c.show_compact_summary === 'boolean') show_compact_summary = c.show_compact_summary;
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
		if (profileOverride === undefined) {
			fetch('/api/auth/profile', { credentials: 'same-origin' })
				.then((r) => (r.ok ? r.json() : null))
				.then((p) => { profile = p as Profile | null; })
				.catch(() => { profile = null; });
		}
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
			// Issue #1717 S3 — vierter Briefing-Kanal, gleicher Write-Back-Pfad.
			send_premium_sms,
			multi_day_trend_morning,
			multi_day_trend_evening,
			multi_day_trend_reports,
			show_compact_summary,
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

	// --- VTSchedulePlan-Verdrahtung (Factory Pattern fuer Safari-Closure-Schutz,
	// analog VersandTab.svelte makeToggleHandler/makeTimeHandler) ---------------
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
</script>

<div class="space-y-6">
	{#if showSchedule && !scheduleGatingEmpty}
	<!-- ====================================================================== -->
	<!-- Briefing-Zeitplan — Issue #1286: geteilte VTSchedulePlan statt eigenem -->
	<!-- Markup (EIN Ort pflegt Morgen-/Abend-Zeitplan-UI, s. Spec KL-1).       -->
	<!-- ====================================================================== -->
	<VTSchedulePlan context="route"
		{hasActiveChannel}
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
	{/if}

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
							disabled={connectionStatus.email.tone !== 'good'}
							onchange={(e) => { const v = (e.target as HTMLInputElement).checked; send_email = v; onChannelChange?.('email', v); }}
						>E-Mail{contactLabel.email}</Checkbox>
					</span>
					<span data-testid="channel-status-email" class="rc-channel-status">
						<Dot tone={connectionStatus.email.tone} size={7} />
						<span class="rc-channel-status-label">{connectionStatus.email.label}</span>
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
						>Telegram{contactLabel.telegram}</Checkbox>
					</span>
					<span data-testid="channel-status-telegram" class="rc-channel-status">
						<Dot tone={connectionStatus.telegram.tone} size={7} />
						<span class="rc-channel-status-label">{connectionStatus.telegram.label}</span>
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
						>SMS{contactLabel.sms}</Checkbox>
					</span>
					<span data-testid="channel-status-sms" class="rc-channel-status">
						<Dot tone={connectionStatus.sms.tone} size={7} />
						<span class="rc-channel-status-label">{connectionStatus.sms.label}</span>
					</span>
				</div>
				{#if profile?.sms_allowed === false}
					<div data-testid="channel-sms-hint" class="pl-6 text-xs text-muted-foreground">
						SMS ab Level Standard verfügbar
					</div>
				{:else if !availableChannels.sms}
					<div data-testid="channel-sms-hint" class="pl-6 text-xs text-muted-foreground">
						Handynummer fehlt — <a href="/account" style="color:var(--g-accent);text-decoration:underline;text-underline-offset:2px">im Account einrichten</a>
					</div>
				{/if}

				<!-- Premium-SMS (Garmin inReach) — Issue #1717 S3: aus dem dauerhaft
				     deaktivierten Slot (#1069) wird ein echter, schaltbarer Kanal.
				     Zustand/Texte kommen aus demselben geteilten Helfer wie in
				     VTBriefingChannels.svelte (Trip-Detail) — dieselben Worte fuer
				     dieselbe Lage, egal auf welcher Seite (AC-2). -->
				<div class="text-sm">
					<span data-testid="channel-premium-sms" class="inline-flex items-center gap-2">
						<Checkbox
							checked={send_premium_sms}
							disabled={premiumSms.disabled}
							onchange={(e) => { send_premium_sms = (e.target as HTMLInputElement).checked; }}
						>Premium-SMS (Garmin inReach){premiumSms.contactLabel}</Checkbox>
					</span>
					<span data-testid="channel-status-premium-sms" class="rc-channel-status">
						<Dot tone={premiumSms.tone} size={7} />
						<span class="rc-channel-status-label">{premiumSms.statusLabel}</span>
					</span>
				</div>
				<p data-testid="channel-premium-sms-hint" class="pl-6 text-xs rc-channel-hint">
					{premiumSms.hint}
				</p>
				{#if premiumSms.reportedAtLabel}
					<p data-testid="channel-premium-sms-reported-at" class="rc-premium-reported-at pl-6">
						{premiumSms.reportedAtLabel}
					</p>
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
		<!-- Fix #971/#774: "Metriken-Überblick"-Checkbox entfernt — der Block wird seit
		     #790 im Mail-Renderer unconditional gerendert (build_metrics_summary_pills),
		     die Checkbox war eine wirkungslose Karteileiche. -->
		<div class="space-y-1" style={email_format === 'compact' ? 'opacity:0.45;pointer-events:none' : ''}>
			<div data-testid="report-content-modules-body" class="space-y-2 pl-2">
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
	/* Issue #1510: Verbindungsstatus-Dot + Mono-Label — 1:1 aus
	   VTBriefingChannels.svelte (.vt-channel-status/-label), eigene Klassen hier
	   weil EditReportConfigSection kein Tailwind-Utility dafuer hat. */
	.rc-channel-status {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		margin-left: 10px;
	}
	.rc-channel-status-label {
		font-family: var(--g-font-mono);
		font-size: 11px;
		letter-spacing: 0.04em;
		color: var(--g-ink-3);
	}
	/* Issue #1717 S3 (AC-9): Meldedatum der gelernten Rueckadresse ist ein
	   DATEN-Label, keine Fussnote — --g-ink-3 wie der Verbindungsstatus, nie
	   --g-ink-4 (2,85:1 auf Weiss, strikt Platzhalter/Disabled vorbehalten).
	   1:1 zu .vt-premium-reported-at in VTBriefingChannels.svelte. */
	.rc-premium-reported-at {
		font-family: var(--g-font-mono);
		font-size: 11px;
		color: var(--g-ink-3);
		margin: 2px 0 0;
	}
	/* Hinweistext des Premium-SMS-Blocks: eigene Klasse statt
	   text-muted-foreground, damit die Farbe nicht in der Utility-Kette
	   verschwindet — derselbe Kontrast-Grund wie oben. */
	.rc-channel-hint {
		color: var(--g-ink-3);
		margin: 2px 0 0;
	}
</style>

