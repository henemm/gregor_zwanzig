<script lang="ts">
	import { Tabs } from 'bits-ui';
	import TripOverview from './TripOverview.svelte';
	import WaypointsPanel from './WaypointsPanel.svelte';
	import WeatherMetricsTab from './WeatherMetricsTab.svelte';
	import AlertsTab from '$lib/components/alerts-tab/AlertsTab.svelte';
	import BriefingsTab from '$lib/components/briefings-tab/BriefingsTab.svelte';
	import {
		EmailIframe,
		SmsPhoneFrame,
		defaultReportType,
		type ReportType
	} from '$lib/components/preview';
	import type { Trip } from '$lib/types';

	interface Badges {
		overview?: number;
		stages?: number;
		weather?: number;
		briefings?: number;
		alerts?: number;
		preview?: number;
	}

	interface Props {
		initialTab?: string;
		badges?: Badges;
		trip?: Trip;
	}

	let { initialTab = 'overview', badges: badgesProp = {}, trip }: Props = $props();

	// Issue #302 — Auto-Badges aus Trip ableiten (Etappenanzahl + enabled Alerts).
	// Explizite Werte in der `badges` Prop ueberschreiben die Auto-Ableitung.
	const badges = $derived<Badges>({
		stages: badgesProp.stages ?? trip?.stages?.length ?? 0,
		alerts: badgesProp.alerts ?? (trip?.alert_rules ?? []).filter((r) => r.enabled).length,
		overview: badgesProp.overview,
		weather: badgesProp.weather,
		briefings: badgesProp.briefings,
		preview: badgesProp.preview
	});

	// Issue #302 — Labels & Badges nach Soll-Mockup:
	//   stages    -> "Etappen" (war: "Etappen & Wegpunkte")
	//   weather   -> "Wetter-Briefing" (war: "Wetter-Metriken")
	//   briefings -> "Reports & Kanäle" (war: "Briefing-Zeitplan")
	//   alerts    -> "Alarmregeln" (war: "Alerts")
	const TABS = [
		{ value: 'overview', label: 'Übersicht' },
		{ value: 'stages', label: 'Etappen' },
		{ value: 'weather', label: 'Wetter-Briefing' },
		{ value: 'briefings', label: 'Reports & Kanäle' },
		{ value: 'alerts', label: 'Alarmregeln' },
		{ value: 'preview', label: 'Vorschau' }
	] as const;

	const PLACEHOLDERS: Record<string, string> = {
		overview: 'Inhalt folgt mit Issue #154 (Hero) + #156 (Höhenprofil) + #157 (Stage-Liste)',
		stages: 'Inhalt folgt mit Epic #137 (Wegpunkt-Editor)',
		preview: 'Inhalt folgt mit Issue #189 (Vorschau-Integration)'
	};

	const VALID_VALUES: readonly string[] = TABS.map((t) => t.value);

	function resolve(value: string): string {
		return VALID_VALUES.includes(value) ? value : 'overview';
	}

	// Default 'overview'; $effect setzt sofort beim Mount den korrekten Tab
	// und synchronisiert bei späteren initialTab-Prop-Änderungen
	// (z.B. hash-only navigation ohne Re-Mount).
	let activeTab = $state<string>('overview');
	let previewType = $state<ReportType>(defaultReportType());

	$effect(() => {
		activeTab = resolve(initialTab);
	});

	function handleValueChange(value: string): void {
		activeTab = value;
		// Update URL hash without triggering SvelteKit navigation — avoids
		// focus loss after keyboard navigation and avoids component re-mount.
		if (typeof window !== 'undefined') {
			history.replaceState(history.state, '', `#${value}`);
		}
	}
</script>

<Tabs.Root value={activeTab} onValueChange={handleValueChange}>
	<Tabs.List data-testid="trip-detail-tab-list" class="trip-tabs-list">
		{#each TABS as tab}
			<Tabs.Trigger
				value={tab.value}
				data-testid="trip-detail-tab-{tab.value}"
				class="trip-tab-trigger"
			>
				{tab.label}
				{#if (badges[tab.value] ?? 0) >= 1}
					<span data-testid="trip-detail-tab-badge-{tab.value}" class="trip-tab-badge">
						{badges[tab.value]}
					</span>
				{/if}
			</Tabs.Trigger>
		{/each}
	</Tabs.List>

	{#each TABS as tab}
		<Tabs.Content value={tab.value} data-testid="trip-detail-panel-{tab.value}">
			{#if tab.value === 'overview' && trip}
				<TripOverview {trip} />
			{:else if tab.value === 'stages' && trip}
				<WaypointsPanel {trip} />
			{:else if tab.value === 'weather' && trip}
				<WeatherMetricsTab {trip} />
			{:else if tab.value === 'alerts' && trip}
				<AlertsTab {trip} />
			{:else if tab.value === 'briefings' && trip}
				<BriefingsTab {trip} />
			{:else if tab.value === 'preview' && trip}
				<div class="preview-shell">
					<div class="preview-controls" data-testid="preview-controls">
						<label>
							<input type="radio" bind:group={previewType} value="morning" /> Morgen
						</label>
						<label>
							<input type="radio" bind:group={previewType} value="evening" /> Abend
						</label>
					</div>
					<div class="preview-grid">
						<EmailIframe tripId={trip.id} type={previewType} />
						<SmsPhoneFrame tripId={trip.id} type={previewType} />
					</div>
				</div>
			{:else}
				<p class="p-4 text-sm">{PLACEHOLDERS[tab.value]}</p>
			{/if}
		</Tabs.Content>
	{/each}
</Tabs.Root>

<style>
	:global(.trip-tabs-list) {
		display: flex;
		border-bottom: 1px solid var(--g-ink-faint);
	}
	:global(.trip-tab-trigger) {
		position: relative;
		padding: 0.5rem 1rem;
		font-size: 0.875rem;
		font-weight: 500;
		border-bottom: 2px solid transparent;
		background: transparent;
		cursor: pointer;
	}
	:global(.trip-tab-trigger[data-state='active']) {
		border-bottom-color: var(--g-accent);
	}
	:global(.trip-tab-badge) {
		display: inline-block;
		margin-left: 0.375rem;
		padding: 0.125rem 0.375rem;
		border-radius: 9999px;
		background: var(--g-accent);
		color: white;
		font-size: 0.75rem;
		font-weight: 600;
	}
	.preview-shell {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		padding: 1rem;
	}
	.preview-controls {
		display: flex;
		gap: 1.25rem;
		font-size: 0.875rem;
		color: var(--g-ink, #1a1a18);
	}
	.preview-controls label {
		display: inline-flex;
		align-items: center;
		gap: 0.375rem;
		cursor: pointer;
	}
	.preview-grid {
		display: grid;
		gap: 1.5rem;
		grid-template-columns: minmax(0, 1fr) 360px;
		align-items: start;
	}
	@media (max-width: 960px) {
		.preview-grid {
			grid-template-columns: 1fr;
		}
	}
	@media (max-width: 899px) {
		/* Scrollbares Tab-Band */
		:global(.trip-tabs-list) {
			overflow-x: auto;
			white-space: nowrap;
			scrollbar-width: none;
			-ms-overflow-style: none;
			scroll-snap-type: x mandatory;
		}
		:global(.trip-tabs-list)::-webkit-scrollbar {
			display: none;
		}

		/* Pill-Trigger: einzeilig, nicht schrumpfbar */
		:global(.trip-tab-trigger) {
			white-space: nowrap;
			flex-shrink: 0;
			scroll-snap-align: start;
			border-bottom: none;
			border-radius: var(--g-radius-pill, 99rem);
			padding: 0.375rem 0.875rem;
		}

		/* Aktiver Pill: gefüllt mit Akzentfarbe */
		:global(.trip-tab-trigger[data-state='active']) {
			background: var(--g-accent);
			color: var(--g-paper, #f6f4ee);
			border-bottom-color: transparent;
		}
	}
</style>
