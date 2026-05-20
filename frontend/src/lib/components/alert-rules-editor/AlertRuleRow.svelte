<script lang="ts">
	// Issue #223 — Eine Zeile pro AlertRule mit View- und Edit-Modus.
	// Spec: docs/specs/modules/issue_223_alert_rules_editor.md §3.
	//
	// Issue #179 — Modus-Toggle (Δ / Absolut / Beides) im Edit-Modus.
	// Spec: docs/specs/modules/issue_179_alert_konfigurator_modus_toggle.md
	//
	// View-Mode: Label + Threshold + Mode-Badge (Abs / Δ) + Severity-Pill +
	//            Enabled-Toggle + [Bearbeiten] + [Löschen]
	// Edit-Mode: ModeCards-Zeile + Metric-Select + Threshold + Severity-Select +
	//            Enabled + Save/Cancel
	// F004-Guard: {#if info} um alles — unbekannte Metric crasht nicht.

	import type { AlertRule, AlertMetric } from '$lib/types';
	import { Pill } from '$lib/components/ui/pill';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import { Select } from '$lib/components/ui/select';
	import {
		ALERT_METRIC_LABELS,
		ALERT_SEVERITY_TONE,
		thunderLevelLabel
	} from '$lib/utils/alertMetricLabels';
	import { DELTA_ONLY_METRICS, expandRules, type AlertRuleMode } from './alertRuleDefaults';
	import ModeCard from './ModeCard.svelte';

	let {
		rule,
		onSave,
		onDelete
	}: {
		rule: AlertRule;
		onSave: (rules: AlertRule[]) => void;
		onDelete: () => void;
	} = $props();

	let editing = $state(false);
	let draft = $state<AlertRule>({ ...rule });
	let editMode = $state<AlertRuleMode>('absolute');

	let info = $derived(ALERT_METRIC_LABELS[rule.metric]);
	let valueText = $derived(
		rule.metric === 'thunder_level'
			? thunderLevelLabel(rule.threshold)
			: `${rule.threshold} ${info?.unit ?? ''}`.trim()
	);

	// Issue #179: Hinweistext wenn 'both' bei Delta-only Metrik auf 'delta' zurueckfaellt.
	let deltaOnlyHint = $derived(
		editing && editMode === 'both' && DELTA_ONLY_METRICS.has(draft.metric)
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
		// AC-2 / AC-3: Mode-Vorauswahl aus rule.kind (Legacy-delta wird korrekt erkannt)
		editMode = rule.kind === 'delta' ? 'delta' : 'absolute';
		editing = true;
	}

	function saveEdit() {
		// Unit nach Metric synchronisieren (z.B. wenn User Metric gewechselt hat)
		const metricInfo = ALERT_METRIC_LABELS[draft.metric];
		const synced: AlertRule = {
			...draft,
			unit: metricInfo?.unit || draft.unit
		};
		// expandRules erzeugt 1 oder 2 Rules abhaengig vom Modus
		onSave(expandRules(synced, editMode));
		editing = false;
	}

	function cancelEdit() {
		draft = { ...rule };
		editing = false;
	}

	function toggleEnabled(e: Event) {
		const checked = (e.target as HTMLInputElement).checked;
		onSave([{ ...rule, enabled: checked }]);
	}

	function onThunderChange(e: Event) {
		// Number-Coercion: Select liefert Strings — wir wollen number im draft
		draft.threshold = parseFloat((e.target as HTMLSelectElement).value);
	}
</script>

{#if info}
	{#if editing}
		<div class="alert-rule-edit" data-testid="alert-rule-edit">
			<div class="mode-selector" role="radiogroup" aria-label="Alarm-Modus">
				<ModeCard
					mode="absolute"
					selected={editMode === 'absolute'}
					onSelect={() => (editMode = 'absolute')}
				/>
				<ModeCard
					mode="delta"
					selected={editMode === 'delta'}
					onSelect={() => (editMode = 'delta')}
				/>
				<ModeCard
					mode="both"
					selected={editMode === 'both'}
					onSelect={() => (editMode = 'both')}
				/>
			</div>

			{#if deltaOnlyHint}
				<p class="delta-only-hint" data-testid="alert-rule-delta-only-hint">
					Diese Metrik misst nur Änderungen — beim Speichern wird nur eine Δ-Regel erzeugt.
				</p>
			{/if}

			<div class="edit-fields">
				<Select
					bind:value={draft.metric}
					data-testid="alert-rule-metric"
					class="field"
				>
					{#each METRIC_OPTIONS as m}
						<option value={m}>{ALERT_METRIC_LABELS[m].label_de}</option>
					{/each}
				</Select>

				{#if draft.metric === 'thunder_level'}
					<Select
						value={draft.threshold}
						onchange={onThunderChange}
						data-testid="alert-rule-threshold"
						class="field"
					>
						<option value={1.0}>MITTEL</option>
						<option value={2.0}>HOCH</option>
					</Select>
				{:else}
					<input
						type="number"
						bind:value={draft.threshold}
						data-testid="alert-rule-threshold"
						class="field"
					/>
				{/if}

				<Select
					bind:value={draft.severity}
					data-testid="alert-rule-severity"
					class="field"
				>
					<option value="info">Info</option>
					<option value="warning">Warnung</option>
					<option value="critical">Kritisch</option>
				</Select>

				<Checkbox bind:checked={draft.enabled}>Aktiv</Checkbox>

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
		</div>
	{:else}
		<div
			class="alert-rule-view"
			data-testid="alert-rule-row"
			class:disabled={!rule.enabled}
		>
			<span class="label">{info.label_de}</span>
			<span class="threshold">{info.comparison} {valueText}</span>
			<Pill tone="default">
				{rule.kind === 'delta' ? 'Δ' : 'Abs'}
			</Pill>
			<Pill tone={ALERT_SEVERITY_TONE[rule.severity]}>{rule.severity}</Pill>
			<Checkbox
				checked={rule.enabled}
				onchange={toggleEnabled}
			>Aktiv</Checkbox>
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
	.alert-rule-view {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
		font-size: 0.875rem;
		padding: 0.5rem;
		border: 1px solid var(--g-ink-faint);
		border-radius: 0.375rem;
		background: var(--g-surface-1, #fff);
	}
	.alert-rule-edit {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		padding: 0.5rem;
		border: 1px solid var(--g-ink-faint);
		border-radius: 0.375rem;
		background: var(--g-surface-1, #fff);
		font-size: 0.875rem;
	}
	.mode-selector {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.delta-only-hint {
		margin: 0;
		font-size: 0.8125rem;
		color: var(--g-ink-muted);
		font-style: italic;
	}
	.edit-fields {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.alert-rule-view.disabled {
		opacity: 0.55;
	}
	.label {
		font-weight: 500;
	}
	.threshold {
		color: var(--g-ink-muted);
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
		border: 1px solid var(--g-ink-faint);
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
		border: 1px solid var(--g-ink-faint);
		background: var(--g-surface-1, #fff);
	}
	.btn-primary {
		background: var(--g-ink);
		color: #fff;
		border-color: var(--g-ink);
	}
	.btn-secondary:hover {
		background: var(--g-surface-2);
	}
</style>
