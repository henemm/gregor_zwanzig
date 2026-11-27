<script lang="ts">
	// Issue #3440 (S5a, Scheibe #2797, ADR-0109 Punkt 6) — Menü „Test schicken ▾“ am Kopf-Knopf.
	// Spec: docs/specs/modules/feat_3440_test_schicken_menue.md
	//
	// EIN Baustein für Trip (`context="route"`) und Orte (`context="vergleich"`, ADR-0097). Er ruft
	// keine API: ein Klick auf eine Kanalzeile bzw. „Alle eingerichteten Kanäle“ meldet nur
	// `onTest({kanal, berichtsart})`, Versand und Rückmeldung liegen bei der Seite (#2278).
	// Desktop bits-ui-DropdownMenu (Tastatur, Escape, Außenklick), ≤899 px ein Sheet mit 44-px-Zeilen
	// (Muster SubscriptionKebab). Den Auslöser (Knopf) reicht der Aufrufer als Snippet herein und
	// bekommt die Menü-Attribute als `props`. Nach „Alle“ folgt ein Erweiterungs-Slot (#3441 Test-Alarm).
	import { untrack, type Snippet } from 'svelte';
	import { DropdownMenu } from 'bits-ui';
	import { Btn, Segmented } from '$lib/components/atoms';
	import Sheet from '$lib/components/mobile/Sheet.svelte';
	import { locale, t } from '$lib/i18n';
	import type { KanalId, ZustellungProfil } from '$lib/components/shared/zustellung-tab/zustellungModell';
	import {
		BERICHTSART_START,
		berichtsartBeiOffen,
		testMenueModell,
		type Berichtsart,
		type TestKanal
	} from './testSchickenModell';

	interface Props {
		context: 'route' | 'vergleich';
		profil: ZustellungProfil | null | undefined;
		mobil?: boolean;
		offen?: boolean;
		disabled?: boolean;
		onTest?: (wahl: { kanal: TestKanal; berichtsart: Berichtsart }) => void;
		/** Erweiterungs-Slot nach dem Trenner unter „Alle“: der Test-Alarm (#3441). */
		onErweiterung?: (id: string) => void;
		/** #3441 AC-17: der Test-Alarm läuft — Eintrag gesperrt bis zur Antwort. */
		alarmLaeuft?: boolean;
		ausloeser: Snippet<[{ props: Record<string, unknown> }]>;
	}

	let {
		context, profil, mobil = false, offen = $bindable(false), disabled = false, onTest, onErweiterung,
		alarmLaeuft = false, ausloeser
	}: Props = $props();

	let berichtsart = $state<Berichtsart>(BERICHTSART_START);
	// Bei jedem Öffnen wieder Vorauswahl Morgen (wie der Sende-Dialog, #2278 F010). Liest nur `offen`
	// (untrack: die aktuelle Berichtsart ist keine Abhängigkeit des Effekts).
	$effect(() => {
		berichtsart = berichtsartBeiOffen(offen, untrack(() => berichtsart));
	});
	// i18n F9: Texte entstehen per tr() — `$locale` hält das Modell reaktiv.
	const modell = $derived.by(() => (void $locale, testMenueModell(profil, context, berichtsart, { alarmLaeuft })));

	function waehle(kanal: KanalId | 'alle'): void {
		offen = false;
		onTest?.({ kanal, berichtsart });
	}

	const mobilProps = $derived({
		'aria-haspopup': 'menu',
		'aria-expanded': offen,
		onclick: () => (offen = !offen)
	});
</script>

{#snippet inhalt()}
	<div class="test-menue" data-abschnitt="test-menue" data-kind={context} role={mobil ? 'menu' : undefined} aria-label={$t('test_schicken.menue_aria')}>
		{#if modell.segment}
			<div class="kopf">
				<Segmented
					rolle="radio"
					size="sm"
					ariaLabel={$t('test_schicken.berichtsart_aria')}
					options={modell.segment.optionen.map((o) => ({ value: o.wert, label: o.text, testid: `test-menue-berichtsart-${o.wert}` }))}
					value={berichtsart}
					onChange={(v: string) => (berichtsart = v as Berichtsart)}
				/>
			</div>
			<hr class="trenner" />
		{/if}
		{#each modell.zeilen as z (z.kanal)}
			{#if !z.bedienbar}
				<div class="zeile gesperrt" role="menuitem" aria-disabled="true" tabindex="-1" data-kanal={z.kanal}>
					<span class="name">{z.name}</span>
					<small>
						{z.sperrText}
						{#if z.kontoLink}<Btn variant="link" size="xs" href={z.kontoLink.href}>{z.kontoLink.text}</Btn>{/if}
					</small>
				</div>
			{:else if mobil}
				<button type="button" class="zeile" role="menuitem" data-kanal={z.kanal} onclick={() => waehle(z.kanal)}>
					<span class="name">{z.name}</span>
					<small>{z.ziel}</small>
				</button>
			{:else}
				<DropdownMenu.Item class="zeile" data-kanal={z.kanal} onSelect={() => waehle(z.kanal)}>
					<span class="name">{z.name}</span>
					<small>{z.ziel}</small>
				</DropdownMenu.Item>
			{/if}
		{/each}
		<hr class="trenner" />
		{#if mobil}
			<button type="button" class="zeile alle" role="menuitem" data-kanal="alle" onclick={() => waehle('alle')}>{modell.alle.text}</button>
		{:else}
			<DropdownMenu.Item class="zeile alle" data-kanal="alle" onSelect={() => waehle('alle')}>{modell.alle.text}</DropdownMenu.Item>
		{/if}
		{#if modell.erweiterungen.length > 0}
			<hr class="trenner" />
			{#each modell.erweiterungen as e (e.id)}
				{#if mobil}
					<button type="button" class="zeile" role="menuitem" data-erweiterung={e.id} disabled={!e.bedienbar} onclick={() => { offen = false; onErweiterung?.(e.id); }}>
						<span class="name">{e.text}</span>
						<small>{e.untertitel}</small>
					</button>
				{:else}
					<DropdownMenu.Item class="zeile" data-erweiterung={e.id} disabled={!e.bedienbar} onSelect={() => onErweiterung?.(e.id)}>
						<span class="name">{e.text}</span>
						<small>{e.untertitel}</small>
					</DropdownMenu.Item>
				{/if}
			{/each}
		{/if}
	</div>
{/snippet}

{#if mobil}
	{@render ausloeser({ props: mobilProps })}
	<Sheet open={offen} onClose={() => (offen = false)} snap="auto" title={$t('aktionen.kopf.test_schicken')}>
		<div role="dialog" aria-label={$t('test_schicken.menue_aria')}>
			{@render inhalt()}
		</div>
	</Sheet>
{:else}
	<DropdownMenu.Root bind:open={offen}>
		<DropdownMenu.Trigger {disabled}>
			{#snippet child({ props })}
				{@render ausloeser({ props })}
			{/snippet}
		</DropdownMenu.Trigger>
		<DropdownMenu.Portal>
			<DropdownMenu.Content align="end" sideOffset={4} class="test-menue-flaeche">
				{@render inhalt()}
			</DropdownMenu.Content>
		</DropdownMenu.Portal>
	</DropdownMenu.Root>
{/if}

<style>
	:global(.test-menue-flaeche) {
		z-index: 50;
		min-width: var(--g-size-190px);
		background: var(--g-card);
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-2);
		box-shadow: var(--g-shadow-2);
		padding: var(--g-s-1) 0;
	}
	.test-menue {
		display: flex;
		flex-direction: column;
	}
	.kopf {
		padding: var(--g-s-2) var(--g-s-3);
	}
	.trenner {
		border: 0;
		border-top: 1px solid var(--g-rule-soft);
		margin: var(--g-s-1) 0;
	}
	.test-menue :global(.zeile) {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: var(--g-s-1);
		width: 100%;
		padding: var(--g-s-2) var(--g-s-3);
		background: transparent;
		border: 0;
		text-align: left;
		font-family: var(--g-font-ui);
		font-size: var(--g-text-sm);
		color: var(--g-ink);
		cursor: pointer;
		outline: none;
	}
	.test-menue :global(.zeile[data-highlighted]),
	.test-menue :global(button.zeile:hover) {
		background: var(--g-paper-deep);
	}
	.test-menue :global(.zeile.alle) {
		font-weight: 600;
	}
	.test-menue :global(.zeile small) {
		font-family: var(--g-font-mono);
		font-size: var(--g-text-xs);
		color: var(--g-ink-3);
	}
	.zeile.gesperrt {
		cursor: default;
		color: var(--g-ink-3);
	}
	.zeile.gesperrt small {
		color: var(--g-bad);
	}
	/* Mobil (≤899 px, Sheet): Zeilen mindestens 44 px hoch (Kebab-Muster). */
	@media (max-width: 899px) {
		.test-menue :global(.zeile) {
			min-height: var(--g-tap-min);
			justify-content: center;
		}
	}
</style>
