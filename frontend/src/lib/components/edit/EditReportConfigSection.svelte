<script lang="ts">
	import { onMount } from 'svelte';
	import type { ReportConfig } from '$lib/types';
	import { toHHMMSS } from '$lib/utils/time';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import * as Card from '$lib/components/ui/card/index.js';
	import { Btn } from '$lib/components/atoms';
	import ChevronDown from '@lucide/svelte/icons/chevron-down';

	interface Props {
		reportConfig: ReportConfig | undefined;
		mode?: 'create' | 'edit';
	}
	let { reportConfig = $bindable(), mode = 'create' }: Props = $props();

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
	let send_signal = $state(false);
	let send_telegram = $state(false);
	let send_sms = $state(false);

	// Erweitert
	let showAdvanced = $state(false);
	let show_compact_summary = $state(true);
	let show_daylight = $state(true);
	let wind_exposition_min_elevation_m: number | null = $state(null);

	// --- Profile (Channel-Verfuegbarkeit) --------------------------------------
	interface Profile {
		mail_to?: string;
		signal_phone?: string;
		telegram_chat_id?: string;
		sms_phone?: string;
	}
	let profile = $state<Profile | null>(null);

	let availableChannels = $derived({
		email: !!profile?.mail_to,
		signal: !!profile?.signal_phone,
		telegram: !!profile?.telegram_chat_id,
		sms: !!profile?.sms_phone
	});

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
			if (typeof c.send_signal === 'boolean') send_signal = c.send_signal;
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
		reportConfig = {
			...originalReportConfig,
			enabled: morning_enabled || evening_enabled,
			morning_enabled,
			evening_enabled,
			morning_time: toHHMMSS(morning_time),
			evening_time: toHHMMSS(evening_time),
			send_email,
			send_signal,
			send_telegram,
			send_sms,
			multi_day_trend_morning,
			multi_day_trend_evening,
			multi_day_trend_reports,
			show_compact_summary,
			show_daylight,
			wind_exposition_min_elevation_m
		};
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
	<!-- Kanaele                                                                -->
	<!-- ====================================================================== -->
	<Card.Root class="p-3 space-y-2 hover:translate-y-0 hover:shadow-none">
		<h3 class="text-sm font-semibold">Kanäle</h3>

		<!-- E-Mail -->
		<div class="text-sm">
			<span data-testid="channel-email" class="inline-flex items-center gap-2">
				<Checkbox
					checked={send_email}
					disabled={!availableChannels.email}
					onchange={(e) => { send_email = (e.target as HTMLInputElement).checked; }}
				>E-Mail{profile?.mail_to ? ` (${profile.mail_to})` : ''}</Checkbox>
			</span>
		</div>
		{#if !availableChannels.email}
			<div data-testid="channel-email-hint" class="pl-6 text-xs text-muted-foreground">
				E-Mail-Adresse fehlt — <a href="/account" style="color:var(--g-accent);text-decoration:underline;text-underline-offset:2px">im Account einrichten</a>
			</div>
		{/if}

		<!-- Signal -->
		<div class="text-sm">
			<span data-testid="channel-signal" class="inline-flex items-center gap-2">
				<Checkbox
					checked={send_signal}
					disabled={!availableChannels.signal}
					onchange={(e) => { send_signal = (e.target as HTMLInputElement).checked; }}
				>Signal{profile?.signal_phone ? ` (${profile.signal_phone})` : ''}</Checkbox>
			</span>
		</div>
		{#if !availableChannels.signal}
			<div data-testid="channel-signal-hint" class="pl-6 text-xs text-muted-foreground">
				Signal-Nummer fehlt — <a href="/account" style="color:var(--g-accent);text-decoration:underline;text-underline-offset:2px">im Account einrichten</a>
			</div>
		{/if}

		<!-- Telegram -->
		<div class="text-sm">
			<span data-testid="channel-telegram" class="inline-flex items-center gap-2">
				<Checkbox
					checked={send_telegram}
					disabled={!availableChannels.telegram}
					onchange={(e) => { send_telegram = (e.target as HTMLInputElement).checked; }}
				>Telegram{profile?.telegram_chat_id ? ` (${profile.telegram_chat_id})` : ''}</Checkbox>
			</span>
		</div>
		{#if !availableChannels.telegram}
			<div data-testid="channel-telegram-hint" class="pl-6 text-xs text-muted-foreground">
				Telegram-Chat-ID fehlt — <a href="/account" style="color:var(--g-accent);text-decoration:underline;text-underline-offset:2px">im Account einrichten</a>
			</div>
		{/if}
	</Card.Root>

	<!-- ====================================================================== -->
	<!-- Erweitert                                                              -->
	<!-- ====================================================================== -->
	<div class="space-y-2">
		<Btn variant="ghost" size="sm" data-testid="report-show-advanced" onclick={() => { showAdvanced = !showAdvanced; }}>
			{showAdvanced ? 'Erweitert ausblenden' : 'Erweitert anzeigen'}
			<ChevronDown style="transform: rotate({showAdvanced ? 180 : 0}deg); transition: transform 150ms ease;" />
		</Btn>
		{#if showAdvanced}
			<div class="space-y-2 pl-2">
				<div class="text-sm">
					<Checkbox
						data-testid="report-compact-summary"
						checked={show_compact_summary}
						onchange={(e) => { show_compact_summary = (e.target as HTMLInputElement).checked; }}
					>Kompakte Zusammenfassung</Checkbox>
				</div>
				<div class="text-sm">
					<Checkbox
						data-testid="report-show-daylight"
						checked={show_daylight}
						onchange={(e) => { show_daylight = (e.target as HTMLInputElement).checked; }}
					>Tageslicht anzeigen</Checkbox>
				</div>
				<div class="text-sm">
					<span class="block text-muted-foreground">Wind-Exposition Mindesthöhe (m)</span>
					<label class="g-num-with-unit block w-full max-w-xs">
						<input
							type="number"
							data-testid="report-wind-exposition"
							class="g-num-input w-full rounded-md border border-input bg-background px-2 py-1 text-sm pr-7"
							value={wind_exposition_min_elevation_m ?? ''}
							oninput={(e) => {
								const v = (e.target as HTMLInputElement).value;
								wind_exposition_min_elevation_m = v === '' ? null : Number(v);
							}}
						/>
						<span class="g-num-unit" aria-hidden="true">m</span>
					</label>
				</div>
			</div>
		{/if}
	</div>
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

	.g-num-with-unit {
		position: relative;
		display: block;
	}
	.g-num-unit {
		position: absolute;
		right: 8px;
		top: 50%;
		transform: translateY(-50%);
		font-family: var(--g-font-data);
		font-size: 11px;
		color: var(--g-ink-muted);
		pointer-events: none;
	}
</style>
