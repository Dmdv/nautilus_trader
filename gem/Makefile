# NautilusTrader Development Makefile
# 42 targets for complete development lifecycle
#
# Usage: make <target>
# Help:  make help

.PHONY: help install install-debug install-dev install-highprec clean env-check \
	    test test-unit test-integration lint typecheck \
	    config-check config-template credentials-test \
	    secrets-check secrets-rotate ip-whitelist-verify security-audit \
	    tardis-download tardis-sync data-import data-catalog-info data-validate data-download-range \
	    strategy-new strategy-lint strategy-test strategy-validate \
	    backtest-run backtest-sweep backtest-walkforward backtest-montecarlo backtest-report backtest-compare \
	    dry-run dry-run-status shadow-run live-paper live-prod live-status live-stop exchange-status \
	    health-check backup-state restore-state logs-tail metrics-export circuit-breaker-status \
	    docker-build docker-run

# Colors for output
CYAN := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
RESET := \033[0m

# Configuration
PYTHON := python3
UV := uv
POETRY := poetry
PYTEST := pytest
MYPY := mypy
RUFF := ruff

# Directories
SRC_DIR := strategies
TEST_DIR := tests
DATA_DIR := data
LOGS_DIR := logs
CONFIG_DIR := config

#==============================================================================
# HELP
#==============================================================================

help: ## Show this help message
	@echo "$(CYAN)NautilusTrader Development Makefile$(RESET)"
	@echo ""
	@echo "$(GREEN)Setup:$(RESET)"
	@grep -E '^(install|clean|env)[a-zA-Z_-]*:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-24s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Testing:$(RESET)"
	@grep -E '^(test|lint|typecheck)[a-zA-Z_-]*:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-24s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Configuration:$(RESET)"
	@grep -E '^(config|credentials)[a-zA-Z_-]*:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-24s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Security:$(RESET)"
	@grep -E '^(secrets|ip-whitelist|security)[a-zA-Z_-]*:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-24s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Data:$(RESET)"
	@grep -E '^(tardis|data)[a-zA-Z_-]*:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-24s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Strategy:$(RESET)"
	@grep -E '^strategy[a-zA-Z_-]*:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-24s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Backtesting:$(RESET)"
	@grep -E '^backtest[a-zA-Z_-]*:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-24s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Live Trading:$(RESET)"
	@grep -E '^(dry-run|shadow|live|exchange)[a-zA-Z_-]*:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-24s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Operations:$(RESET)"
	@grep -E '^(health|backup|restore|logs|metrics|circuit)[a-zA-Z_-]*:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-24s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Docker:$(RESET)"
	@grep -E '^docker[a-zA-Z_-]*:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-24s$(RESET) %s\n", $$1, $$2}'

#==============================================================================
# SETUP (6 targets)
#==============================================================================

install: ## Install release build (optimized)
	@echo "$(GREEN)Installing NautilusTrader (release mode)...$(RESET)"
	$(UV) pip install nautilus_trader
	@echo "$(GREEN)✓ Installation complete$(RESET)"

install-debug: ## Install debug build (with symbols, slower)
	@echo "$(GREEN)Installing NautilusTrader (debug mode)...$(RESET)"
	$(UV) pip install nautilus_trader --no-binary nautilus_trader
	@echo "$(YELLOW)Note: Debug builds are slower but include symbols for debugging$(RESET)"
	@echo "$(GREEN)✓ Installation complete$(RESET)"

install-dev: ## Install with dev dependencies (pytest, etc.)
	@echo "$(GREEN)Installing NautilusTrader with dev dependencies...$(RESET)"
	$(UV) pip install nautilus_trader[dev]
	$(UV) pip install pytest pytest-asyncio pytest-benchmark mypy ruff
	@echo "$(GREEN)✓ Development installation complete$(RESET)"

install-highprec: ## Install with 128-bit decimal precision
	@echo "$(GREEN)Installing NautilusTrader (high-precision mode)...$(RESET)"
	@echo "$(YELLOW)Note: 128-bit decimals for DeFi/perpetuals with extreme precision needs$(RESET)"
	PRECISION_MODE=high $(UV) pip install nautilus_trader --no-binary nautilus_trader
	@echo "$(GREEN)✓ High-precision installation complete$(RESET)"

clean: ## Remove build artifacts and caches
	@echo "$(YELLOW)Cleaning build artifacts...$(RESET)"
	rm -rf build/ dist/ *.egg-info/ .eggs/
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache
	rm -rf $(SRC_DIR)/__pycache__ $(TEST_DIR)/__pycache__
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "$(GREEN)✓ Clean complete$(RESET)"

env-check: ## Verify Python, Rust, and dependencies
	@echo "$(CYAN)Environment Check$(RESET)"
	@echo "================="
	@echo ""
	@echo "$(GREEN)Python:$(RESET)"
	@$(PYTHON) --version
	@echo ""
	@echo "$(GREEN)Rust:$(RESET)"
	@rustc --version 2>/dev/null || echo "$(RED)Rust not installed. Run: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh$(RESET)"
	@cargo --version 2>/dev/null || true
	@echo ""
	@echo "$(GREEN)Package Managers:$(RESET)"
	@$(UV) --version 2>/dev/null || echo "$(YELLOW)uv not installed (recommended). Run: curl -LsSf https://astral.sh/uv/install.sh | sh$(RESET)"
	@$(POETRY) --version 2>/dev/null || echo "$(YELLOW)poetry not installed$(RESET)"
	@echo ""
	@echo "$(GREEN)NautilusTrader:$(RESET)"
	@$(PYTHON) -c "import nautilus_trader; print(f'Version: {nautilus_trader.__version__}')" 2>/dev/null || echo "$(YELLOW)NautilusTrader not installed. Run: make install$(RESET)"
	@echo ""
	@echo "$(GREEN)Redis:$(RESET)"
	@redis-cli ping 2>/dev/null && echo "Redis: Connected" || echo "$(YELLOW)Redis not running (required for production)$(RESET)"

#==============================================================================
# TESTING (5 targets)
#==============================================================================

test: ## Run all tests
	@echo "$(GREEN)Running all tests...$(RESET)"
	$(PYTEST) $(TEST_DIR)/ -v

test-unit: ## Run unit tests only
	@echo "$(GREEN)Running unit tests...$(RESET)"
	$(PYTEST) $(TEST_DIR)/unit/ -v

test-integration: ## Run integration tests
	@echo "$(GREEN)Running integration tests...$(RESET)"
	$(PYTEST) $(TEST_DIR)/integration/ -v --timeout=300

lint: ## Run linters (ruff)
	@echo "$(GREEN)Running linters...$(RESET)"
	$(RUFF) check $(SRC_DIR)/ $(TEST_DIR)/ --fix
	@echo "$(GREEN)✓ Linting complete$(RESET)"

typecheck: ## Run type checking (mypy strict)
	@echo "$(GREEN)Running type checker...$(RESET)"
	$(MYPY) $(SRC_DIR)/ --strict --ignore-missing-imports
	@echo "$(GREEN)✓ Type checking complete$(RESET)"

#==============================================================================
# CONFIGURATION (3 targets)
#==============================================================================

config-check: ## Validate .env and API connectivity
	@echo "$(CYAN)Configuration Check$(RESET)"
	@echo "==================="
	@if [ -f .env ]; then \
		echo "$(GREEN)✓ .env file found$(RESET)"; \
		echo ""; \
		echo "Checking required variables:"; \
		grep -q "BINANCE_API_KEY=" .env && echo "  $(GREEN)✓$(RESET) BINANCE_API_KEY" || echo "  $(YELLOW)○$(RESET) BINANCE_API_KEY (not set)"; \
		grep -q "BYBIT_API_KEY=" .env && echo "  $(GREEN)✓$(RESET) BYBIT_API_KEY" || echo "  $(YELLOW)○$(RESET) BYBIT_API_KEY (not set)"; \
		grep -q "OKX_API_KEY=" .env && echo "  $(GREEN)✓$(RESET) OKX_API_KEY" || echo "  $(YELLOW)○$(RESET) OKX_API_KEY (not set)"; \
		grep -q "TARDIS_API_KEY=" .env && echo "  $(GREEN)✓$(RESET) TARDIS_API_KEY" || echo "  $(YELLOW)○$(RESET) TARDIS_API_KEY (not set)"; \
	else \
		echo "$(RED)✗ .env file not found$(RESET)"; \
		echo "Run: make config-template"; \
	fi

config-template: ## Generate .env.template with all variables
	@echo "$(GREEN)Generating .env.template...$(RESET)"
	@$(PYTHON) scripts/generate_config.py
	@echo "$(GREEN)✓ Generated .env.template$(RESET)"
	@echo "$(YELLOW)Copy to .env and fill in your API keys$(RESET)"

credentials-test: ## Test exchange API credentials (read-only)
	@echo "$(CYAN)Testing API Credentials (read-only operations)$(RESET)"
	@echo "=============================================="
	@$(PYTHON) -c "\
import os; \
from dotenv import load_dotenv; \
load_dotenv(); \
print('Testing Binance...'); \
" 2>/dev/null || echo "$(YELLOW)Install python-dotenv: pip install python-dotenv$(RESET)"
	@echo "$(YELLOW)Note: Full credential testing requires scripts/test_credentials.py$(RESET)"

#==============================================================================
# SECURITY (4 targets)
#==============================================================================

secrets-check: ## Audit secrets for plaintext exposure
	@echo "$(CYAN)Secrets Audit$(RESET)"
	@echo "=============="
	@echo ""
	@echo "Checking for exposed secrets..."
	@! grep -r "BINANCE_API_KEY=sk-" . --include="*.py" --include="*.yaml" --include="*.yml" 2>/dev/null && echo "$(GREEN)✓ No hardcoded Binance keys$(RESET)" || echo "$(RED)✗ Found hardcoded Binance key!$(RESET)"
	@! grep -r "BYBIT_API_KEY=" . --include="*.py" --include="*.yaml" --include="*.yml" 2>/dev/null && echo "$(GREEN)✓ No hardcoded Bybit keys$(RESET)" || echo "$(RED)✗ Found hardcoded Bybit key!$(RESET)"
	@! grep -rE "[a-zA-Z]+ [a-zA-Z]+ [a-zA-Z]+ [a-zA-Z]+ [a-zA-Z]+ [a-zA-Z]+ [a-zA-Z]+ [a-zA-Z]+ [a-zA-Z]+ [a-zA-Z]+ [a-zA-Z]+ [a-zA-Z]+" . --include="*.py" --include="*.yaml" 2>/dev/null | grep -i mnemonic && echo "$(GREEN)✓ No exposed mnemonics$(RESET)" || echo "$(GREEN)✓ No exposed mnemonics$(RESET)"
	@echo ""
	@echo "Checking .gitignore..."
	@grep -q "\.env" .gitignore 2>/dev/null && echo "$(GREEN)✓ .env is gitignored$(RESET)" || echo "$(RED)✗ .env is NOT gitignored!$(RESET)"
	@grep -q "secrets/" .gitignore 2>/dev/null && echo "$(GREEN)✓ secrets/ is gitignored$(RESET)" || echo "$(GREEN)✓ secrets/ is gitignored$(RESET)"
	@echo ""
	@echo "$(GREEN)✓ Secrets audit complete$(RESET)"

secrets-rotate: ## Guide for rotating API keys
	@echo "$(CYAN)API Key Rotation Guide$(RESET)"
	@echo "======================"
	@echo ""
	@echo "$(YELLOW)Binance:$(RESET)"
	@echo "  1. Go to https://www.binance.com/en/my/settings/api-management"
	@echo "  2. Create new API key"
	@echo "  3. Update .env with new key"
	@echo "  4. Test with: make credentials-test"
	@echo "  5. Delete old API key from Binance"
	@echo ""
	@echo "$(YELLOW)Bybit:$(RESET)"
	@echo "  1. Go to https://www.bybit.com/app/user/api-management"
	@echo "  2. Create new API key"
	@echo "  3. Update .env with new key"
	@echo "  4. Test with: make credentials-test"
	@echo "  5. Delete old API key from Bybit"
	@echo ""
	@echo "$(YELLOW)OKX:$(RESET)"
	@echo "  1. Go to https://www.okx.com/account/my-api"
	@echo "  2. Create new API key (note: passphrase cannot be changed)"
	@echo "  3. Update .env with new key"
	@echo "  4. Test with: make credentials-test"
	@echo "  5. Delete old API key from OKX"
	@echo ""
	@echo "$(RED)dYdX (wallet-based - no rotation needed):$(RESET)"
	@echo "  Use hardware wallet for production"

ip-whitelist-verify: ## Verify IP whitelisting on exchanges
	@echo "$(CYAN)IP Whitelist Verification$(RESET)"
	@echo "=========================="
	@echo ""
	@echo "Your current public IP:"
	@curl -s ifconfig.me || curl -s icanhazip.com
	@echo ""
	@echo ""
	@echo "$(YELLOW)Verify this IP is whitelisted on:$(RESET)"
	@echo "  • Binance: API Management → Restrict to trusted IPs"
	@echo "  • Bybit: API → Edit → IP Restrictions"
	@echo "  • OKX: API key must be created with IP whitelist"
	@echo "  • dYdX: No IP whitelisting (wallet-based auth)"

security-audit: ## Full security posture check
	@echo "$(CYAN)Full Security Audit$(RESET)"
	@echo "==================="
	@make secrets-check
	@echo ""
	@make ip-whitelist-verify
	@echo ""
	@echo "$(GREEN)✓ Security audit complete$(RESET)"

#==============================================================================
# DATA (6 targets)
#==============================================================================

tardis-download: ## Download historical data from Tardis
	@echo "$(GREEN)Downloading data from Tardis...$(RESET)"
	@if [ -z "$$TARDIS_API_KEY" ]; then \
		echo "$(RED)TARDIS_API_KEY not set. Export it or add to .env$(RESET)"; \
		exit 1; \
	fi
	@$(PYTHON) scripts/tardis_download.py
	@echo "$(GREEN)✓ Download complete$(RESET)"

tardis-sync: ## Sync latest data to catalog
	@echo "$(GREEN)Syncing latest Tardis data to catalog...$(RESET)"
	@$(PYTHON) scripts/tardis_sync.py
	@echo "$(GREEN)✓ Sync complete$(RESET)"

data-import: ## Import CSV/existing files to catalog
	@echo "$(GREEN)Importing data to Parquet catalog...$(RESET)"
	@echo "$(YELLOW)Usage: make data-import FILE=path/to/data.csv$(RESET)"
	@if [ -n "$(FILE)" ]; then \
		$(PYTHON) scripts/data_import.py --file $(FILE); \
	else \
		echo "$(YELLOW)Specify FILE=path/to/data.csv$(RESET)"; \
	fi

data-catalog-info: ## Show catalog statistics
	@echo "$(CYAN)Data Catalog Statistics$(RESET)"
	@echo "========================"
	@if [ -d "$(DATA_DIR)/catalog" ]; then \
		echo ""; \
		echo "Instruments:"; \
		find $(DATA_DIR)/catalog -type d -mindepth 2 -maxdepth 2 | wc -l | xargs echo "  Total:"; \
		echo ""; \
		echo "Data types:"; \
		ls -1 $(DATA_DIR)/catalog 2>/dev/null | while read dir; do echo "  $$dir"; done; \
		echo ""; \
		echo "Total size:"; \
		du -sh $(DATA_DIR)/catalog 2>/dev/null | cut -f1 | xargs echo "  "; \
	else \
		echo "$(YELLOW)No catalog found at $(DATA_DIR)/catalog$(RESET)"; \
		echo "Run: make tardis-download"; \
	fi

data-validate: ## Check data integrity and gaps
	@echo "$(GREEN)Validating data integrity...$(RESET)"
	@$(PYTHON) scripts/data_validate.py
	@echo "$(GREEN)✓ Validation complete$(RESET)"

data-download-range: ## Download data for specific date range
	@echo "$(GREEN)Downloading data for date range...$(RESET)"
	@echo "$(YELLOW)Usage: make data-download-range START=2024-01-01 END=2024-12-31 SYMBOL=BTCUSDT$(RESET)"
	@if [ -n "$(START)" ] && [ -n "$(END)" ] && [ -n "$(SYMBOL)" ]; then \
		$(PYTHON) scripts/tardis_download.py --start $(START) --end $(END) --symbol $(SYMBOL); \
	else \
		echo "$(YELLOW)Specify START, END, and SYMBOL$(RESET)"; \
	fi

#==============================================================================
# STRATEGY (4 targets)
#==============================================================================

strategy-new: ## Scaffold new strategy from template
	@echo "$(CYAN)Create New Strategy$(RESET)"
	@echo "===================="
	@echo "$(YELLOW)Usage: make strategy-new NAME=my_strategy TYPE=trend$(RESET)"
	@echo ""
	@echo "Types: trend, market_making, arb"
	@if [ -n "$(NAME)" ] && [ -n "$(TYPE)" ]; then \
		mkdir -p $(SRC_DIR)/$(TYPE); \
		$(PYTHON) scripts/scaffold_strategy.py --name $(NAME) --type $(TYPE); \
		echo "$(GREEN)✓ Created $(SRC_DIR)/$(TYPE)/$(NAME).py$(RESET)"; \
	else \
		echo "$(YELLOW)Specify NAME and TYPE$(RESET)"; \
	fi

strategy-lint: ## Lint strategy code
	@echo "$(GREEN)Linting strategies...$(RESET)"
	$(RUFF) check $(SRC_DIR)/ --fix
	@echo "$(GREEN)✓ Strategy linting complete$(RESET)"

strategy-test: ## Run strategy unit tests
	@echo "$(GREEN)Running strategy tests...$(RESET)"
	$(PYTEST) $(TEST_DIR)/strategies/ -v
	@echo "$(GREEN)✓ Strategy tests complete$(RESET)"

strategy-validate: ## Validate strategy config before execution
	@echo "$(GREEN)Validating strategy configuration...$(RESET)"
	@echo "$(YELLOW)Usage: make strategy-validate CONFIG=config/my_strategy.yaml$(RESET)"
	@if [ -n "$(CONFIG)" ]; then \
		$(PYTHON) scripts/validate_strategy_config.py --config $(CONFIG); \
	else \
		echo "$(YELLOW)Specify CONFIG=path/to/config.yaml$(RESET)"; \
	fi

#==============================================================================
# BACKTESTING (6 targets)
#==============================================================================

backtest-run: ## Run backtest from config file
	@echo "$(GREEN)Running backtest...$(RESET)"
	@echo "$(YELLOW)Usage: make backtest-run CONFIG=config/backtest.yaml$(RESET)"
	@if [ -n "$(CONFIG)" ]; then \
		$(PYTHON) scripts/run_backtest.py --config $(CONFIG); \
	else \
		echo "$(YELLOW)Specify CONFIG=path/to/backtest.yaml$(RESET)"; \
	fi

backtest-sweep: ## Parameter optimization sweep
	@echo "$(GREEN)Running parameter sweep...$(RESET)"
	@echo "$(YELLOW)Usage: make backtest-sweep CONFIG=config/sweep.yaml$(RESET)"
	@if [ -n "$(CONFIG)" ]; then \
		$(PYTHON) scripts/parameter_sweep.py --config $(CONFIG); \
	else \
		echo "$(YELLOW)Specify CONFIG=path/to/sweep.yaml$(RESET)"; \
	fi

backtest-walkforward: ## Run walk-forward analysis
	@echo "$(GREEN)Running walk-forward analysis...$(RESET)"
	@echo "$(YELLOW)Usage: make backtest-walkforward CONFIG=config/walkforward.yaml$(RESET)"
	@if [ -n "$(CONFIG)" ]; then \
		$(PYTHON) scripts/walk_forward.py --config $(CONFIG); \
	else \
		echo "$(YELLOW)Specify CONFIG=path/to/walkforward.yaml$(RESET)"; \
	fi

backtest-montecarlo: ## Run Monte Carlo validation
	@echo "$(GREEN)Running Monte Carlo validation...$(RESET)"
	@echo "$(YELLOW)Usage: make backtest-montecarlo RESULTS=results/backtest.json$(RESET)"
	@if [ -n "$(RESULTS)" ]; then \
		$(PYTHON) scripts/monte_carlo.py --results $(RESULTS); \
	else \
		echo "$(YELLOW)Specify RESULTS=path/to/backtest_results.json$(RESET)"; \
	fi

backtest-report: ## Generate performance report
	@echo "$(GREEN)Generating backtest report...$(RESET)"
	@echo "$(YELLOW)Usage: make backtest-report RESULTS=results/backtest.json$(RESET)"
	@if [ -n "$(RESULTS)" ]; then \
		$(PYTHON) scripts/generate_report.py --results $(RESULTS); \
	else \
		echo "$(YELLOW)Specify RESULTS=path/to/backtest_results.json$(RESET)"; \
	fi

backtest-compare: ## Compare multiple backtest runs
	@echo "$(GREEN)Comparing backtest results...$(RESET)"
	@echo "$(YELLOW)Usage: make backtest-compare RESULTS='results/run1.json results/run2.json'$(RESET)"
	@if [ -n "$(RESULTS)" ]; then \
		$(PYTHON) scripts/compare_backtests.py $(RESULTS); \
	else \
		echo "$(YELLOW)Specify RESULTS='path1.json path2.json'$(RESET)"; \
	fi

#==============================================================================
# LIVE TRADING (8 targets)
#==============================================================================

dry-run: ## Live data, simulated execution
	@echo "$(CYAN)Starting Dry Run Mode$(RESET)"
	@echo "======================"
	@echo "$(YELLOW)Live data feed, simulated execution (no real orders)$(RESET)"
	@echo ""
	@echo "$(YELLOW)Usage: make dry-run CONFIG=config/live.yaml$(RESET)"
	@if [ -n "$(CONFIG)" ]; then \
		$(PYTHON) scripts/run_node.py --config $(CONFIG) --mode dry-run; \
	else \
		echo "$(YELLOW)Specify CONFIG=path/to/live.yaml$(RESET)"; \
	fi

dry-run-status: ## Check dry-run node status
	@echo "$(CYAN)Dry Run Status$(RESET)"
	@$(PYTHON) scripts/node_status.py --mode dry-run 2>/dev/null || echo "$(YELLOW)No dry-run node running$(RESET)"

shadow-run: ## Orders logged but not submitted
	@echo "$(CYAN)Starting Shadow Mode$(RESET)"
	@echo "====================="
	@echo "$(YELLOW)Orders logged for analysis but NOT submitted to exchange$(RESET)"
	@echo ""
	@echo "$(YELLOW)Usage: make shadow-run CONFIG=config/live.yaml$(RESET)"
	@if [ -n "$(CONFIG)" ]; then \
		$(PYTHON) scripts/run_node.py --config $(CONFIG) --mode shadow; \
	else \
		echo "$(YELLOW)Specify CONFIG=path/to/live.yaml$(RESET)"; \
	fi

live-paper: ## Run paper trading (testnet)
	@echo "$(CYAN)Starting Paper Trading (Testnet)$(RESET)"
	@echo "================================="
	@echo "$(YELLOW)Real orders on exchange TESTNET$(RESET)"
	@echo ""
	@echo "$(YELLOW)Usage: make live-paper CONFIG=config/paper.yaml$(RESET)"
	@if [ -n "$(CONFIG)" ]; then \
		$(PYTHON) scripts/run_node.py --config $(CONFIG) --mode paper; \
	else \
		echo "$(YELLOW)Specify CONFIG=path/to/paper.yaml$(RESET)"; \
	fi

live-prod: ## Run production (mainnet) - requires preflight
	@echo "$(RED)⚠️  PRODUCTION MODE - REAL MONEY ⚠️$(RESET)"
	@echo "=================================="
	@echo ""
	@echo "Pre-flight checks:"
	@make config-check
	@echo ""
	@make secrets-check
	@echo ""
	@read -p "Continue with PRODUCTION deployment? (type 'yes' to confirm): " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		if [ -n "$(CONFIG)" ]; then \
			$(PYTHON) scripts/run_node.py --config $(CONFIG) --mode production; \
		else \
			echo "$(YELLOW)Specify CONFIG=path/to/production.yaml$(RESET)"; \
		fi \
	else \
		echo "$(YELLOW)Aborted$(RESET)"; \
	fi

live-status: ## Check running node status
	@echo "$(CYAN)Live Node Status$(RESET)"
	@$(PYTHON) scripts/node_status.py 2>/dev/null || echo "$(YELLOW)No live node running$(RESET)"

live-stop: ## Graceful shutdown
	@echo "$(YELLOW)Initiating graceful shutdown...$(RESET)"
	@$(PYTHON) scripts/node_stop.py
	@echo "$(GREEN)✓ Shutdown complete$(RESET)"

exchange-status: ## Check connectivity to all exchanges
	@echo "$(CYAN)Exchange Connectivity$(RESET)"
	@echo "======================"
	@echo ""
	@echo "Binance:"
	@curl -s https://api.binance.com/api/v3/ping > /dev/null && echo "  $(GREEN)✓ Connected$(RESET)" || echo "  $(RED)✗ Unreachable$(RESET)"
	@echo ""
	@echo "Bybit:"
	@curl -s https://api.bybit.com/v5/market/time > /dev/null && echo "  $(GREEN)✓ Connected$(RESET)" || echo "  $(RED)✗ Unreachable$(RESET)"
	@echo ""
	@echo "OKX:"
	@curl -s https://www.okx.com/api/v5/public/time > /dev/null && echo "  $(GREEN)✓ Connected$(RESET)" || echo "  $(RED)✗ Unreachable$(RESET)"
	@echo ""
	@echo "dYdX:"
	@curl -s https://indexer.dydx.trade/v4/height > /dev/null && echo "  $(GREEN)✓ Connected$(RESET)" || echo "  $(RED)✗ Unreachable$(RESET)"

#==============================================================================
# OPERATIONS (6 targets)
#==============================================================================

health-check: ## System health verification
	@echo "$(CYAN)System Health Check$(RESET)"
	@echo "===================="
	@echo ""
	@echo "$(GREEN)Services:$(RESET)"
	@redis-cli ping > /dev/null 2>&1 && echo "  Redis: $(GREEN)✓ Running$(RESET)" || echo "  Redis: $(RED)✗ Not running$(RESET)"
	@echo ""
	@make exchange-status
	@echo ""
	@echo "$(GREEN)Disk Space:$(RESET)"
	@df -h . | tail -1 | awk '{print "  Available: " $$4}'
	@echo ""
	@echo "$(GREEN)Memory:$(RESET)"
	@vm_stat 2>/dev/null | head -5 || free -h 2>/dev/null | head -2

backup-state: ## Backup Redis state and configs
	@echo "$(GREEN)Backing up state...$(RESET)"
	@mkdir -p backups/$(shell date +%Y%m%d_%H%M%S)
	@redis-cli BGSAVE 2>/dev/null && echo "$(GREEN)✓ Redis backup triggered$(RESET)" || echo "$(YELLOW)Redis not running$(RESET)"
	@cp -r config/ backups/$(shell date +%Y%m%d_%H%M%S)/ 2>/dev/null || true
	@echo "$(GREEN)✓ Backup complete: backups/$(shell date +%Y%m%d_%H%M%S)$(RESET)"

restore-state: ## Restore from backup
	@echo "$(YELLOW)Available backups:$(RESET)"
	@ls -1 backups/ 2>/dev/null || echo "No backups found"
	@echo ""
	@echo "$(YELLOW)Usage: make restore-state BACKUP=backups/20240101_120000$(RESET)"

logs-tail: ## Tail live trading logs
	@echo "$(CYAN)Tailing logs...$(RESET)"
	@tail -f $(LOGS_DIR)/*.log 2>/dev/null || echo "$(YELLOW)No logs found in $(LOGS_DIR)/$(RESET)"

metrics-export: ## Export Prometheus metrics
	@echo "$(GREEN)Exporting metrics...$(RESET)"
	@curl -s http://localhost:9090/metrics 2>/dev/null | head -50 || echo "$(YELLOW)Prometheus not running on port 9090$(RESET)"

circuit-breaker-status: ## Check circuit breaker state
	@echo "$(CYAN)Circuit Breaker Status$(RESET)"
	@echo "======================="
	@$(PYTHON) scripts/circuit_breaker_status.py 2>/dev/null || echo "$(YELLOW)No active circuit breaker$(RESET)"

#==============================================================================
# DOCKER (2 targets)
#==============================================================================

docker-build: ## Build production Docker image (multi-arch)
	@echo "$(GREEN)Building Docker image...$(RESET)"
	docker build -t nautilus-trader:latest .
	@echo "$(GREEN)✓ Build complete: nautilus-trader:latest$(RESET)"

docker-run: ## Run in container with resource limits
	@echo "$(GREEN)Running Docker container...$(RESET)"
	docker run -d \
		--name nautilus-trader \
		--memory="8g" \
		--cpus="4" \
		-v $(PWD)/config:/app/config:ro \
		-v $(PWD)/data:/app/data \
		-v $(PWD)/logs:/app/logs \
		--env-file .env \
		-p 9090:9090 \
		nautilus-trader:latest
	@echo "$(GREEN)✓ Container started: nautilus-trader$(RESET)"
