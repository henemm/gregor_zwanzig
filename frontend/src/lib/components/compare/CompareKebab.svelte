<script lang="ts">
	// Issue #488 — CompareKebab (Molecule, Svelte 5).
	//
	// Kebab-Kontextmenü für CompareTile mit statusabhängigen Aktionen.
	// Nutzt das bits-ui v2 {#snippet child({ props })}-Trigger-Pattern
	// (Portal-basiert, Safari-/iOS-tauglich).
	//
	// Kein API-Call hier: emittiert nur onSelect(id) — die Elternkomponente
	// (CompareTile / CompareGrid) ist für API-Aufruf + Confirm-Dialog zuständig.
	//
	// Spec: docs/specs/modules/issue_488_compare_tile_atoms.md §4
	// Referenz: frontend/src/routes/trips/+page.svelte (TripKebab-Muster)

	import { DropdownMenu } from 'bits-ui';
	import EllipsisVerticalIcon from '@lucide/svelte/icons/ellipsis-vertical';
	import { compareActions } from './subscriptionHelpers.js';
	import type { CompareStatus } from './subscriptionHelpers.js';

	interface Props {
		status: CompareStatus;
		onSelect?: (id: string) => void;
		class?: string;
	}

	let { status, onSelect, class: className = '' }: Props = $props();

	const actions = $derived(compareActions(status));
</script>

<DropdownMenu.Root>
	<DropdownMenu.Trigger>
		{#snippet child({ props })}
			<button
				{...props}
				type="button"
				class={className}
				onclick={(e: MouseEvent) => {
					e.stopPropagation();
				}}
				aria-label="Weitere Aktionen"
				title="Weitere Aktionen"
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

	<DropdownMenu.Content
		align="end"
		sideOffset={4}
		class="z-50 min-w-[180px] rounded-md border bg-popover shadow-md py-1"
	>
		{#each actions as action (action.id)}
			<DropdownMenu.Item
				class={'w-full text-left px-3 py-1.5 text-sm cursor-default outline-none hover:bg-muted ' +
					(action.danger ? 'text-destructive' : '')}
				onSelect={() => onSelect?.(action.id)}
			>
				{action.label}
			</DropdownMenu.Item>
		{/each}
	</DropdownMenu.Content>
</DropdownMenu.Root>
