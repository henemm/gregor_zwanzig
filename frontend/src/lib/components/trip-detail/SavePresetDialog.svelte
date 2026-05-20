<script lang="ts">
	// Epic #138 Issue #177 — Dialog "Als Preset speichern". POST /api/metric-presets.
	// Spec: docs/specs/modules/epic_138_174_178_metriken_ui.md §6

	import { api } from '$lib/api.js';
	import type { MetricPreset } from '$lib/types';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { Checkbox } from '$lib/components/ui/checkbox';

	interface MetricEntry {
		id: string;
		label: string;
		unit: string;
		category: string;
		default_enabled: boolean;
		has_friendly_format: boolean;
	}
	type MetricCatalog = Record<string, MetricEntry[]>;

	interface Props {
		open: boolean;
		enabledMap: Record<string, boolean>;
		friendlyMap: Record<string, boolean>;
		catalog: MetricCatalog;
		indicatorCapable: (id: string) => boolean;
		onClose: () => void;
		onSaved: (preset: MetricPreset) => void;
	}

	let { open = $bindable(false), enabledMap, friendlyMap, catalog, indicatorCapable, onClose, onSaved }: Props = $props();

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

	const enabledIds = $derived(allMetrics.filter((m) => enabledMap[m.id]).map((m) => m.id));
	const friendlyIds = $derived(
		enabledIds.filter((id) => indicatorCapable(id) && friendlyMap[id])
	);
	const indicatorCount = $derived(friendlyIds.length);
	// Rohwert: nur indicator-capable Metriken mit friendlyMap[id] === false zaehlen.
	// Metriken ohne indicatorCapable (z.B. temperature) zaehlen weder als Roh noch Indikator.
	// Konsistent mit metricsEditor.ts::buildPresetSummary.
	const rawCount = $derived(
		enabledIds.filter((id) => indicatorCapable(id) && !friendlyMap[id]).length
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
			const preset = await api.post<MetricPreset>('/api/metric-presets', {
				name: name.trim(),
				description: description.trim() || undefined,
				is_default: isDefault,
				metrics: enabledIds,
				friendly_ids: friendlyIds,
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
					placeholder="Optimiert für Tagestouren"
				></textarea>
			</label>

			<div class="summary" data-testid="save-preset-summary">
				{enabledIds.length} Metriken aktiv · {rawCount} Rohwert · {indicatorCount} Indikator
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
		gap: 0.75rem;
		padding: 0.5rem 0;
	}
	.field {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}
	.field-label {
		font-size: 0.8125rem;
		font-weight: 500;
	}
	.required {
		color: var(--g-accent);
	}
	.field input[type='text'],
	.field textarea {
		padding: 0.4rem 0.6rem;
		border: 1px solid var(--g-ink-faint);
		border-radius: 4px;
		font: inherit;
		font-size: 0.875rem;
	}
	.field-inline {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.875rem;
		cursor: pointer;
	}
	.summary {
		font-size: 0.8125rem;
		color: var(--g-ink-faint);
		padding: 0.5rem 0.6rem;
		background: var(--g-surface-1);
		border-radius: 4px;
	}
	.error {
		font-size: 0.8125rem;
		color: #dc2626;
	}
	.btn-primary, .btn-secondary {
		padding: 0.45rem 1rem;
		border-radius: 4px;
		font-size: 0.875rem;
		font-weight: 500;
		cursor: pointer;
		border: 1px solid transparent;
	}
	.btn-primary {
		background: var(--g-accent);
		color: #fff;
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
			font-size: 16px;
		}
	}
</style>
