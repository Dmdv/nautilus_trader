from decimal import Decimal

class RiskManager:
    """
    Base Risk Manager.
    Handles position sizing and pre-trade risk checks.
    """
    def __init__(self, portfolio, config):
        self.portfolio = portfolio
        self.config = config

    def check_risk(self, instrument_id, side, qty: Decimal) -> bool:
        """
        Check if order allows adherence to risk limits.
        """
        # 1. Max position size check
        current_pos = self.portfolio.net_position(instrument_id)
        current_qty = current_pos.quantity if current_pos else 0
        
        # Simple absolute limit check
        if abs(current_qty + qty) > self.config.get('max_position_size', float('inf')):
            return False

        # 2. Daily Loss Limit (simplified)
        # In a real impl, we'd check PnL state
        
        return True
