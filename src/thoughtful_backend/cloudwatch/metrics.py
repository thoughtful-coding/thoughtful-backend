import logging

from aws_embedded_metrics import metric_scope

_LOGGER = logging.getLogger(__name__)


class MetricsManager:
    """A wrapper for the aws_embedded_metrics library to make it more testable."""

    def __init__(self, namespace: str):
        self._namespace = namespace
        self._metrics = {}
        self._dimensions = {}

    def set_dimension(self, name: str, value: str):
        """Adds a dimension to all metrics emitted in this context."""
        self._dimensions[name] = value

    def put_metric(self, name: str, value: int, unit: str = "Count"):
        """Queues a metric to be emitted."""
        self._metrics[name] = (value, unit)
        _LOGGER.info(f"Queued metric '{name}' with value {value} in namespace '{self._namespace}'")

    @metric_scope
    def flush(self, metrics):
        """Emits all queued metrics to CloudWatch Logs."""
        metrics.set_namespace(self._namespace)
        for name, (value, unit) in self._metrics.items():
            metrics.put_metric(name, value, unit)
        for name, value in self._dimensions.items():
            metrics.set_dimension(name, value)

        _LOGGER.info(f"Flushed {len(self._metrics)} metrics to namespace '{self._namespace}'.")
        self._metrics = {}  # Clear after flushing
