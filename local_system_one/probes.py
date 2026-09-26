"""Small non-sensitive startup probe set."""

from __future__ import annotations

PROBES = [
    (
        {
            "from": "user@example.com",
            "subject": "Duplicate charge on invoice #4411",
            "body": (
                "We were billed twice for March. Please refund the duplicate today "
                "or we will cancel our plan."
            ),
        },
        {
            "type": "choice",
            "instructions": "Which department should handle this email?",
            "criteria": {
                "billing": "invoices, payments, refunds",
                "technical": "bugs, outages, system errors",
                "sales": "pricing, new contracts",
                "other": "everything else",
            },
        },
    ),
    (
        {
            "service": "production checkout",
            "status": "degraded",
            "errors": "payments intermittently fail",
            "customers_affected": "multiple",
        },
        {
            "type": "score",
            "instructions": "How urgent is this incident?",
            "criteria": ["low", "medium", "high", "critical"],
        },
    ),
    (
        {
            "task": "summarize a private local note",
            "requires_current_information": False,
        },
        {
            "type": "noul",
            "instructions": "Does this task require current information from the web?",
        },
    ),
]