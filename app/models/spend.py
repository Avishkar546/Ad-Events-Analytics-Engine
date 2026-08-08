from decimal import Decimal

from pydantic import BaseModel


class SpendRow(BaseModel):
    """
    campaign_id/category/device are None when that dimension wasn't
    requested via group_by — the row is a total across that dimension,
    not attributable to one value.
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
