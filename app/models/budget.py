from decimal import Decimal

from pydantic import BaseModel, Field


class SetBudgetRequest(BaseModel):
    monthly_budget: Decimal = Field(gt=0, decimal_places=4)


class BudgetStatusResponse(BaseModel):
    advertiser_id: int
    monthly_budget: Decimal | None  # None means no budget has been set yet
    spend_this_month: Decimal
    remaining: Decimal | None  # None when monthly_budget is None — nothing to compare against
    over_budget: bool | None
