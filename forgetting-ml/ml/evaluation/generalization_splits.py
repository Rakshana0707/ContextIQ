"""
generalization_splits.py

Group-aware and spatiotemporal splitting strategies for evaluating user-level
generalization vs individual memorization (Phase 2.6).

Scenarios:
- Scenario A (Temporal Holdout): Within-user chronological split.
- Scenario B (User-Grouped Holdout): Completely disjoint users across all time.
- Scenario C (User-and-Time Holdout): Unseen users evaluated exclusively on future dates.
- Scenario D (Personalization Trajectory): Simulates progressive history accumulation.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple
import numpy as np
import pandas as pd

from ml.training.config import SEED


def scenario_a_temporal_split(
    df: pd.DataFrame,
    date_col: str = "date",
    train_frac: float = 0.70,
    val_frac: float = 0.15,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Scenario A: Standard temporal holdout across all users.
    Evaluates: Within-user temporal generalization.
    """
    dates = sorted(df[date_col].unique())
    n_dates = len(dates)
    train_end = int(n_dates * train_frac)
    val_end = int(n_dates * (train_frac + val_frac))

    train_dates = set(dates[:train_end])
    val_dates = set(dates[train_end:val_end])
    test_dates = set(dates[val_end:])

    train_df = df[df[date_col].isin(train_dates)].reset_index(drop=True)
    val_df = df[df[date_col].isin(val_dates)].reset_index(drop=True)
    test_df = df[df[date_col].isin(test_dates)].reset_index(drop=True)

    return train_df, val_df, test_df


def scenario_b_user_split(
    df: pd.DataFrame,
    user_col: str = "user_id",
    test_user_frac: float = 0.20,
    val_user_frac: float = 0.10,
    seed: int = SEED,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Scenario B: User-Grouped Holdout.
    Evaluates: Cross-user generalization across all time.
    Guarantees: Strict user disjointness: Train Users ∩ Test Users = ∅.
    """
    users = sorted(df[user_col].unique())
    rng = np.random.RandomState(seed)
    shuffled_users = rng.permutation(users)

    n_users = len(shuffled_users)
    n_test = max(1, int(n_users * test_user_frac))
    n_val = max(1, int(n_users * val_user_frac))

    test_users = set(shuffled_users[:n_test])
    val_users = set(shuffled_users[n_test:n_test + n_val])
    train_users = set(shuffled_users[n_test + n_val:])

    # Assert strict disjointness
    assert train_users.isdisjoint(test_users), "Scenario B violation: Train/Test user overlap!"
    assert train_users.isdisjoint(val_users), "Scenario B violation: Train/Val user overlap!"
    assert val_users.isdisjoint(test_users), "Scenario B violation: Val/Test user overlap!"

    train_df = df[df[user_col].isin(train_users)].reset_index(drop=True)
    val_df = df[df[user_col].isin(val_users)].reset_index(drop=True)
    test_df = df[df[user_col].isin(test_users)].reset_index(drop=True)

    return train_df, val_df, test_df


def scenario_c_user_and_time_split(
    df: pd.DataFrame,
    user_col: str = "user_id",
    date_col: str = "date",
    test_user_frac: float = 0.20,
    train_date_frac: float = 0.70,
    seed: int = SEED,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Scenario C: User-and-Time Holdout (Spatiotemporal).
    Evaluates: Generalization to completely unseen users in future time periods.
    Train: 80% users on early 70% dates.
    Val: 80% users on next 15% dates.
    Test: 20% unseen users strictly on the final 30% dates.
    """
    # 1. Partition users
    users = sorted(df[user_col].unique())
    rng = np.random.RandomState(seed)
    shuffled_users = rng.permutation(users)
    n_test = max(1, int(len(users) * test_user_frac))

    unseen_test_users = set(shuffled_users[:n_test])
    training_users = set(shuffled_users[n_test:])

    # 2. Partition dates
    dates = sorted(df[date_col].unique())
    n_dates = len(dates)
    train_date_end = int(n_dates * train_date_frac)
    val_date_end = int(n_dates * (train_date_frac + 0.15))

    train_dates = set(dates[:train_date_end])
    val_dates = set(dates[train_date_end:val_date_end])
    test_dates = set(dates[train_date_end:])  # Future dates only

    # 3. Form subsets
    train_df = df[df[user_col].isin(training_users) & df[date_col].isin(train_dates)].reset_index(drop=True)
    val_df = df[df[user_col].isin(training_users) & df[date_col].isin(val_dates)].reset_index(drop=True)
    test_df = df[df[user_col].isin(unseen_test_users) & df[date_col].isin(test_dates)].reset_index(drop=True)

    # Guarantees
    assert set(train_df[user_col]).isdisjoint(set(test_df[user_col])), "Scenario C user leakage!"
    assert max(train_df[date_col]) < min(test_df[date_col]), "Scenario C temporal leakage!"

    return train_df, val_df, test_df


def build_scenario_d_learning_curve(
    test_df: pd.DataFrame,
    sample_sizes: Optional[List[int]] = None,
    user_col: str = "user_id",
    date_col: str = "date",
    seed: int = SEED,
) -> Dict[int, pd.DataFrame]:
    """
    Scenario D: Simulates incremental personalization learning curves.
    For each test user, partitions their tasks chronologically.
    Evaluates model performance on their remaining tasks after seeing N initial tasks:
    N in [0, 5, 10, 25, 50].
    """
    if sample_sizes is None:
        sample_sizes = [0, 5, 10, 25, 50]

    curve_data: Dict[int, List[pd.DataFrame]] = {n: [] for n in sample_sizes}

    for uid, user_tasks in test_df.groupby(user_col):
        sorted_tasks = user_tasks.sort_values(date_col).reset_index(drop=True)
        total_tasks = len(sorted_tasks)

        for n in sample_sizes:
            if total_tasks > n + 5:
                # User has enough tasks to evaluate the post-N trajectory
                remaining_eval = sorted_tasks.iloc[n:].copy()
                remaining_eval["simulated_history_size"] = n
                curve_data[n].append(remaining_eval)

    return {n: pd.concat(dfs).reset_index(drop=True) for n, dfs in curve_data.items() if dfs}
