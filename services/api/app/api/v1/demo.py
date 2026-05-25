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
                "id": "cn_staff_en_internal",
                "role": "cn_staff",
                "question": "Explain the English internal handbook release coordination policy.",
                "expected": "denied",
            },
            {
                "id": "en_staff_cn_internal",
                "role": "en_staff",
                "question": "请解释中文内部手册中的变更发布节奏。",
                "expected": "denied",
            },
        ]
    }
