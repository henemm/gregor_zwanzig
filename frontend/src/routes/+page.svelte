<script lang="ts">
	import type { Trip, Subscription, StagesWeatherResponse } from '$lib/types.js';
	import { Card, Pill, Dot, Eyebrow, Btn, ElevSparkline, SectionH } from '$lib/components/atoms';
	import { StagePill, BriefingTimelineRow } from '$lib/components/molecules';
	import {
		tripStatus,
		activeOrNextTrip,
		todayStageIndex
	} from '$lib/utils/tripStatus.js';
	import {
		stageProfile,
		stageWindow,
		stageStats,
		riskTone,
		weatherSummary,
		plannedBriefings,
		archivedTrips,
		stageStripState
	} from './_home/cockpitHelpers.js';
	import TripKachel from './_home/TripKachel.svelte';
	import CompareKachel from './_home/CompareKachel.svelte';
	import EmptyKachel from './_home/EmptyKachel.svelte';

	let { data } = $props();

	const now = new Date();
	const trips = $derived((data.trips ?? []) as Trip[]);
	const subscriptions = $derived((data.subscriptions ?? []) as Subscription[]);
	const heroWeather = null as StagesWeatherResponse | null; // Issue 395: kein Live-Wetter auf der Website (dormant; späteres On-Demand-Laden separat)
	const isEmpty = $derived(trips.length === 0 && subscriptions.length === 0);

	const todayPretty = now.toLocaleDateString('de-DE', {
		weekday: 'short',
		day: '2-digit',
		month: 'long',
		year: 'numeric'
	});

	// --- Hero-Tour (aktiv oder nächste) -------------------------------------
	const hero = $derived(activeOrNextTrip(trips, now));
	const heroIsActive = $derived(hero ? tripStatus(hero, now) === 'aktiv' : false);
	const heroStages = $derived(hero?.stages ?? []);

	// Heutige Etappe (aktiv) bzw. erste Etappe (nächste Tour).
	const todayIdx = $derived(hero ? todayStageIndex(hero, now) : -1);
	// F002: Findet sich bei einer aktiven Tour keine exakte Heute-Etappe
	// (Datums-Lücke), fallen wir bewusst auf Etappe 0 zurück. Annahme: eine
	// Etappe pro Tag (GR20/KHW). Datums-Lücken sind in diesem Modell selten.
	const heroStageIdx = $derived(todayIdx >= 0 ? todayIdx : heroStages.length > 0 ? 0 : -1);
	const heroStage = $derived(heroStageIdx >= 0 ? heroStages[heroStageIdx] : null);
	const heroWeatherResult = $derived(
		heroStage ? (heroWeather?.results?.[heroStage.id] ?? null) : null
	);

	const heroLabel = $derived(
		heroIsActive ? `Tag ${heroStageIdx + 1} von ${heroStages.length}` : 'Nächster Trip'
	);
	const heroStats = $derived(stageStats(heroStage));
	const heroWindow = $derived(stageWindow(heroStage));
	const heroProfile = $derived(stageProfile(heroStage));
	const heroRisk = $derived(riskTone(heroWeatherResult));
	const heroSummary = $derived(weatherSummary(heroWeatherResult));

	// Folge-Etappe (nach der Hero-Etappe).
	const nextIdx = $derived(heroStageIdx >= 0 ? heroStageIdx + 1 : -1);
	const nextStage = $derived(nextIdx >= 0 && nextIdx < heroStages.length ? heroStages[nextIdx] : null);
	const nextWeatherResult = $derived(
		nextStage ? (heroWeather?.results?.[nextStage.id] ?? null) : null
	);
	const nextStats = $derived(stageStats(nextStage));
	const nextProfile = $derived(stageProfile(nextStage));
	const nextRisk = $derived(riskTone(nextWeatherResult));
	const nextSummary = $derived(weatherSummary(nextWeatherResult));

	// --- Rechte Spalte: geplante Briefings ----------------------------------
	const briefings = $derived(hero ? plannedBriefings(hero.report_config) : []);

	// --- Archiv -------------------------------------------------------------
	const archive = $derived(archivedTrips(trips, now, 4));

	// --- Rückwärtskompatibilität: weitere Touren (ohne Hero) ----------------
	const otherTrips = $derived(trips.filter((t) => t.id !== hero?.id));
</script>

<div style:position="relative" style:padding="0 0 80px" style:max-width="1320px">
	<!-- Topbar -->
	<header
		style:display="flex"
		style:align-items="center"
		style:justify-content="space-between"
		style:padding="20px 0"
		style:border-bottom="1px solid var(--g-rule-soft)"
		style:margin-bottom="32px"
	>
		<div>
			<Eyebrow>Übersicht · {todayPretty}</Eyebrow>
			<div style:font-size="22px" style:font-weight="600" style:margin-top="2px" style:letter-spacing="-0.005em">
				Deine Trips & Vergleiche
			</div>
			<div style:font-size="0.9375rem" style:color="var(--g-ink-muted)" style:margin-top="4px" style:line-height="1.5">
				Was du jetzt vorbereitest, läuft unterwegs autark. Briefings gehen per Email oder Signal, du musst am Berg nichts tun.
			</div>
		</div>
		<div style:display="flex" style:gap="10px" style:align-items="center">
			<Btn href="/compare" variant="ghost" size="sm">Neuer Vergleich</Btn>
			<Btn href="/trips/new" variant="primary" size="sm">+ Neuer Trip</Btn>
		</div>
	</header>

	{#if isEmpty}
		<EmptyKachel />
	{:else}
		<!-- HERO + rechte Spalte -->
		{#if hero}
			<div class="cockpit-hero">
				<!-- Aktiver/Nächster Trip -->
				<Card class="!p-0" style="overflow: hidden; border-left: 3px solid var(--g-accent);">
					<div style:padding="24px 28px 0">
						<div style:display="flex" style:align-items="center" style:gap="10px" style:margin-bottom="8px">
							<Pill tone="accent">
								{#if heroIsActive}<Dot tone="bad" size={6} /> Live · {/if}{heroLabel}
							</Pill>
						</div>
						<a
							href="/trips/{hero.id}"
							style:display="block"
							style:font-size="32px"
							style:font-weight="600"
							style:letter-spacing="-0.02em"
							style:line-height="1.05"
							style:margin-bottom="6px"
							style:color="var(--g-ink)"
							style:text-decoration="none"
						>{hero.name}</a>
						{#if hero.region}
							<div style:font-size="15px" style:color="var(--g-ink-2)" style:margin-bottom="18px">
								{hero.region}
							</div>
						{/if}

						<!-- Hero-Etappe -->
						{#if heroStage}
							<div
								style:background="var(--g-card-alt)"
								style:border="1px solid var(--g-rule-soft)"
								style:border-radius="var(--g-r-3)"
								style:padding="16px 18px"
								style:margin-bottom="16px"
							>
								<div style:display="flex" style:justify-content="space-between" style:align-items="flex-start" style:margin-bottom="12px">
									<div>
										<Eyebrow>{heroIsActive ? 'Heutige Etappe' : 'Erste Etappe'}</Eyebrow>
										<div style:font-size="18px" style:font-weight="600" style:margin-top="4px">
											{heroStage.name}
										</div>
										<div
											style:font-family="var(--g-font-mono)"
											style:font-size="12px"
											style:color="var(--g-ink-3)"
											style:margin-top="4px"
										>
											{#if heroWindow}{heroWindow} · {/if}{heroStats.km} km · ↑{heroStats.ascent} ↓{heroStats.descent} · max {heroStats.maxElev} m
										</div>
									</div>
									{#if heroRisk}
										<Pill tone={heroRisk}>Risk</Pill>
									{/if}
								</div>
								{#if heroProfile.length > 1}
									<ElevSparkline data={heroProfile} width={520} height={56} stroke="var(--g-accent)" showArea />
								{/if}
								{#if heroSummary}
									<div
										style:font-size="14px"
										style:color="var(--g-ink-2)"
										style:margin-top="14px"
										style:padding-top="14px"
										style:border-top="1px dashed var(--g-rule-soft)"
										style:line-height="1.55"
									>{heroSummary}</div>
								{/if}
							</div>
						{/if}
					</div>

					<!-- Etappen-Streifen -->
					{#if heroStages.length > 0}
						<div style:border-top="1px solid var(--g-rule-soft)" style:padding="14px 28px 18px" style:background="var(--g-card)">
							<div style:display="flex" style:justify-content="space-between" style:align-items="center" style:margin-bottom="10px">
								<Eyebrow>Etappen-Verlauf</Eyebrow>
								<a
									href="/trips/{hero.id}"
									style:font-size="12px"
									style:color="var(--g-ink-3)"
									style:text-decoration="none"
									style:font-family="var(--g-font-mono)"
								>Alle anzeigen →</a>
							</div>
							<div style:display="flex" style:gap="4px" style:overflow="hidden">
								{#each heroStages as s, i (s.id)}
									<StagePill stage={{ code: s.name }} state={stageStripState(todayIdx, i)} />
								{/each}
							</div>
						</div>
					{/if}
				</Card>

				<!-- Rechte Spalte -->
				<div style:display="flex" style:flex-direction="column" style:gap="16px">
					<!-- Was geht heute raus -->
					<Card>
						<div style:padding="20px">
							<SectionH eyebrow="Heute" title="Was geht raus" />
							{#if briefings.length > 0}
								<div style:display="flex" style:flex-direction="column" style:gap="8px">
									{#each briefings as r, i (i)}
										<BriefingTimelineRow report={r} />
									{/each}
								</div>
							{:else}
								<div style:font-size="13px" style:color="var(--g-ink-3)">
									Keine Briefings für diesen Trip geplant.
								</div>
							{/if}
						</div>
					</Card>

					<!-- Alarme · letzte 24 h (sauberer Leerzustand, AC-6) -->
					<Card>
						<div style:padding="20px">
							<SectionH eyebrow="Alarme · letzte 24 h" title="Keine Alarme" />
							<div style:font-size="13px" style:color="var(--g-ink-3)" style:line-height="1.5">
								Keine Alarme in den letzten 24 Stunden. Schwellen verwaltest du im Trip.
							</div>
						</div>
					</Card>
				</div>
			</div>
		{/if}

		<!-- Nächste Etappe -->
		{#if nextStage}
			<div style:margin="40px 0">
				<Card>
					<div style:padding="20px">
						<SectionH eyebrow="Nächste Etappe" title={nextStage.name} />
						<div style:font-family="var(--g-font-mono)" style:font-size="12px" style:color="var(--g-ink-3)" style:margin-bottom="12px">
							{nextStats.km} km · ↑{nextStats.ascent} ↓{nextStats.descent} · max {nextStats.maxElev} m
							{#if nextRisk}<span> · Risk</span>{/if}
						</div>
						{#if nextProfile.length > 1}
							<ElevSparkline data={nextProfile} width={480} height={50} stroke="var(--g-accent)" showArea />
						{/if}
						{#if nextSummary}
							<div
								style:font-size="13px"
								style:color="var(--g-ink-2)"
								style:margin-top="12px"
								style:padding-top="12px"
								style:border-top="1px dashed var(--g-rule-soft)"
								style:line-height="1.55"
							>{nextSummary}</div>
						{/if}
					</div>
				</Card>
			</div>
		{/if}

		<!-- Archiv -->
		{#if archive.length > 0}
			<div style:margin-bottom="40px">
				<Card>
					<div style:padding="20px">
						<SectionH eyebrow="Archiv" title="Frühere Trips" right={archiveLink} />
						<div class="archive-grid">
							{#each archive as t (t.id)}
								<a
									href="/trips/{t.id}"
									style:padding="14px 16px"
									style:border="1px solid var(--g-rule-soft)"
									style:border-radius="var(--g-r-2)"
									style:background="var(--g-card-alt)"
									style:text-decoration="none"
									style:color="var(--g-ink)"
									style:display="block"
								>
									<div
										style:font-family="var(--g-font-mono)"
										style:font-size="10px"
										style:color="var(--g-ink-3)"
										style:text-transform="uppercase"
										style:letter-spacing="0.1em"
										style:margin-bottom="4px"
									>{t.dates}</div>
									<div style:font-size="14px" style:font-weight="600" style:line-height="1.3" style:margin-bottom="6px">
										{t.name}
									</div>
									<div style:font-family="var(--g-font-mono)" style:font-size="11px" style:color="var(--g-ink-3)">
										{t.stages} {t.stages === 1 ? 'Etappe' : 'Etappen'}
									</div>
								</a>
							{/each}
						</div>
					</div>
				</Card>
			</div>
		{/if}

		<!-- AC-12: Weitere Trips + Vergleiche (nichts verschwindet) -->
		{#if otherTrips.length > 0}
			<section style:margin-bottom="32px">
				<div class="kachel-grid">
					{#each otherTrips as trip (trip.id)}
						<TripKachel {trip} />
					{/each}
				</div>
			</section>
		{/if}

		{#if subscriptions.length > 0}
			<section style:margin-bottom="32px">
				<div class="kachel-grid">
					{#each subscriptions as sub (sub.id)}
						<CompareKachel {sub} />
					{/each}
				</div>
			</section>
		{/if}

		<div style:display="flex" style:gap="12px" style:flex-wrap="wrap">
			<Btn href="/trips/new" variant="accent">+ Neuer Trip</Btn>
			<Btn href="/compare" variant="outline">+ Neuer Vergleich</Btn>
		</div>
	{/if}
</div>

{#snippet archiveLink()}
	<Btn href="/trips" variant="quiet" size="sm">Alle anzeigen</Btn>
{/snippet}

<style>
	.cockpit-hero {
		display: grid;
		grid-template-columns: 1.4fr 1fr;
		gap: 24px;
		margin-bottom: 40px;
	}
	.archive-grid {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 12px;
	}
	.kachel-grid {
		display: grid;
		grid-template-columns: 1fr;
		gap: 0.75rem;
	}
	@media (max-width: 899px) {
		.cockpit-hero {
			grid-template-columns: 1fr;
		}
		.archive-grid {
			grid-template-columns: repeat(2, 1fr);
		}
	}
	@media (min-width: 640px) {
		.kachel-grid {
			grid-template-columns: repeat(2, 1fr);
		}
	}
	@media (min-width: 1024px) {
		.kachel-grid {
			grid-template-columns: repeat(3, 1fr);
		}
	}
</style>
