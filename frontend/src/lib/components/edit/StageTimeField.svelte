<script lang="ts">
	// Issue #675 — Startzeit je Etappe editieren.
	//
	// Duenner Wrapper um native <input type="time"> mit:
	//   - kleinem "STARTZEIT"-Label (uppercase, muted, mono)
	//   - Anzeige-Default 08:00 wenn kein Wert gesetzt
	//
	// Svelte-5: $props, $derived. Analoger Aufbau zu StageDateField.
	//
	// onchange-Callback gibt den neuen HH:MM-String direkt zurueck (oder ""
	// wenn der Nutzer das Feld leert) — der Parent entscheidet, ob das als
	// "kein Override" behandelt wird.

	interface Props {
		value?: string;
		onchange?: (newValue: string) => void;
	}

	let { value, onchange }: Props = $props();

	// 08:00 wird nur angezeigt (displayValue), NICHT in stages geschrieben,
	// solange der Nutzer nichts aendert (AC-4: alt-treu).
	const displayValue = $derived(value ?? '08:00');

	function handleChange(e: Event): void {
		const newVal = (e.target as HTMLInputElement).value;
		onchange?.(newVal);
	}
</script>

<div class="stage-time" data-testid="stage-start-time-field">
	<span class="label">Startzeit</span>
	<label class="box">
		<input type="time" value={displayValue} onchange={handleChange} />
	</label>
</div>

<style>
	.stage-time {
		display: inline-flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 4px;
		min-width: 100px;
	}

	.label {
		font-family: var(--g-font-data);
		font-size: 10px;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--g-ink-muted);
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

	.box input[type='time'] {
		background: transparent;
		border: none;
		outline: none;
		font-family: var(--g-font-data);
		font-size: 13px;
		color: var(--g-ink);
		font-variant-numeric: tabular-nums;
		padding: 0;
		min-width: 70px;
	}
</style>
