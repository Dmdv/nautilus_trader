import numpy as np
import pandas as pd
from scipy.stats import norm
from hmmlearn import hmm
from arch.bootstrap import StationaryBootstrap
from statsmodels.tsa.stattools import adfuller

class RegimeDetector:
    """Detect market regimes using Hidden Markov Model."""

    def __init__(self, n_regimes: int = 3, lookback_days: int = 252):
        self.n_regimes = n_regimes
        self.lookback_days = lookback_days
        self.model = None
        self.regime_names = {0: "bear", 1: "sideways", 2: "bull"}

    def fit(self, prices: pd.Series) -> "RegimeDetector":
        returns = prices.pct_change().dropna()
        volatility = returns.rolling(20).std()
        trend = (prices / prices.rolling(50).mean() - 1)

        features = np.column_stack([
            returns.values[-self.lookback_days:],
            volatility.values[-self.lookback_days:],
            trend.values[-self.lookback_days:],
        ])
        features = features[~np.isnan(features).any(axis=1)]

        self.model = hmm.GaussianHMM(
            n_components=self.n_regimes,
            covariance_type="full",
            n_iter=100,
            random_state=42,
        )
        self.model.fit(features)
        return self

    def predict(self, prices: pd.Series) -> pd.Series:
        returns = prices.pct_change().dropna()
        volatility = returns.rolling(20).std()
        trend = (prices / prices.rolling(50).mean() - 1)

        features = np.column_stack([
            returns.values,
            volatility.values,
            trend.values,
        ])
        
        valid_idx = ~np.isnan(features).any(axis=1)
        regimes = np.full(len(features), np.nan)
        regimes[valid_idx] = self.model.predict(features[valid_idx])

        return pd.Series(regimes, index=prices.index[1:], name="regime")

class BootstrapValidator:
    """Bootstrap confidence intervals for strategy metrics."""

    def __init__(self, n_samples: int = 10000, confidence_level: float = 0.95):
        self.n_samples = n_samples
        self.confidence_level = confidence_level

    def calculate_cis(self, returns: pd.Series) -> dict:
        block_length = max(1, int(np.sqrt(len(returns))))
        bs = StationaryBootstrap(block_length, returns.values)
        
        sharpe_samples = []
        for data, in bs.bootstrap(self.n_samples):
            if np.std(data) == 0:
                sharpe_samples.append(0.0)
            else:
                sharpe_samples.append(np.mean(data) * np.sqrt(252) / np.std(data))
        
        sharpe_samples = np.array(sharpe_samples)
        alpha = 1 - self.confidence_level
        lower = np.percentile(sharpe_samples, alpha / 2 * 100)
        upper = np.percentile(sharpe_samples, (1 - alpha / 2) * 100)

        return {
            "sharpe": {
                "estimate": np.mean(sharpe_samples),
                "ci_lower": lower,
                "ci_upper": upper
            }
        }

def deflated_sharpe_ratio(sharpe_observed: float, n_strategies_tested: int, variance_of_sharpe: float, n_observations: int) -> float:
    """Calculate Deflated Sharpe Ratio."""
    std_sharpe = np.sqrt(variance_of_sharpe)
    e_max_sharpe = std_sharpe * (
        (1 - np.euler_gamma) * norm.ppf(1 - 1 / n_strategies_tested) +
        np.euler_gamma * norm.ppf(1 - 1 / (n_strategies_tested * np.e))
    )
    sharpe_se = 1 / np.sqrt(n_observations) # Simplified SE
    dsr = norm.cdf((sharpe_observed - e_max_sharpe) / sharpe_se)
    return dsr

def test_stationarity(spread: pd.Series, significance: float = 0.05) -> dict:
    """Test spread stationarity using ADF."""
    result = adfuller(spread.dropna())
    return {
        "adf_statistic": result[0],
        "p_value": result[1],
        "is_stationary": result[1] < significance
    }
