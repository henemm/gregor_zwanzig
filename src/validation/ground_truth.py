"""
Ground Truth Fetcher for TDD validation.

Fetches "expected" values from external sources (bergfex, GeoSphere Portal)
to use as ground truth in test-driven development.
"""

import re
from dataclasses import dataclass
from datetime import date
from typing import Optional

import httpx

from validation.resort_mapping import RESORT_COORDINATES, get_resort


@dataclass
class SnowReport:
    """Snow report data from bergfex."""

    resort_name: str
    snow_depth_mountain_cm: Optional[int]
    snow_depth_valley_cm: Optional[int]
    snow_condition: Optional[str]
    last_snowfall: Optional[date]
    elevation_mountain: Optional[int]
    elevation_valley: Optional[int]


class BergfexScraper:
    """Scrapes snow data from bergfex.com."""

    BASE_URL = "https://www.bergfex.com"
    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    def __init__(self) -> None:
        self._client = httpx.Client(
            headers={"User-Agent": self.USER_AGENT},
            follow_redirects=True,
            timeout=30.0,
        )

    def get_snow_report(self, resort_slug: str) -> SnowReport:
        """
        Fetch snow report for a resort.

        Args:
            resort_slug: Bergfex URL slug (e.g., "stubaier-gletscher")

        Returns:
            SnowReport with current snow data
        """
        resort_info = get_resort(resort_slug)
        resort_name = resort_info[0]
        elevation_top = resort_info[3]
        elevation_base = resort_info[4]

        # Use main page (not /schneebericht/) - has inline data
        url = f"{self.BASE_URL}/{resort_slug}/"
        response = self._client.get(url)
        response.raise_for_status()

        html = response.text

        return SnowReport(
            resort_name=resort_name,
            snow_depth_mountain_cm=self._extract_snow_depth(html, "mountain"),
            snow_depth_valley_cm=self._extract_snow_depth(html, "valley"),
            snow_condition=self._extract_condition(html),
            last_snowfall=self._extract_last_snowfall(html),
            elevation_mountain=elevation_top,
            elevation_valley=elevation_base,
        )

    def _extract_snow_depth(self, html: str, location: str) -> Optional[int]:
        """Extract snow depth in cm from HTML."""
        # Bergfex HTML structure:
        # <span class="tw-font-semibold">Mountain:</span>
        # <span>110 cm</span>
        if location == "mountain":
            patterns = [
                # Primary: "Mountain:" followed by span with value
                r'Mountain:</span>\s*<span>(\d+)\s*cm</span>',
                # German: "Berg:"
                r'Berg:</span>\s*<span>(\d+)\s*cm</span>',
                # Fallbacks
                r'Mountain[^0-9]{0,50}?(\d+)\s*cm',
                r'Berg[^0-9]{0,50}?(\d+)\s*cm',
            ]
        else:
            patterns = [
                # Primary: "Valley:" followed by span with value
                r'Valley:</span>\s*<span>(\d+)\s*cm</span>',
                # German: "Tal:"
                r'Tal:</span>\s*<span>(\d+)\s*cm</span>',
                # Fallbacks
                r'Valley[^0-9]{0,50}?(\d+)\s*cm',
                r'Tal[^0-9]{0,50}?(\d+)\s*cm',
            ]

        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
            if match:
                return int(match.group(1))

        return None

    def _extract_condition(self, html: str) -> Optional[str]:
        """Extract snow condition (e.g., 'grainy', 'powder')."""
        conditions = [
            "grainy", "powder", "wet", "icy", "packed", "crusty",
            "körnig", "pulver", "nass", "eisig", "griffig", "hart",
        ]
        html_lower = html.lower()
        for condition in conditions:
            if condition in html_lower:
                return condition
        return None

    def _extract_last_snowfall(self, html: str) -> Optional[date]:
        """Extract last snowfall date."""
        # Pattern: "12/08/2025" or "08.12.2025"
        patterns = [
            r'(\d{2})/(\d{2})/(\d{4})',  # MM/DD/YYYY
            r'(\d{2})\.(\d{2})\.(\d{4})',  # DD.MM.YYYY
        ]

        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                try:
                    g1, g2, g3 = match.groups()
                    if "/" in pattern:
                        # MM/DD/YYYY format
                        return date(int(g3), int(g1), int(g2))
                    else:
                        # DD.MM.YYYY format
                        return date(int(g3), int(g2), int(g1))
                except ValueError:
                    continue
        return None

    def get_all_resorts(self) -> dict[str, SnowReport]:
        """Fetch snow reports for all configured resorts."""
        reports = {}
        for slug in RESORT_COORDINATES:
            try:
                reports[slug] = self.get_snow_report(slug)
            except httpx.HTTPError:
                continue
        return reports


class GroundTruthFetcher:
    """
    Central class for fetching ground truth data from external sources.

    Used in TDD to get "expected" values for comparison with our API.
    """

    def __init__(self) -> None:
        self._bergfex = BergfexScraper()

    def get_resort_snow(self, resort_slug: str) -> SnowReport:
        """
        Get snow data for a ski resort from bergfex.

        This is the TDD "expected" value for snow depth comparisons.
        """
        return self._bergfex.get_snow_report(resort_slug)

    def get_snow_depth_mountain(self, resort_slug: str) -> Optional[int]:
        """Get mountain snow depth in cm for TDD comparison."""
        report = self.get_resort_snow(resort_slug)
        return report.snow_depth_mountain_cm

    def get_snow_depth_valley(self, resort_slug: str) -> Optional[int]:
        """Get valley snow depth in cm for TDD comparison."""
        report = self.get_resort_snow(resort_slug)
        return report.snow_depth_valley_cm
