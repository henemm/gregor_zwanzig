<script lang="ts">
	// Issue #2278 — kind-neutrales Kebab-Menue (verallgemeinert CompareKebab). Zeigt genau die
	// uebergebenen Aktionen und emittiert onSelect(id); API-Aufrufe/Dialoge liegen beim Aufrufer.
	// #2837 S1 (ADR-0110): mobil ein eigener 44×44-Knopf, der das Aktionsblatt der Seite oeffnet
	// (`onSheetOpen`); Desktop das Dropdown. Symbol immer vertikal.
	// #3442: Archivieren/Löschen fragen im Menü nach (KebabBestaetigungPanel); onSelect erst nach Bestätigung.

	import { DropdownMenu } from 'bits-ui';
	import EllipsisVerticalIcon from '@lucide/svelte/icons/ellipsis-vertical';
	import { locale, t } from '$lib/i18n';
	import KebabBestaetigungPanel from '$lib/components/shared/KebabBestaetigungPanel.svelte';
	import { braucheRueckfrage, rueckfrage } from '$lib/components/shared/kebabBestaetigung';

	interface Props {
		actions: Array<{ id: string; label: string; danger?: boolean }>;
		onSelect?: (id: string) => void;
		mobil?: boolean;
		/** #3442: Name des Abos für die Rückfrage. */
		name?: string;
		/** #3442: Rückfrage im Menü (Hub); die Listen-Karte fragt mit ihrem eigenen Dialog (AC-16) und schaltet sie ab. */
		rueckfragen?: boolean;
		onSheetOpen?: () => void;
		class?: string;
		'data-testid'?: string;
	}

	let { actions, onSelect, mobil = false, name = '', rueckfragen = true, onSheetOpen, class: className = '', 'data-testid': testid }: Props = $props();

	// Offene Rückfrage (Aktions-Kennung); Schließen des Menüs setzt sie zurück (AC-7).
	let frage = $state<string | null>(null);
	const rf = $derived.by(() => (void $locale, frage ? rueckfrage(frage, name) : null));
</script>

{#if mobil}
	<button type="button" class="kebab-mobil {className}" data-testid={testid} aria-label={$t('aktionen.weitere')} title={$t('aktionen.weitere')} onclick={() => onSheetOpen?.()} style:display="inline-flex" style:align-items="center" style:justify-content="center" style:width="44px" style:height="44px" style:background="transparent" style:border="none" style:cursor="pointer" style:color="var(--g-ink-2)">
		<EllipsisVerticalIcon size={18} />
	</button>
{:else}
<DropdownMenu.Root onOpenChange={(offen: boolean) => { if (!offen) frage = null; }}>
	<DropdownMenu.Trigger>
		{#snippet child({ props })}
			<button
				{...props}
				type="button"
				class="kebab-trigger {className}"
				data-testid={testid}
				onclick={(e: MouseEvent) => {
					e.stopPropagation();
				}}
				aria-label={$t('aktionen.weitere')}
				title={$t('aktionen.weitere')}
				style:display="inline-flex"
				style:align-items="center"
				style:justify-content="center"
				style:width="28px"
				style:height="28px"
				style:border-radius="var(--g-r-2)"
				style:border="1px solid var(--g-rule-soft)"
				style:background="transparent"
				style:color="var(--g-ink-2)"
				style:cursor="pointer"
			>
				<EllipsisVerticalIcon size={16} />
			</button>
		{/snippet}
	</DropdownMenu.Trigger>

	<DropdownMenu.Portal>
		<DropdownMenu.Content
			align="end"
			sideOffset={4}
			class="z-50 min-w-[180px] rounded-md border bg-popover shadow-md py-1"
		>
			{#if rf}
				<KebabBestaetigungPanel rueckfrage={rf} imMenue onBestaetigen={() => onSelect?.(rf.id)} onAbbrechen={() => (frage = null)} />
			{:else}
			<div data-abschnitt="kebab-menue" role="none">
			{#each actions as action (action.id)}
				<DropdownMenu.Item
					data-testid="subscription-action-{action.id}"
					class={'w-full text-left px-3 py-1.5 text-sm cursor-default outline-none hover:bg-muted ' +
						(action.danger ? 'text-destructive' : '')}
					onSelect={(e: Event) => {
						if (!rueckfragen || !braucheRueckfrage(action.id)) return onSelect?.(action.id);
						e.preventDefault();
						frage = action.id;
					}}
					onclick={(e: MouseEvent) => e.stopPropagation()}
				>
					{action.label}
				</DropdownMenu.Item>
			{/each}
			</div>
			{/if}
		</DropdownMenu.Content>
	</DropdownMenu.Portal>
</DropdownMenu.Root>
{/if}

<style>
	@media (pointer: coarse) {
		.kebab-trigger {
			position: relative;
		}
		.kebab-trigger::after {
			content: '';
			position: absolute;
			inset: -8px;
		}
	}
</style>
