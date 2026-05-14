<script lang="ts">
	// Issue #223 — Eine Zeile pro AlertRule mit View- und Edit-Modus.
	// Spec: docs/specs/modules/issue_223_alert_rules_editor.md §3.
	//
	// View-Mode: Label + Threshold + Severity-Pill + Enabled-Toggle +
	//            [Bearbeiten] + [Löschen]
	// Edit-Mode: Metric-Select + Threshold (number-input ODER thunder-select
	//            bei thunder_level) + Severity-Select + Enabled + Save/Cancel
	// F004-Guard: {#if info} um alles — unbekannte Metric crasht nicht.

	import type { AlertRule, AlertMetric } from '$lib/types';
	import { Pill } from '$lib/components/ui/pill';
	import {
		ALERT_METRIC_LABELS,
		ALERT_SEVERITY_TONE,
		thunderLevelLabel
	} from '$lib/utils/alertMetricLabels';

	let {
		rule,
		onUpdate,
		onDelete
	}: {
		rule: AlertRule;
		onUpdate: (r: AlertRule) => void;
		onDelete: () => void;
	} = $props();

	let editing = $state(false);
	let draft = $state<AlertRule>({ ...rule });

	let info = $derived(ALERT_METRIC_LABELS[rule.metric]);
	let valueText = $derived(
		rule.metric === 'thunder_level'
			? thunderLevelLabel(rule.threshold)
			: `${rule.threshold} ${info?.unit ?? ''}`.trim()
	);

	// Alle bekannten Metrics fuer das Select im Edit-Mode
	const METRIC_OPTIONS: AlertMetric[] = [
		'wind_gust',
		'precipitation_sum',
		'temperature_min',
		'temperature_max',
		'thunder_level',
		'snow_line',
		'temperature_change',
		'wind_change',
		'precipitation_change'
	];

	function startEdit() {
		draft = { ...rule };
		editing = true;
	}

	function saveEdit() {
		// Unit nach Metric synchronisieren (z.B. wenn User Metric gewechselt hat)
		const metricInfo = ALERT_METRIC_LABELS[draft.metric];
		const synced: AlertRule = {
			...draft,
			unit: metricInfo?.unit || draft.unit
		};
		onUpdate(synced);
		editing = false;
	}

	function cancelEdit() {
		draft = { ...rule };
		editing = false;
	}

	function toggleEnabled(e: Event) {
		const checked = (e.target as HTMLInputElement).checked;
		onUpdate({ ...rule, enabled: checked });
	}

	function onThunderChange(e: Event) {
		// Number-Coercion: Select liefert Strings — wir wollen number im draft
		draft.threshold = parseFloat((e.target as HTMLSelectElement).value);
	}
</script>

{#if info}
	{#if editing}
		<div class="alert-rule-edit" data-testid="alert-rule-edit">
			<select
				bind:value={draft.metric}
				data-testid="alert-rule-metric"
				class="field"
			>
				{#each METRIC_OPTIONS as m}
					<option value={m}>{ALERT_METRIC_LABELS[m].label_de}</option>
				{/each}
			</select>

			{#if draft.metric === 'thunder_level'}
				<select
					value={draft.threshold}
					onchange={onThunderChange}
					data-testid="alert-rule-threshold"
					class="field"
				>
					<option value={1.0}>MITTEL</option>
					<option value={2.0}>HOCH</option>
				</select>
			{:else}
				<input
					type="number"
					bind:value={draft.threshold}
					data-testid="alert-rule-threshold"
					class="field"
				/>
			{/if}

			<select
				bind:value={draft.severity}
				data-testid="alert-rule-severity"
				class="field"
			>
				<option value="info">Info</option>
				<option value="warning">Warnung</option>
				<option value="critical">Kritisch</option>
			</select>

			<label class="enabled-toggle">
				<input type="checkbox" bind:checked={draft.enabled} />
				Aktiv
			</label>

			<button
				type="button"
				onclick={saveEdit}
				data-testid="alert-rule-save"
				class="btn-primary"
			>Speichern</button>
			<button
				type="button"
				onclick={cancelEdit}
				data-testid="alert-rule-cancel"
				class="btn-secondary"
			>Abbrechen</button>
		</div>
	{:else}
		<div
			class="alert-rule-view"
			data-testid="alert-rule-row"
			class:disabled={!rule.enabled}
		>
			<span class="label">{info.label_de}</span>
			<span class="threshold">{info.comparison} {valueText}</span>
			<Pill tone={ALERT_SEVERITY_TONE[rule.severity]}>{rule.severity}</Pill>
			<label class="enabled-toggle">
				<input
					type="checkbox"
					checked={rule.enabled}
					onchange={toggleEnabled}
				/>
				Aktiv
			</label>
			<button
				type="button"
				onclick={startEdit}
				data-testid="alert-rule-edit-btn"
				class="btn-secondary"
			>Bearbeiten</button>
			<button
				type="button"
				onclick={onDelete}
				data-testid="alert-rule-delete"
				class="btn-secondary"
			>Löschen</button>
		</div>
	{/if}
{/if}

<style>
	.alert-rule-view,
	.alert-rule-edit {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
		font-size: 0.875rem;
		padding: 0.5rem;
		border: 1px solid var(--g-border, #e5e7eb);
		border-radius: 0.375rem;
		background: var(--g-surface-1, #fff);
	}
	.alert-rule-view.disabled {
		opacity: 0.55;
	}
	.label {
		font-weight: 500;
	}
	.threshold {
		color: var(--g-ink-muted, #6b7280);
	}
	.enabled-toggle {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		font-size: 0.8125rem;
	}
	.field {
		min-height: 36px;
		padding: 0.25rem 0.5rem;
		border: 1px solid var(--g-border, #e5e7eb);
		border-radius: 0.25rem;
		background: var(--g-surface-1, #fff);
	}
	.btn-primary,
	.btn-secondary {
		min-height: 36px;
		padding: 0.25rem 0.75rem;
		border-radius: 0.25rem;
		font-size: 0.8125rem;
		cursor: pointer;
		border: 1px solid var(--g-border, #e5e7eb);
		background: var(--g-surface-1, #fff);
	}
	.btn-primary {
		background: var(--g-primary, #2563eb);
		color: #fff;
		border-color: var(--g-primary, #2563eb);
	}
	.btn-secondary:hover {
		background: var(--g-surface-2, #f3f4f6);
	}
</style>
