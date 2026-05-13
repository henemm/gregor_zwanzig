<script lang="ts">
	import { Tabs } from 'bits-ui';
	import TripOverview from './TripOverview.svelte';
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

	let { initialTab = 'overview', badges = {}, trip }: Props = $props();

	const TABS = [
		{ value: 'overview', label: 'Übersicht' },
		{ value: 'stages', label: 'Etappen & Wegpunkte' },
		{ value: 'weather', label: 'Wetter-Metriken' },
		{ value: 'briefings', label: 'Briefing-Zeitplan' },
		{ value: 'alerts', label: 'Alerts' },
		{ value: 'preview', label: 'Vorschau' }
	] as const;

	const PLACEHOLDERS: Record<string, string> = {
		overview: 'Inhalt folgt mit Issue #154 (Hero) + #156 (Höhenprofil) + #157 (Stage-Liste)',
		stages: 'Inhalt folgt mit Epic #137 (Wegpunkt-Editor)',
		weather: 'Inhalt folgt mit Issue #158 + Epic #138 (Metriken-Editor)',
		briefings: 'Inhalt folgt mit Issue #159 (rechte Spalte)',
		alerts: 'Inhalt folgt mit Epic #139 (Alert-Konfigurator)',
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
			{:else}
				<p class="p-4 text-sm">{PLACEHOLDERS[tab.value]}</p>
			{/if}
		</Tabs.Content>
	{/each}
</Tabs.Root>

<style>
	:global(.trip-tabs-list) {
		display: flex;
		border-bottom: 1px solid var(--g-border, #ddd);
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
</style>
