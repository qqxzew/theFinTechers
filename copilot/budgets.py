"""Step, token, cost, and wall-clock budgets for copilot agents."""

import time


class BudgetExceeded(Exception):
    """Raised when a copilot budget limit is exceeded."""


class Budget:
    """Tracks usage against step, token, cost, and time limits."""

    def __init__(self, max_steps: int, max_tokens: int, max_cost_usd: float, timeout_s: float) -> None:
        self.max_steps = max_steps
        self.max_tokens = max_tokens
        self.max_cost_usd = max_cost_usd
        self.timeout_s = timeout_s
        self.steps = 0
        self.tokens = 0
        self.cost_usd = 0.0
        self.start = time.monotonic()

    def charge_step(self) -> None:
        """Charge one agent step; raise if the step limit is exceeded."""
        self.steps += 1
        if self.steps > self.max_steps:
            raise BudgetExceeded(f"max_steps {self.max_steps} exceeded")

    def charge_usage(self, usage: dict, price_in: float, price_out: float) -> None:
        """Charge token usage and cost; raise if token or cost limits are exceeded."""
        tokens_in = int(usage.get("inputTokens", 0))
        tokens_out = int(usage.get("outputTokens", 0))
        self.tokens += tokens_in + tokens_out
        self.cost_usd += tokens_in * price_in + tokens_out * price_out
        if self.tokens > self.max_tokens:
            raise BudgetExceeded(f"max_tokens {self.max_tokens} exceeded")
        if self.cost_usd > self.max_cost_usd:
            raise BudgetExceeded(f"max_cost {self.max_cost_usd} USD exceeded")

    def check_time(self) -> None:
        """Raise if the wall-clock timeout has elapsed."""
        if time.monotonic() - self.start > self.timeout_s:
            raise BudgetExceeded(f"timeout {self.timeout_s}s exceeded")
