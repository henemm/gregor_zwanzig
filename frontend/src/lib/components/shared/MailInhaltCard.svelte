<script lang="ts">
	// Issue #2277 S5: Karte "E-Mail-Inhalt" als geteilter Baustein (Hub + Anlegen).
	// Ehemals der Mail-Zweig der alten Report-Config-Section (entfernt).
	// Nur Mail-Felder: Kanaele und Zeitplan besitzt VersandTab, telegram_style
	// ebenfalls — der Baustein schreibt sie nie (Fehlerklasse Fix-Loop 4, #1738).
	import { onMount, untrack } from 'svelte';
	import type { ReportConfig } from '$lib/types';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import * as Card from '$lib/components/ui/card/index.js';
	import { baueReportConfigPayload } from './versand-tab/reportConfigPayload.ts';
	import { CONTENT_MODULE_DESCRIPTIONS } from './mailInhaltKonstanten.ts';
	import { ladeMailZustand } from './mailInhaltZustand.ts';

	interface Props {
		reportConfig: ReportConfig | undefined;
	}
	let { reportConfig = $bindable() }: Props = $props();

	// Original-Blob (Rueckfall fuer den ersten Effekt-Lauf vor onMount).
	let originalReportConfig: ReportConfig = {};

	// Startzustand BEIM ERZEUGEN aus dem Blob (untrack) — onMount laeuft serverseitig
	// nie; ein Wert, der erst danach erscheint, ist einen Wimpernschlag falsch.
	const start = ladeMailZustand(untrack(() => (reportConfig ?? {}) as ReportConfig));
	let email_format = $state<'full' | 'compact'>(start.email_format);
	let show_outlook = $state(start.show_outlook);
	let show_stage_stats = $state(start.show_stage_stats);
	let show_yesterday_comparison = $state(start.show_yesterday_comparison);

	// Bestandsdaten-Erhalt: nicht im UI gezeigt, aber im Read-Modify-Write benoetigt.
	let show_compact_summary = $state(start.show_compact_summary);
	let wind_exposition_min_elevation_m: number | null = $state(start.wind_exposition_min_elevation_m);
	let show_quick_take_tags = $state(start.show_quick_take_tags);
	let show_stability = $state(start.show_stability);
	let show_highlights = $state(start.show_highlights);
	let dailySummaryMetrics = $state<string[]>(start.daily_summary_metrics);
	let show_metrics_summary = $state(start.show_metrics_summary);

	onMount(() => {
		if (!reportConfig) return;
		originalReportConfig = { ...reportConfig };
		const z = ladeMailZustand(originalReportConfig);
		show_compact_summary = z.show_compact_summary;
		wind_exposition_min_elevation_m = z.wind_exposition_min_elevation_m;
		show_stage_stats = z.show_stage_stats;
		show_quick_take_tags = z.show_quick_take_tags;
		show_stability = z.show_stability;
		show_highlights = z.show_highlights;
		dailySummaryMetrics = z.daily_summary_metrics;
		show_metrics_summary = z.show_metrics_summary;
		show_outlook = z.show_outlook;
		email_format = z.email_format;
		show_yesterday_comparison = z.show_yesterday_comparison;
	});

	// Write-Back: Read-Modify-Write. Basis ist der LEBENDE Blob (untrack -> kein
	// Selbst-Trigger), nicht der Mount-Schnappschuss (#1738: zwei Schreiber im
	// selben report_config). showSchedule/showChannels bewusst literal false:
	// Zeitplan-/Kanal-Felder und telegram_style besitzt VersandTab. `zustand` ist
	// rein formal — seine Gruppen werden bei false nicht geschrieben.
	$effect(() => {
		reportConfig = baueReportConfigPayload({
			snapshot: originalReportConfig as Record<string, unknown>,
			live: untrack(() => reportConfig) as Record<string, unknown> | undefined,
			eigene: {
				show_compact_summary,
				wind_exposition_min_elevation_m,
				show_stage_stats,
				show_quick_take_tags,
				show_stability,
				show_highlights,
				daily_summary_metrics: [...dailySummaryMetrics],
				show_metrics_summary,
				show_outlook,
				email_format,
				show_yesterday_comparison,
			},
			showSchedule: false,
			showChannels: false,
			zustand: {
				morning_enabled: false,
				evening_enabled: false,
				morning_time: '07:00',
				evening_time: '18:00',
				multi_day_trend_morning: false,
				multi_day_trend_evening: false,
				send_email: true,
				send_telegram: false,
				send_sms: false,
				send_premium_sms: false,
			},
		}) as ReportConfig;
	});
</script>

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

	<!-- Inhalts-Bausteine (Issue #723: genau 3, Issue #774: direkt ohne Einklapp-Toggle).
	     Fix #971/#774: "Metriken-Überblick"-Checkbox entfernt — der Block wird seit
	     #790 im Mail-Renderer unconditional gerendert. -->
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
