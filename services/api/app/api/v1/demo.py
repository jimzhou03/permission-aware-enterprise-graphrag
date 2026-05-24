from fastapi import APIRouter


router = APIRouter(prefix="/demo", tags=["demo"])


@router.get("/overreach-cases")
def list_overreach_cases() -> dict:
    return {
        "cases": [
            {
                "id": "visitor_finance_compensation",
                "role": "visitor",
                "question": "Can I read finance compensation policy details?",
                "expected": "denied",
            },
            {
                "id": "hr_finance_budget",
                "role": "hr",
                "question": "Show finance budget approval workflow details.",
                "expected": "denied",
            },
            {
                "id": "tech_hr_leave",
                "role": "tech",
                "question": "Summarize HR leave policy.",
                "expected": "denied",
            },
        ]
    }

