from decimal import Decimal

from pydantic import BaseModel


class SpendRow(BaseModel):
    """
    One row of the spend query result. The group_by dimension fields
    (campaign_id, category, device) are optional because which ones are
    present depends on what the caller asked to group by — see
    spend_query_service.query_spend for how this gets built.
    """

    campaign_id: int | None = None
    category: str | None = None
    device: str | None = None
    impressions: int
    clicks: int
    spend: Decimal


class SpendResponse(BaseModel):
    advertiser_id: int
    from_: str
    to: str
    group_by: list[str]
    rows: list[SpendRow]
