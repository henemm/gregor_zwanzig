<script lang="ts">
	import { onMount } from 'svelte';

	interface Props {
		reportConfig: Record<string, unknown> | undefined;
		mode?: 'create' | 'edit';
	}
	let { reportConfig = $bindable(), mode = 'create' }: Props = $props();

	// Zeitplan
	let enabled = $state(true);
	let morning_time = $state('07:00');
	let evening_time = $state('18:00');

	// Channels
	let send_email = $state(true);
	let send_signal = $state(false);
	let send_telegram = $state(false);

	// Alerts
	let alert_on_changes = $state(true);
	let change_threshold_temp_c = $state(5.0);
	let change_threshold_wind_kmh = $state(20.0);
	let change_threshold_precip_mm = $state(10.0);

	// Erweitert
	let showAdvanced = $state(false);
	let show_compact_summary = $state(true);
	let show_daylight = $state(true);
	let wind_exposition_min_elevation_m: number | null = $state(null);
	let trend_morning = $state(false);
	let trend_evening = $state(true);

	onMount(() => {
		if (!reportConfig) return;

		const c = reportConfig as Record<string, unknown>;

		if (typeof c.enabled === 'boolean') enabled = c.enabled;
		if (typeof c.morning_time === 'string') morning_time = c.morning_time.slice(0, 5);
		if (typeof c.evening_time === 'string') evening_time = c.evening_time.slice(0, 5);

		if (typeof c.send_email === 'boolean') send_email = c.send_email;
		if (typeof c.send_signal === 'boolean') send_signal = c.send_signal;
		if (typeof c.send_telegram === 'boolean') send_telegram = c.send_telegram;

		if (typeof c.alert_on_changes === 'boolean') alert_on_changes = c.alert_on_changes;
		if (typeof c.change_threshold_temp_c === 'number') change_threshold_temp_c = c.change_threshold_temp_c;
		if (typeof c.change_threshold_wind_kmh === 'number') change_threshold_wind_kmh = c.change_threshold_wind_kmh;
		if (typeof c.change_threshold_precip_mm === 'number') change_threshold_precip_mm = c.change_threshold_precip_mm;

		if (typeof c.show_compact_summary === 'boolean') show_compact_summary = c.show_compact_summary;
		if (typeof c.show_daylight === 'boolean') show_daylight = c.show_daylight;
		wind_exposition_min_elevation_m = typeof c.wind_exposition_min_elevation_m === 'number'
			? c.wind_exposition_min_elevation_m
			: null;

		if (Array.isArray(c.multi_day_trend_reports)) {
			const arr = c.multi_day_trend_reports as string[];
			trend_morning = arr.includes('morning');
			trend_evening = arr.includes('evening');
		}
	});

	$effect(() => {
		const multi_day_trend_reports: string[] = [];
		if (trend_morning) multi_day_trend_reports.push('morning');
		if (trend_evening) multi_day_trend_reports.push('evening');

		reportConfig = {
			enabled,
			morning_time,
			evening_time,
			send_email,
			send_signal,
			send_telegram,
			alert_on_changes,
			change_threshold_temp_c,
			change_threshold_wind_kmh,
			change_threshold_precip_mm,
			show_compact_summary,
			show_daylight,
			wind_exposition_min_elevation_m,
			multi_day_trend_reports,
		};
	});
</script>

<div data-testid="wizard-step4-report" class="space-y-6">
	<!-- Zeitplan -->
	<div class="space-y-3">
		<h3 class="text-sm font-semibold">Zeitplan</h3>
		<label class="flex cursor-pointer items-center gap-2 text-sm">
			<input
				type="checkbox"
				data-testid="report-enabled"
				class="rounded border-input"
				checked={enabled}
				onchange={(e) => { enabled = (e.target as HTMLInputElement).checked; }}
			/>
			<span>Reports aktiviert</span>
		</label>
		<div class="flex items-center gap-4">
			<label class="flex items-center gap-2 text-sm">
				<span>Morgen:</span>
				<input
					type="time"
					data-testid="report-morning-time"
					class="rounded-md border border-input bg-background px-2 py-1 text-sm"
					bind:value={morning_time}
				/>
			</label>
			<label class="flex items-center gap-2 text-sm">
				<span>Abend:</span>
				<input
					type="time"
					data-testid="report-evening-time"
					class="rounded-md border border-input bg-background px-2 py-1 text-sm"
					bind:value={evening_time}
				/>
			</label>
		</div>
	</div>

	<!-- Channels -->
	<div class="space-y-2">
		<h3 class="text-sm font-semibold">Channels</h3>
		<label class="flex cursor-pointer items-center gap-2 text-sm">
			<input
				type="checkbox"
				data-testid="report-send-email"
				class="rounded border-input"
				checked={send_email}
				onchange={(e) => { send_email = (e.target as HTMLInputElement).checked; }}
			/>
			<span>E-Mail</span>
		</label>
		<label class="flex cursor-pointer items-center gap-2 text-sm">
			<input
				type="checkbox"
				data-testid="report-send-signal"
				class="rounded border-input"
				checked={send_signal}
				onchange={(e) => { send_signal = (e.target as HTMLInputElement).checked; }}
			/>
			<span>Signal</span>
		</label>
		<label class="flex cursor-pointer items-center gap-2 text-sm">
			<input
				type="checkbox"
				data-testid="report-send-telegram"
				class="rounded border-input"
				checked={send_telegram}
				onchange={(e) => { send_telegram = (e.target as HTMLInputElement).checked; }}
			/>
			<span>Telegram</span>
		</label>
	</div>

	<!-- Alerts -->
	<div class="space-y-2">
		<h3 class="text-sm font-semibold">Alerts</h3>
		<div class="space-y-2">
			<label class="flex cursor-pointer items-center gap-2 text-sm">
				<input
					type="checkbox"
					data-testid="report-alert-changes"
					class="rounded border-input"
					checked={alert_on_changes}
					onchange={(e) => { alert_on_changes = (e.target as HTMLInputElement).checked; }}
				/>
				<span>Bei Aenderungen benachrichtigen</span>
			</label>
			<div class="grid grid-cols-1 gap-2 sm:grid-cols-3 pl-6">
				<label class="text-sm">
					<span class="block text-muted-foreground">Temperatur (C)</span>
					<input
						type="number"
						class="w-full rounded-md border border-input bg-background px-2 py-1 text-sm"
						step="0.1"
						bind:value={change_threshold_temp_c}
					/>
				</label>
				<label class="text-sm">
					<span class="block text-muted-foreground">Wind (km/h)</span>
					<input
						type="number"
						class="w-full rounded-md border border-input bg-background px-2 py-1 text-sm"
						step="0.1"
						bind:value={change_threshold_wind_kmh}
					/>
				</label>
				<label class="text-sm">
					<span class="block text-muted-foreground">Niederschlag (mm)</span>
					<input
						type="number"
						class="w-full rounded-md border border-input bg-background px-2 py-1 text-sm"
						step="0.1"
						bind:value={change_threshold_precip_mm}
					/>
				</label>
			</div>
		</div>
	</div>

	<!-- Erweitert -->
	<div class="space-y-2">
		<button
			type="button"
			data-testid="report-show-advanced"
			class="text-sm font-semibold text-primary hover:underline"
			onclick={() => { showAdvanced = !showAdvanced; }}
		>
			{showAdvanced ? 'Erweitert ausblenden' : 'Erweitert anzeigen'}
		</button>
		{#if showAdvanced}
			<div class="space-y-2 pl-2">
				<label class="flex cursor-pointer items-center gap-2 text-sm">
					<input
						type="checkbox"
						data-testid="report-compact-summary"
						class="rounded border-input"
						checked={show_compact_summary}
						onchange={(e) => { show_compact_summary = (e.target as HTMLInputElement).checked; }}
					/>
					<span>Kompakte Zusammenfassung</span>
				</label>
				<label class="flex cursor-pointer items-center gap-2 text-sm">
					<input
						type="checkbox"
						data-testid="report-show-daylight"
						class="rounded border-input"
						checked={show_daylight}
						onchange={(e) => { show_daylight = (e.target as HTMLInputElement).checked; }}
					/>
					<span>Tageslicht anzeigen</span>
				</label>
				<label class="text-sm">
					<span class="block text-muted-foreground">Wind-Exposition Mindesthoehe (m)</span>
					<input
						type="number"
						data-testid="report-wind-exposition"
						class="w-full rounded-md border border-input bg-background px-2 py-1 text-sm max-w-xs"
						value={wind_exposition_min_elevation_m ?? ''}
						oninput={(e) => {
							const v = (e.target as HTMLInputElement).value;
							wind_exposition_min_elevation_m = v === '' ? null : Number(v);
						}}
					/>
				</label>
				<label class="flex cursor-pointer items-center gap-2 text-sm">
					<input
						type="checkbox"
						data-testid="report-trend-morning"
						class="rounded border-input"
						checked={trend_morning}
						onchange={(e) => { trend_morning = (e.target as HTMLInputElement).checked; }}
					/>
					<span>Mehrtages-Trend: Morgen</span>
				</label>
				<label class="flex cursor-pointer items-center gap-2 text-sm">
					<input
						type="checkbox"
						data-testid="report-trend-evening"
						class="rounded border-input"
						checked={trend_evening}
						onchange={(e) => { trend_evening = (e.target as HTMLInputElement).checked; }}
					/>
					<span>Mehrtages-Trend: Abend</span>
				</label>
			</div>
		{/if}
	</div>
</div>
