<script lang="ts">
	// Issue #223 — Eine Zeile pro AlertRule mit View- und Edit-Modus.
	// Spec: docs/specs/modules/issue_223_alert_rules_editor.md §3.
	//
	// #1895 Schritt 1 — die Modus-Auswahl (Änderung / Absolut / Beides) und das
	// Absolut-Schwellenfeld sind zurueckgebaut; es gibt nur noch Aenderungsregeln.
	// Spec: docs/specs/modules/fix_1895_alarm_modus_rueckbau.md
	//
	// #1895 Schritt 2 — Δ-Schwelle, Zeitfenster, der Wert-Text und die „Δ"-Pille
	// sind aus BEIDEN Ansichten der Karte zurueckgebaut. Sie loesen keinen Alarm
	// aus (ADR-0043: die Empfindlichkeitsstufe ist der einzige Regler). Die
	// Datenfelder `threshold`/`delta_window` bleiben im Modell und werden von
	// expandRules() unveraendert durchgereicht.
	// Spec: docs/specs/modules/fix_1895_s2_alarmkarte_rueckbau.md
	//
	// View-Mode: Label + Kanal-Chips + Enabled-Toggle + Kebab [Bearbeiten] [Löschen]
	// Edit-Mode: Metric-Select + Kanal-Chips + Enabled + Save/Cancel
	// F004-Guard: {#if info} um alles — unbekannte Metric crasht nicht.

	import type { AlertRule, AlertMetric } from '$lib/types';
	import { Btn } from '$lib/components/atoms';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import { Select } from '$lib/components/ui/select';
	import { ALERT_METRIC_LABELS } from '$lib/utils/alertMetricLabels';
	import { expandRules } from './alertRuleDefaults';
	import { effectiveAlertChannels, toggleAlertChannel } from './alertChannels';

	const CHANNEL_LABEL_DE: Record<string, string> = { email: 'E-Mail', telegram: 'Telegram', sms: 'SMS' };

	let {
		rule,
		onSave,
		onDelete,
		pairFollower = false,
		activeChannels = []
	}: {
		rule: AlertRule;
		onSave: (rules: AlertRule[]) => void;
		onDelete: () => void;
		pairFollower?: boolean;
		activeChannels?: string[];
	} = $props();

	let editing = $state(false);
	let draft = $state<AlertRule>({ ...rule });
	let kebabOpen = $state(false);

	let info = $derived(ALERT_METRIC_LABELS[rule.metric]);
	let editChannels = $derived(effectiveAlertChannels(draft, activeChannels));

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
		// #1895 Schritt 2 (E-3): voller Spread, keine Vorbelegung. `threshold` und
		// `delta_window` werden unveraendert durchgereicht — ein Ueberschreiben
		// waere aktive Datenaenderung ohne Nutzerhandlung.
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
		// #1895: expandRules() kennt weder Modus noch Zusatzparameter mehr und
		// liefert genau eine Aenderungsregel.
		onSave(expandRules(synced));
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

</script>

{#if info}
	{#if editing}
		<div class="alert-rule-edit" data-testid="alert-rule-edit">
			<div class="edit-fields">
				<Select
					bind:value={draft.metric}
					data-testid="alert-rule-metric"
				>
					{#each METRIC_OPTIONS as m}
						<option value={m}>{ALERT_METRIC_LABELS[m].label_de}</option>
					{/each}
				</Select>

				<!-- #1895 Schritt 2: die beiden Eingaben fuer Schwelle und Fenster
					 sind zurueckgebaut, sie loesen keinen Alarm aus (ADR-0043). -->
				{#each activeChannels as ch}
					<button type="button"
						data-testid="alert-rule-channel-{ch}"
						aria-pressed={editChannels.includes(ch)}
						class="channel-chip" class:chip-active={editChannels.includes(ch)}
						onclick={() => (draft = toggleAlertChannel(draft, ch, activeChannels))}
					>{CHANNEL_LABEL_DE[ch] ?? ch}</button>
				{/each}

				<Checkbox bind:checked={draft.enabled}>Aktiv</Checkbox>

				<Btn
					variant="primary"
					size="sm"
					onclick={saveEdit}
					data-testid="alert-rule-save">Speichern</Btn
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
			<!-- #1895 Schritt 2: kein Wert-Text und keine Modus-Pille mehr — die
				 Zeile zeigt Metrik, Kanaele und den Aktiv-Haken. -->
			{#each effectiveAlertChannels(rule, activeChannels) as ch}
				<span class="channel-chip chip-active">{CHANNEL_LABEL_DE[ch] ?? ch}</span>
			{/each}
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
		/* #1895 Schritt 2: exakt um die zwei entfallenen Spuren reduziert (6 -> 4). */
		grid-template-columns: minmax(140px, 1fr) auto auto auto;
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
		color: var(--g-accent-deep);
		font-weight: 600;
	}
	.channel-chip {
		display: inline-flex;
		align-items: center;
		padding: 2px 8px;
		border-radius: 999px;
		border: 1px solid var(--g-ink-faint);
		background: var(--g-surface-1, #fff);
		font-size: var(--g-text-xs, 0.75rem);
		color: var(--g-ink-muted);
		cursor: default;
		user-select: none;
	}
	button.channel-chip {
		cursor: pointer;
	}
	.channel-chip.chip-active {
		background: var(--g-accent-soft, #e8f0fe);
		border-color: var(--g-accent, #4a7fc1);
		color: var(--g-accent-deep, #1a4f8a);
		font-weight: 500;
	}
</style>
