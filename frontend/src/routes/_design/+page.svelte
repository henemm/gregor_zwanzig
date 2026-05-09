<script lang="ts">
	import { Btn } from '$lib/components/ui/btn';
	import { GCard } from '$lib/components/ui/g-card';
	import { Pill } from '$lib/components/ui/pill';
	import { Eyebrow } from '$lib/components/ui/eyebrow';
	import { Dot } from '$lib/components/ui/dot';
	import { TopoBg } from '$lib/components/ui/topo';
	import { ElevSparkline } from '$lib/components/ui/elev-sparkline';
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
		<TopoBg opacity={0.06}>
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
</div>
