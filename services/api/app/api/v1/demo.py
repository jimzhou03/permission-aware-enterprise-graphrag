from fastapi import APIRouter


router = APIRouter(prefix="/demo", tags=["demo"])


@router.get("/overreach-cases")
def list_overreach_cases() -> dict:
    return {
        "cases": [
            {
                "id": "visitor_hr_internal",
                "role": "visitor",
                "question": "请提供人事部考勤制度细则。",
                "expected": "denied",
            },
            {
                "id": "sales_staff_tech_internal",
                "role": "sales_staff",
                "question": "Explain the SDK deployment troubleshooting checklist.",
                "expected": "denied",
            },
            {
                "id": "tech_staff_sales_internal",
                "role": "tech_staff",
                "question": "请解释销售部的渠道返点政策。",
                "expected": "denied",
            },
        ]
    }
