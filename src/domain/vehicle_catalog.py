"""Reference data for the manual-registration form's maker/model/year pickers
(see presentation/web.py, templates/manuals.html). Selecting from a list instead
of free-typing avoids the typo class of bug (a maker/model spelled two different
ways across two registrations silently creates two unrelated-looking entries).

MAKERS is the 10 highest-volume light-vehicle brands by actual 2025 full-year US
sales (not corporate groups — e.g. GM and Stellantis are excluded as such, but
their highest-volume individual brands, Chevrolet/GMC and Jeep, are included in
their own right), and MODELS_BY_MAKER is each of those makers' own model lineup
ranked the same way, both confirmed against real sales data (best-selling-cars.com
and goodcarbadcar.net 2025 full-year figures) rather than guessed. This is a
convenience list, not an exhaustive one: a real manual for a maker/model outside
it is still fully supported via the form's own "Other" free-text fallback, which
this module does not need to know about.

This data will drift as real-world sales rankings and lineups change year to
year; it is not re-derived automatically and isn't meant to be authoritative
beyond "a reasonable, real default list to pick from."
"""
from __future__ import annotations

MAKERS: list[str] = [
    "Chevrolet",
    "Ford",
    "GMC",
    "Honda",
    "Hyundai",
    "Jeep",
    "Kia",
    "Nissan",
    "Subaru",
    "Toyota",
]

MODELS_BY_MAKER: dict[str, list[str]] = {
    "Chevrolet": [
        "Silverado",
        "Equinox",
        "Trax",
        "Silverado HD",
        "Traverse",
        "Tahoe",
        "Colorado",
        "Trailblazer",
        "Suburban",
        "Express",
    ],
    "Ford": [
        "F-150",
        "Explorer",
        "Transit",
        "Maverick",
        "Bronco",
        "Escape",
        "Bronco Sport",
        "Expedition",
        "Ranger",
        "Mustang Mach-E",
    ],
    "GMC": [
        "Sierra",
        "Sierra HD",
        "Yukon",
        "Terrain",
        "Acadia",
        "Canyon",
        "Savana",
        "Hummer EV",
        "Sierra EV",
    ],
    "Honda": [
        "CR-V",
        "Civic",
        "Accord",
        "HR-V",
        "Pilot",
        "Odyssey",
        "Passport",
        "Ridgeline",
        "Prologue",
        "Prelude",
    ],
    "Hyundai": [
        "Tucson",
        "Elantra",
        "Santa Fe",
        "Palisade",
        "Kona",
        "Sonata",
        "Ioniq 5",
        "Venue",
        "Santa Cruz",
        "Ioniq 6",
    ],
    "Jeep": [
        "Grand Cherokee",
        "Wrangler",
        "Compass",
        "Gladiator",
        "Wagoneer",
        "Wagoneer S",
        "Grand Wagoneer",
        "Renegade",
        "Cherokee",
        "Recon",
    ],
    "Kia": [
        "Sportage",
        "K4",
        "Telluride",
        "Sorento",
        "K5",
        "Carnival",
        "Seltos",
        "Soul",
        "Niro",
        "EV9",
    ],
    "Nissan": [
        "Rogue",
        "Sentra",
        "Kicks",
        "Pathfinder",
        "Altima",
        "Frontier",
        "Versa",
        "Murano",
        "Armada",
        "Ariya",
    ],
    "Subaru": [
        "Crosstrek",
        "Forester",
        "Outback",
        "Ascent",
        "Impreza",
        "Legacy",
        "WRX",
        "Solterra",
        "BRZ",
    ],
    "Toyota": [
        "RAV4",
        "Camry",
        "Tacoma",
        "Corolla",
        "Tundra",
        "Grand Highlander",
        "Sienna",
        "Corolla Cross",
        "4Runner",
        "Prius",
    ],
}
