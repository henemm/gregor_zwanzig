<script lang="ts">
	import { Btn, Dot, ElevSparkline, Eyebrow, Input, Pill, Segmented, TopoBg, WIcon } from '$lib/components/atoms';
	import { GCard } from '$lib/components/ui/g-card';
	import PencilIcon from '@lucide/svelte/icons/pencil';
	import { profileSignature } from '$lib/utils/profileSignature';
	import type { ActivityProfile } from '$lib/types';

	import { Badge } from '$lib/components/ui/badge';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import { Label } from '$lib/components/ui/label';
	import { Select } from '$lib/components/ui/select';
	import Wordmark from '$lib/components/ui/wordmark/Wordmark.svelte';
	import BrandWordmark from '$lib/brand/BrandWordmark.svelte';
	import * as Card from '$lib/components/ui/card/index.js';
	import * as Table from '$lib/components/ui/table/index.js';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import AccordionSection from '$lib/components/edit/AccordionSection.svelte';
	import Loader2 from '@lucide/svelte/icons/loader-2';

	const PROFILES: ActivityProfile[] = ['wintersport', 'wandern', 'summer_trekking', 'allgemein'];

	// Issue #377: Kontrast-Belege — Ratio auf weisser Card (#ffffff), gemessen mit
	// scripts/contrast_audit.py (WCAG 2.1 relative luminance). Quelle: Spec-Matrix.
	const CONTRAST_TOKENS: { name: string; hex: string; ratio: number; cls: string }[] = [
		{ name: '--g-ink', hex: '#1a1a18', ratio: 17.43, cls: 'AAA' },
		{ name: '--g-ink-2', hex: '#45433d', ratio: 9.89, cls: 'AAA' },
		{ name: '--g-ink-3', hex: '#6b675c', ratio: 5.65, cls: 'AA' },
		{ name: '--g-ink-muted', hex: '#5c5a52', ratio: 6.91, cls: 'AA' },
		{ name: '--g-ink-4', hex: '#9a958a', ratio: 2.98, cls: 'FAIL' },
		{ name: '--g-ink-faint', hex: '#9c9a90', ratio: 2.82, cls: 'FAIL' },
		{ name: '--g-accent', hex: '#c45a2a', ratio: 4.34, cls: 'AA-large' },
		{ name: '--g-accent-deep', hex: '#8c3e1a', ratio: 7.45, cls: 'AAA' },
		{ name: '--g-good', hex: '#3d6b3a', ratio: 6.25, cls: 'AA' },
		{ name: '--g-warn', hex: '#c08a1a', ratio: 3.05, cls: 'AA-large' },
		{ name: '--g-warning', hex: '#c8882a', ratio: 3.0, cls: 'FAIL' },
		{ name: '--g-bad', hex: '#a83232', ratio: 6.63, cls: 'AA' },
		{ name: '--g-danger', hex: '#b33a2a', ratio: 5.91, cls: 'AA' },
		{ name: '--g-info', hex: '#2a6cb3', ratio: 5.39, cls: 'AA' },
		{ name: '--g-success', hex: '#3a7d44', ratio: 5.0, cls: 'AA' }
	];

	let dialogOpen = $state(false);
	let accordionAOpen = $state(true);
	let accordionBOpen = $state(false);
	let segmentedSelected = $state('etappe');
	let checkboxChecked = $state(true);

	// Issue #370: unbekannte Prop-Werte fuer den Fallback-Test (md/left).
	// Bewusst ueber die TS-Union hinaus, um AC-8 zu pruefen.
	const fallbackSize = 'xl' as unknown as 'sm' | 'md' | 'lg';
	const fallbackIcon = 'bottom' as unknown as 'left' | 'only' | 'none';
</script>

<div class="p-8 space-y-10">
	<div class="space-y-1">
		<Eyebrow>Wetter-Design-System</Eyebrow>
		<h1 data-testid="design-showcase-title">Design-System Showcase</h1>
	</div>

	<section data-testid="atoms-section" class="space-y-8">
		<div class="space-y-3">
			<Eyebrow>Buttons</Eyebrow>
			<div class="flex gap-2 items-center flex-wrap">
				<Btn variant="accent">Speichern</Btn>
				<Btn variant="ghost">Abbrechen</Btn>
				<Btn variant="outline" size="sm">Mehr</Btn>
			</div>
		</div>

		<div class="space-y-3">
			<Eyebrow>Btn — Variants</Eyebrow>
			<div class="flex gap-2 items-center flex-wrap">
				<Btn variant="primary"     data-testid="btn-showcase-variant-primary">Primary</Btn>
				<Btn variant="accent"      data-testid="btn-showcase-variant-accent">Accent</Btn>
				<Btn variant="outline"     data-testid="btn-showcase-variant-outline">Outline</Btn>
				<Btn variant="ghost"       data-testid="btn-showcase-variant-ghost">Ghost</Btn>
				<Btn variant="secondary"   data-testid="btn-showcase-variant-secondary">Secondary</Btn>
				<Btn variant="destructive" data-testid="btn-showcase-variant-destructive">Delete</Btn>
				<Btn variant="link"        data-testid="btn-showcase-variant-link">Link</Btn>
			</div>
		</div>

		<div class="space-y-3">
			<Eyebrow>Btn — Sizes</Eyebrow>
			<div class="flex gap-2 items-center flex-wrap">
				<Btn size="xs"      data-testid="btn-showcase-size-xs"><PencilIcon />XS</Btn>
				<Btn size="sm"      data-testid="btn-showcase-size-sm"><PencilIcon />SM</Btn>
				<Btn size="md"      data-testid="btn-showcase-size-md"><PencilIcon />MD</Btn>
				<Btn size="lg"      data-testid="btn-showcase-size-lg"><PencilIcon />LG</Btn>
				<Btn size="icon-xs" data-testid="btn-showcase-size-icon-xs" aria-label="Bearbeiten XS"><PencilIcon /></Btn>
				<Btn size="icon-sm" data-testid="btn-showcase-size-icon-sm" aria-label="Bearbeiten SM"><PencilIcon /></Btn>
				<Btn size="icon"    data-testid="btn-showcase-size-icon"    aria-label="Bearbeiten"><PencilIcon /></Btn>
				<Btn size="icon-lg" data-testid="btn-showcase-size-icon-lg" aria-label="Bearbeiten LG"><PencilIcon /></Btn>
			</div>
		</div>

		<div class="space-y-3">
			<Eyebrow>Btn — States</Eyebrow>
			<div class="flex gap-2 items-center flex-wrap">
				<Btn disabled data-testid="btn-showcase-state-disabled">Disabled</Btn>
				<Btn data-testid="btn-showcase-state-icon"><PencilIcon />With Icon</Btn>
				<Btn href="/_design" data-testid="btn-showcase-state-link">As Link</Btn>
				<Btn href="/_design" disabled data-testid="btn-showcase-state-link-disabled">Link Disabled</Btn>
			</div>
		</div>

		<div class="space-y-3">
			<Eyebrow>Pills</Eyebrow>
			<div class="flex gap-2 items-center flex-wrap">
				<Pill tone="default">Default</Pill>
				<Pill tone="success">OK</Pill>
				<Pill tone="warning">Achtung</Pill>
				<Pill tone="danger">Fehler</Pill>
				<Pill tone="info">Info</Pill>
				<Pill tone="accent">Akzent</Pill>
			</div>
		</div>

		<div class="space-y-3">
			<Eyebrow>Wetter-Tones</Eyebrow>
			<div class="flex gap-4 items-center flex-wrap text-sm">
				<span class="inline-flex items-center gap-2"><Dot tone="rain" size="md" /> Regen</span>
				<span class="inline-flex items-center gap-2"><Dot tone="sun" size="md" /> Sonne</span>
				<span class="inline-flex items-center gap-2"><Dot tone="thunder" size="md" /> Gewitter</span>
				<span class="inline-flex items-center gap-2"><Dot tone="snow" size="md" /> Schnee</span>
				<span class="inline-flex items-center gap-2"><Dot tone="wind" size="md" /> Wind</span>
				<span class="inline-flex items-center gap-2"><Dot tone="fog" size="md" /> Nebel</span>
			</div>
		</div>

		<div class="space-y-3">
			<Eyebrow>GCard mit Wetter-Stempel</Eyebrow>
			<GCard>
				<div class="flex items-center gap-3">
					<Dot tone="sun" size="md" />
					<div>
						<Eyebrow>Heute · 14:00</Eyebrow>
						<div class="text-lg font-semibold">22°C, sonnig</div>
						<div class="text-sm text-[color:var(--g-ink-muted)]">Wind 8 km/h SW · klar</div>
					</div>
				</div>
			</GCard>
		</div>

		<div class="space-y-3">
			<Eyebrow>Btn — Loading-State</Eyebrow>
			<div class="flex gap-2 items-center flex-wrap">
				<Btn variant="primary" disabled data-testid="btn-loading">
					<Loader2 class="animate-spin" size={16} />
					Lädt…
				</Btn>
			</div>
		</div>

		<div class="space-y-3">
			<Eyebrow>Pills — Outlined</Eyebrow>
			<div class="flex gap-2 items-center flex-wrap">
				<Pill tone="warning" data-outlined>Outlined Warning</Pill>
				<Pill tone="danger" data-outlined>Outlined Danger</Pill>
				<Pill tone="info" data-outlined>Outlined Info</Pill>
			</div>
		</div>

		<div class="space-y-3">
			<Eyebrow>Dot — Semantic-Tones × Sizes</Eyebrow>
			<div data-testid="dot-semantic-group" class="flex flex-col gap-2">
				<div class="flex gap-3 items-center">
					<Dot tone="success" size="xs" /> <Dot tone="success" size="sm" /> <Dot tone="success" size="md" />
				</div>
				<div class="flex gap-3 items-center">
					<Dot tone="warning" size="xs" /> <Dot tone="warning" size="sm" /> <Dot tone="warning" size="md" />
				</div>
				<div class="flex gap-3 items-center">
					<Dot tone="danger" size="xs" /> <Dot tone="danger" size="sm" /> <Dot tone="danger" size="md" />
				</div>
				<div class="flex gap-3 items-center">
					<Dot tone="info" size="xs" /> <Dot tone="info" size="sm" /> <Dot tone="info" size="md" />
				</div>
			</div>
		</div>

		<div class="space-y-3">
			<Eyebrow>Badge — Variants</Eyebrow>
			<div class="flex gap-2 items-center flex-wrap">
				<Badge variant="default">Default</Badge>
				<Badge variant="secondary">Secondary</Badge>
				<Badge variant="destructive">Destructive</Badge>
				<Badge variant="outline">Outline</Badge>
				<Badge variant="ghost">Ghost</Badge>
				<Badge variant="link">Link</Badge>
			</div>
		</div>

		<div class="space-y-3">
			<Eyebrow>WIcon — Wetter-Icons</Eyebrow>
			<div data-testid="wicon-group" class="flex gap-3 items-center flex-wrap">
				<WIcon kind="sun" />
				<WIcon kind="cloud" />
				<WIcon kind="rain" />
				<WIcon kind="thunder" />
				<WIcon kind="snow" />
				<WIcon kind="wind" />
				<WIcon kind="moon" />
				<WIcon kind="headlamp" />
			</div>
		</div>
	</section>

	<section data-testid="wordmark-section" class="space-y-3">
		<Eyebrow>Wordmark</Eyebrow>
		<div class="flex items-end" style:gap="var(--g-s-6)">
			<Wordmark size="sm" />
			<Wordmark size="md" />
			<Wordmark size="lg" />
		</div>
	</section>

	<section data-testid="brand-section" class="space-y-6">
		<Eyebrow>Brand-Bibliothek (Issue #370)</Eyebrow>

		<div class="space-y-3">
			<Eyebrow>BrandWordmark — icon="left" (Default-Lockup)</Eyebrow>
			<div data-testid="brand-demo-left" class="flex items-end" style:gap="var(--g-s-6)">
				<BrandWordmark size="sm" />
				<BrandWordmark size="md" />
				<BrandWordmark size="lg" />
			</div>
		</div>

		<div class="space-y-3">
			<Eyebrow>BrandWordmark — icon="only" (nur Glyph)</Eyebrow>
			<div data-testid="brand-demo-icon-only">
				<BrandWordmark icon="only" />
			</div>
		</div>

		<div class="space-y-3">
			<Eyebrow>BrandWordmark — icon="none" (nur Typo)</Eyebrow>
			<div data-testid="brand-demo-icon-none">
				<BrandWordmark icon="none" caption={null} />
			</div>
		</div>

		<div class="space-y-3">
			<Eyebrow>BrandWordmark — dark</Eyebrow>
			<div
				data-testid="brand-demo-dark"
				style="display:inline-block;padding:16px;background:var(--g-ink)"
			>
				<BrandWordmark dark={true} />
			</div>
		</div>

		<div class="space-y-3">
			<Eyebrow>BrandWordmark — Fallback (unbekannte Props → md/left)</Eyebrow>
			<div data-testid="brand-demo-fallback">
				<BrandWordmark size={fallbackSize} icon={fallbackIcon} />
			</div>
		</div>
	</section>

	<section data-testid="form-controls-section" class="space-y-6">
		<Eyebrow>Form Controls</Eyebrow>

		<div class="space-y-3">
			<Eyebrow>Checkbox</Eyebrow>
			<div class="flex gap-4 items-center flex-wrap">
				<Checkbox bind:checked={checkboxChecked}>Checked</Checkbox>
				<Checkbox>Unchecked</Checkbox>
				<Checkbox disabled>Disabled</Checkbox>
			</div>
		</div>

		<div class="space-y-3">
			<Eyebrow>Segmented</Eyebrow>
			<Segmented
				options={[
					{ value: 'etappe', label: 'Etappe' },
					{ value: 'tag', label: 'Tag' }
				]}
				selected={segmentedSelected}
				onselect={(v) => (segmentedSelected = v)}
			/>
		</div>

		<div class="space-y-3">
			<Eyebrow>Label + Input</Eyebrow>
			<div class="flex flex-col gap-2 max-w-sm">
				<Label for="demo-input">Name</Label>
				<Input id="demo-input" placeholder="Eingabe…" />
				<Input placeholder="Disabled" disabled />
				<Input placeholder="Fehler" aria-invalid="true" />
			</div>
		</div>

		<div class="space-y-3">
			<Eyebrow>Select</Eyebrow>
			<div class="flex gap-3 items-center flex-wrap">
				<Select>
					<option value="a">Option A</option>
					<option value="b">Option B</option>
				</Select>
				<Select disabled>
					<option value="a">Disabled</option>
				</Select>
			</div>
		</div>
	</section>

	<section data-testid="card-section" class="space-y-3">
		<Eyebrow>Card</Eyebrow>
		<Card.Root>
			<Card.Header>
				<Card.Title>Kartentitel</Card.Title>
				<Card.Description>Beschreibungstext der Karte.</Card.Description>
			</Card.Header>
			<Card.Content>Inhalt der Karte.</Card.Content>
			<Card.Footer>
				<Btn variant="ghost" size="sm">Aktion</Btn>
			</Card.Footer>
		</Card.Root>
	</section>

	<section data-testid="table-section" class="space-y-3">
		<Eyebrow>Table</Eyebrow>
		<Table.Root>
			<Table.Header>
				<Table.Row>
					<Table.Head>Etappe</Table.Head>
					<Table.Head>Distanz</Table.Head>
					<Table.Head>Status</Table.Head>
				</Table.Row>
			</Table.Header>
			<Table.Body>
				<Table.Row>
					<Table.Cell>Calenzana → Ortu</Table.Cell>
					<Table.Cell>16 km</Table.Cell>
					<Table.Cell>Aktiv</Table.Cell>
				</Table.Row>
				<Table.Row>
					<Table.Cell>Ortu → Carrozzu</Table.Cell>
					<Table.Cell>12 km</Table.Cell>
					<Table.Cell>Geplant</Table.Cell>
				</Table.Row>
			</Table.Body>
		</Table.Root>
	</section>

	<section data-testid="dialog-section" class="space-y-3">
		<Eyebrow>Dialog</Eyebrow>
		<Btn variant="outline" data-testid="dialog-open-trigger" onclick={() => (dialogOpen = true)}>
			Dialog öffnen
		</Btn>
		<Dialog.Root bind:open={dialogOpen}>
			<Dialog.Content>
				<Dialog.Header>
					<Dialog.Title>Beispiel-Dialog</Dialog.Title>
					<Dialog.Description>Beschreibungstext des Dialogs.</Dialog.Description>
				</Dialog.Header>
				<Dialog.Footer>
					<Btn variant="ghost" data-testid="dialog-close-btn" onclick={() => (dialogOpen = false)}>
						Schliessen
					</Btn>
				</Dialog.Footer>
			</Dialog.Content>
		</Dialog.Root>
	</section>

	<section data-testid="accordion-section" class="space-y-3">
		<Eyebrow>Accordion</Eyebrow>
		<AccordionSection
			id="demo-a"
			title="Sektion A (offen)"
			open={accordionAOpen}
			onToggle={() => (accordionAOpen = !accordionAOpen)}
		>
			Inhalt von Sektion A ist sichtbar.
		</AccordionSection>
		<AccordionSection
			id="demo-b"
			title="Sektion B (geschlossen)"
			open={accordionBOpen}
			onToggle={() => (accordionBOpen = !accordionBOpen)}
		>
			Inhalt von Sektion B ist verborgen.
		</AccordionSection>
	</section>

	<section data-testid="nav-hint-section" class="space-y-3">
		<Eyebrow>Navigation</Eyebrow>
		<p class="text-sm text-[color:var(--g-ink-muted)]">
			Sidebar, TopAppBar und BottomNav sind in dieser Seite nicht live darstellbar, da sie
			$app/state-Abhängigkeiten haben. Visuell prüfbar über normale App-Navigation.
		</p>
	</section>

	<section data-testid="topo-section" class="space-y-3">
		<Eyebrow>Topo-Hintergrund</Eyebrow>
		<TopoBg>
			<div class="p-8" style:border-radius="var(--g-radius-lg)">
				<Eyebrow>Topo-Hintergrundmuster</Eyebrow>
				<p class="mt-2">Subtiler Höhenlinien-Hintergrund. Wird hinter Inhalten gelegt, ohne Lesbarkeit zu stören.</p>
			</div>
		</TopoBg>
	</section>

	<section data-testid="sparkline-section" class="space-y-6">
		<div class="space-y-3">
			<Eyebrow>Höhenprofil-Sparkline</Eyebrow>
			<div class="inline-flex items-center gap-2">
				<span style:font-family="var(--g-font-data)" class="text-xs">800m</span>
				<ElevSparkline data={[800, 1200, 950, 1500, 1100]} width={200} height={40} />
				<span style:font-family="var(--g-font-data)" class="text-xs">1500m</span>
			</div>
		</div>

		<div class="space-y-3">
			<Eyebrow>Edge-Cases</Eyebrow>
			<div class="flex gap-6 items-start">
				<div class="flex flex-col items-start gap-1">
					<ElevSparkline data={[]} width={120} height={24} />
					<span class="text-xs text-[color: var(--g-ink-muted)]">leer</span>
				</div>
				<div class="flex flex-col items-start gap-1">
					<ElevSparkline data={[1500]} width={120} height={24} />
					<span class="text-xs text-[color: var(--g-ink-muted)]">Single-Point</span>
				</div>
			</div>
		</div>
	</section>

	<section data-testid="profile-signatures-section" class="space-y-3">
		<Eyebrow>Aktivitätsprofile (Issue #238)</Eyebrow>
		<div class="grid grid-cols-2 md:grid-cols-4 gap-4">
			{#each PROFILES as p (p)}
				{@const sig = profileSignature(p)}
				<GCard>
					<div class="flex flex-col gap-2">
						<Eyebrow>{sig.icon} {sig.eyebrow}</Eyebrow>
						<div class="flex items-center gap-2">
							<span
								class="inline-block w-3 h-3 rounded-full"
								style:background-color={sig.accent}
								aria-hidden="true"
							></span>
							<code class="text-xs" style:font-family="var(--g-font-data)">
								{sig.accent}
							</code>
						</div>
					</div>
				</GCard>
			{/each}
		</div>
	</section>
	<section data-testid="contrast-section" class="space-y-3">
		<Eyebrow>Issue #377</Eyebrow>
		<h2>Kontrast-Belege (WCAG-AA auf weißer Card)</h2>
		<p style="color: var(--g-ink-muted); font-size: var(--g-text-sm);">
			Ratio gemessen auf <code>--g-card #ffffff</code> via <code>scripts/contrast_audit.py</code>.
		</p>
		<div class="grid grid-cols-2 md:grid-cols-3 gap-3">
			{#each CONTRAST_TOKENS as t (t.name)}
				{@const pass = t.ratio >= 4.5}
				<div
					class="flex items-center gap-3 rounded p-2"
					style="border: 1px solid var(--g-rule); background: var(--g-card);"
				>
					<span
						class="inline-block rounded"
						style="width: 32px; height: 32px; flex: 0 0 auto; background-color: {t.hex};"
						aria-hidden="true"
					></span>
					<div class="flex flex-col" style="min-width: 0;">
						<code style="font-family: var(--g-font-data); font-size: var(--g-text-xs); color: var(--g-ink);">{t.name}</code>
						<span style="font-family: var(--g-font-data); font-size: var(--g-text-xs); color: var(--g-ink-muted);">
							{t.hex} · {t.ratio.toFixed(2)}:1
						</span>
					</div>
					<span
						class="ml-auto rounded"
						style="font-family: var(--g-font-data); font-size: 10px; font-weight: 600; padding: 2px 6px; color: {pass ? 'var(--g-success)' : 'var(--g-danger)'}; background: {pass ? 'rgba(61,107,58,0.12)' : 'rgba(168,50,50,0.12)'};"
					>{pass ? `${t.cls} ✓` : 'FAIL'}</span>
				</div>
			{/each}
		</div>
	</section>
</div>
