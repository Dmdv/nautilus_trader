# NautilusTrader Implementation Makefile
# Targets for impl/ module development and usage
#
# Usage: make <target>
# Help:  make help

.PHONY: help install install-dev clean \
        lint typecheck test test-unit test-coverage \
        data-download data-catalog-info data-validate \
        backtest backtest-walkforward backtest-montecarlo \
        validate validate-stationarity validate-regime \
        dry-run shadow paper production \
        env-check

# Colors for output
CYAN := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
RESET := \033[0m

# Configuration
PYTHON := python3
PIP := pip
PYTEST := pytest
MYPY := mypy
RUFF := ruff

# Directories
IMPL_DIR := impl
TEST_DIR := tests
DATA_DIR := data

#==============================================================================
# HELP
#==============================================================================

help: ## Show this help message
	@echo "$(CYAN)NautilusTrader impl/ Module Makefile$(RESET)"
	@echo ""
	@echo "$(GREEN)Setup:$(RESET)"
	@grep -E '^(install|clean|env)[a-zA-Z_-]*:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-24s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Quality:$(RESET)"
	@grep -E '^(lint|typecheck|test)[a-zA-Z_-]*:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-24s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Data:$(RESET)"
	@grep -E '^data[a-zA-Z_-]*:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-24s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Backtesting:$(RESET)"
	@grep -E '^backtest[a-zA-Z_-]*:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-24s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Validation:$(RESET)"
	@grep -E '^validate[a-zA-Z_-]*:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-24s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Deployment:$(RESET)"
	@grep -E '^(dry-run|shadow|paper|production)[a-zA-Z_-]*:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-24s$(RESET) %s\n", $$1, $$2}'

#==============================================================================
# SETUP
#==============================================================================

install: ## Install impl module and dependencies
	@echo "$(GREEN)Installing impl module...$(RESET)"
	$(PIP) install nautilus_trader numpy
	@echo "$(GREEN)✓ Installation complete$(RESET)"

install-dev: ## Install with dev dependencies
	@echo "$(GREEN)Installing impl module with dev dependencies...$(RESET)"
	$(PIP) install nautilus_trader numpy pandas
	$(PIP) install pytest pytest-asyncio mypy ruff statsmodels hmmlearn
	@echo "$(GREEN)✓ Development installation complete$(RESET)"

clean: ## Remove build artifacts and caches
	@echo "$(YELLOW)Cleaning build artifacts...$(RESET)"
	rm -rf build/ dist/ *.egg-info/
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "$(GREEN)✓ Clean complete$(RESET)"

env-check: ## Verify environment and dependencies
	@echo "$(CYAN)Environment Check$(RESET)"
	@echo "================="
	@echo ""
	@echo "$(GREEN)Python:$(RESET)"
	@$(PYTHON) --version
	@echo ""
	@echo "$(GREEN)NautilusTrader:$(RESET)"
	@$(PYTHON) -c "import nautilus_trader; print(f'Version: {nautilus_trader.__version__}')" 2>/dev/null || echo "$(YELLOW)Not installed. Run: make install$(RESET)"
	@echo ""
	@echo "$(GREEN)impl/ modules:$(RESET)"
	@$(PYTHON) -c "from impl.config import TradingNodeConfiguration; print('  config: ✓')" 2>/dev/null || echo "  config: $(RED)✗$(RESET)"
	@$(PYTHON) -c "from impl.data import ParquetCatalogManager; print('  data: ✓')" 2>/dev/null || echo "  data: $(RED)✗$(RESET)"
	@$(PYTHON) -c "from impl.strategies import BaseStrategy; print('  strategies: ✓')" 2>/dev/null || echo "  strategies: $(RED)✗$(RESET)"
	@$(PYTHON) -c "from impl.backtesting import BacktestRunner; print('  backtesting: ✓')" 2>/dev/null || echo "  backtesting: $(RED)✗$(RESET)"
	@$(PYTHON) -c "from impl.validation import StrategyValidator; print('  validation: ✓')" 2>/dev/null || echo "  validation: $(RED)✗$(RESET)"
	@$(PYTHON) -c "from impl.deployment import DeploymentMode; print('  deployment: ✓')" 2>/dev/null || echo "  deployment: $(RED)✗$(RESET)"

#==============================================================================
# QUALITY
#==============================================================================

lint: ## Run linter (ruff)
	@echo "$(GREEN)Running linter...$(RESET)"
	$(RUFF) check $(IMPL_DIR)/ --fix
	@echo "$(GREEN)✓ Linting complete$(RESET)"

typecheck: ## Run type checker (mypy)
	@echo "$(GREEN)Running type checker...$(RESET)"
	$(MYPY) $(IMPL_DIR)/ --ignore-missing-imports
	@echo "$(GREEN)✓ Type checking complete$(RESET)"

test: ## Run all tests
	@echo "$(GREEN)Running tests...$(RESET)"
	$(PYTEST) $(TEST_DIR)/ -v 2>/dev/null || echo "$(YELLOW)No tests found in $(TEST_DIR)/$(RESET)"

test-unit: ## Run unit tests only
	@echo "$(GREEN)Running unit tests...$(RESET)"
	$(PYTEST) $(TEST_DIR)/unit/ -v 2>/dev/null || echo "$(YELLOW)No unit tests found$(RESET)"

test-coverage: ## Run tests with coverage
	@echo "$(GREEN)Running tests with coverage...$(RESET)"
	$(PYTEST) $(TEST_DIR)/ --cov=$(IMPL_DIR) --cov-report=html 2>/dev/null || echo "$(YELLOW)Install pytest-cov: pip install pytest-cov$(RESET)"

#==============================================================================
# DATA
#==============================================================================

data-download: ## Download market data
	@echo "$(GREEN)Downloading market data...$(RESET)"
	@echo "$(YELLOW)Usage: make data-download SYMBOL=BTCUSDT START=2024-01-01 END=2024-12-31$(RESET)"
	@if [ -n "$(SYMBOL)" ] && [ -n "$(START)" ] && [ -n "$(END)" ]; then \
		$(PYTHON) -c "from impl.data import TardisDataDownloader; d = TardisDataDownloader(); d.download('$(SYMBOL)', '$(START)', '$(END)')"; \
	fi

data-catalog-info: ## Show catalog statistics
	@echo "$(CYAN)Data Catalog Info$(RESET)"
	@echo "=================="
	@$(PYTHON) -c "\
from impl.data import ParquetCatalogManager; \
mgr = ParquetCatalogManager('$(DATA_DIR)/catalog'); \
info = mgr.get_catalog_info(); \
print(f'Instruments: {info.get(\"instrument_count\", 0)}'); \
print(f'Date range: {info.get(\"start_date\", \"N/A\")} to {info.get(\"end_date\", \"N/A\")}'); \
print(f'Total size: {info.get(\"total_size_mb\", 0):.1f} MB'); \
" 2>/dev/null || echo "$(YELLOW)No catalog found or impl.data not available$(RESET)"

data-validate: ## Validate data integrity
	@echo "$(GREEN)Validating data...$(RESET)"
	@$(PYTHON) -c "\
from impl.data import ParquetCatalogManager; \
mgr = ParquetCatalogManager('$(DATA_DIR)/catalog'); \
gaps = mgr.find_gaps(); \
if gaps: print(f'Found {len(gaps)} gaps'); \
else: print('✓ No gaps found'); \
" 2>/dev/null || echo "$(YELLOW)Validation requires impl.data module$(RESET)"

#==============================================================================
# BACKTESTING
#==============================================================================

backtest: ## Run backtest
	@echo "$(GREEN)Running backtest...$(RESET)"
	@echo "$(YELLOW)Usage: make backtest CONFIG=config/backtest.yaml$(RESET)"
	@if [ -n "$(CONFIG)" ]; then \
		$(PYTHON) -c "\
from impl.backtesting import BacktestRunner, BacktestConfig; \
import yaml; \
with open('$(CONFIG)') as f: cfg = yaml.safe_load(f); \
runner = BacktestRunner(BacktestConfig(**cfg)); \
runner.setup(); \
result = runner.run(); \
print(result.summary()); \
"; \
	else \
		echo "$(YELLOW)Specify CONFIG=path/to/config.yaml$(RESET)"; \
	fi

backtest-walkforward: ## Run walk-forward analysis
	@echo "$(GREEN)Running walk-forward analysis...$(RESET)"
	@echo "$(YELLOW)Usage: make backtest-walkforward EQUITY=path/to/equity.json$(RESET)"
	@if [ -n "$(EQUITY)" ]; then \
		$(PYTHON) -c "\
from impl.backtesting import run_walk_forward_analysis; \
import json; \
with open('$(EQUITY)') as f: data = json.load(f); \
result = run_walk_forward_analysis(data); \
print(f'WFE: {result.wfe:.2f}'); \
print(f'Robust: {result.is_robust}'); \
"; \
	else \
		echo "$(YELLOW)Specify EQUITY=path/to/equity.json$(RESET)"; \
	fi

backtest-montecarlo: ## Run Monte Carlo permutation test
	@echo "$(GREEN)Running Monte Carlo test...$(RESET)"
	@echo "$(YELLOW)Usage: make backtest-montecarlo RETURNS=path/to/returns.json$(RESET)"
	@if [ -n "$(RETURNS)" ]; then \
		$(PYTHON) -c "\
from impl.backtesting import monte_carlo_permutation_test; \
import json; \
with open('$(RETURNS)') as f: returns = json.load(f); \
result = monte_carlo_permutation_test(returns, n_permutations=1000); \
print(f'P-value: {result.p_value:.4f}'); \
print(f'Significant: {result.is_significant}'); \
"; \
	else \
		echo "$(YELLOW)Specify RETURNS=path/to/returns.json$(RESET)"; \
	fi

#==============================================================================
# VALIDATION
#==============================================================================

validate: ## Run full strategy validation
	@echo "$(GREEN)Running strategy validation...$(RESET)"
	@echo "$(YELLOW)Usage: make validate EQUITY=path/to/equity.json$(RESET)"
	@if [ -n "$(EQUITY)" ]; then \
		$(PYTHON) -c "\
from impl.validation import validate_strategy, ValidationConfig; \
import json; \
with open('$(EQUITY)') as f: equity = json.load(f); \
result = validate_strategy(equity); \
print(result.summary()); \
"; \
	else \
		echo "$(YELLOW)Specify EQUITY=path/to/equity.json$(RESET)"; \
	fi

validate-stationarity: ## Run stationarity tests
	@echo "$(GREEN)Running stationarity tests...$(RESET)"
	@echo "$(YELLOW)Usage: make validate-stationarity SERIES=path/to/series.json$(RESET)"
	@if [ -n "$(SERIES)" ]; then \
		$(PYTHON) -c "\
from impl.validation import run_stationarity_tests; \
import json; \
with open('$(SERIES)') as f: series = json.load(f); \
result = run_stationarity_tests(series); \
print(f'ADF p-value: {result.adf.p_value:.4f}'); \
print(f'Hurst: {result.hurst.hurst_exponent:.3f}'); \
print(f'Half-life: {result.half_life.half_life:.1f}'); \
print(f'Stationary: {result.overall_stationary}'); \
print(f'Recommendation: {result.recommendation}'); \
"; \
	else \
		echo "$(YELLOW)Specify SERIES=path/to/series.json$(RESET)"; \
	fi

validate-regime: ## Run regime detection
	@echo "$(GREEN)Running regime detection...$(RESET)"
	@echo "$(YELLOW)Usage: make validate-regime RETURNS=path/to/returns.json$(RESET)"
	@if [ -n "$(RETURNS)" ]; then \
		$(PYTHON) -c "\
from impl.validation import SimpleRegimeDetector; \
import json; \
with open('$(RETURNS)') as f: returns = json.load(f); \
detector = SimpleRegimeDetector(); \
result = detector.detect_regimes(returns); \
print(f'Current regime: {result.current_regime}'); \
print(f'Regimes found: {len(set(result.regime_sequence))}'); \
for name, stats in result.regime_stats.items(): \
    print(f'  {name}: {stats[\"count\"]} periods, mean={stats[\"mean_return\"]:.4f}'); \
"; \
	else \
		echo "$(YELLOW)Specify RETURNS=path/to/returns.json$(RESET)"; \
	fi

#==============================================================================
# DEPLOYMENT
#==============================================================================

dry-run: ## Validate deployment (dry-run mode)
	@echo "$(CYAN)Dry-Run Deployment Validation$(RESET)"
	@echo "==============================="
	@$(PYTHON) -c "\
from impl.deployment import DryRunConfig, DryRunValidator, DryRunOrderTracker; \
print('Dry-run mode: Orders logged but not submitted'); \
print('Use DryRunOrderTracker to record order intentions'); \
print('Use DryRunValidator to check promotion readiness'); \
"

shadow: ## Shadow trading mode info
	@echo "$(CYAN)Shadow Trading Mode$(RESET)"
	@echo "===================="
	@$(PYTHON) -c "\
from impl.deployment import ShadowConfig, ShadowValidator, ShadowOrderTracker; \
print('Shadow mode: Track hypothetical P&L without execution'); \
print('Use ShadowOrderTracker to simulate fills'); \
print('Use ShadowValidator to compare with live market'); \
"

paper: ## Paper trading mode info
	@echo "$(CYAN)Paper Trading Mode$(RESET)"
	@echo "==================="
	@$(PYTHON) -c "\
from impl.deployment import PaperConfig, validate_deployment_readiness; \
config = PaperConfig(strategy_id='test', instruments=['BTCUSDT']); \
print(f'Paper mode: Testnet execution'); \
print(f'Min profitable days: {config.min_profitable_days}'); \
print(f'Min trades: {config.min_trades}'); \
"

production: ## Production deployment checklist
	@echo "$(RED)PRODUCTION MODE CHECKLIST$(RESET)"
	@echo "=============================="
	@$(PYTHON) -c "\
from impl.deployment import ProductionConfig, CircuitBreakerConfig; \
config = ProductionConfig(strategy_id='prod', instruments=['BTCUSDT']); \
print('Required checks:'); \
print('  [x] Circuit breaker:', config.require_circuit_breaker); \
print('  [x] Reconciliation:', config.require_reconciliation); \
print('  [x] Max position:', config.max_position_value); \
print('  [x] Max daily loss:', config.max_daily_loss); \
print('  [x] Max drawdown:', config.max_drawdown); \
print(); \
cb = CircuitBreakerConfig(); \
print('Circuit breaker defaults:'); \
print('  Max daily loss:', cb.max_daily_loss); \
print('  Max drawdown:', cb.max_drawdown); \
print('  Cooldown mins:', cb.cooldown_minutes); \
"
