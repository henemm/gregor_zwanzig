<script lang="ts" module>
	/** an/aus = Kontrollkästchen · gesperrt/nicht_in_email = Strich mit Grund · fest = Haken ohne Abwahl. */
	export type HakenZustand = 'an' | 'aus' | 'gesperrt' | 'nicht_in_email' | 'fest';
</script>

<script lang="ts">
	// Issue #3122 B3a — Haken-Atom der Einstell-Tabelle „Was steht wo“ (Mockup Fassung 4: `.ck`, `.nix`, `.lockck`).
	// an/aus ist ein echtes Kontrollkästchen (Tastatur und Screenreader ohne Zutun), gesteuert vom Aufrufer:
	// ein Klick meldet nur den Wunsch, der Zustand folgt der Prop. Alle Texte kommen als Props.
	import { t } from '$lib/i18n';

	interface Props {
		zustand: HakenZustand;
		/** Zugänglicher Name, z. B. „Wind in E-Mail“. */
		name: string;
		/** Grund bei gesperrt, nicht_in_email und fest. Sichtbar als Kurztext nur bei gesperrt. */
		grund?: string;
		/** false: ganzer Block aus bzw. Kurzstil — an/aus bleibt sichtbar, lässt sich aber nicht ändern. */
		bedienbar?: boolean;
		onAenderung?: (an: boolean) => void;
		testid?: string;
	}
	let { zustand, name, grund, bedienbar = true, onAenderung, testid }: Props = $props();

	const nameMitGrund = $derived(grund ? $t('bausteine.haken.name_mit_grund', { name, grund }) : name);

	function aendern(e: Event & { currentTarget: HTMLInputElement }) {
		const neu = e.currentTarget.checked;
		// Gesteuert: die Anzeige folgt der Prop. Ein Skript-Klick auf ein gesperrtes Kästchen meldet nichts.
		e.currentTarget.checked = zustand === 'an';
		if (bedienbar) onAenderung?.(neu);
	}
</script>

{#if zustand === 'an' || zustand === 'aus'}
	<label class="hk" data-slot="haken" data-zustand={zustand} data-testid={testid}>
		<input type="checkbox" aria-label={name} checked={zustand === 'an'} disabled={!bedienbar} onchange={aendern} />
		<span class="hk-box" aria-hidden="true"></span>
	</label>
{:else if zustand === 'fest'}
	<span class="hk-fest" data-slot="haken" data-zustand={zustand} data-testid={testid} role="img" aria-label={nameMitGrund} title={grund}>
		<span class="hk-fest-haken" aria-hidden="true"></span>
	</span>
{:else}
	<span class="hk-strich" data-slot="haken" data-zustand={zustand} data-testid={testid} role="img" aria-label={nameMitGrund} title={grund}>
		<span class="hk-nix" aria-hidden="true">–</span>
		{#if zustand === 'gesperrt' && grund}<em class="hk-grund" data-slot="haken-grund">{grund}</em>{/if}
	</span>
{/if}

<style>
	.hk,
	.hk-fest,
	.hk-nix {
		display: inline-grid;
		place-items: center;
		flex: 0 0 auto;
		width: var(--g-size-28px);
		height: var(--g-size-28px);
	}
	.hk {
		position: relative;
		cursor: pointer;
	}
	.hk input {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		margin: 0;
		opacity: 0;
		cursor: pointer;
	}
	.hk-box {
		position: relative;
		display: block;
		box-sizing: border-box;
		pointer-events: none;
		width: var(--g-s-5);
		height: var(--g-s-5);
		border: var(--g-size-2px) solid var(--g-ink-3);
		border-radius: var(--g-r-2);
		background: var(--g-card);
	}
	.hk input:checked + .hk-box {
		background: var(--g-ink);
		border-color: var(--g-ink);
	}
	.hk input:checked + .hk-box::after,
	.hk-fest-haken {
		content: '';
		box-sizing: border-box;
		border: solid var(--g-paper);
		border-width: 0 var(--g-size-2px) var(--g-size-2px) 0;
		transform: rotate(45deg);
	}
	.hk input:checked + .hk-box::after {
		position: absolute;
		left: 34%;
		top: 8%;
		width: 34%;
		height: 66%;
	}
	.hk input:disabled,
	.hk:has(input:disabled) {
		cursor: not-allowed;
	}
	.hk input:disabled + .hk-box {
		opacity: 0.35;
	}
	.hk input:focus-visible + .hk-box {
		outline: var(--g-size-2px) solid var(--g-accent);
		outline-offset: var(--g-size-2px);
	}
	.hk-fest-haken {
		display: block;
		width: var(--g-size-6px);
		height: var(--g-s-3);
		margin-top: calc(-1 * var(--g-size-3px));
		border-color: var(--g-ink-3);
	}
	.hk-strich {
		display: inline-flex;
		align-items: center;
		gap: var(--g-size-6px);
		min-width: 0;
		color: var(--g-ink-3);
	}
	/* Mit Kurztext daneben rückt der Strich enger, damit der Grund in eine schmale Spalte passt. */
	.hk-strich[data-zustand='gesperrt'] .hk-nix {
		width: var(--g-s-5);
	}
	.hk-grund {
		font-style: normal;
		font-size: var(--g-text-xs);
		font-weight: 500;
		flex: 0 1 auto;
		min-width: 0;
		line-height: 1.2;
		overflow-wrap: anywhere;
		color: var(--g-ink-3);
	}
	/* Tippfläche ≥ --g-tap-min (Charter §7), die sichtbare Größe bleibt. Bedingung wie app.css (#2601). */
	@media (max-width: 899px), (pointer: coarse) {
		.hk {
			width: var(--g-tap-min);
			height: var(--g-tap-min);
		}
	}
</style>
