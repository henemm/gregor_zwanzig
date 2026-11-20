<script lang="ts" module>
	/** Die zwei Formen einer Stelle (Vokabular des gespeicherten Formats, Spec #3122 Teil A Nr. 1). */
	export type Darstellung = 'raw' | 'simplified';
</script>

<script lang="ts">
	// Issue #3122 B3a — Roh/Einfach-Knopf der Einstell-Tabelle „Was steht wo“ (Mockup Fassung 4: `.mini`).
	// Ein Knopf, der die aktuelle Form als Wort zeigt und beim Auslösen die andere meldet. Der Zustand
	// steht im Text und im zugänglichen Namen, nicht in der Farbe. `wert = null`: die Stelle hat nur
	// eine Form, der Knopf erscheint nicht (das entscheidet der Aufrufer).
	import { t } from '$lib/i18n';

	interface Props {
		wert: Darstellung | null;
		/** Wofür der Knopf gilt, z. B. „Wind in E-Mail“ (Teil des zugänglichen Namens). */
		name: string;
		onAenderung?: (neu: Darstellung) => void;
		testid?: string;
	}
	let { wert, name, onAenderung, testid }: Props = $props();

	const form = $derived(wert === 'simplified' ? $t('bausteine.darstellung.simplified') : $t('bausteine.darstellung.raw'));
	const kurz = $derived(wert === 'simplified' ? $t('bausteine.darstellung.simplified_kurz') : $t('bausteine.darstellung.raw'));
</script>

{#if wert}
	<button
		type="button"
		class="rek"
		data-slot="roh-einfach"
		data-wert={wert}
		data-tap="true"
		data-testid={testid}
		aria-label={$t('bausteine.darstellung.name', { name, form })}
		onclick={() => onAenderung?.(wert === 'raw' ? 'simplified' : 'raw')}
	>
		<span class="rek-pille" data-slot="roh-einfach-pille">
			<span data-slot="roh-einfach-lang">{form}</span><span class="rek-kurz" data-slot="roh-einfach-kurz">{kurz}</span>
		</span>
	</button>
{/if}

<style>
	.rek {
		position: relative;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		flex: 0 0 auto;
		min-height: 0;
		margin: 0;
		padding: 0;
		border: 0;
		background: none;
		font: inherit;
		cursor: pointer;
	}
	/* #3212: unsichtbare Tippfläche ≥ --g-tap-min auf allen Breiten (Muster Btn data-tap, app.css);
	   die sichtbare Pille bleibt 32×22 / 56×22 (Mockup Fassung 4 `.mini`). */
	.rek::before {
		content: '';
		position: absolute;
		left: 50%;
		top: 50%;
		width: max(100%, var(--g-tap-min));
		height: max(100%, var(--g-tap-min));
		transform: translate(-50%, -50%);
	}
	.rek-pille {
		padding: var(--g-size-3px) var(--g-size-6px);
		border: 1px solid var(--g-rule);
		border-radius: var(--g-size-3px);
		background: var(--g-paper);
		color: var(--g-accent-deep);
		font-family: var(--g-font-mono);
		font-size: var(--g-size-10-5px);
		font-weight: 600;
		line-height: 1.3;
		white-space: nowrap;
	}
	.rek:hover .rek-pille {
		border-color: var(--g-ink-3);
	}
	.rek:focus-visible {
		outline: none;
	}
	.rek:focus-visible .rek-pille {
		outline: var(--g-size-2px) solid var(--g-accent);
		outline-offset: var(--g-size-2px);
	}
	/* Kurzwort („Einf.“) nur im engen Raster; die Einstell-Tabelle schaltet es über data-slot um. */
	.rek-kurz {
		display: none;
	}
	/* Tippfläche ≥ --g-tap-min (Charter §7), die sichtbare Pille bleibt klein. Bedingung wie app.css (#2601). */
	@media (max-width: 899px), (pointer: coarse) {
		.rek {
			min-width: var(--g-tap-min);
			min-height: var(--g-tap-min);
		}
	}
</style>
