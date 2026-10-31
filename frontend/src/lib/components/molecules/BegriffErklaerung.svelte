<script lang="ts">
	// Issue #2521 S1 — Begriff-Erklaerung: ein ⓘ neben dem Fachbegriff.
	// Tippen/Klicken (oder Enter/Leertaste) oeffnet die Sprechblase, Esc oder
	// Tippen daneben schliesst sie; Hover wird nicht vorausgesetzt.
	// Spec: docs/specs/modules/begriff_erklaerung_infobox.md (Entscheidung 1, 9).
	// Alle Texte kommen aus dem Katalog ($t()), sichtbar ist nur das Zeichen ⓘ.
	import * as Popover from '$lib/components/ui/popover/index.js';
	import { t } from '$lib/i18n';
	import { BEGRIFF_KEYS, type Begriff } from '$lib/components/shared/infoboxKeys';

	interface Props {
		begriff: Begriff;
		/** Unterscheidet gleichzeitig gerenderte Instanzen (Desktop/Mobil, Reiter, Kontext). */
		suffix?: string;
	}

	let { begriff, suffix }: Props = $props();

	const testid = $derived(suffix ? `begriff-erklaerung-${begriff}-${suffix}` : `begriff-erklaerung-${begriff}`);
	const ariaLabel = $derived($t(BEGRIFF_KEYS[begriff].aria));
	const erklaerung = $derived($t(BEGRIFF_KEYS[begriff].text));
</script>

<Popover.Root>
	<Popover.Trigger>
		{#snippet child(arg)}
			<button {...arg.props} type="button" class="ii-btn" data-testid={testid} aria-label={ariaLabel}>ⓘ</button>
		{/snippet}
	</Popover.Trigger>
	<Popover.Content>
		{erklaerung}
	</Popover.Content>
</Popover.Root>

<style>
	.ii-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-width: 24px;
		min-height: 24px;
		margin: -4px 0;
		padding: 0;
		border: 0;
		border-radius: 50%;
		background: transparent;
		color: var(--g-ink-2);
		font-size: 15px;
		line-height: 1;
		cursor: pointer;
		vertical-align: middle;
		text-transform: none;
		letter-spacing: normal;
	}
	.ii-btn:focus-visible {
		outline: 2px solid var(--g-ink-2);
		outline-offset: 1px;
	}
</style>
