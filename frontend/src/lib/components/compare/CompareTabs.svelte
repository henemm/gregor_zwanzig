<script lang="ts">
	// Issue #517 — CompareTabs: 6-Tab-Orchestrator für /compare/[id] Detail-Seite.
	//
	// Tabs: Übersicht · Orte · Idealwerte · Layout · Versand · Vorschau
	//
	// URL-Sync via history.replaceState (?tab=VALUE), kein Hash wie TripTabs.
	// Mobile (<900px): scrollbare Pill-Tabs analog TripTabs.svelte.
	//
	// Spec: docs/specs/modules/issue_517_compare_hub.md

	import { Segmented, Dot, Pill, Btn } from '$lib/components/atoms';
	import CompareLocationRow from '$lib/components/molecules/CompareLocationRow.svelte';
	import CompareIdealRow from '$lib/components/molecules/CompareIdealRow.svelte';
	import CompareLayoutRow from '$lib/components/molecules/CompareLayoutRow.svelte';
	import {
		deriveStatusFromPreset,
		presetScheduleLabel,
		formatLastSent,
		STATUS_MAP
	} from '$lib/components/compare/subscriptionHelpers.js';
	import type { ComparePreset, Location } from '$lib/types.js';

	interface Props {
		preset: ComparePreset;
		locations: Location[];
		initialTab?: string;
	}

	let { preset, locations, initialTab = 'uebersicht' }: Props = $props();

	const TABS = [
		{ value: 'uebersicht', label: 'Übersicht' },
		{ value: 'orte', label: 'Orte' },
		{ value: 'idealwerte', label: 'Idealwerte' },
		{ value: 'layout', label: 'Layout' },
		{ value: 'versand', label: 'Versand' },
		{ value: 'vorschau', label: 'Vorschau' }
	] as const;

	const segmentedOptions = $derived(
		TABS.map((tab) => ({
			value: tab.value,
			label: tab.label,
			testid: `compare-detail-tab-${tab.value}`
		}))
	);

	const VALID_VALUES: readonly string[] = TABS.map((t) => t.value);
	function resolve(value: string): string {
		return VALID_VALUES.includes(value) ? value : 'uebersicht';
	}

	let activeTab = $state<string>('uebersicht');
	$effect(() => {
		activeTab = resolve(initialTab);
	});

	function handleValueChange(value: string): void {
		activeTab = value;
		if (typeof window !== 'undefined') {
			const url = new URL(window.location.href);
			url.searchParams.set('tab', value);
			history.replaceState(history.state, '', url.toString());
		}
	}

	// Tab-Daten ──────────────────────────────────────────────────────────────────

	const status = $derived(deriveStatusFromPreset(preset));
	const statusInfo = $derived(STATUS_MAP[status]);

	// Orts-Auflösung: location_ids → locations[] (mit elevation_m für CompareLocationRow).
	const resolvedLocations = $derived(
		preset.location_ids.map((id, idx) => ({
			rank: idx + 1,
			loc: locations.find((l) => l.id === id)
		}))
	);

	const idealRanges = $derived(
		preset.display_config?.ideal_ranges as
			| Record<string, { min: number; max: number; unit?: string }>
			| undefined
	);

	const CHANNEL_COLS: Record<string, number> = {
		email: 99,
		telegram: 8,
		signal: 6,
		sms: 0
	};
	const channels = ['email', 'telegram', 'signal', 'sms'];
</script>

<div class="compare-tabs" data-testid="compare-detail-tab-list">
	<Segmented options={segmentedOptions} selected={activeTab} onselect={handleValueChange} />

	{#if activeTab === 'uebersicht'}
		<div class="tab-panel" data-testid="compare-detail-panel-uebersicht">
			<!-- Monitoring-Streifen -->
			<div class="monitoring-strip">
				<div class="monitoring-item">
					<Dot style="background:{statusInfo.dot}" />
					<span class="monitoring-label-inline">{statusInfo.label}</span>
				</div>
				<div class="monitoring-item-col">
					<span class="monitoring-label">Nächster Versand</span>
					<span class="monitoring-value">{presetScheduleLabel(preset)}</span>
				</div>
				<div class="monitoring-item-col">
					<span class="monitoring-label">Zuletzt</span>
					<span class="monitoring-value">{formatLastSent(preset.letzter_versand)}</span>
				</div>
				<div class="monitoring-item-col">
					<span class="monitoring-label">Kanäle</span>
					<span class="monitoring-value">{preset.empfaenger.length}</span>
				</div>
			</div>

			<!-- Summary -->
			<div class="summary">
				<p>
					{preset.display_config?.region ?? '—'} · {preset.profil} · {preset.location_ids.length}
					{preset.location_ids.length === 1 ? 'Ort' : 'Orte'}
				</p>
			</div>

			<!-- Edit-Links -->
			<div class="edit-links">
				<a href="?tab=orte">Orte bearbeiten →</a>
				<a href="?tab=idealwerte">Idealwerte bearbeiten →</a>
				<a href="?tab=layout">Layout bearbeiten →</a>
				<a href="?tab=versand">Versand bearbeiten →</a>
			</div>
		</div>
	{/if}

	{#if activeTab === 'orte'}
		<div class="tab-panel" data-testid="compare-detail-panel-orte">
			{#if resolvedLocations.length === 0}
				<p class="empty-state">Noch keine Orte ausgewählt.</p>
			{:else}
				{#each resolvedLocations as { rank, loc }}
					{#if loc}
						<CompareLocationRow {loc} index={rank} />
					{/if}
				{/each}
			{/if}
			<div class="footer-link">
				<a href="/compare/{preset.id}/edit">Im Wizard bearbeiten →</a>
			</div>
		</div>
	{/if}

	{#if activeTab === 'idealwerte'}
		<div class="tab-panel" data-testid="compare-detail-panel-idealwerte">
			{#if idealRanges && Object.keys(idealRanges).length > 0}
				{#each Object.entries(idealRanges) as [metric, r]}
					<CompareIdealRow
						item={{
							metric,
							range: `${r.min}–${r.max}${r.unit ? ' ' + r.unit : ''}`,
							weight: 'mittel'
						}}
					/>
				{/each}
			{:else}
				<p class="empty-state">Keine Idealwerte konfiguriert.</p>
			{/if}
			<div class="footer-link">
				<a href="/compare/{preset.id}/edit">Im Wizard bearbeiten →</a>
			</div>
		</div>
	{/if}

	{#if activeTab === 'layout'}
		<div class="tab-panel" data-testid="compare-detail-panel-layout">
			{#each channels as ch}
				<CompareLayoutRow channel={ch} cols={CHANNEL_COLS[ch]} />
			{/each}
			<div class="footer-link">
				<a href="/compare/{preset.id}/edit">Im Wizard bearbeiten →</a>
			</div>
		</div>
	{/if}

	{#if activeTab === 'versand'}
		<div class="tab-panel" data-testid="compare-detail-panel-versand">
			<dl class="kv-list">
				<dt>Zeitplan</dt>
				<dd>{presetScheduleLabel(preset)}</dd>
				<dt>Zeitfenster</dt>
				<dd>{preset.hour_from}–{preset.hour_to} Uhr</dd>
				<dt>Profil</dt>
				<dd>{preset.profil}</dd>
			</dl>
			<div class="empfaenger-block">
				<span class="monitoring-label">Empfänger</span>
				<div class="pill-row">
					{#each preset.empfaenger as e}
						<Pill>{e}</Pill>
					{:else}
						<span class="empty-state">Keine Empfänger</span>
					{/each}
				</div>
			</div>
			{#if deriveStatusFromPreset(preset) === 'draft'}
				<p class="draft-hint">Noch nicht aktiv</p>
			{/if}
			<div class="footer-link">
				<a href="/compare/{preset.id}/edit">Im Wizard bearbeiten →</a>
			</div>
		</div>
	{/if}

	{#if activeTab === 'vorschau'}
		<div class="tab-panel" data-testid="compare-detail-panel-vorschau">
			<p class="placeholder">E-Mail-Vorschau folgt, sobald CompareEmail implementiert ist.</p>
			<p class="hint">Dein Briefing wird im Postfach gelesen — nicht hier.</p>
			<div class="footer-link">
				<Btn href="/compare/{preset.id}/edit">Test-Briefing senden</Btn>
			</div>
		</div>
	{/if}
</div>

<style>
	.compare-tabs :global([data-slot='segmented']) {
		display: flex;
		border-bottom: 1px solid var(--g-ink-faint);
	}
	.compare-tabs :global([data-slot='segmented-item']) {
		position: relative;
		padding: 0.5rem 1rem;
		font-size: 0.875rem;
		font-weight: 500;
		border-bottom: 2px solid transparent;
		background: transparent;
		color: var(--g-ink);
		cursor: pointer;
	}
	.compare-tabs :global([data-slot='segmented-item'][data-active='true']) {
		background: transparent;
		color: var(--g-ink);
	}
	.compare-tabs :global([data-slot='segmented-item'][data-state='active']) {
		border-bottom-color: var(--g-accent);
	}

	.tab-panel {
		padding: 1.5rem 0;
	}

	.monitoring-strip {
		display: flex;
		gap: 2rem;
		padding: 0.75rem 1rem;
		margin-bottom: 1.5rem;
		border-radius: var(--g-r-2, 0.5rem);
		background: var(--g-paper, #f6f4ee);
		border: 1px solid var(--g-rule-soft);
		font-size: 0.875rem;
		flex-wrap: wrap;
	}
	.monitoring-item {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.monitoring-item-col {
		display: flex;
		flex-direction: column;
	}
	.monitoring-label {
		font-size: 0.75rem;
		color: var(--g-ink-3);
		text-transform: uppercase;
		letter-spacing: 0.06em;
		font-family: var(--g-font-mono);
	}
	.monitoring-label-inline {
		font-weight: 500;
	}
	.monitoring-value {
		font-size: 0.875rem;
	}

	.summary {
		margin-bottom: 1.5rem;
		font-size: 0.875rem;
		color: var(--g-ink-3);
	}

	.edit-links {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.edit-links a {
		color: var(--g-accent);
		font-size: 0.875rem;
		text-decoration: none;
	}
	.edit-links a:hover {
		text-decoration: underline;
	}

	.empty-state {
		font-size: 0.875rem;
		color: var(--g-ink-3);
		padding: 1rem 0;
	}

	.footer-link {
		margin-top: 1rem;
	}
	.footer-link a {
		color: var(--g-accent);
		font-size: 0.875rem;
		text-decoration: none;
	}
	.footer-link a:hover {
		text-decoration: underline;
	}

	.kv-list {
		display: grid;
		grid-template-columns: max-content 1fr;
		column-gap: 1.5rem;
		row-gap: 0.5rem;
		margin: 0 0 1rem 0;
		font-size: 0.875rem;
	}
	.kv-list dt {
		color: var(--g-ink-3);
		font-family: var(--g-font-mono);
		font-size: 0.75rem;
		text-transform: uppercase;
		letter-spacing: 0.06em;
	}
	.kv-list dd {
		margin: 0;
	}

	.empfaenger-block {
		margin-bottom: 1rem;
	}
	.pill-row {
		display: flex;
		flex-wrap: wrap;
		gap: 0.25rem;
		margin-top: 0.5rem;
	}

	.draft-hint {
		font-size: 0.875rem;
		color: var(--g-ink-3);
		font-style: italic;
		margin: 0.5rem 0;
	}

	.placeholder {
		font-size: 0.875rem;
		color: var(--g-ink);
		margin: 0 0 0.5rem 0;
	}
	.hint {
		font-size: 0.8125rem;
		color: var(--g-ink-3);
		margin: 0 0 1rem 0;
	}

	@media (max-width: 899px) {
		/* Scrollbares Tab-Band */
		.compare-tabs :global([data-slot='segmented']) {
			overflow-x: auto;
			white-space: nowrap;
			scrollbar-width: none;
			-ms-overflow-style: none;
			scroll-snap-type: x mandatory;
		}
		.compare-tabs :global([data-slot='segmented'])::-webkit-scrollbar {
			display: none;
		}

		/* Pill-Trigger: einzeilig, nicht schrumpfbar */
		.compare-tabs :global([data-slot='segmented-item']) {
			white-space: nowrap;
			flex-shrink: 0;
			scroll-snap-align: start;
			border-bottom: none;
			border-radius: var(--g-radius-pill, 99rem);
			padding: 0.375rem 0.875rem;
		}

		/* Aktiver Pill: gefüllt mit Akzentfarbe */
		.compare-tabs :global([data-slot='segmented-item'][data-state='active']) {
			background: var(--g-accent);
			color: var(--g-paper, #f6f4ee);
			border-bottom-color: transparent;
		}

		.monitoring-strip {
			gap: 1rem;
		}
	}
</style>
