CATEGORY_WEIGHTS = {
    "security": 20,
    "reliability": 20,
    "maintainability": 20,
    "testing": 15,
    "operational_readiness": 15,
    "developer_experience": 10,
}

MAX_PENALTY_PER_FINDING = 20

# Index = nth finding in same category (0-based). Diminishing returns.
DIMINISHING_RETURNS = [1.0, 0.5, 0.25, 0.1]
