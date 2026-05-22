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
	import { Btn } from '$lib/components/ui/btn';
	import {
		ALERT_METRIC_LABELS,
		ALERT_SEVERITY_TONE,
		SEVERITY_LABEL_DE,
		thunderLevelLabel
	} from '$lib/utils/alertMetricLabels';
	import { DELTA_ONLY_METRICS, expandRules, type AlertRuleMode } from './alertRuleDefaults';
	import ModeCard from './ModeCard.svelte';

	let {
		rule,
		onSave,
		onDelete,
		pairFollower = false
	}: {
		rule: AlertRule;
		onSave: (rules: AlertRule[]) => void;
		onDelete: () => void;
		pairFollower?: boolean;
	} = $props();

	let editing = $state(false);
	let draft = $state<AlertRule>({ ...rule });
	let editMode = $state<AlertRuleMode>('absolute');
	let kebabOpen = $state(false);

	// Issue #297 — separate Felder fuer Absolut-Schwelle, Delta-Schwelle und Zeitfenster.
	// Initialwerte werden in startEdit() aus rule.* gesetzt; Defaults dienen Erst-Render.
	let draftAbsThreshold = $state<number>(50);
	let draftDeltaThreshold = $state<number>(20);
	let draftDeltaWindow = $state<string>('6h');

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
		// Issue #297 — Mode-Vorauswahl: pair_id zeigt mode='both', sonst rule.kind.
		if (rule.pair_id) {
			editMode = 'both';
			if (rule.kind === 'absolute') {
				draftAbsThreshold = rule.threshold;
				draftDeltaThreshold = 20; // Partner-Wert nicht zugaenglich — Default.
			} else {
				draftDeltaThreshold = rule.threshold;
				draftDeltaWindow = rule.delta_window ?? '6h';
				draftAbsThreshold = 50; // Partner-Wert nicht zugaenglich — Default.
			}
		} else {
			// AC-2 / AC-3: Mode-Vorauswahl aus rule.kind (Legacy-delta wird korrekt erkannt)
			editMode = rule.kind === 'delta' ? 'delta' : 'absolute';
			if (rule.kind === 'absolute') {
				draftAbsThreshold = rule.threshold;
			} else {
				draftDeltaThreshold = rule.threshold;
				draftDeltaWindow = rule.delta_window ?? '6h';
			}
		}
		editing = true;
	}

	function saveEdit() {
		// Unit nach Metric synchronisieren (z.B. wenn User Metric gewechselt hat)
		const metricInfo = ALERT_METRIC_LABELS[draft.metric];
		const synced: AlertRule = {
			...draft,
			unit: metricInfo?.unit || draft.unit
		};
		// Issue #297 — neue Signatur: separate Threshold-Felder + delta-Zeitfenster.
		onSave(
			expandRules(synced, editMode, draftAbsThreshold, draftDeltaThreshold, draftDeltaWindow)
		);
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
					>
						<option value={1.0}>MITTEL</option>
						<option value={2.0}>HOCH</option>
					</Select>
				{:else if editMode === 'both'}
					<!-- Issue #297 AC-3: drei Felder bei mode='both' — abs + delta + zeitfenster. -->
					<input
						type="number"
						bind:value={draftAbsThreshold}
						data-testid="alert-rule-threshold-abs"
						class="number-input"
						aria-label="Absolut-Schwelle"
					/>
					<input
						type="number"
						bind:value={draftDeltaThreshold}
						data-testid="alert-rule-threshold-delta"
						class="number-input"
						aria-label="Δ-Schwelle"
					/>
					<Select
						bind:value={draftDeltaWindow}
						data-testid="alert-rule-delta-window"
						class="window-select"
						aria-label="Zeitfenster"
					>
						<option value="1h">1 Stunde</option>
						<option value="3h">3 Stunden</option>
						<option value="6h">6 Stunden</option>
						<option value="12h">12 Stunden</option>
						<option value="24h">24 Stunden</option>
					</Select>
				{:else if editMode === 'delta'}
					<!-- Issue #297 AC-2: Threshold + Zeitfenster bei mode='delta'. -->
					<input
						type="number"
						bind:value={draftDeltaThreshold}
						data-testid="alert-rule-threshold"
						class="number-input"
					/>
					<Select
						bind:value={draftDeltaWindow}
						data-testid="alert-rule-delta-window"
						class="window-select"
						aria-label="Zeitfenster"
					>
						<option value="1h">1 Stunde</option>
						<option value="3h">3 Stunden</option>
						<option value="6h">6 Stunden</option>
						<option value="12h">12 Stunden</option>
						<option value="24h">24 Stunden</option>
					</Select>
				{:else}
					<!-- AC-1: ein Threshold-Feld bei mode='absolute'. -->
					<input
						type="number"
						bind:value={draftAbsThreshold}
						data-testid="alert-rule-threshold"
						class="number-input"
					/>
				{/if}

				<Select
					bind:value={draft.severity}
					data-testid="alert-rule-severity"
				>
					<option value="info">Info</option>
					<option value="warning">Warnung</option>
					<option value="critical">Kritisch</option>
				</Select>

				<Checkbox bind:checked={draft.enabled}>Aktiv</Checkbox>

				<Btn
					variant="primary"
					size="sm"
					onclick={saveEdit}
					data-testid="alert-rule-save"
					>{editMode === 'both' ? 'Beide Regeln speichern' : 'Speichern'}</Btn
				>
				<Btn
					variant="ghost"
					size="sm"
					onclick={cancelEdit}
					data-testid="alert-rule-cancel">Abbrechen</Btn
				>
			</div>
		</div>
	{:else}
		<div
			class="alert-rule-view"
			data-testid="alert-rule-row"
			class:disabled={!rule.enabled}
			class:pair-follower={pairFollower}
		>
			{#if pairFollower}
				<span
					class="pair-indicator"
					data-testid="pair-indicator"
					title="Zweite Regel des Paares"
					aria-label="Paar-Regel"
				>paar</span>
			{/if}
			<span class="label">{info.label_de}</span>
			<span class="threshold">{info.comparison} {valueText}</span>
			<Pill tone="default" data-outlined>
				{rule.kind === 'delta' ? 'Δ' : 'Abs'}
			</Pill>
			<Pill tone={ALERT_SEVERITY_TONE[rule.severity]} data-outlined
				>{SEVERITY_LABEL_DE[rule.severity]}</Pill
			>
			<Checkbox
				checked={rule.enabled}
				onchange={toggleEnabled}
			>Aktiv</Checkbox>
			<!-- svelte-ignore a11y_no_static_element_interactions -->
			<div class="relative"
				onkeydown={(e: KeyboardEvent) => { if (e.key === 'Escape') kebabOpen = false; }}
				onfocusout={(e: FocusEvent) => {
					if (!(e.currentTarget as Element).contains(e.relatedTarget as Node)) kebabOpen = false;
				}}
			>
				<Btn variant="ghost" size="icon-sm" type="button"
					 onclick={() => (kebabOpen = !kebabOpen)}
					 aria-label="Aktionen"
					 data-testid="alert-rule-kebab-trigger">⋯</Btn>

				{#if kebabOpen}
					<div class="kebab-dropdown" role="menu">
						<Btn
							variant="ghost"
							size="sm"
							type="button"
							role="menuitem"
							onclick={() => { kebabOpen = false; startEdit(); }}
							data-testid="alert-rule-edit-btn"
						>Bearbeiten</Btn>
						<Btn
							variant="ghost"
							size="sm"
							type="button"
							role="menuitem"
							onclick={() => { kebabOpen = false; onDelete(); }}
							data-testid="alert-rule-delete"
						>Löschen</Btn>
					</div>
				{/if}
			</div>
		</div>
	{/if}
{:else}
	<div class="alert-rule-view alert-rule-unknown" data-testid="alert-rule-row" data-unknown="true">
		<span class="label">[{rule.metric}]</span>
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div class="relative"
			onkeydown={(e: KeyboardEvent) => { if (e.key === 'Escape') kebabOpen = false; }}
			onfocusout={(e: FocusEvent) => {
				if (!(e.currentTarget as Element).contains(e.relatedTarget as Node)) kebabOpen = false;
			}}
		>
			<Btn variant="ghost" size="icon-sm" type="button"
				 onclick={() => (kebabOpen = !kebabOpen)}
				 aria-label="Aktionen"
				 data-testid="alert-rule-kebab-trigger">⋯</Btn>

			{#if kebabOpen}
				<div class="kebab-dropdown" role="menu">
					<Btn
						variant="ghost"
						size="sm"
						type="button"
						role="menuitem"
						onclick={() => { kebabOpen = false; onDelete(); }}
						data-testid="alert-rule-delete"
					>Löschen</Btn>
				</div>
			{/if}
		</div>
	</div>
{/if}

<style>
	.alert-rule-view {
		display: grid;
		grid-template-columns: minmax(140px, 1fr) auto auto auto auto auto;
		align-items: center;
		gap: var(--g-s-3);
		padding: var(--g-s-3) var(--g-s-4);
		border: none;
		border-bottom: 1px solid var(--g-ink-faint);
		border-radius: 0;
		background: transparent;
		font-size: var(--g-text-sm);
	}
	.alert-rule-view:hover { background: var(--g-surface-2); }
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
		font-family: var(--g-font-data);
		font-variant-numeric: tabular-nums;
		color: var(--g-ink-muted);
	}
	.number-input {
		min-height: 36px;
		padding: 0.25rem 0.5rem;
		border: 1px solid var(--g-ink-faint);
		border-radius: var(--g-radius-sm);
		background: var(--g-paper);
		font-family: var(--g-font-ui);
		font-size: var(--g-text-sm);
		color: var(--g-ink);
		width: 80px;
	}
	.window-select {
		min-height: 36px;
		padding: 0.25rem 0.5rem;
		border: 1px solid var(--g-ink-faint);
		border-radius: var(--g-radius-sm);
		background: var(--g-paper);
		font-family: var(--g-font-ui);
		font-size: var(--g-text-sm);
		color: var(--g-ink);
	}
	.relative {
		position: relative;
	}
	.kebab-dropdown {
		position: absolute;
		right: 0;
		top: 100%;
		z-index: 50;
		background: var(--g-surface);
		border: 1px solid var(--g-ink-faint);
		border-radius: 6px;
		min-width: 120px;
		box-shadow: 0 4px 12px rgba(0,0,0,0.12);
		padding: var(--g-s-1) 0;
	}
	.kebab-dropdown button {
		display: block;
		width: 100%;
		padding: var(--g-s-2) var(--g-s-4);
		text-align: left;
		background: none;
		border: none;
		cursor: pointer;
		font-size: var(--g-text-sm);
		color: var(--g-ink);
	}
	.kebab-dropdown button:hover {
		background: var(--g-surface-raised);
	}
	/* Issue #297 — visuelle Paar-Markierung: zweite Rule eines Paares. */
	.alert-rule-view.pair-follower {
		border-left: 2px solid var(--g-accent);
		padding-left: 12px;
	}
	.pair-indicator {
		font-size: 0.6875rem;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--g-accent);
		font-weight: 600;
	}
</style>
