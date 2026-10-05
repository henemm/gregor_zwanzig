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
	import SaveIndicator from '$lib/components/ui/SaveIndicator.svelte';
	import type { SaveStatus } from '$lib/stores/saveStatusStore.svelte';

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
		/** #2284 S2: testid der Überschrift (Trip: `trip-detail-h1`); ohne Prop keine testid. */
		titleTestid?: string;
		/** #2284 S2: Desktop-Titelgröße je Hub (Parameter statt kind-Verzweigung); Standard 30 px. */
		titleSize?: 30 | 38;
		/** #2284 S2: Controller des Hubs — der Baustein rendert den Speicher-Chip selbst. */
		saveController?: SaveStatus;
		onSaveField: (field: Field, value: string, schliessen: () => void) => Promise<void>;
		eyebrow?: Snippet;
		namePrefix?: Snippet;
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
		titleTestid,
		titleSize = 30,
		saveController,
		onSaveField,
		eyebrow,
		namePrefix,
		badges,
		meta,
		actions
	}: Props = $props();

	let open = $state({ name: false, region: false });
	let draft = $state({ name: '', region: '' });
	let saving = $state<Record<Field, boolean>>({ name: false, region: false, profile: false });
	let errors = $state<Record<Field, string | null>>({ name: null, region: null, profile: null });
	// #2284 S2 (Entscheidung 14): Handy-Knopf. Text nur aus der Prop `profile` (kein
	// optimistischer Zustand) ⇒ nach Erfolg sofort neu, nach Fehler unverändert.
	let auswahlOffen = $state(false);
	const knopfText = $derived(profileOptions.find((o) => o.value === profile)?.label ?? 'Aktivität wählen');
	function waehle(value: string): void {
		auswahlOffen = false;
		save('profile', value);
	}

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

<div data-kind={kind} class="min-w-0 flex-1 flex flex-col gap-2 desktop:block">
	{#if eyebrow}{@render eyebrow()}{/if}
	<div class="flex items-center gap-2 desktop:gap-3 min-h-[44px] desktop:min-h-0">
		{#if open.name}
			<input type="text" data-testid={`${p}-name-edit`} bind:value={draft.name} aria-label="Name bearbeiten" class="min-w-0 flex-1 desktop:flex-none font-semibold px-2 py-1 rounded-md desktop:text-2xl" style="border: 1px solid var(--g-rule); background: var(--g-card)" />
			{@render editButtons('name', 'Umbenennen')}
		{:else}
			<h1 data-testid={titleTestid} class="{titleSize === 38 ? 'desktop:text-[38px]' : 'desktop:text-[30px]'} m-0 min-w-0 truncate desktop:whitespace-normal font-semibold text-[length:var(--g-text-xl)] desktop:leading-[1.1] desktop:tracking-[-0.025em]">{#if namePrefix}{@render namePrefix()}{/if}{name}</h1>
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
			<span>{region || '—'}</span>
			<!-- Mobil 44×44-Tippfläche ohne Layout-Höhe (negativer Rand), Desktop unverändert (#2284 S2 AC-13). -->
			<button type="button" data-testid={`${p}-region-edit-toggle`} aria-label="Region bearbeiten" onclick={() => start('region')} class="inline-flex items-center justify-center min-h-[44px] min-w-[44px] -my-3 -mx-2 desktop:min-h-0 desktop:min-w-0 desktop:m-0 p-0.5 cursor-pointer" style="color: var(--g-ink-3)"><PencilIcon size={13} /></button>
			<!-- {' · '} statt " · ": Svelte trimmt sonst das Leerzeichen vor {/if} weg. -->
			{#if profileLabel}<span>{' · '}{profileLabel}</span>{/if}
			{#if meta}{@render meta()}{/if}
		{/if}
	</div>
	{@render fieldError('region', 'order-1')}
	<!-- #2284 S2 (Entscheidung 14): Kacheln nur am Desktop, Knopf nur mobil — Umschaltung allein per CSS. -->
	<div class="order-2 hidden desktop:flex gap-2 flex-wrap desktop:mb-[18px]">
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
	<div class="order-2 relative self-start desktop:hidden">
		<button type="button" data-testid={`${p}-profil-knopf`} data-selected-value={profile ?? ''} aria-haspopup="true" aria-expanded={auswahlOffen} disabled={saving.profile} onclick={() => (auswahlOffen = !auswahlOffen)} class="inline-flex items-center gap-1.5 min-h-[44px] px-3.5 text-sm font-medium cursor-pointer" style:background={profile ? 'var(--g-accent-tint)' : 'var(--g-card)'} style:border={profile ? '1.5px solid var(--g-accent)' : '1px solid var(--g-rule)'} style:color={profile ? 'var(--g-accent-deep)' : 'var(--g-ink)'} style="border-radius: var(--g-r-3)">{knopfText}<span aria-hidden="true">▾</span></button>
		<div data-testid={`${p}-profil-auswahl`} hidden={!auswahlOffen} class="absolute left-0 top-full mt-1 z-20 flex flex-col min-w-[220px] p-1" style="background: var(--g-card); border: 1px solid var(--g-rule); border-radius: var(--g-r-3); box-shadow: 0 4px 12px rgba(0,0,0,0.12)">
			{#each profileOptions as opt (opt.value)}
				<button type="button" data-testid={`${p}-profil-auswahl-option-${opt.value}`} data-selected={profile === opt.value ? 'true' : 'false'} disabled={saving.profile} onclick={() => waehle(opt.value)} class="min-h-[44px] px-3 text-left text-sm cursor-pointer rounded-md" style:background={profile === opt.value ? 'var(--g-accent-tint)' : 'transparent'} style="color: var(--g-ink)">{opt.label}</button>
			{/each}
		</div>
	</div>
	{@render fieldError('profile', 'order-2')}
</div>

<!-- #2284 S2: Speicher-Chip (position:fixed, Mount-Stelle frei) — vom Baustein, nicht von den Seiten. -->
{#if saveController}
	<SaveIndicator controller={saveController} />
{/if}
