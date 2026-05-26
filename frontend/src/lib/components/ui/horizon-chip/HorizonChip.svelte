<script lang="ts">
	// Issue #343 — HorizonChip-Atom (Vorbild: Segmented + Pill).
	// Spec: docs/specs/modules/issue_343_horizon_chip_ui.md §1
	//
	// Brand-Pattern: [data-slot="horizon-chip"] mit [data-active]-Attribut.
	// Touch-Target ≥ 44 px (Padding hebt die 32 px Chip-Hoehe auf 44 × 44 px).
	// Mono-Caps-Schrift, Token-only Styling — keine Hex-Inlines.

	type Day = 'today' | 'tomorrow' | 'day_after';

	let {
		day,
		active,
		onclick,
		disabled = false,
		'data-testid': dataTestid,
	}: {
		day: Day;
		active: boolean;
		onclick: () => void;
		disabled?: boolean;
		'data-testid'?: string;
	} = $props();

	const LABELS: Record<Day, string> = {
		today: 'HEUTE',
		tomorrow: 'MORGEN',
		day_after: 'ÜBERMORGEN',
	};
</script>

<button
	type="button"
	data-slot="horizon-chip"
	data-active={active}
	data-day={day}
	data-testid={dataTestid}
	{disabled}
	aria-pressed={active}
	{onclick}
>{LABELS[day]}</button>

<style>
	[data-slot='horizon-chip'] {
		/* Touch-Target ≥ 44 × 44 px (Charter §7). box-sizing: border-box ist Default,
		   daher muss min-height die volle 44 px abdecken (Padding ist innerhalb). */
		min-height: 44px;
		min-width: 44px;
		padding: var(--g-s-2) var(--g-s-3);
		border-radius: var(--g-radius-pill);
		border: 1px solid var(--g-ink-faint);
		background: transparent;
		color: var(--g-ink-muted);
		font-family: var(--g-font-data);
		font-size: var(--g-text-xs);
		letter-spacing: var(--g-track-caps);
		text-transform: uppercase;
		cursor: pointer;
		transition: background 120ms, color 120ms, border-color 120ms;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		line-height: 1;
	}
	[data-slot='horizon-chip'][data-active='true'] {
		background: var(--g-ink);
		color: var(--g-paper);
		border-color: var(--g-ink);
	}
	[data-slot='horizon-chip']:disabled {
		cursor: not-allowed;
		opacity: 0.5;
	}
	[data-slot='horizon-chip']:focus-visible {
		outline: 2px solid var(--g-accent);
		outline-offset: 2px;
	}
</style>
