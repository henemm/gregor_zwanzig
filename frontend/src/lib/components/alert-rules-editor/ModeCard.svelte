<script lang="ts">
	// Issue #179 — Eine Modus-Karte fuer den AlertRulesEditor.
	// Spec: docs/specs/modules/issue_179_alert_konfigurator_modus_toggle.md
	//
	// Rendert genau eine der drei Optionen ('absolute' | 'delta' | 'both')
	// als anklickbare Radio-Karte. Layout: Eyebrow -> Title -> Beschreibung
	// -> Beispiel. Aktive Karte erhaelt visuelles Highlight.

	export type AlertRuleMode = 'absolute' | 'delta' | 'both';

	let {
		mode,
		selected,
		onSelect
	}: {
		mode: AlertRuleMode;
		selected: boolean;
		onSelect: () => void;
	} = $props();

	type ModeCopy = {
		eyebrow: string;
		title: string;
		description: string;
		example: string;
	};

	const COPY: Record<AlertRuleMode, ModeCopy> = {
		absolute: {
			eyebrow: 'Absolut',
			title: 'Schwellwert',
			description: 'Alarm wenn Wert überschritten',
			example: 'Wind > 80 km/h'
		},
		delta: {
			eyebrow: 'Änderung',
			title: 'Δ Differenz',
			description: 'Alarm bei starker Änderung',
			example: 'Temperatur −8°C in 6h'
		},
		both: {
			eyebrow: 'Kombiniert',
			title: 'Beides',
			description: 'Absolut und Änderung überwachen',
			example: 'Wind > 80 km/h oder +30 km/h'
		}
	};

	let copy = $derived(COPY[mode]);
	let testid = $derived(
		selected ? `mode-card-${mode}-selected` : `mode-card-${mode}`
	);
</script>

<button
	type="button"
	class="mode-card"
	class:selected
	role="radio"
	aria-checked={selected}
	data-testid={testid}
	onclick={onSelect}
>
	<span class="eyebrow">{copy.eyebrow}</span>
	<span class="title">{copy.title}</span>
	<span class="description">{copy.description}</span>
	<span class="example">{copy.example}</span>
</button>

<style>
	.mode-card {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		flex: 1 1 0;
		min-width: 0;
		padding: 0.75rem;
		border: 1px solid var(--g-ink-faint);
		border-radius: 0.5rem;
		background: var(--g-surface-1, #fff);
		text-align: left;
		cursor: pointer;
		font: inherit;
		color: inherit;
		transition: border-color 120ms ease, background 120ms ease;
	}
	.mode-card:hover {
		background: var(--g-surface-2);
	}
	.mode-card.selected {
		border-color: var(--g-accent);
		background: var(--g-surface-1, #fff);
		box-shadow: 0 0 0 1px var(--g-accent) inset;
	}
	.eyebrow {
		font-size: 0.6875rem;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--g-ink-faint);
	}
	.title {
		font-weight: 600;
		font-size: 0.9375rem;
	}
	.description {
		font-size: 0.8125rem;
		color: var(--g-ink-muted);
	}
	.example {
		font-size: 0.75rem;
		font-style: italic;
		color: var(--g-ink-faint);
	}
</style>
