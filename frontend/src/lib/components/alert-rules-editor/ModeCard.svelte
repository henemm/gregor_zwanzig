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
		badge: string;
	};

	// Issue #297 — Feld-Anzahl-Badge: zeigt wie viele Eingaben der Modus erzeugt.
	//   'absolute' -> 1 Feld  (Schwelle)
	//   'delta'    -> 2 Felder (Schwelle + Zeitfenster)
	//   'both'     -> 3 Felder (AbsSchwelle + ΔSchwelle + Zeitfenster)
	const COPY: Record<AlertRuleMode, ModeCopy> = {
		absolute: {
			eyebrow: 'Absolut',
			title: 'Schwellwert',
			description: 'Alarm wenn Wert überschritten',
			example: 'Wind > 80 km/h',
			badge: '1 Feld'
		},
		delta: {
			eyebrow: 'Änderung',
			title: 'Δ Differenz',
			description: 'Alarm bei starker Änderung',
			example: 'Temperatur −8°C in 6h',
			badge: '2 Felder'
		},
		both: {
			eyebrow: 'Kombiniert',
			title: 'Beides',
			description: 'Absolut und Änderung überwachen',
			example: 'Wind > 80 km/h oder +30 km/h',
			badge: '3 Felder'
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
	<span class="field-count-badge" data-testid={`mode-card-badge-${mode}`}>{copy.badge}</span>
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
		font-size: var(--g-text-xs);
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--g-ink-muted);
	}
	.title {
		font-weight: 600;
		font-size: var(--g-text-md);
	}
	.description {
		font-size: var(--g-text-sm);
		color: var(--g-ink-muted);
	}
	.example {
		font-family: var(--g-font-data);
		font-size: var(--g-text-xs);
		font-style: normal;
		letter-spacing: 0;
		color: var(--g-ink-muted);
	}
	.field-count-badge {
		align-self: flex-start;
		margin-top: 0.25rem;
		padding: 0.125rem 0.5rem;
		border: 1px solid var(--g-ink-faint);
		border-radius: 999px;
		font-size: var(--g-text-xs);
		font-family: var(--g-font-ui);
		color: var(--g-ink-muted);
		background: var(--g-surface-2);
		letter-spacing: 0.02em;
	}
</style>
