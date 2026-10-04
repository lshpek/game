"""Daily missions and cosmetic endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, rate_limit
from app.db.session import get_db
from app.models.enums import AnalyticsEventName
from app.models.numora import Mission
from app.models.user import User
from app.schemas.plates import CosmeticItem, EquipCosmeticResponse, MissionItem
from app.services.analytics import AnalyticsService
from app.services.cosmetics import CosmeticService
from app.services.missions import MissionService

router = APIRouter(tags=["missions"])


@router.get("/missions", response_model=list[MissionItem], summary="Today's daily missions")
def missions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MissionItem]:
    service = MissionService(db)
    outcomes = service.progress(user.id)
    db.commit()

    descriptions = {
        row.code: row
        for row in db.execute(select(Mission).where(Mission.code.in_([o.code for o in outcomes])))
        .scalars()
        .all()
    }
    items: list[MissionItem] = []
    for outcome in outcomes:
        definition = descriptions.get(outcome.code)
        items.append(
            MissionItem(
                code=outcome.code,
                name_en=outcome.name_en,
                name_ru=outcome.name_ru,
                description_en=definition.description_en if definition else "",
                description_ru=definition.description_ru if definition else "",
                icon=definition.icon if definition else "target",
                progress=outcome.progress,
                target=outcome.target,
                completed=outcome.completed,
                reward_coins=outcome.reward_coins,
                reward_rolls=outcome.reward_rolls,
                reward_xp=outcome.reward_xp,
            )
        )
    return items


@router.get("/cosmetics", response_model=list[CosmeticItem], summary="Cosmetic catalogue")
def cosmetics(
    kind: str | None = Query(default=None, max_length=32),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CosmeticItem]:
    items = CosmeticService(db).serialize(user.id)
    if kind:
        wanted = kind.upper()
        items = [item for item in items if item["kind"] == wanted]
    return [CosmeticItem(**item) for item in items]


@router.post(
    "/cosmetics/{code}/equip",
    response_model=EquipCosmeticResponse,
    dependencies=[Depends(rate_limit("default", "rate_limit_default"))],
    summary="Equip one owned cosmetic",
)
def equip_cosmetic(
    code: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EquipCosmeticResponse:
    service = CosmeticService(db)
    equipped = service.equip(user, code)
    AnalyticsService(db).track(
        AnalyticsEventName.COSMETIC_EQUIPPED.value,
        user_id=user.id,
        telegram_id=user.telegram_id,
        props={"cosmetic": equipped},
    )
    db.commit()
    return EquipCosmeticResponse(
        code=equipped,
        equipped=True,
        equipped_map=service.equipped_codes(user.id),
    )


@router.post(
    "/cosmetics/{code}/unequip",
    response_model=EquipCosmeticResponse,
    dependencies=[Depends(rate_limit("default", "rate_limit_default"))],
    summary="Unequip a cosmetic",
)
def unequip_cosmetic(
    code: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EquipCosmeticResponse:
    service = CosmeticService(db)
    service.unequip(user, code)
    db.commit()
    return EquipCosmeticResponse(
        code=code, equipped=False, equipped_map=service.equipped_codes(user.id)
    )


@router.get("/cosmetics/titles", summary="Owned titles")
def titles(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    return CosmeticService(db).titles(user.id)
