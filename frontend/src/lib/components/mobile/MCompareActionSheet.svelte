<script lang="ts">
	// Issue #493 — MCompareActionSheet (Block E, Epic #485).
	//
	// Bottom-Sheet (snap="half") für statusabhängige Compare-Aktionen.
	// Aktionsliste kommt aus compareActions() — keine eigene Logik.
	// Aktions-Dispatch via onAction(id), danach onClose() — Eltern-Seite
	// ist für API-Calls und Confirm-Dialoge zuständig.
	//
	// Spec: docs/specs/modules/issue_493_compare_mobile.md §4

	import Sheet from './Sheet.svelte';
	import {
		compareActions,
		type CompareStatus
	} from '$lib/components/compare/subscriptionHelpers.js';

	interface Props {
		open: boolean;
		onClose: () => void;
		status: CompareStatus;
		onAction: (id: string) => void;
		presetName?: string;
	}

	let { open, onClose, status, onAction, presetName }: Props = $props();

	const actions = $derived(compareActions(status));
</script>

<Sheet {open} {onClose} snap="half" title={presetName} eyebrow="AKTIONEN">
	<div style:display="flex" style:flex-direction="column" style:gap="2px">
		{#each actions as action (action.id)}
			<button
				type="button"
				class="w-full text-left px-4"
				style:min-height="52px"
				style:background="transparent"
				style:border="none"
				style:cursor="pointer"
				style:font-size="15px"
				style:color={action.danger ? 'var(--g-danger)' : 'var(--g-ink-1)'}
				onclick={() => {
					onAction(action.id);
					onClose();
				}}
			>
				{action.label}
			</button>
		{/each}
	</div>
</Sheet>
