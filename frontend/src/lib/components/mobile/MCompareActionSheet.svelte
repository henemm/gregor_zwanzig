<script lang="ts">
	// Issue #493 — MCompareActionSheet (Block E, Epic #485).
	// Issue #1256 Scheibe 8 (AC-23) — Aktionsliste kommt jetzt aus
	// compareLifecycleActions() statt dem vollen Umfang: das mobile Bottom-Sheet
	// zeigt nur noch Lifecycle-Aktionen (Toggle/Archivieren/Löschen), deckungs-
	// gleich mit dem Desktop-Hub-Header-Kebab (Scheibe 3). „Briefing jetzt
	// senden"/„Vorschau"/„Bearbeiten" gehören mobil nicht mehr ins Sheet.
	//
	// Bottom-Sheet (snap="half") für statusabhängige Compare-Aktionen.
	// Aktions-Dispatch via onAction(id), danach onClose() — Eltern-Seite
	// ist für API-Calls und Confirm-Dialoge zuständig.
	//
	// Spec: docs/specs/modules/issue_1256_compare_ui_rewire.md AC-23

	import Sheet from './Sheet.svelte';
	import {
		compareLifecycleActions,
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

	const actions = $derived(compareLifecycleActions(status));
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
