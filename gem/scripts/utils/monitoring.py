from prometheus_client import Counter, Gauge, Histogram, start_http_server

# Metrics Definitions
ORDERS_SUBMITTED = Counter('nautilus_orders_submitted_total', 'Total orders submitted', ['venue', 'side'])
ORDERS_FILLED = Counter('nautilus_orders_filled_total', 'Total orders filled', ['venue', 'side'])
ORDER_LATENCY = Histogram('nautilus_order_latency_seconds', 'Order submission to fill latency')
POSITION_VALUE = Gauge('nautilus_position_value', 'Current position value', ['instrument'])
DAILY_PNL = Gauge('nautilus_daily_pnl', 'Daily P&L')
DRAWDOWN = Gauge('nautilus_drawdown', 'Current drawdown from peak')

class MetricsPublisher:
    """Publish trading metrics to Prometheus."""

    def __init__(self, port: int = 8000):
        try:
            start_http_server(port)
            print(f"Prometheus metrics server started on port {port}")
        except OSError:
            print(f"Prometheus metrics server failed to start on port {port} (port likely in use)")

    def on_order_submitted(self, venue: str, side: str):
        ORDERS_SUBMITTED.labels(venue=venue, side=side).inc()

    def on_order_filled(self, venue: str, side: str, fill_time_seconds: float):
        ORDERS_FILLED.labels(venue=venue, side=side).inc()
        ORDER_LATENCY.observe(fill_time_seconds)

    def update_position(self, instrument_id: str, value: float):
        POSITION_VALUE.labels(instrument=instrument_id).set(value)

    def update_pnl(self, pnl: float, dd: float):
        DAILY_PNL.set(pnl)
        DRAWDOWN.set(dd)
