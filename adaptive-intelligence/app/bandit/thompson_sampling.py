"""
Contextual Linear Thompson Sampling adapter (Phase 4.6).
Maintains Bayesian linear posterior over theta for each arm.
Samples contextual payoff from posterior distribution:
p_t ~ N(x^T theta_a, v^2 * (x^T A_a^-1 x)).
"""
from __future__ import annotations

import math
import random
from typing import Dict, List, Optional, Tuple

from app.bandit.linucb import (
    _identity_matrix,
    _zero_vector,
    dot_product,
    mat_vec_mul,
    outer_product,
)


class LinearThompsonSamplingArm:
    """Disjoint Contextual Linear Thompson Sampling model for an individual arm."""

    def __init__(
        self,
        arm_id: str,
        dim: int = 12,
        v_scale: float = 0.5,
        a_inv: Optional[List[List[float]]] = None,
        b: Optional[List[float]] = None,
        theta: Optional[List[float]] = None,
        pull_count: int = 0,
        cumulative_reward: float = 0.0,
    ):
        self.arm_id = arm_id
        self.dim = dim
        self.v_scale = v_scale
        self.pull_count = pull_count
        self.cumulative_reward = cumulative_reward

        self.a_inv = a_inv if a_inv is not None else _identity_matrix(dim)
        self.b = b if b is not None else _zero_vector(dim)
        if theta is not None:
            self.theta = theta
        else:
            self.theta = mat_vec_mul(self.a_inv, self.b)

    @classmethod
    def create_cold_start(cls, arm_id: str, dim: int = 12, v_scale: float = 0.5) -> LinearThompsonSamplingArm:
        """Initializes unpulled arm with identity covariance and zero payoff."""
        return cls(arm_id=arm_id, dim=dim, v_scale=v_scale)

    def sample_score(self, x: List[float], seed: Optional[int] = None) -> Tuple[float, float, float]:
        """
        Samples simulated payoff from posterior Gaussian distribution:
        mean = x^T theta
        variance = v^2 * (x^T A^-1 x)
        Returns (sampled_score, expected_payoff, sample_noise).
        """
        if seed is not None:
            rng = random.Random(seed)
        else:
            rng = random

        expected_payoff = dot_product(x, self.theta)
        a_inv_x = mat_vec_mul(self.a_inv, x)
        variance = dot_product(x, a_inv_x)
        std_dev = self.v_scale * math.sqrt(max(0.0, variance))

        sample_noise = rng.gauss(0.0, std_dev)
        sampled_score = expected_payoff + sample_noise

        return sampled_score, expected_payoff, sample_noise

    def update(self, x: List[float], reward: float) -> None:
        """
        Sherman-Morrison update of covariance inverse matrix and b vector.
        """
        v = mat_vec_mul(self.a_inv, x)
        denom = 1.0 + dot_product(x, v)

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
