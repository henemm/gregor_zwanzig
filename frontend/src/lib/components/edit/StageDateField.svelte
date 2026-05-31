<script lang="ts">
	// Issue #498 — Etappen-Datum nachträglich bearbeiten.
	// Spec: docs/design-requests/stage_date_edit.md
	//
	// Dünner Wrapper um native <input type="date"> mit:
	//   - kleinem "DATUM"-Label (uppercase, muted, mono)
	//   - Wochentag-Chip (Mo/Di/…/So) aus ISO-Datum abgeleitet
	//   - optional "· TOURSTART"-Marker für die erste Etappe
	//
	// Svelte-5: $props, $bindable, $derived. Kein Legacy-Event-Handler-Syntax.
	//
	// onchange-Callback gibt den neuen ISO-String direkt zurück — so kann der
	// Parent (EditStagesPanelNew / PauseStageView) das Datum entweder via
	// bind ODER via Handler-Pattern übernehmen, ohne aus dem Event zu fischen.

	interface Props {
		value: string;
		isFirst?: boolean;
		onchange?: (newValue: string) => void;
	}

	let { value = $bindable(''), isFirst = false, onchange }: Props = $props();

	const WD = ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'];
	const wd = $derived(value ? WD[new Date(value + 'T00:00:00').getDay()] : '—');

	function handleChange(e: Event): void {
		const newVal = (e.target as HTMLInputElement).value;
		value = newVal;
		onchange?.(newVal);
	}
</script>

<div class="stage-date" data-testid="stage-date-field">
	<span class="label">
		Datum{#if isFirst} · <em>Tourstart</em>{/if}
	</span>
	<label class="box">
		<span class="wd">{wd}</span>
		<input type="date" {value} onchange={handleChange} />
	</label>
</div>

<style>
	.stage-date {
		display: inline-flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 4px;
		min-width: 168px;
	}

	.label {
		font-family: var(--g-font-data);
		font-size: 10px;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--g-ink-muted);
	}

	.label em {
		font-style: normal;
		color: var(--g-ink);
	}

	.box {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		padding: 4px 6px 4px 4px;
		background: var(--g-card, #ffffff);
		border: 1px solid var(--g-rule);
		border-radius: 4px;
		cursor: pointer;
	}

	.wd {
		display: inline-block;
		padding: 3px 7px;
		background: var(--g-accent-tint);
		color: var(--g-accent-deep);
		font-family: var(--g-font-data);
		font-size: 11px;
		font-weight: 700;
		border-radius: 3px;
		font-variant-numeric: tabular-nums;
	}

	.box input[type='date'] {
		background: transparent;
		border: none;
		outline: none;
		font-family: var(--g-font-data);
		font-size: 13px;
		color: var(--g-ink);
		font-variant-numeric: tabular-nums;
		padding: 0;
		min-width: 110px;
	}
</style>
