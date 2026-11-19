from fastapi import APIRouter, HTTPException, Query, Request
from app.geocoding.models import SearchResponse
from app.geocoding.providers import ProviderError

router = APIRouter()


@router.get("/geocode/autocomplete", response_model=SearchResponse)
async def autocomplete(request: Request, q: str = Query(min_length=3, max_length=200),
                       limit: int = Query(default=6, ge=1, le=10)):
    try:
        return await request.app.state.geocoding.autocomplete(q, limit)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    except ProviderError:
        raise HTTPException(503, "Location search temporarily unavailable") from None
