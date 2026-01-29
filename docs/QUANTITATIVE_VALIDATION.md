# Quantitative Validation Guide

This guide covers rigorous statistical validation to ensure strategy robustness and avoid overfitting.

---

## Validation Framework

```
┌─────────────────────────────────────────────────────────────────┐
│                    Quantitative Validation                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Walk-Forward Analysis          2. Monte Carlo Validation     │
│     ├── WFE > 0.5                     ├── Permutation test       │
│     ├── Parameter stability           ├── p-value < 0.05         │
│     └── Min trades/window             └── Percentile ranking     │
│                                                                  │
│  3. Regime Detection               4. Bootstrap CIs              │
│     ├── Hidden Markov Model           ├── Stationary bootstrap   │
│     ├── Bull/Bear/Sideways            ├── 95% confidence         │
│     └── Regime-conditional perf       └── Sharpe CI > 0          │
│                                                                  │
│  5. Deflated Sharpe Ratio          6. Stationarity Tests         │
│     ├── Multiple testing adj          ├── ADF test               │
│     ├── DSR > 0.5                     ├── Hurst exponent         │
│     └── Honest strategy count         └── Half-life estimation   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1. Monte Carlo Validation

Monte Carlo permutation testing determines if strategy returns are statistically significant versus random chance.

### Concept

1. Run actual strategy, record Sharpe ratio
2. Permute entry signals randomly (N=1000 times)
3. Calculate Sharpe for each permutation
4. Compare actual Sharpe to permutation distribution
5. If actual Sharpe > 95th percentile → statistically significant

### Implementation

```python
import numpy as np
from scipy import stats

class MonteCarloValidator:
    """Monte Carlo permutation testing for strategy validation."""

    def __init__(
        self,
        n_permutations: int = 1000,
        significance_level: float = 0.05,
        random_seed: int = 42,
    ):
        self.n_permutations = n_permutations
        self.significance_level = significance_level
        self.rng = np.random.default_rng(random_seed)

    def validate(
        self,
        actual_returns: np.ndarray,
        signal_returns: np.ndarray,
    ) -> dict:
        """
        Validate strategy using permutation test.

        Args:
            actual_returns: Strategy returns
            signal_returns: Returns attributed to signals (not drift)

        Returns:
            Validation results with p-value and significance
        """
        actual_sharpe = self._calculate_sharpe(actual_returns)

        # Generate permutation distribution
        permutation_sharpes = []

        for _ in range(self.n_permutations):
            # Randomly permute signal timing
            permuted_signals = self.rng.permutation(signal_returns)
            permuted_sharpe = self._calculate_sharpe(permuted_signals)
            permutation_sharpes.append(permuted_sharpe)

        permutation_sharpes = np.array(permutation_sharpes)

        # Calculate p-value (proportion of permutations >= actual)
        p_value = np.mean(permutation_sharpes >= actual_sharpe)

        # Calculate percentile
        percentile = stats.percentileofscore(permutation_sharpes, actual_sharpe)

        return {
            "actual_sharpe": actual_sharpe,
            "p_value": p_value,
            "is_significant": p_value < self.significance_level,
            "percentile": percentile,
            "permutation_mean": np.mean(permutation_sharpes),
            "permutation_std": np.std(permutation_sharpes),
            "permutation_95th": np.percentile(permutation_sharpes, 95),
        }

    def _calculate_sharpe(self, returns: np.ndarray) -> float:
        """Calculate annualized Sharpe ratio."""
        if len(returns) == 0 or np.std(returns) == 0:
            return 0.0

        mean_return = np.mean(returns) * 252
        volatility = np.std(returns) * np.sqrt(252)

        return mean_return / volatility
```

### Usage

```python
validator = MonteCarloValidator(n_permutations=1000)

results = validator.validate(
    actual_returns=strategy_returns,
    signal_returns=signal_attributed_returns,
)

print(f"Actual Sharpe: {results['actual_sharpe']:.2f}")
print(f"P-value: {results['p_value']:.4f}")
print(f"Significant: {results['is_significant']}")
print(f"Percentile: {results['percentile']:.1f}%")
```

### Interpretation

| P-value | Interpretation |
|---------|----------------|
| < 0.01 | Highly significant - very unlikely to be random |
| 0.01-0.05 | Significant - unlikely to be random |
| 0.05-0.10 | Marginally significant - some evidence |
| > 0.10 | Not significant - could be random |

---

## 2. Regime Detection

Market regimes (bull, bear, sideways) affect strategy performance. Test strategy across regimes.

### Hidden Markov Model

```python
from hmmlearn import hmm
import numpy as np
import pandas as pd

class RegimeDetector:
    """Detect market regimes using Hidden Markov Model."""

    def __init__(
        self,
        n_regimes: int = 3,
        lookback_days: int = 252,
    ):
        self.n_regimes = n_regimes
        self.lookback_days = lookback_days
        self.model = None
        self.regime_names = {0: "bear", 1: "sideways", 2: "bull"}

    def fit(self, prices: pd.Series) -> "RegimeDetector":
        """Fit HMM to price data."""

        # Calculate features
        returns = prices.pct_change().dropna()
        volatility = returns.rolling(20).std()
        trend = (prices / prices.rolling(50).mean() - 1)

        features = np.column_stack([
            returns.values[-self.lookback_days:],
            volatility.values[-self.lookback_days:],
            trend.values[-self.lookback_days:],
        ])

        # Remove NaN rows
        features = features[~np.isnan(features).any(axis=1)]

        # Fit HMM
        self.model = hmm.GaussianHMM(
            n_components=self.n_regimes,
            covariance_type="full",
            n_iter=100,
            random_state=42,
        )
        self.model.fit(features)

        # Order regimes by mean return
        self._order_regimes(returns.values[-len(features):])

        return self

    def predict(self, prices: pd.Series) -> pd.Series:
        """Predict regime for each time point."""

        returns = prices.pct_change().dropna()
        volatility = returns.rolling(20).std()
        trend = (prices / prices.rolling(50).mean() - 1)

        features = np.column_stack([
            returns.values,
            volatility.values,
            trend.values,
        ])

        # Handle NaN
        valid_idx = ~np.isnan(features).any(axis=1)
        regimes = np.full(len(features), np.nan)
        regimes[valid_idx] = self.model.predict(features[valid_idx])

        return pd.Series(regimes, index=prices.index[1:], name="regime")

    def _order_regimes(self, returns: np.ndarray):
        """Order regimes so 0=bear, 1=sideways, 2=bull."""
        hidden_states = self.model.predict(returns.reshape(-1, 1))

        # Calculate mean return per regime
        regime_returns = {}
        for regime in range(self.n_regimes):
            mask = hidden_states == regime
            if mask.sum() > 0:
                regime_returns[regime] = returns[mask].mean()

        # Create mapping
        sorted_regimes = sorted(regime_returns.keys(), key=lambda x: regime_returns[x])
        self.regime_mapping = {old: new for new, old in enumerate(sorted_regimes)}

    def analyze_strategy_by_regime(
        self,
        strategy_returns: pd.Series,
        regimes: pd.Series,
    ) -> pd.DataFrame:
        """Analyze strategy performance by regime."""

        results = []
        for regime in range(self.n_regimes):
            mask = regimes == regime
            regime_returns = strategy_returns[mask]

            if len(regime_returns) > 0:
                sharpe = self._calculate_sharpe(regime_returns)
                results.append({
                    "regime": self.regime_names[regime],
                    "sharpe": sharpe,
                    "return": regime_returns.sum(),
                    "volatility": regime_returns.std() * np.sqrt(252),
                    "max_drawdown": self._max_drawdown(regime_returns),
                    "observations": len(regime_returns),
                    "pct_time": len(regime_returns) / len(strategy_returns),
                })

        return pd.DataFrame(results)
```

### Usage

```python
# Detect regimes
detector = RegimeDetector(n_regimes=3)
detector.fit(prices)
regimes = detector.predict(prices)

# Analyze strategy by regime
regime_analysis = detector.analyze_strategy_by_regime(strategy_returns, regimes)
print(regime_analysis)
```

### Expected Output

```
    regime  sharpe  return  volatility  max_drawdown  observations  pct_time
0     bear   -0.5   -0.15        0.35         -0.25           120      0.20
1  sideways    0.8    0.10        0.20         -0.08           300      0.50
2     bull    1.5    0.45        0.25         -0.12           180      0.30
```

---

## 3. Bootstrap Confidence Intervals

Bootstrap provides confidence intervals for performance metrics, quantifying uncertainty.

### Stationary Bootstrap

```python
from arch.bootstrap import StationaryBootstrap
import numpy as np
import pandas as pd

class BootstrapValidator:
    """Bootstrap confidence intervals for strategy metrics."""

    def __init__(
        self,
        n_samples: int = 10000,
        confidence_level: float = 0.95,
        block_length: str = "auto",
    ):
        self.n_samples = n_samples
        self.confidence_level = confidence_level
        self.block_length = block_length

    def calculate_cis(self, returns: pd.Series) -> dict:
        """
        Calculate confidence intervals for key metrics.

        Uses stationary bootstrap to handle time series autocorrelation.
        """

        # Determine optimal block length
        if self.block_length == "auto":
            block_length = self._optimal_block_length(returns)
        else:
            block_length = int(self.block_length)

        # Create bootstrap
        bs = StationaryBootstrap(block_length, returns.values)

        metrics = {}

        # Sharpe ratio
        sharpe_samples = self._bootstrap_metric(
            bs, returns.values, self._sharpe_ratio
        )
        metrics["sharpe"] = self._calculate_ci(sharpe_samples)

        # Maximum drawdown
        dd_samples = self._bootstrap_metric(
            bs, returns.values, self._max_drawdown
        )
        metrics["max_drawdown"] = self._calculate_ci(dd_samples)

        # Calmar ratio
        calmar_samples = self._bootstrap_metric(
            bs, returns.values, self._calmar_ratio
        )
        metrics["calmar"] = self._calculate_ci(calmar_samples)

        # Sortino ratio
        sortino_samples = self._bootstrap_metric(
            bs, returns.values, self._sortino_ratio
        )
        metrics["sortino"] = self._calculate_ci(sortino_samples)

        return metrics

    def _bootstrap_metric(self, bs, returns, metric_func) -> np.ndarray:
        """Generate bootstrap samples for a metric."""
        samples = []
        for data, in bs.bootstrap(self.n_samples):
            samples.append(metric_func(data))
        return np.array(samples)

    def _calculate_ci(self, samples: np.ndarray) -> dict:
        """Calculate confidence interval from samples."""
        alpha = 1 - self.confidence_level
        lower = np.percentile(samples, alpha / 2 * 100)
        upper = np.percentile(samples, (1 - alpha / 2) * 100)

        return {
            "estimate": np.mean(samples),
            "std": np.std(samples),
            "ci_lower": lower,
            "ci_upper": upper,
            "confidence": self.confidence_level,
        }

    def _optimal_block_length(self, returns: pd.Series) -> int:
        """Estimate optimal block length using Politis-White method."""
        # Simplified: use sqrt(n)
        return max(1, int(np.sqrt(len(returns))))

    def _sharpe_ratio(self, returns: np.ndarray) -> float:
        if np.std(returns) == 0:
            return 0.0
        return np.mean(returns) * np.sqrt(252) / (np.std(returns) * np.sqrt(252))

    def _max_drawdown(self, returns: np.ndarray) -> float:
        cumulative = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = cumulative / running_max - 1
        return np.min(drawdowns)

    def _calmar_ratio(self, returns: np.ndarray) -> float:
        annual_return = (np.prod(1 + returns) ** (252 / len(returns))) - 1
        max_dd = abs(self._max_drawdown(returns))
        return annual_return / max_dd if max_dd > 0 else 0

    def _sortino_ratio(self, returns: np.ndarray) -> float:
        downside_returns = returns[returns < 0]
        if len(downside_returns) == 0:
            return float('inf')
        downside_std = np.std(downside_returns) * np.sqrt(252)
        annual_return = np.mean(returns) * 252
        return annual_return / downside_std if downside_std > 0 else 0
```

### Usage

```python
validator = BootstrapValidator(n_samples=10000, confidence_level=0.95)

cis = validator.calculate_cis(strategy_returns)

print(f"Sharpe: {cis['sharpe']['estimate']:.2f} "
      f"[{cis['sharpe']['ci_lower']:.2f}, {cis['sharpe']['ci_upper']:.2f}]")

# Check if Sharpe CI includes zero
if cis['sharpe']['ci_lower'] > 0:
    print("✓ Sharpe significantly greater than zero")
else:
    print("✗ Sharpe CI includes zero - not significant")
```

### Interpretation

| Condition | Interpretation |
|-----------|----------------|
| Sharpe CI lower > 0 | Strategy has positive risk-adjusted returns |
| Sharpe CI includes 0 | Cannot confirm strategy beats risk-free rate |
| CI width small | Metric is precisely estimated |
| CI width large | High uncertainty, need more data |

---

## 4. Deflated Sharpe Ratio

The Deflated Sharpe Ratio (DSR) adjusts for multiple testing bias when selecting strategies.

### The Problem

If you test 100 strategy variants and pick the best one, you're likely to find one that looks good by chance.

### Bailey-Lopez de Prado Formula

```python
from scipy.stats import norm
import numpy as np

def deflated_sharpe_ratio(
    sharpe_observed: float,
    n_strategies_tested: int,
    variance_of_sharpe: float,
    skewness: float = 0,
    kurtosis: float = 3,
    n_observations: int = 252,
) -> float:
    """
    Calculate Deflated Sharpe Ratio.

    Accounts for multiple testing bias in strategy selection.

    Reference: Bailey & López de Prado (2014)
    "The Deflated Sharpe Ratio: Correcting for Selection Bias"

    Args:
        sharpe_observed: The reported Sharpe ratio
        n_strategies_tested: Number of strategy variants tested (be honest!)
        variance_of_sharpe: Variance in Sharpe across strategies
        skewness: Return distribution skewness
        kurtosis: Return distribution kurtosis
        n_observations: Number of return observations

    Returns:
        Deflated Sharpe ratio (probability strategy is truly skillful)
    """

    # Standard deviation of Sharpe
    std_sharpe = np.sqrt(variance_of_sharpe)

    # Expected maximum Sharpe under null hypothesis
    e_max_sharpe = std_sharpe * (
        (1 - np.euler_gamma) * norm.ppf(1 - 1 / n_strategies_tested) +
        np.euler_gamma * norm.ppf(1 - 1 / (n_strategies_tested * np.e))
    )

    # Standard error of Sharpe estimate
    sharpe_se = np.sqrt(
        (1 - skewness * sharpe_observed +
         (kurtosis - 1) / 4 * sharpe_observed ** 2) / n_observations
    )

    # Deflated Sharpe Ratio
    dsr = norm.cdf(
        (sharpe_observed - e_max_sharpe) / sharpe_se
    )

    return dsr
```

### Practical Usage

```python
# Be honest about how many strategies you tested!
n_strategies = 50  # Tested 50 parameter combinations

# Calculate variance of Sharpe across tested strategies
all_sharpes = [run_backtest(params)["sharpe"] for params in param_grid]
variance_of_sharpe = np.var(all_sharpes)

# Get the "best" strategy
best_sharpe = max(all_sharpes)

# Calculate DSR
dsr = deflated_sharpe_ratio(
    sharpe_observed=best_sharpe,
    n_strategies_tested=n_strategies,
    variance_of_sharpe=variance_of_sharpe,
    n_observations=252 * 2,  # 2 years of daily returns
)

print(f"Observed Sharpe: {best_sharpe:.2f}")
print(f"Deflated Sharpe Ratio: {dsr:.2%}")
print(f"Probability of true skill: {dsr:.1%}")
```

### Interpretation

| DSR | Interpretation |
|-----|----------------|
| > 0.95 | Very likely to be skillful |
| 0.80-0.95 | Probably skillful |
| 0.50-0.80 | Uncertain - more testing needed |
| < 0.50 | Likely data snooping / overfit |

---

## 5. Stationarity Tests (for Stat Arb)

For statistical arbitrage, test that spreads are stationary (mean-reverting).

### ADF Test

```python
from statsmodels.tsa.stattools import adfuller

def test_stationarity(spread: pd.Series, significance: float = 0.05) -> dict:
    """
    Test spread stationarity using Augmented Dickey-Fuller.

    Args:
        spread: Spread time series
        significance: Significance level (default 0.05)

    Returns:
        Test results with stationarity determination
    """
    result = adfuller(spread.dropna())

    return {
        "adf_statistic": result[0],
        "p_value": result[1],
        "critical_values": result[4],
        "is_stationary": result[1] < significance,
        "confidence": 1 - result[1],
    }
```

### Hurst Exponent

```python
def hurst_exponent(series: np.ndarray) -> float:
    """
    Calculate Hurst exponent to test for mean reversion.

    H < 0.5: Mean-reverting (good for stat arb)
    H = 0.5: Random walk (no edge)
    H > 0.5: Trending (not suitable for stat arb)
    """
    n = len(series)
    max_lag = min(100, n // 4)

    lags = range(2, max_lag)
    tau = []
    rs = []

    for lag in lags:
        # Split into chunks of size lag
        chunks = [series[i:i+lag] for i in range(0, n - lag, lag)]

        for chunk in chunks:
            if len(chunk) < lag:
                continue

            mean = np.mean(chunk)
            std = np.std(chunk)

            if std == 0:
                continue

            # Calculate R/S statistic
            cumsum = np.cumsum(chunk - mean)
            r = np.max(cumsum) - np.min(cumsum)
            s = std

            rs.append(r / s)
            tau.append(lag)

    if len(tau) == 0:
        return 0.5

    # Fit log-log regression
    log_tau = np.log(tau)
    log_rs = np.log(rs)

    coeffs = np.polyfit(log_tau, log_rs, 1)
    hurst = coeffs[0]

    return hurst
```

### Half-Life Estimation

```python
from statsmodels.regression.linear_model import OLS

def estimate_half_life(spread: pd.Series) -> dict:
    """
    Estimate mean-reversion half-life using Ornstein-Uhlenbeck process.

    Half-life = ln(2) / theta

    Where theta is the mean-reversion speed from:
    dS = theta * (mu - S) * dt + sigma * dW
    """
    spread = spread.dropna()

    # Lag spread
    spread_lag = spread.shift(1).dropna()
    spread_diff = spread.diff().dropna()

    # Align
    spread_lag = spread_lag.iloc[:-1]
    spread_diff = spread_diff.iloc[1:]

    # Regress: spread_diff = alpha + beta * spread_lag
    X = spread_lag.values.reshape(-1, 1)
    y = spread_diff.values

    model = OLS(y, X)
    result = model.fit()

    theta = -result.params[0]

    if theta <= 0:
        return {
            "theta": theta,
            "half_life_days": float('inf'),
            "is_mean_reverting": False,
            "message": "Spread is not mean-reverting (theta <= 0)",
        }

    half_life = np.log(2) / theta

    return {
        "theta": theta,
        "half_life_days": half_life,
        "is_mean_reverting": True,
        "r_squared": result.rsquared,
    }
```

### Usage

```python
# Test spread stationarity
stationarity = test_stationarity(spread)
print(f"ADF p-value: {stationarity['p_value']:.4f}")
print(f"Stationary: {stationarity['is_stationary']}")

# Calculate Hurst exponent
H = hurst_exponent(spread.values)
print(f"Hurst exponent: {H:.2f}")
if H < 0.5:
    print("✓ Mean-reverting")
else:
    print("✗ Not mean-reverting")

# Estimate half-life
hl = estimate_half_life(spread)
print(f"Half-life: {hl['half_life_days']:.1f} days")
```

---

## Complete Validation Pipeline

### Run All Validations

```python
def full_quantitative_validation(
    strategy_returns: pd.Series,
    prices: pd.Series,
    signals: pd.Series,
    n_strategies_tested: int = 1,
) -> dict:
    """
    Run complete quantitative validation suite.

    Returns comprehensive validation report.
    """
    results = {}

    # 1. Monte Carlo
    mc_validator = MonteCarloValidator(n_permutations=1000)
    results["monte_carlo"] = mc_validator.validate(
        strategy_returns.values,
        signals.values,
    )

    # 2. Regime detection
    regime_detector = RegimeDetector(n_regimes=3)
    regime_detector.fit(prices)
    regimes = regime_detector.predict(prices)
    results["regime_analysis"] = regime_detector.analyze_strategy_by_regime(
        strategy_returns, regimes
    ).to_dict(orient="records")

    # 3. Bootstrap CIs
    bootstrap_validator = BootstrapValidator(n_samples=10000)
    results["confidence_intervals"] = bootstrap_validator.calculate_cis(
        strategy_returns
    )

    # 4. Deflated Sharpe
    sharpe = strategy_returns.mean() / strategy_returns.std() * np.sqrt(252)
    dsr = deflated_sharpe_ratio(
        sharpe_observed=sharpe,
        n_strategies_tested=n_strategies_tested,
        variance_of_sharpe=0.5,  # Typical variance
        n_observations=len(strategy_returns),
    )
    results["deflated_sharpe"] = {
        "raw_sharpe": sharpe,
        "dsr": dsr,
        "n_strategies_tested": n_strategies_tested,
    }

    # 5. Overall assessment
    results["validation_passed"] = all([
        results["monte_carlo"]["is_significant"],
        results["confidence_intervals"]["sharpe"]["ci_lower"] > 0,
        dsr > 0.5,
    ])

    return results
```

### Usage

```bash
# Via Makefile
make backtest-montecarlo RESULTS=results/backtest.json
```

```python
# Programmatically
validation = full_quantitative_validation(
    strategy_returns=returns,
    prices=btc_prices,
    signals=signal_returns,
    n_strategies_tested=50,  # Be honest!
)

print("=" * 50)
print("QUANTITATIVE VALIDATION REPORT")
print("=" * 50)

# Monte Carlo
mc = validation["monte_carlo"]
print(f"\n1. Monte Carlo Permutation Test")
print(f"   Sharpe: {mc['actual_sharpe']:.2f}")
print(f"   P-value: {mc['p_value']:.4f}")
print(f"   Significant: {'✓' if mc['is_significant'] else '✗'}")

# Bootstrap
ci = validation["confidence_intervals"]["sharpe"]
print(f"\n2. Bootstrap Confidence Intervals")
print(f"   Sharpe: {ci['estimate']:.2f} [{ci['ci_lower']:.2f}, {ci['ci_upper']:.2f}]")
print(f"   CI > 0: {'✓' if ci['ci_lower'] > 0 else '✗'}")

# Deflated Sharpe
dsr = validation["deflated_sharpe"]
print(f"\n3. Deflated Sharpe Ratio")
print(f"   Raw Sharpe: {dsr['raw_sharpe']:.2f}")
print(f"   DSR: {dsr['dsr']:.2%}")
print(f"   Strategies tested: {dsr['n_strategies_tested']}")
print(f"   Likely skillful: {'✓' if dsr['dsr'] > 0.5 else '✗'}")

# Regimes
print(f"\n4. Regime Analysis")
for regime in validation["regime_analysis"]:
    print(f"   {regime['regime']}: Sharpe={regime['sharpe']:.2f}, "
          f"Time={regime['pct_time']:.1%}")

# Overall
print(f"\n{'=' * 50}")
print(f"OVERALL: {'PASSED ✓' if validation['validation_passed'] else 'FAILED ✗'}")
print(f"{'=' * 50}")
```

---

## Validation Checklist

Before deploying to production:

- [ ] Walk-forward WFE > 0.5
- [ ] Monte Carlo p-value < 0.05
- [ ] Sharpe 95% CI lower bound > 0
- [ ] Deflated Sharpe Ratio > 0.5
- [ ] Performs in all market regimes (or regime-aware)
- [ ] Half-life < 30 days (for stat arb)
- [ ] Hurst exponent < 0.5 (for stat arb)
- [ ] Minimum 30 trades per walk-forward window
- [ ] Parameter stability across windows < 0.3

---

## Next Steps

1. **Deploy carefully**: [DEPLOYMENT.md](DEPLOYMENT.md)
