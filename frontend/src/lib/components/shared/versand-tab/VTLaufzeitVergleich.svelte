<script lang="ts">
	// VT_LaufzeitVergleich — Issue #1232 Scheibe 2b: "Laufzeit" (vergleich =
	// editierbar) im geteilten VersandTab-Organism. 1:1-Struktur aus
	// versand-tab.jsx (VT_LaufzeitVergleich / CompareEndDateControl). Kein
	// eigener Persistenz-State — controlled component, bindet direkt an
	// wiz.endDate (kein Self-Save im vergleich-Zweig).
	//
	// Segmented "Bis auf Weiteres" (id "open") / "Bis Datum" (id "date"): der
	// aktive Modus ist bewusst NICHT rein aus `value` abgeleitet (null ist
	// mehrdeutig: "nie berührt" vs. "Bis auf Weiteres" gewählt) — ein Wechsel
	// zu "Bis Datum" ohne sofortige Datumsauswahl muss das Eingabefeld zeigen,
	// waehrend wiz.endDate bis zur Auswahl null bleibt (Spec Implementation
	// Details Punkt 3, Edge Cases).
	//
	// Spec: docs/specs/modules/versand_tab_vergleich.md (AC-3)
	import { Eyebrow } from '$lib/components/atoms';

	interface Props {
		value: string | null;
		onChange: (value: string | null) => void;
	}
	let { value, onChange }: Props = $props();

	let mode = $state<'open' | 'date'>(value === null ? 'open' : 'date');

	function selectOpen() {
		mode = 'open';
		onChange(null);
	}
	function selectDate() {
		mode = 'date';
		// Kein Auto-Fülldatum: wiz.endDate bleibt null, bis der Nutzer aktiv
		// ein Datum waehlt (siehe onDateInput).
	}
	function onDateInput(e: Event) {
		const v = (e.target as HTMLInputElement).value;
		mode = 'date';
		onChange(v || null);
	}
</script>

<div>
	<Eyebrow style="margin-bottom: 10px;">Laufzeit</Eyebrow>
	<div class="vt-laufzeit-vergleich" data-testid="briefings-laufzeit-vergleich">
		<div class="vt-segmented" role="tablist">
			<button
				type="button"
				role="tab"
				aria-selected={mode === 'open'}
				class:active={mode === 'open'}
				data-testid="compare-versand-enddate-open"
				onclick={selectOpen}
			>
				Bis auf Weiteres
			</button>
			<button
				type="button"
				role="tab"
				aria-selected={mode === 'date'}
				class:active={mode === 'date'}
				data-testid="compare-versand-enddate-date"
				onclick={selectDate}
			>
				Bis Datum
			</button>
		</div>
		{#if mode === 'date'}
			<input
				type="date"
				data-testid="compare-versand-enddate-input"
				value={value ?? ''}
				onchange={onDateInput}
				class="vt-date-input"
			/>
		{:else}
			<p class="vt-laufzeit-hint">Der Versand läuft ohne Enddatum weiter.</p>
		{/if}
	</div>
</div>

<style>
	.vt-laufzeit-vergleich {
		background: var(--g-card);
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-3, 12px);
		padding: 20px 22px;
		display: flex;
		flex-direction: column;
		gap: 12px;
	}
	.vt-segmented {
		display: inline-flex;
		gap: 2px;
		align-self: flex-start;
	}
	.vt-segmented button {
		min-height: 44px;
		padding: 9px 14px;
		border: 1px solid var(--g-rule);
		background: var(--g-paper-deep, #efece3);
		color: var(--g-ink-3);
		font-family: var(--g-font-sans);
		font-size: 13px;
		font-weight: 500;
		cursor: pointer;
	}
	.vt-segmented button.active {
		background: var(--g-ink);
		border-color: var(--g-ink);
		color: var(--g-paper);
	}
	.vt-date-input {
		font-family: var(--g-font-mono);
		font-size: 13px;
		font-weight: 600;
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-1, 4px);
		padding: 8px 10px;
		background: var(--g-card);
		color: var(--g-ink);
		width: fit-content;
	}
	.vt-laufzeit-hint {
		margin: 0;
		font-size: 12.5px;
		color: var(--g-ink-3);
		line-height: 1.5;
	}

	@media (max-width: 899px) {
		.vt-laufzeit-vergleich {
			padding: 14px;
		}
		.vt-date-input {
			min-height: 44px;
			font-size: 16px;
			width: 100%;
			box-sizing: border-box;
		}
	}
</style>
