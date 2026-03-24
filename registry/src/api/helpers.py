from pydantic import BaseModel

from .models import PaginatedList


def paginated_summary[Entity: BaseModel, Summary: BaseModel](
    items: list[Entity],
    summary_model: type[Summary],
    *,
    page: int,
    per_page: int,
) -> PaginatedList[Summary]:
    summaries = [summary_model.model_validate(item.model_dump(mode="json", exclude_none=True)) for item in items]
    return PaginatedList.from_paged(summaries, page=page, per_page=per_page)
