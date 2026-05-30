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
	import { Btn } from '$lib/components/atoms';

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
		<div class="rules-card">
			<p class="empty-state" data-testid="alert-rules-editor-empty">
				Noch keine Alarmregeln konfiguriert.
			</p>
			<div class="card-footer">
				<Btn variant="ghost" size="sm" type="button" data-testid="alert-rules-editor-add" onclick={addRule}>+ Regel hinzufügen</Btn>
			</div>
		</div>
	{:else}
		<div class="rules-card">
			<ul class="rules-list">
				{#each rules as rule, i (rule.id)}
					{@const isPairFollower = !!(
						rule.pair_id && rules[i - 1]?.pair_id === rule.pair_id
					)}
					<li>
						<AlertRuleRow
							{rule}
							onSave={(updated) => updateRules(i, updated)}
							onDelete={() => deleteRule(i)}
							pairFollower={isPairFollower}
						/>
					</li>
				{/each}
			</ul>
			<div class="card-footer">
				<Btn variant="ghost" size="sm" type="button" data-testid="alert-rules-editor-add" onclick={addRule}>+ Regel hinzufügen</Btn>
			</div>
		</div>
	{/if}
</div>

<style>
	.alert-rules-editor {
		display: flex;
		flex-direction: column;
	}
	.rules-card {
		border: 1px solid var(--g-ink-faint);
		border-radius: var(--g-radius-md);
		overflow: hidden;
	}
	.empty-state {
		font-size: 0.875rem;
		color: var(--g-ink-muted);
		margin: 0;
		padding: var(--g-s-3) var(--g-s-4);
	}
	.rules-list {
		list-style: none;
		padding: 0;
		margin: 0;
	}
	.card-footer {
		padding: var(--g-s-2) var(--g-s-3);
		border-top: 1px solid var(--g-ink-faint);
	}
	.rules-list li:last-child :global(.alert-rule-view) {
		border-bottom: none;
	}
</style>
