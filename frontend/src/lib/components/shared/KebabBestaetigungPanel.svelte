<script lang="ts">
	// Issue #3442 (S5c aus #2797) — EINE Rückfrage für Archivieren/Löschen, im Desktop-Kebab
	// (`imMenue`: Knöpfe als DropdownMenu.Item, Pfeiltasten/Enter) und im mobilen Aktionsblatt (Btn).
	// Texte aus kebabBestaetigung.rueckfrage(); die Aktion führt erst der Aufrufer nach onBestaetigen aus.
	// Steht in SEITEN_SCOPE (Regel (a), ADR-0112): keine eigenen Stile; Knöpfe im Stil Btn
	// (`data-slot="btn"`, Gefahrknopf „destructive“ = --g-danger, WCAG-AA), Rahmen `[data-slot="rueckfrage"]` in app.css.
	import { DropdownMenu } from 'bits-ui';
	import { Btn } from '$lib/components/atoms';
	import type { KebabRueckfrage } from './kebabBestaetigung.ts';

	interface Props {
		rueckfrage: KebabRueckfrage;
		onBestaetigen: () => void;
		onAbbrechen: () => void;
		imMenue?: boolean;
	}

	let { rueckfrage, onBestaetigen, onAbbrechen, imMenue = false }: Props = $props();

	const knoepfe = $derived([
		{ was: 'bestaetigen', text: rueckfrage.bestaetigen, variant: rueckfrage.gefahr ? 'destructive' : 'primary', tun: onBestaetigen },
		{ was: 'abbrechen', text: rueckfrage.abbrechen, variant: 'ghost', tun: onAbbrechen }
	] as const);

	// AC-8: nach dem Umschalten liegt der Fokus in der Rückfrage, auf der folgenlosen Wahl „Abbrechen“.
	let box = $state<HTMLElement | null>(null);
	$effect(() => {
		box?.querySelector<HTMLElement>('[data-testid="kebab-rueckfrage-abbrechen"]')?.focus();
	});
</script>

<div bind:this={box} data-slot="rueckfrage" data-abschnitt={rueckfrage.abschnitt} data-testid="kebab-rueckfrage">
	<p data-rolle="titel">{rueckfrage.titel}</p>
	<p data-rolle="text">{rueckfrage.text}</p>
	<div data-rolle="knoepfe">
		{#each knoepfe as k (k.was)}
			{#if imMenue}
				<DropdownMenu.Item
					data-testid="kebab-rueckfrage-{k.was}"
					data-slot="btn"
					data-variant={k.variant}
					data-size="sm"
					onSelect={(e: Event) => {
						if (k.was === 'abbrechen') e.preventDefault();
						k.tun();
					}}
					onclick={(e: MouseEvent) => e.stopPropagation()}
				>{k.text}</DropdownMenu.Item>
			{:else}
				<Btn variant={k.variant} size="sm" data-testid="kebab-rueckfrage-{k.was}" onclick={() => k.tun()}>{k.text}</Btn>
			{/if}
		{/each}
	</div>
</div>
