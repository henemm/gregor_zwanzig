<script lang="ts">
	// Epic #138 Issue #177 — Dialog "Als Preset speichern". POST /api/metric-presets.
	// Issue #343 — ZEITHORIZONTE-Box: Eyebrow + Wording-Heuristik + Dot-Pattern;
	//              Save-Payload sendet metrics[] mit horizons mit (Schema #342).
	// Spec: docs/specs/modules/epic_138_174_178_metriken_ui.md §6
	//       docs/specs/modules/issue_343_horizon_chip_ui.md §5

	import { api } from '$lib/api.js';
	import type { MetricPreset, Horizons, MetricEntry } from '$lib/types';
	import { HORIZONS_ALL } from '$lib/types';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import { Eyebrow } from '$lib/components/ui/eyebrow/index.js';
	import { computeHorizonSummary, dotsForHorizons } from '$lib/utils/horizonHelpers';
	import { buildBucketSummary, type Buckets } from './metricsEditor.ts';

	type MetricCatalog = Record<string, MetricEntry[]>;

	interface Props {
		open: boolean;
		enabledMap: Record<string, boolean>;
		friendlyMap: Record<string, boolean>;
		horizonsMap: Record<string, Horizons>;
		catalog: MetricCatalog;
		indicatorCapable: (id: string) => boolean;
		onClose: () => void;
		onSaved: (preset: MetricPreset) => void;
		// Issue #365 — optional: bucket-bewusste Zusammenfassung (Spalten/Detail/Skala).
		buckets?: Buckets;
	}

	let {
		open = $bindable(false),
		enabledMap,
		friendlyMap,
		horizonsMap,
		catalog,
		indicatorCapable,
		onClose,
		onSaved,
		buckets,
	}: Props = $props();

	// Issue #365 — Spalten/Detail/Skala-Zähler (nur wenn Buckets übergeben).
	const bucketSummary = $derived(buckets ? buildBucketSummary(buckets, friendlyMap) : null);

	let name = $state('');
	let description = $state('');
	let isDefault = $state(false);
	let saving = $state(false);
	let error: string | null = $state(null);

	const allMetrics = $derived.by(() => {
		const out: MetricEntry[] = [];
		for (const ms of Object.values(catalog)) {
			for (const m of ms) out.push(m);
		}
		return out;
	});

	const enabledMetrics = $derived(allMetrics.filter((m) => enabledMap[m.id]));
	const enabledIds = $derived(enabledMetrics.map((m) => m.id));
	const indicatorCount = $derived(
		enabledIds.filter((id) => indicatorCapable(id) && friendlyMap[id]).length,
	);
	const rawCount = $derived(
		enabledIds.filter((id) => indicatorCapable(id) && !friendlyMap[id]).length,
	);

	// Issue #343 — Wording-Heuristik + Dot-Pattern fuer ZEITHORIZONTE-Box
	const horizonSummary = $derived(
		computeHorizonSummary(
			enabledMetrics.map((m) => ({
				metric_id: m.id,
				horizons: horizonsMap[m.id] ?? HORIZONS_ALL,
				enabled: true,
			})),
		),
	);

	const canSubmit = $derived(name.trim().length > 0 && !saving);

	function reset() {
		name = '';
		description = '';
		isDefault = false;
		saving = false;
		error = null;
	}

	function close() {
		open = false;
		reset();
		onClose();
	}

	async function submit() {
		if (!canSubmit) return;
		saving = true;
		error = null;
		try {
			// Issue #343 — Neues Schema (#342): metrics[] mit horizons statt
			// metrics: string[] + friendly_ids: string[].
			const preset = await api.post<MetricPreset>('/api/metric-presets', {
				name: name.trim(),
				description: description.trim() || undefined,
				is_default: isDefault,
				metrics: enabledMetrics.map((m) => ({
					metric_id: m.id,
					enabled: true,
					use_friendly_format: friendlyMap[m.id] ?? false,
					horizons: horizonsMap[m.id] ?? { ...HORIZONS_ALL },
				})),
			});
			onSaved(preset);
			open = false;
			reset();
		} catch (e: unknown) {
			error = (e as { error?: string })?.error ?? 'Speichern fehlgeschlagen';
		} finally {
			saving = false;
		}
	}
</script>

<Dialog.Root bind:open onOpenChange={(o) => { if (!o) close(); }}>
	<Dialog.Content data-testid="save-preset-dialog" class="save-preset-dialog">
		<Dialog.Header>
			<Dialog.Title>Als Preset speichern</Dialog.Title>
			<Dialog.Description>
				Speichert die aktuelle Metrik-Auswahl als wiederverwendbares Preset.
			</Dialog.Description>
		</Dialog.Header>

		<div class="dialog-body">
			<label class="field">
				<span class="field-label">Name <span class="required">*</span></span>
				<input
					data-testid="save-preset-name"
					type="text"
					bind:value={name}
					maxlength="40"
					placeholder="Mein Wandern-Preset"
					required
				/>
			</label>

			<label class="field">
				<span class="field-label">Beschreibung</span>
				<textarea
					data-testid="save-preset-description"
					bind:value={description}
					maxlength="120"
					rows="2"
					placeholder="Optimiert für Tages-Trips"
				></textarea>
			</label>

			<!-- Issue #343 — Box „WIRD GESPEICHERT" mit ZEITHORIZONTE-Block -->
			<div class="will-save-box" data-testid="save-preset-will-save-box">
				<Eyebrow>WIRD GESPEICHERT</Eyebrow>
				<div class="status" data-testid="save-preset-summary">
					<strong>{enabledIds.length}</strong> Metriken aktiv ·
					<strong>{rawCount}</strong> Rohwert ·
					<strong>{indicatorCount}</strong> Indikator
				</div>
				{#if bucketSummary}
					<div class="status" data-testid="save-preset-bucket-summary">
						<strong>{bucketSummary.spalten}</strong> Spalten ·
						<strong>{bucketSummary.detail}</strong> Detail ·
						<strong>{bucketSummary.skala}</strong> als Skala
					</div>
				{/if}
				<hr />
				<Eyebrow>ZEITHORIZONTE</Eyebrow>
				<div class="horizon-summary" data-testid="save-preset-horizon-summary">
					{horizonSummary || 'Keine Metrik aktiv'}
				</div>
				{#if enabledMetrics.length > 0}
					<div class="metric-dot-grid">
						{#each enabledMetrics as m}
							<div class="metric-dot-row" data-testid="save-preset-dot-row-{m.id}">
								<span class="metric-name">{m.label}</span>
								<span class="dots">{dotsForHorizons(horizonsMap[m.id] ?? HORIZONS_ALL)}</span>
							</div>
						{/each}
					</div>
				{/if}
			</div>

			<div class="field-inline">
				<Checkbox
					data-testid="save-preset-is-default"
					bind:checked={isDefault}
				>Als Standard für neue Trips</Checkbox>
			</div>

			{#if error}
				<div class="error" data-testid="save-preset-error">{error}</div>
			{/if}
		</div>

		<Dialog.Footer>
			<button type="button" class="btn-secondary" onclick={close} disabled={saving}>
				Abbrechen
			</button>
			<button
				type="button"
				class="btn-primary"
				data-testid="save-preset-submit"
				disabled={!canSubmit}
				onclick={submit}
			>
				{saving ? 'Speichern…' : 'Speichern'}
			</button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>

<style>
	.dialog-body {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-3);
		padding: var(--g-s-2) 0;
	}
	.field {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-1);
	}
	.field-label {
		font-size: var(--g-text-xs);
		font-weight: 500;
	}
	.required {
		color: var(--g-accent-deep);
	}
	.field input[type='text'],
	.field textarea {
		padding: var(--g-s-2) var(--g-s-3);
		border: 1px solid var(--g-ink-faint);
		border-radius: var(--g-radius-sm);
		font: inherit;
		font-size: var(--g-text-sm);
	}
	.field-inline {
		display: flex;
		align-items: center;
		gap: var(--g-s-2);
		font-size: var(--g-text-sm);
		cursor: pointer;
	}
	.will-save-box {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-2);
		padding: var(--g-s-4);
		background: var(--g-surface-1);
		border: 1px solid var(--g-ink-faint);
		border-radius: var(--g-radius-sm);
	}
	.will-save-box hr {
		border: none;
		border-top: 1px solid var(--g-ink-faint);
		margin: var(--g-s-1) 0;
		width: 100%;
	}
	.status {
		font-size: var(--g-text-sm);
		color: var(--g-ink);
	}
	.horizon-summary {
		font-size: var(--g-text-sm);
		color: var(--g-ink);
		font-family: var(--g-font-data);
	}
	.metric-dot-grid {
		display: grid;
		grid-template-columns: repeat(2, 1fr);
		gap: var(--g-s-1) var(--g-s-4);
		margin-top: var(--g-s-2);
	}
	.metric-dot-row {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: var(--g-s-2);
		font-size: var(--g-text-xs);
	}
	.metric-dot-row .metric-name {
		color: var(--g-ink);
	}
	.metric-dot-row .dots {
		font-family: var(--g-font-data);
		color: var(--g-ink);
		letter-spacing: 0.1em;
	}
	@media (max-width: 599px) {
		.metric-dot-grid {
			grid-template-columns: 1fr;
		}
	}
	.error {
		font-size: var(--g-text-xs);
		color: var(--g-danger);
	}
	.btn-primary, .btn-secondary {
		padding: var(--g-s-2) var(--g-s-4);
		border-radius: var(--g-radius-sm);
		font-size: var(--g-text-sm);
		font-weight: 500;
		cursor: pointer;
		border: 1px solid transparent;
	}
	.btn-primary {
		background: var(--g-accent);
		color: var(--g-paper);
	}
	.btn-primary:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
	.btn-secondary {
		background: var(--g-surface-0);
		border-color: var(--g-ink-faint);
		color: var(--g-ink);
	}
	@media (max-width: 767px) {
		.field input[type='text'], .field textarea {
			/* iOS zoom guard (#272): exakt 16px */
			font-size: 16px;
		}
	}
</style>
