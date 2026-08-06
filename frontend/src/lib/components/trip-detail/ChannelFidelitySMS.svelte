<script lang="ts">
	// Issue #496 — Schicht 2 (SMS): Token-Stream aus dem echten Backend-
	// Renderer (Issue #923, ADR-0011 — kein zweiter Renderer im Frontend).
	// SMS ist KEIN Spalten-Kanal — der Renderer uebersetzt nur
	// entscheidungskritische Metriken in kompakte Tokens (sms_format.md §6).
	import { untrack } from 'svelte';
	import { api } from '$lib/api';
	import type { MetricEntry } from './metricsEditor.ts';
	import { loadSmsFidelityPreview, type SmsFidelityPreview } from './smsFidelityPreview.ts';

	interface Props {
		primary: string[];
		secondary: string[];
		metricById: Record<string, MetricEntry>;
		/** RED-Infrastruktur (#923, analog `profileOverride` in
		 * VTBriefingChannels.svelte): optionaler SSR-Test-Override fuer die
		 * Server-Vorschau. Falls gesetzt (auch explizit `null`) wird `preview`
		 * daraus initialisiert und der Fetch uebersprungen — `svelte/server`s
		 * `render()` fuehrt weder `onMount` noch `$effect` aus, ohne diesen
		 * Override bliebe `preview` in SSR-Tests immer `null`. Ohne Uebergabe
		 * unveraendertes Verhalten (Fetch bei Mount/Aenderung von
		 * primary/secondary). */
		previewOverride?: SmsFidelityPreview | null;
	}
	let { primary, secondary, metricById, previewOverride }: Props = $props();

	let preview = $state<SmsFidelityPreview | null>(
		untrack(() => (previewOverride !== undefined ? previewOverride : null))
	);
	let loading = $state(false);
	let error = $state<string | null>(null);

	const metricIds = $derived([...primary, ...secondary]);

	$effect(() => {
		const ids = metricIds;
		if (previewOverride !== undefined) return;
		loading = true;
		error = null;
		loadSmsFidelityPreview(ids, (path, body) => api.post<SmsFidelityPreview>(path, body)).then(
			(result) => {
				preview = result.preview;
				error = result.error;
				loading = false;
			}
		);
	});

	function labelOf(id: string): string {
		return metricById[id]?.label ?? id;
	}

	const carried = $derived(
		metricIds.filter((id) => preview?.carried_ids.includes(id) ?? false)
	);
	const dropped = $derived(metricIds.filter((id) => !carried.includes(id)));
	const line = $derived(preview?.line ?? '');
	const charCount = $derived(preview?.char_count ?? 0);
	const maxLength = $derived(preview?.max_length ?? 160);
	const overLimit = $derived(charCount > maxLength);
</script>

<div class="fidelity" data-testid="channel-fidelity-sms">
	<div class="chat">
		<div class="bubble">
			<pre class="mono line">{line}</pre>
		</div>
	</div>

	<div class="counter mono" class:over={overLimit}>
		{#if loading && preview === null}
			Lade Vorschau…
		{:else}
			{charCount}/{maxLength} Zeichen · gesendet 06:00
		{/if}
	</div>

	{#if error !== null}
		<p class="error">{error}</p>
	{/if}

	<div class="grid">
		<div class="col">
			<div class="col-head mono ok">✓ {carried.length} mit SMS-Code</div>
			{#if carried.length === 0}
				<div class="empty mono">— keine —</div>
			{:else}
				{#each carried as id}
					<div class="row">
						<span class="row-label">{labelOf(id)}</span>
						<span class="row-token mono">{metricById[id]?.sms_code ?? ''}</span>
					</div>
				{/each}
			{/if}
		</div>
		<div class="col">
			<div class="col-head mono warn">✕ {dropped.length} fallen weg</div>
			{#if dropped.length === 0}
				<div class="empty mono">— keine —</div>
			{:else}
				{#each dropped as id}
					<div class="row">
						<span class="row-label">{labelOf(id)}</span>
						<span class="row-token mono muted">
							{metricById[id]?.sms_code ? 'Zeichenlimit' : 'kein Code'}
						</span>
					</div>
				{/each}
			{/if}
		</div>
	</div>

	<div class="banner">
		SMS ist <strong>kein Spalten-Kanal</strong>: der Renderer uebersetzt nur
		entscheidungskritische Metriken in kompakte Tokens. Alles, was keinen Code
		hat oder die {maxLength}-Zeichen-Grenze sprengt, faellt heraus.
	</div>
</div>

<style>
	.fidelity {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-3);
	}
	.chat {
		background: #e9e6dc;
		border-radius: var(--g-r-3, 16px);
		padding: var(--g-s-4);
	}
	.bubble {
		background: #e5e5ea;
		border-radius: 14px;
		padding: var(--g-s-3);
		max-width: 320px;
	}
	.line {
		margin: 0;
		font-size: var(--g-text-xs);
		line-height: 1.5;
		word-break: break-all;
		white-space: pre-wrap;
		color: var(--g-ink);
	}
	.counter {
		font-size: var(--g-text-xs);
		color: var(--g-ink-muted);
	}
	.counter.over {
		color: var(--g-danger, #c83e3e);
		font-weight: 600;
	}
	.grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: var(--g-s-3);
	}
	@media (max-width: 600px) {
		.grid { grid-template-columns: 1fr; }
	}
	.col {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}
	.col-head {
		font-size: var(--g-text-xs);
		font-weight: 700;
		letter-spacing: var(--g-track-wide);
		padding-bottom: 4px;
		border-bottom: 1px solid var(--g-rule-soft);
	}
	.col-head.ok {
		color: var(--g-success, #2f7d4f);
	}
	.col-head.warn {
		color: var(--g-warning);
	}
	.row {
		display: flex;
		justify-content: space-between;
		gap: var(--g-s-2);
		font-size: var(--g-text-xs);
		padding: 2px 0;
	}
	.row-label {
		color: var(--g-ink);
	}
	.row-token {
		color: var(--g-ink-muted);
	}
	.row-token.muted {
		font-style: italic;
		font-size: 10px;
	}
	.empty {
		font-size: var(--g-text-xs);
		color: var(--g-ink-muted);
		font-style: italic;
		padding: 2px 0;
	}
	.banner {
		padding: var(--g-s-2) var(--g-s-3);
		border-radius: var(--g-radius-sm);
		font-size: var(--g-text-xs);
		line-height: 1.5;
		background: color-mix(in srgb, var(--g-warning) 8%, transparent);
		border-left: 3px solid var(--g-warning);
		color: var(--g-ink);
	}
	.error {
		margin: 0;
		font-size: var(--g-text-xs);
		color: var(--g-danger, #dc2626);
	}
</style>
