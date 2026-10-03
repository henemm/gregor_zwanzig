<script lang="ts">
	// Issue #2284 S1 — geteilter Hub-Kopf für Trip und Vergleich: Name (<h1>),
	// Region und Aktivitätsprofil inline editierbar. EIN Markup für Desktop und
	// Mobil (responsive `desktop:`-Klassen), keine Verzweigung nach `kind` —
	// Unterschiede laufen nur über Props und Snippets. Kein Speicherweg im
	// Baustein: `onSaveField(field, value, schliessen)` kommt von der Seite.
	// Drei Ausgänge: (a) gespeichert ⇒ die Seite ruft `schliessen()`, das Feld
	// schließt; (b) Konflikt an „Nochmal speichern" übergeben ⇒ Promise erfüllt
	// OHNE `schliessen()`: Feld bleibt offen, keine Meldung — schließt erst, wenn
	// die Seite `schliessen()` nach erfolgreichem Retry ruft; (c) Fehler ⇒ WIRFT,
	// die Meldung erscheint am Feld, das Eingabefeld bleibt mit dem Wert offen.
	import type { Snippet } from 'svelte';
	import { Btn } from '$lib/components/atoms';
	import PencilIcon from '@lucide/svelte/icons/pencil';

	type Field = 'name' | 'region' | 'profile';

	interface Props {
		kind: 'trip' | 'vergleich';
		name: string;
		region: string | undefined;
		profile: string | undefined;
		profileOptions: ReadonlyArray<{ value: string; label: string }>;
		profileLabel?: string;
		regionMaxLength?: number;
		testidPrefix: string;
		onSaveField: (field: Field, value: string, schliessen: () => void) => Promise<void>;
		eyebrow?: Snippet;
		badges?: Snippet;
		meta?: Snippet;
		actions?: Snippet;
	}

	let {
		kind,
		name,
		region,
		profile,
		profileOptions,
		profileLabel = '',
		regionMaxLength = 60,
		testidPrefix: p,
		onSaveField,
		eyebrow,
		badges,
		meta,
		actions
	}: Props = $props();

	let open = $state({ name: false, region: false });
	let draft = $state({ name: '', region: '' });
	let saving = $state<Record<Field, boolean>>({ name: false, region: false, profile: false });
	let errors = $state<Record<Field, string | null>>({ name: null, region: null, profile: null });

	function start(field: 'name' | 'region'): void {
		draft[field] = (field === 'name' ? name : region) ?? '';
		errors[field] = null;
		open[field] = true;
	}
	function cancel(field: 'name' | 'region'): void {
		errors[field] = null;
		open[field] = false;
	}
	async function save(field: Field, value: string): Promise<void> {
		saving[field] = true;
		errors[field] = null;
		try {
			// Geschlossen wird NUR über den Callback — auch später, nach erfolgreichem „Nochmal speichern".
			await onSaveField(field, value, () => {
				if (field !== 'profile') open[field] = false;
			});
		} catch (e: unknown) {
			errors[field] = (e as { error?: string })?.error || 'Speichern fehlgeschlagen';
		} finally {
			saving[field] = false;
		}
	}
</script>

{#snippet editButtons(field: 'name' | 'region', desktopLabel: string)}
	<Btn variant="ghost" size="sm" data-testid={`${p}-${field}-save`} disabled={saving[field]} onclick={() => save(field, draft[field])}>
		{#if saving[field]}…{:else}<span class="hidden desktop:inline">{desktopLabel}</span><span class="desktop:hidden">OK</span>{/if}
	</Btn>
	<Btn variant="ghost" size="sm" aria-label="Abbrechen" onclick={() => cancel(field)}><span class="hidden desktop:inline">Abbrechen</span><span class="desktop:hidden">×</span></Btn>
{/snippet}

<!-- Mobil (flex-col) stehen Name- und Region-Fehler wie bisher unter der Unterzeile:
     `order` wirkt nur dort, Desktop ist ein Block in DOM-Reihenfolge. -->
{#snippet fieldError(field: Field, order: string)}
	{#if errors[field]}<div data-testid={`${p}-${field === 'profile' ? 'profil' : field}-save-error`} role="alert" class="text-sm desktop:mt-1.5 desktop:mb-2 {order}" style="color: var(--g-bad)">{errors[field]}</div>{/if}
{/snippet}

<div data-kind={kind} class="min-w-0 flex-1 flex flex-col gap-4 desktop:block">
	{#if eyebrow}{@render eyebrow()}{/if}
	<div class="flex items-center gap-2 desktop:gap-3 min-h-[44px] desktop:min-h-0">
		{#if open.name}
			<input type="text" data-testid={`${p}-name-edit`} bind:value={draft.name} aria-label="Name bearbeiten" class="min-w-0 flex-1 desktop:flex-none font-semibold px-2 py-1 rounded-md desktop:text-2xl" style="border: 1px solid var(--g-rule); background: var(--g-card)" />
			{@render editButtons('name', 'Umbenennen')}
		{:else}
			<h1 class="m-0 min-w-0 truncate desktop:whitespace-normal font-semibold text-base desktop:text-[30px] desktop:leading-[1.1] desktop:tracking-[-0.025em]">{name}</h1>
			<button type="button" data-testid={`${p}-name-edit-toggle`} aria-label="Name bearbeiten" onclick={() => start('name')} class="flex-shrink-0 inline-flex items-center justify-center min-h-[44px] min-w-[44px] desktop:min-h-0 desktop:min-w-0 desktop:p-1 cursor-pointer" style="color: var(--g-ink-3)"><PencilIcon size={15} /></button>
		{/if}
		{#if badges}{@render badges()}{/if}
		{#if actions}{@render actions()}{/if}
	</div>
	{@render fieldError('name', 'order-1')}
	<div class="text-sm flex items-center gap-2 flex-wrap desktop:mt-2 desktop:mb-2.5" style="color: var(--g-ink-3)">
		{#if open.region}
			<input type="text" data-testid={`${p}-region-edit`} bind:value={draft.region} aria-label="Region bearbeiten" maxlength={regionMaxLength} class="min-w-0 flex-1 desktop:flex-none px-2 py-1 rounded-md text-sm" style="border: 1px solid var(--g-rule); background: var(--g-card)" />
			{@render editButtons('region', 'Speichern')}
		{:else}
			<span>{region ?? '—'}</span>
			<button type="button" data-testid={`${p}-region-edit-toggle`} aria-label="Region bearbeiten" onclick={() => start('region')} class="inline-flex items-center p-0.5 cursor-pointer" style="color: var(--g-ink-3)"><PencilIcon size={13} /></button>
			<!-- {' · '} statt " · ": Svelte trimmt sonst das Leerzeichen vor {/if} weg. -->
			{#if profileLabel}<span>{' · '}{profileLabel}</span>{/if}
			{#if meta}{@render meta()}{/if}
		{/if}
	</div>
	{@render fieldError('region', 'order-1')}
	<div class="order-2 flex gap-2 flex-wrap desktop:mb-[18px]">
		{#each profileOptions as opt (opt.value)}
			{@const sel = profile === opt.value}
			<button
				type="button"
				data-testid={`${p}-profil-option-${opt.value}`}
				data-selected={sel ? 'true' : 'false'}
				disabled={saving.profile}
				onclick={() => save('profile', opt.value)}
				style:padding="6px 12px"
				style:font-size="13px"
				style:cursor="pointer"
				style:background={sel ? 'var(--g-accent-tint)' : 'var(--g-card)'}
				style:border={sel ? '1.5px solid var(--g-accent)' : '1px solid var(--g-rule)'}
				style:border-radius="var(--g-r-3)"
				style:color={sel ? 'var(--g-accent-deep)' : 'var(--g-ink)'}
			>{opt.label}</button>
		{/each}
	</div>
	{@render fieldError('profile', 'order-2')}
</div>
