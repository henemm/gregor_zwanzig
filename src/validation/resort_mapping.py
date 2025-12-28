"""
Resort to coordinates mapping.

Maps ski resort slugs (bergfex format) to geographic coordinates.
Used for comparing resort-reported snow depths with SNOWGRID data.
"""

from typing import Dict, Tuple

# Resort data: (name, lat, lon, elevation_top, elevation_base)
# 5 Skigebiete Tirol
RESORT_COORDINATES: Dict[str, Tuple[str, float, float, int, int]] = {
    "stubaier-gletscher": ("Stubaier Gletscher", 47.00, 11.30, 3210, 1750),
    "axamer-lizum": ("Axamer Lizum", 47.19, 11.31, 2340, 1560),
    "obergurgl-hochgurgl": ("Obergurgl-Hochgurgl", 46.87, 11.03, 3080, 1800),
    "soelden": ("Sölden", 46.97, 10.87, 3340, 1350),
    "ischgl": ("Ischgl", 46.97, 10.29, 2872, 1400),
}


def get_resort(slug: str) -> Tuple[str, float, float, int, int]:
    """
    Get resort info by slug.

    Returns:
        Tuple of (name, lat, lon, elevation_top, elevation_base)
    """
    if slug not in RESORT_COORDINATES:
        raise ValueError(f"Unknown resort: {slug}")
    return RESORT_COORDINATES[slug]


def get_coordinates(slug: str) -> Tuple[float, float]:
    """Get (lat, lon) for a resort."""
    return RESORT_COORDINATES[slug][1:3]


def get_elevation_top(slug: str) -> int:
    """Get top elevation for a resort."""
    return RESORT_COORDINATES[slug][3]


def all_resort_slugs() -> list[str]:
    """Get all resort slugs."""
    return list(RESORT_COORDINATES.keys())
