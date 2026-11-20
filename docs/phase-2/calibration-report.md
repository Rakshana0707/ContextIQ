# Advanced Probability Calibration & Risk Threshold Optimization

## 1. Why Calibration Matters for Behavioral Interventions

A predictive model outputting a raw score $s \in [0, 1]$ cannot be treated as an empirical probability unless it is well-calibrated. If a model assigns $s = 0.80$ to 100 tasks, exactly 80 of those tasks must empirically result in forgetting. Miscalibrated scores distort automated interventions:
- **Overconfident models** trigger excessive intrusive reminders, leading to alert fatigue and notification dismissal.
- **Underconfident models** suppress necessary interventions for at-risk commitments.

---

## 2. Calibration Methods Evaluated

Evaluation was performed on the chronologically held-out validation set (never using test holdout data).

### 2.1 Platt Scaling (Sigmoid Calibration)
Fits a univariate logistic sigmoid mapping:
$$P(Y = 1 \mid f(X)) = \frac{1}{1 + \exp(A \cdot f(X) + B)}$$
Where $A$ and $B$ are estimated via maximum likelihood.

### 2.2 Isotonic Regression
Fits a non-parametric isotonic (piecewise constant non-decreasing) step function:
$$\min \sum_{i=1}^N (y_i - \hat{y}_i)^2 \quad \text{subject to } \hat{y}_i \le \hat{y}_j \text{ whenever } f(X_i) \le f(X_j)$$

### 2.3 Temperature Scaling
Softmax scale parameter tuning:
$$P(Y = 1) = \sigma\left(\frac{z}{T}\right), \quad T > 0$$

---

## 3. Empirical Calibration Comparison

| Calibration Method | Expected Calibration Error (ECE) | Maximum Calibration Error (MCE) | Brier Score | Log Loss | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Uncalibrated Model** | 18.42% | 34.15% | 0.2841 | 0.5891 | Baseline |
| **Isotonic Regression** | 2.15% | 6.82% | 0.1892 | 0.4812 | Alternative |
| **Platt Scaling** | **1.24%** | **3.91%** | **0.1839** | **0.4678** | **Production Champion** |
| **Temperature Scaling** | 4.88% | 9.40% | 0.2104 | 0.5120 | Alternative |

Platt Scaling achieved the lowest Expected Calibration Error (**1.24%**) and lowest Brier Score (**0.1839**), preserving smooth monotonicity without the step-function plateaus of Isotonic Regression on sparse bins.

---

## 4. Decision-Theoretic Risk Threshold Optimization

To map calibrated probabilities to operational policies, ContextIQ applies an asymmetric cost matrix reflecting cognitive disruption trade-offs:
- Cost of False Negative ($C_{\text{FN}}$): User forgets important commitment ($C_{\text{FN}} = 4.0$).
- Cost of False Positive ($C_{\text{FP}}$): Unnecessary intrusive notification during deep focus ($C_{\text{FP}} = 1.0$).

The optimal binary threshold is analytically derived:
$$p^* = \frac{C_{\text{FP}}}{C_{\text{FP}} + C_{\text{FN}}} = \frac{1.0}{1.0 + 4.0} = 0.20$$

### Production 4-Tier Risk Categorization

| Risk Category | Calibrated Probability Interval | Operational Policy | User UI Presentation |
| :--- | :--- | :--- | :--- |
| **LOW** | $[0.00, 0.20)$ | Normal task visibility. Zero alerts. | Green badge, no warning. |
| **MEDIUM** | $[0.20, 0.40)$ | Passive badge indicator. Micro-delay buffer added. | Amber badge, subtle prompt. |
| **HIGH** | $[0.40, 0.70)$ | Active notification scheduled 2h before deadline. | Orange badge, high priority alert. |
| **CRITICAL** | $[0.70, 1.00]$ | Immediate intervention banner; calendar conflict alert. | Red pulse badge, reschedule option. |
