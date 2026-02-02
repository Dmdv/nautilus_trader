from decimal import Decimal
import logging

class ProductionRiskManager:
    """Production risk controls beyond built-in limits."""

    def __init__(self, strategy, config: dict):
        self.strategy = strategy
        self.max_daily_loss = config.get("max_daily_loss", 1000.0)
        self.max_drawdown = config.get("max_drawdown", 0.10)
        
        self.daily_pnl = 0.0
        self.peak_equity = 0.0
        self.circuit_breaker_triggered = False
        self.logger = logging.getLogger("RiskManager")

    def check_daily_loss(self, pnl_update: float) -> bool:
        self.daily_pnl += pnl_update
        if self.daily_pnl < -self.max_daily_loss:
            self._trigger_circuit_breaker("Daily loss limit breached")
            return False
        return True

    def check_drawdown(self, equity: float) -> bool:
        self.peak_equity = max(self.peak_equity, equity)
        drawdown = (self.peak_equity - equity) / self.peak_equity if self.peak_equity > 0 else 0
        
        if drawdown > self.max_drawdown:
            self._trigger_circuit_breaker("Drawdown limit breached")
            return False
        return True

    def _trigger_circuit_breaker(self, reason: str):
        self.circuit_breaker_triggered = True
        self.logger.critical(f"CIRCUIT BREAKER: {reason}")
        self._flatten_all_positions()

    def _flatten_all_positions(self):
        """Close all open positions immediately."""
        if not self.strategy:
            return

        # Close all positions
        for position in self.strategy.cache.positions():
            if position.is_open:
                self.strategy.close_position(position)
                self.logger.warning(f"Flattening position: {position.instrument_id}")

        # Cancel all open orders
        for order in self.strategy.cache.orders_open():
            self.strategy.cancel_order(order)
            self.logger.warning(f"Cancelling order: {order.client_order_id}")