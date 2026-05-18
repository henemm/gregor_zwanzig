<script lang="ts">
	// Issue #223 — Container fuer die AlertRulesEditor-Komponente.
	// Spec: docs/specs/modules/issue_223_alert_rules_editor.md §1.
	//
	// Issue #179 — Modus-Toggle: updateRule(index, updated) wird zu
	// updateRules(index, updated[]) damit "Beides" 1 Rule durch 2 ersetzen kann.
	// Spec: docs/specs/modules/issue_179_alert_konfigurator_modus_toggle.md
	//
	// Liste-basierter Editor fuer Trip.alert_rules. Empty-State, Liste,
	// Add-Button. Die einzelnen Rules werden in AlertRuleRow gerendert.

	import type { AlertRule } from '$lib/types';
	import AlertRuleRow from './AlertRuleRow.svelte';
	import { newDefaultRule } from './alertRuleDefaults';

	let { rules = $bindable<AlertRule[]>([]) }: { rules: AlertRule[] } = $props();

	function addRule() {
		rules = [...rules, newDefaultRule()];
	}

	function updateRules(index: number, updated: AlertRule[]) {
		// Ersetzt rules[index] durch 1 oder 2 neue Rules (Modus 'Beides' -> 2 Rules).
		rules = [
			...rules.slice(0, index),
			...updated,
			...rules.slice(index + 1)
		];
	}

	function deleteRule(index: number) {
		rules = rules.filter((_, i) => i !== index);
	}
</script>

<div class="alert-rules-editor" data-testid="alert-rules-editor">
	{#if rules.length === 0}
		<p class="empty-state" data-testid="alert-rules-editor-empty">
			Noch keine Alarmregeln konfiguriert.
		</p>
	{:else}
		<ul class="rules-list">
			{#each rules as rule, i (rule.id)}
				<li>
					<AlertRuleRow
						{rule}
						onSave={(updated) => updateRules(i, updated)}
						onDelete={() => deleteRule(i)}
					/>
				</li>
			{/each}
		</ul>
	{/if}
	<button
		type="button"
		data-testid="alert-rules-editor-add"
		class="add-button"
		onclick={addRule}
	>+ Regel hinzufügen</button>
</div>

<style>
	.alert-rules-editor {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}
	.empty-state {
		font-size: 0.875rem;
		color: var(--g-ink-faint, #6b7280);
		margin: 0;
	}
	.rules-list {
		list-style: none;
		padding: 0;
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.add-button {
		align-self: flex-start;
		font-size: 0.875rem;
		padding: 0.5rem 0.75rem;
		min-height: 44px;
		border: 1px solid var(--g-border, #e5e7eb);
		border-radius: 0.375rem;
		background: var(--g-surface-1, #fff);
		cursor: pointer;
	}
	.add-button:hover {
		background: var(--g-surface-2, #f3f4f6);
	}
</style>
