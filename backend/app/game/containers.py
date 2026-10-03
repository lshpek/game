"""Container catalogue (loaded into the database by the seeder)."""

from __future__ import annotations

from dataclasses import dataclass

from app.game.rarity import Rarity


@dataclass(frozen=True, slots=True)
class ContainerDefinition:
    """A purchasable box with its own loot table."""

    code: str
    name: str
    description: str
    price: int
    rarity_weights: dict[str, float]
    accent: str
    animation: str
    minimum_rarity: str = Rarity.COMMON.value
    premium_only: bool = False
    sort_order: int = 0


CONTAINER_DEFINITIONS: tuple[ContainerDefinition, ...] = (
    ContainerDefinition(
        code="basic",
        name="Basic Box",
        description="A cheap box with a fair shot at uncommon finds.",
        price=100,
        rarity_weights={
            Rarity.COMMON.value: 62.0,
            Rarity.UNCOMMON.value: 27.0,
            Rarity.RARE.value: 8.5,
            Rarity.EPIC.value: 2.0,
            Rarity.LEGENDARY.value: 0.45,
            Rarity.MYTHIC.value: 0.05,
            Rarity.SECRET.value: 0.0,
        },
        accent="#38bdf8",
        animation="shake",
        minimum_rarity=Rarity.COMMON.value,
        sort_order=1,
    ),
    ContainerDefinition(
        code="premium",
        name="Premium Box",
        description="Better odds and a higher floor - Rare or above guaranteed.",
        price=500,
        rarity_weights={
            Rarity.COMMON.value: 0.0,
            Rarity.UNCOMMON.value: 40.0,
            Rarity.RARE.value: 39.0,
            Rarity.EPIC.value: 15.0,
            Rarity.LEGENDARY.value: 5.0,
            Rarity.MYTHIC.value: 0.9,
            Rarity.SECRET.value: 0.1,
        },
        accent="#a855f7",
        animation="glow",
        minimum_rarity=Rarity.RARE.value,
        sort_order=2,
    ),
    ContainerDefinition(
        code="mystery",
        name="Mystery Box",
        description="Everything is on the table, including secrets.",
        price=1000,
        rarity_weights={
            Rarity.COMMON.value: 0.0,
            Rarity.UNCOMMON.value: 18.0,
            Rarity.RARE.value: 42.0,
            Rarity.EPIC.value: 26.0,
            Rarity.LEGENDARY.value: 11.0,
            Rarity.MYTHIC.value: 2.7,
            Rarity.SECRET.value: 0.3,
        },
        accent="#f43f5e",
        animation="burst",
        minimum_rarity=Rarity.RARE.value,
        sort_order=3,
    ),
    ContainerDefinition(
        code="pro",
        name="Pro Box",
        description="Premium members only. Epic floor, mythic dreams.",
        price=2500,
        rarity_weights={
            Rarity.COMMON.value: 0.0,
            Rarity.UNCOMMON.value: 0.0,
            Rarity.RARE.value: 30.0,
            Rarity.EPIC.value: 48.0,
            Rarity.LEGENDARY.value: 18.0,
            Rarity.MYTHIC.value: 3.6,
            Rarity.SECRET.value: 0.4,
        },
        accent="#fbbf24",
        animation="burst",
        minimum_rarity=Rarity.EPIC.value,
        premium_only=True,
        sort_order=4,
    ),
)


def container_by_code(code: str) -> ContainerDefinition | None:
    return next((item for item in CONTAINER_DEFINITIONS if item.code == code), None)
