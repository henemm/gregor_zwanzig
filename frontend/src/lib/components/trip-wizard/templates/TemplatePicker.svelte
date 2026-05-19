<script lang="ts">
	// TemplatePicker — rechte Spalte in Step 2 (Epic #136 Sub-Spec #165).
	// Spec: docs/specs/modules/epic_136_step5_templates.md
	//
	// Zeigt drei vordefinierte Routen (GR20, KHW, Stubai) als Karten an.
	// Klick auf "Vorlage laden" befuellt wizard.stages direkt — bei vorhandenen
	// Etappen erscheint ein Bestaetigungs-Dialog.
	//
	// Safari/Factory: benannte Handler statt anonymer Inline-Closures (Spec §6).

	import { getContext } from 'svelte';
	import { GCard } from '$lib/components/ui/g-card';
	import { Btn } from '$lib/components/ui/btn';
	import { Eyebrow } from '$lib/components/ui/eyebrow';
	import { Pill } from '$lib/components/ui/pill';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { TRIP_TEMPLATES, type TripTemplate } from './tripTemplates.ts';
	import type { WizardState } from '../wizardState.svelte.ts';

	const wizard = getContext<WizardState>('trip-wizard-state');

	let pendingTemplate = $state<TripTemplate | null>(null);
	let showConfirm = $state(false);

	const REGION: Record<string, string> = {
		gr20: 'Korsika',
		khw: 'Karnische Alpen',
		stubai: 'Tirol'
	};
	const STAGE_COUNTS: Record<string, number> = {
		gr20: 14,
		khw: 13,
		stubai: 7
	};

	function applyTemplate(tpl: TripTemplate): void {
		wizard.stages = tpl.stages();
		wizard.activity = tpl.activity;
		if (!wizard.name.trim()) wizard.name = tpl.name;
		if (!wizard.shortcode.trim()) wizard.shortcode = tpl.shortcode;
		wizard.recomputeStageDates();
		showConfirm = false;
		pendingTemplate = null;
	}

	function makeApplyHandler(tpl: TripTemplate) {
		return function handleApply() {
			if (wizard.stages.length > 0) {
				pendingTemplate = tpl;
				showConfirm = true;
			} else {
				applyTemplate(tpl);
			}
		};
	}

	function confirmReplace(): void {
		if (pendingTemplate) applyTemplate(pendingTemplate);
	}

	function cancelReplace(): void {
		showConfirm = false;
		pendingTemplate = null;
	}
</script>

<div data-testid="trip-wizard-template-picker" class="flex flex-col gap-3">
	<Eyebrow>Vorlagen</Eyebrow>
	{#each TRIP_TEMPLATES as tpl (tpl.id)}
		<GCard data-testid="trip-wizard-template-card-{tpl.id}" class="p-3">
			<div class="flex items-start justify-between gap-2 mb-2">
				<div>
					<p class="font-semibold text-sm">{tpl.name}</p>
					<p class="text-xs text-[var(--g-ink-faint)]">
						{REGION[tpl.id]} · {STAGE_COUNTS[tpl.id]} Etappen
					</p>
				</div>
				<Pill tone="default">Trekking</Pill>
			</div>
			<Btn
				variant="secondary"
				size="sm"
				class="w-full"
				data-testid="trip-wizard-template-apply-{tpl.id}"
				onclick={makeApplyHandler(tpl)}
			>
				Vorlage laden
			</Btn>
		</GCard>
	{/each}
</div>

<Dialog.Root bind:open={showConfirm}>
	<Dialog.Content
		data-testid="trip-wizard-template-confirm-dialog"
		showCloseButton={false}
	>
		<Dialog.Header>
			<Dialog.Title>Vorhandene Etappen ersetzen?</Dialog.Title>
			<Dialog.Description>
				Die aktuellen {wizard.stages.length} Etappen werden durch die Vorlage „{pendingTemplate?.name}" ersetzt.
			</Dialog.Description>
		</Dialog.Header>
		<Dialog.Footer>
			<Btn
				variant="ghost"
				data-testid="trip-wizard-template-confirm-cancel"
				onclick={cancelReplace}
			>
				Abbrechen
			</Btn>
			<Btn
				variant="accent"
				data-testid="trip-wizard-template-confirm-ok"
				onclick={confirmReplace}
			>
				Ja, ersetzen
			</Btn>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
