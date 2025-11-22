from fastapi import APIRouter

router = APIRouter(tags=["core"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}
