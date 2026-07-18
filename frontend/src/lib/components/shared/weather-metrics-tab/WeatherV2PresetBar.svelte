<script lang="ts">
	// Issue #587 — Wetter-Metriken-Tab v2: Abschnitt 1 Profil/Preset.
	// 1:1 nach WM2_PresetBar aus screen-trip-edit-v2-weather.jsx.
	// STANDALONE: nicht abhängig von shared/OutputLayoutEditor oder Geschwistern.
	import type { MetricPreset } from '$lib/types';

	interface Template {
		id: string;
		label: string;
		metrics: string[];
	}

	interface Props {
		selectedTemplate: string;
		dirty: boolean;
		templates: Template[];
		userPresets: MetricPreset[];
		onSelectPreset: (id: string) => void;
		onOpenSaveDialog: () => void;
	}

	let { selectedTemplate, dirty, templates, userPresets, onSelectPreset, onOpenSaveDialog }: Props = $props();
</script>

<div class="preset-bar">
	<div class="pill-row">
		{#each userPresets as p}
			{@const active = p.id === selectedTemplate && !dirty}
			<button
				type="button"
				class="preset-pill"
				class:active
				onclick={() => onSelectPreset(p.id)}
				title={p.name}
				data-testid="weather-preset-pill-{p.id}"
			>
				{p.name}
				<span class="own-badge" data-testid="weather-preset-own-badge-{p.id}">Eigene</span>
			</button>
		{/each}
		{#each templates as t}
			{@const active = t.id === selectedTemplate && !dirty}
			<button
				type="button"
				class="preset-pill"
				class:active
				onclick={() => onSelectPreset(t.id)}
				title={t.label}
				data-testid="weather-preset-pill-{t.id}"
			>
				{t.label}
			</button>
		{/each}
	</div>
	{#if dirty}
		<div class="dirty-hint">
			Geändert —
			<button type="button" class="save-link" onclick={onOpenSaveDialog}>
				als eigenes Profil speichern
			</button>
		</div>
	{/if}
</div>

<style>
	.preset-bar {
		display: flex;
		flex-direction: column;
		gap: 7px;
	}
	.pill-row {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
	}
	.preset-pill {
		padding: 7px 13px;
		border-radius: var(--g-r-pill);
		cursor: pointer;
		border: 1px solid var(--g-rule);
		background: var(--g-card);
		color: var(--g-ink-2);
		font-size: 12.5px;
		font-weight: 500;
		font-family: inherit;
		transition: border-color 120ms, background 120ms, color 120ms;
	}
	.preset-pill.active {
		border-color: var(--g-accent);
		background: var(--g-accent-tint);
		color: var(--g-accent-deep);
		font-weight: 600;
	}
	.preset-pill:hover:not(.active) {
		border-color: var(--g-ink-faint);
		background: var(--g-card-alt);
	}
	.dirty-hint {
		font-size: 12px;
		color: var(--g-ink-3);
	}
	.save-link {
		color: var(--g-accent);
		background: none;
		border: none;
		cursor: pointer;
		font-size: 12px;
		padding: 0;
		font-family: inherit;
		text-decoration: underline;
		text-underline-offset: 2px;
	}
	.own-badge {
		display: inline-block;
		margin-left: 5px;
		padding: 1px 5px;
		border-radius: 3px;
		font-size: 10px;
		font-family: var(--g-font-mono, monospace);
		font-weight: 600;
		letter-spacing: 0.04em;
		color: var(--g-accent-deep, #1a5940);
		background: var(--g-accent-tint, #e8f5ee);
		border: 1px solid var(--g-accent, #2d7a55);
		vertical-align: middle;
		line-height: 1.2;
	}
</style>
