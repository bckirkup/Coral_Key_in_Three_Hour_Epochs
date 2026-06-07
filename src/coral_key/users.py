"""Domain user profiles: Patrol Commander, Stock Scientist, Policy Director."""

from __future__ import annotations

import numpy as np
from tattletots.models.user import User


def create_patrol_commander(n_priority_dims: int) -> User:
    """Patrol Commander: values IUU intercepts and dark-vessel detection.

    Attention budget: daily/weekly (relatively high per epoch).
    Priority: enforcement, vessel anomalies, AIS gaps.
    """
    priority = np.zeros(n_priority_dims)
    # First third: enforcement-related signals (AIS, SAR, dark vessels)
    enforcement_dims = n_priority_dims // 3
    priority[:enforcement_dims] = 1.0
    if np.linalg.norm(priority) > 0:
        priority = priority / np.linalg.norm(priority)

    return User(
        name="Patrol Commander",
        attention_budget=1.5,
        priority_vector=priority,
    )


def create_stock_scientist(n_priority_dims: int) -> User:
    """Stock Assessment Scientist: values CPUE trends and data quality.

    Attention budget: monthly/quarterly (lower per epoch).
    Priority: biomass estimates, CPUE, eDNA, oceanographic correlations.
    """
    priority = np.zeros(n_priority_dims)
    # Middle third: stock-related signals
    start = n_priority_dims // 3
    end = 2 * n_priority_dims // 3
    priority[start:end] = 1.0
    if np.linalg.norm(priority) > 0:
        priority = priority / np.linalg.norm(priority)

    return User(
        name="Stock Assessment Scientist",
        attention_budget=0.8,
        priority_vector=priority,
    )


def create_policy_director(n_priority_dims: int) -> User:
    """Policy Director: values decision-ready summaries, MPA effectiveness.

    Attention budget: seasonal/annual (lowest per epoch).
    Priority: quota compliance, MPA metrics, economic impact.
    """
    priority = np.zeros(n_priority_dims)
    # Last third: policy-related signals
    start = 2 * n_priority_dims // 3
    priority[start:] = 1.0
    if np.linalg.norm(priority) > 0:
        priority = priority / np.linalg.norm(priority)

    return User(
        name="Policy Director",
        attention_budget=0.5,
        priority_vector=priority,
    )


def create_all_users(n_priority_dims: int) -> list[User]:
    """Create the standard set of ReefWatch domain users."""
    return [
        create_patrol_commander(n_priority_dims),
        create_stock_scientist(n_priority_dims),
        create_policy_director(n_priority_dims),
    ]
