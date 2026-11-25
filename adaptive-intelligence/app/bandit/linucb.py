"""
Contextual LinUCB with Disjoint Linear Models adapter (Phase 4.6).
Maintains A^-1 covariance matrix and b payoff vector per arm.
Implements UCB scoring and online O(d^2) Sherman-Morrison updates.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple


def _identity_matrix(dim: int) -> List[List[float]]:
    return [[1.0 if i == j else 0.0 for j in range(dim)] for i in range(dim)]


def _zero_vector(dim: int) -> List[float]:
    return [0.0] * dim


def mat_vec_mul(mat: List[List[float]], vec: List[float]) -> List[float]:
    """Matrix-vector multiplication M * v."""
    return [sum(row[j] * vec[j] for j in range(len(vec))) for row in mat]


def dot_product(v1: List[float], v2: List[float]) -> float:
    """Dot product v1^T v2."""
    return sum(a * b for a, b in zip(v1, v2))


def outer_product(v1: List[float], v2: List[float]) -> List[List[float]]:
    """Outer product v1 v2^T."""
    return [[a * b for b in v2] for a in v1]


class LinUCBArm:
    """Disjoint LinUCB model for an individual arm."""

    def __init__(
        self,
        arm_id: str,
        dim: int = 12,
        alpha: float = 0.85,
        a_inv: Optional[List[List[float]]] = None,
        b: Optional[List[float]] = None,
        theta: Optional[List[float]] = None,
        pull_count: int = 0,
        cumulative_reward: float = 0.0,
    ):
        self.arm_id = arm_id
        self.dim = dim
        self.alpha = alpha
        self.pull_count = pull_count
        self.cumulative_reward = cumulative_reward

        self.a_inv = a_inv if a_inv is not None else _identity_matrix(dim)
        self.b = b if b is not None else _zero_vector(dim)
        if theta is not None:
            self.theta = theta
        else:
            self.theta = mat_vec_mul(self.a_inv, self.b)

    @classmethod
    def create_cold_start(cls, arm_id: str, dim: int = 12, alpha: float = 1.0) -> LinUCBArm:
        """Initializes unpulled arm with identity covariance and zero payoff."""
        return cls(arm_id=arm_id, dim=dim, alpha=alpha)

    def score(self, x: List[float]) -> Tuple[float, float, float]:
        """
        Computes (ucb_score, expected_payoff, exploration_bonus) for context x.
        p_t = x^T theta + alpha * sqrt(x^T A^-1 x).
        """
        expected_payoff = dot_product(x, self.theta)

        # Variance term: x^T A^-1 x
        a_inv_x = mat_vec_mul(self.a_inv, x)
        variance = dot_product(x, a_inv_x)
        std_dev = math.sqrt(max(0.0, variance))
        exploration_bonus = self.alpha * std_dev

        ucb_score = expected_payoff + exploration_bonus
        return ucb_score, expected_payoff, exploration_bonus

    def update(self, x: List[float], reward: float) -> None:
        """
        Performs O(d^2) Sherman-Morrison rank-1 update of A^-1 and b:
        A^-1 <- A^-1 - (A^-1 x x^T A^-1) / (1 + x^T A^-1 x)
        b <- b + r * x
        theta <- A^-1 * b
        """
        v = mat_vec_mul(self.a_inv, x)  # v = A^-1 x
        denom = 1.0 + dot_product(x, v)  # 1 + x^T A^-1 x

        if abs(denom) > 1e-12:
            v_v_t = outer_product(v, v)
            for i in range(self.dim):
                for j in range(self.dim):
                    self.a_inv[i][j] -= v_v_t[i][j] / denom

        for i in range(self.dim):
            self.b[i] += reward * x[i]

        for i in range(self.dim):
            if self.a_inv[i][i] < 1e-6:
                self.a_inv[i][i] = 1e-3

        self.theta = mat_vec_mul(self.a_inv, self.b)
        self.pull_count += 1
        self.cumulative_reward += reward
