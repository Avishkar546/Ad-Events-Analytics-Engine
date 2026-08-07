"""
Query endpoints. Everything here reads from ad_spend_5min_latest (or
advertiser_budgets_latest) only — never raw events. If a query here feels
slow, that's a signal something upstream broke this contract, not a
reason to add a raw-table fallback.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.db.clickhouse import get_client
from app.models.budget import BudgetStatusResponse, SetBudgetRequest
from app.models.spend import SpendResponse
from app.services.budget_service import get_budget, set_budget
from app.services.spend_query_service import query_spend, query_total_spend, validate_group_by

router = APIRouter()


@router.get("/advertisers/{advertiser_id}/spend", response_model=SpendResponse)
def get_spend(
    advertiser_id: int,
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = Query(None),
    group_by: str | None = Query(None, description="Comma-separated: campaign_id,category,device"),
) -> SpendResponse:
    group_by_list = [g.strip() for g in group_by.split(",")] if group_by else []

    try:
        validate_group_by(group_by_list)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    client = get_client()
    resolved_from, resolved_to, rows = query_spend(client, advertiser_id, from_, to, group_by_list)

    return SpendResponse(
        advertiser_id=advertiser_id,
        from_=str(resolved_from),
        to=str(resolved_to),
        group_by=group_by_list,
        rows=rows,
    )


@router.get("/advertisers/{advertiser_id}/budget-status", response_model=BudgetStatusResponse)
def get_budget_status(advertiser_id: int) -> BudgetStatusResponse:
    client = get_client()

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    budget = get_budget(client, advertiser_id)
    spend_this_month = query_total_spend(client, advertiser_id, month_start, now)

    remaining = (budget - spend_this_month) if budget is not None else None
    over_budget = (spend_this_month > budget) if budget is not None else None

    return BudgetStatusResponse(
        advertiser_id=advertiser_id,
        monthly_budget=budget,
        spend_this_month=spend_this_month,
        remaining=remaining,
        over_budget=over_budget,
    )


@router.post("/advertisers/{advertiser_id}/budget", status_code=201)
def create_or_update_budget(advertiser_id: int, request: SetBudgetRequest) -> dict:
    client = get_client()
    set_budget(client, advertiser_id, request.monthly_budget)
    return {"advertiser_id": advertiser_id, "monthly_budget": str(request.monthly_budget)}
