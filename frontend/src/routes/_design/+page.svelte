<script lang="ts">
	import { Btn } from '$lib/components/ui/btn';
	import { GCard } from '$lib/components/ui/g-card';
	import { Pill } from '$lib/components/ui/pill';
	import { Eyebrow } from '$lib/components/ui/eyebrow';
	import { Dot } from '$lib/components/ui/dot';
	import { TopoBg } from '$lib/components/ui/topo';
	import { ElevSparkline } from '$lib/components/ui/elev-sparkline';
	import Pencil from '@lucide/svelte/icons/pencil';
	import { profileSignature } from '$lib/utils/profileSignature';
	import type { ActivityProfile } from '$lib/types';

	const PROFILES: ActivityProfile[] = ['wintersport', 'wandern', 'summer_trekking', 'allgemein'];
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
				<Btn size="xs"      data-testid="btn-showcase-size-xs"><Pencil />XS</Btn>
				<Btn size="sm"      data-testid="btn-showcase-size-sm"><Pencil />SM</Btn>
				<Btn size="md"      data-testid="btn-showcase-size-md"><Pencil />MD</Btn>
				<Btn size="lg"      data-testid="btn-showcase-size-lg"><Pencil />LG</Btn>
				<Btn size="icon-xs" data-testid="btn-showcase-size-icon-xs" aria-label="Bearbeiten XS"><Pencil /></Btn>
				<Btn size="icon-sm" data-testid="btn-showcase-size-icon-sm" aria-label="Bearbeiten SM"><Pencil /></Btn>
				<Btn size="icon"    data-testid="btn-showcase-size-icon"    aria-label="Bearbeiten"><Pencil /></Btn>
				<Btn size="icon-lg" data-testid="btn-showcase-size-icon-lg" aria-label="Bearbeiten LG"><Pencil /></Btn>
			</div>
		</div>

		<div class="space-y-3">
			<Eyebrow>Btn — States</Eyebrow>
			<div class="flex gap-2 items-center flex-wrap">
				<Btn disabled data-testid="btn-showcase-state-disabled">Disabled</Btn>
				<Btn data-testid="btn-showcase-state-icon"><Pencil />With Icon</Btn>
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
					<span class="text-xs text-[color:var(--g-ink-faint)]">leer</span>
				</div>
				<div class="flex flex-col items-start gap-1">
					<ElevSparkline data={[1500]} width={120} height={24} />
					<span class="text-xs text-[color:var(--g-ink-faint)]">Single-Point</span>
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
</div>
