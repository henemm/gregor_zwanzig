<script lang="ts">
	import { t } from '$lib/i18n';
	import UhrzeitFeld from '$lib/components/molecules/UhrzeitFeld.svelte';
	// Issue #675 — Startzeit je Etappe editieren.
	//
	// Duenner Wrapper um den Baustein molecules/UhrzeitFeld (#2881 Lieferung B, vorher
	// natives <input type="time">) mit:
	//   - kleinem "STARTZEIT"-Label (uppercase, muted, mono)
	//   - Anzeige-Default 08:00 wenn kein Wert gesetzt
	//
	// Svelte-5: $props, $derived. Analoger Aufbau zu StageDateField.
	//
	// onchange-Callback gibt den neuen HH:MM-String direkt zurueck — der Parent
	// entscheidet, ob ein leerer Wert als "kein Override" behandelt wird.

	interface Props {
		value?: string;
		onchange?: (newValue: string) => void;
		/** #2496: 'inline' = Label-los fuer Kartenkontext (mobile StageCardM). */
		variant?: 'default' | 'inline';
	}

	let { value, onchange, variant = 'default' }: Props = $props();

	// 08:00 wird nur angezeigt (displayValue), NICHT in stages geschrieben,
	// solange der Nutzer nichts aendert (AC-4: alt-treu).
	const displayValue = $derived(value ?? '08:00');

	function handleChange(newVal: string): void {
		onchange?.(newVal);
	}
</script>

{#if variant === 'inline'}
	<div class="box inline" data-testid="stage-start-time-field">
		<UhrzeitFeld value={displayValue} onchange={handleChange} groesse="kompakt" leerMelden ariaLabel={$t('trip.startzeit')} />
	</div>
{:else}
	<div class="stage-time" data-testid="stage-start-time-field">
		<span class="label">{$t('trip.startzeit')}</span>
		<div class="box">
			<UhrzeitFeld value={displayValue} onchange={handleChange} groesse="kompakt" leerMelden ariaLabel={$t('trip.startzeit')} />
		</div>
	</div>
{/if}

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
		font-size: 11px;
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
	}

	.box.inline {
		min-width: 0;
	}

	/* #2601: Touch — Trefferhöhe >= 36px (16 px gegen iOS-Auto-Zoom setzt UhrzeitFeld selbst). */
	@media (max-width: 899px), (pointer: coarse) {
		.box {
			min-height: 36px;
		}
	}
</style>
