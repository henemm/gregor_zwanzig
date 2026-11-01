<script lang="ts">
	// Issue #478 — ConfirmDialog-Molecule (Atomic Design Phase 2 Restposten).
	//
	// Kapselt das Bestaetigungs-Dialog-Muster (Bits-UI Dialog + zwei Btn-Atome)
	// und befreit Konsumenten (z. B. trips/[id]/+page.svelte) von direkten
	// $lib/components/ui/-Importen.
	//
	// Spec: docs/specs/modules/issue_478_trip_detail_dialog_migration.md

	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { Btn } from '$lib/components/atoms';
	import type { Snippet } from 'svelte';
	import { t } from '$lib/i18n';

	interface Props {
		open: boolean;
		title: string;
		description: string;
		confirmLabel: string;
		confirmVariant?: 'primary' | 'destructive';
		cancelLabel?: string;
		disabled?: boolean;
		'data-testid'?: string;
		cancelTestid?: string;
		confirmTestid?: string;
		onConfirm: () => void;
		onCancel: () => void;
		onOpenChange: (open: boolean) => void;
		/** Optionaler Zusatzinhalt zwischen Beschreibung und Knoepfen (z. B. Berichtsart-Wahl, #2278). */
		children?: Snippet;
	}

	let {
		open,
		title,
		description,
		confirmLabel,
		confirmVariant = 'primary',
		cancelLabel,
		disabled = false,
		'data-testid': dataTestid,
		cancelTestid,
		confirmTestid,
		onConfirm,
		onCancel,
		onOpenChange,
		children
	}: Props = $props();
</script>

<Dialog.Root {open} {onOpenChange}>
	<Dialog.Content data-testid={dataTestid}>
		<Dialog.Header>
			<Dialog.Title>{title}</Dialog.Title>
			<Dialog.Description>{description}</Dialog.Description>
		</Dialog.Header>
		{@render children?.()}
		<Dialog.Footer>
			<Btn variant="outline" data-testid={cancelTestid} onclick={onCancel}>
				{cancelLabel ?? $t('aktionen.abbrechen')}
			</Btn>
			<Btn
				variant={confirmVariant}
				data-testid={confirmTestid}
				onclick={onConfirm}
				{disabled}
			>
				{confirmLabel}
			</Btn>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
