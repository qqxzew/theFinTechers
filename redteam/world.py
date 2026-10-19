"""Red-team world builder: emits canonical tx/client rows plus hidden labels. ISOLATED: blue-team code must never import this package."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import numpy as np

START = datetime(2026, 7, 1, tzinfo=UTC)
END = datetime(2026, 7, 31, 23, 59, 59, tzinfo=UTC)


@dataclass
class World:
    START = START  # also reachable as w.START
    END = END

    rng: np.random.Generator
    banks: list[str]
    tx: list[dict] = field(default_factory=list)
    clients: list[dict] = field(default_factory=list)
    labels: list[dict] = field(default_factory=list)
    _n_client: int = 0
    _n_tx: int = 0
    _n_ext: int = 0
    _bank_of: dict = field(default_factory=dict)
    popular_tokens: list = field(default_factory=list)

    def new_ext_account(self, country: str = "CZ") -> str:
        """A fresh external account token (e.g. an IBAN-like string of an account outside the bank)."""
        self._n_ext += 1
        return f"X{country}{self._n_ext:06d}"

    def popular_pool(self, n: int = 20) -> list[str]:
        """Genuinely popular external accounts (utilities, employers, merchants) taken from the ČNB-derived background."""
        if len(self.popular_tokens) >= n:
            idx = self.rng.choice(len(self.popular_tokens), size=n, replace=False)
            return [self.popular_tokens[int(i)] for i in idx]
        return [self.new_ext_account() for _ in range(n)]

    def add_everyday(self, client_id: str, n_lo: int = 6, n_hi: int = 12) -> None:
        """Ordinary life: small payments to genuinely popular accounts (utilities, shops) at random times."""
        pool = self.popular_pool(20)
        for _ in range(int(self.rng.integers(n_lo, n_hi + 1))):
            self.add_tx(client_id, self.random_time(1, 28), float(self.rng.uniform(200, 2500)), "out", pool[int(self.rng.integers(0, len(pool)))])

    def new_client(self, bank_id: str, *, contract_date: datetime, contract_form: str = "in person",
                   client_type: str = "natural person", country: str = "CZ", pep: bool = False, aml_risk: str = "low",
                   expected_volume: float = 100000.0, expected_count: float = 30.0, q2_volume: float | None = None,
                   q2_count: float | None = None, q2_max: float | None = None) -> str:
        self._n_client += 1
        cid = f"R{self._n_client:05d}"
        self._bank_of[cid] = bank_id
        self.clients.append({
            "client_id": cid, "bank_id": bank_id, "client_country": country, "contract_date": contract_date,
            "contract_form": contract_form, "pep": pep, "client_type": client_type, "expected_volume": expected_volume,
            "expected_count": expected_count,
            "q2_volume": expected_volume * 3 if q2_volume is None else q2_volume,
            "q2_count": expected_count * 3 if q2_count is None else q2_count,
            "q2_max": expected_volume / 4 if q2_max is None else q2_max,
            "aml_risk": aml_risk, "source_dataset": "redteam", "derived": False,
        })
        return cid

    def add_tx(self, client_id: str, ts: datetime, amount_czk: float, direction: str, counterparty_token: str,
               country: str = "CZ", currency: str = "CZK") -> str:
        """direction in {'in','out','remit_out'}; the client's own account is the client id."""
        assert direction in ("in", "out", "remit_out")
        assert START <= ts <= END + timedelta(days=1), ts
        bank = self._bank_of[client_id]
        self._n_tx += 1
        txid = f"RT{self._n_tx:08d}"
        self.tx.append({
            "tx_id": txid, "bank_id": bank, "client_id": client_id, "ts": ts, "amount_czk": float(amount_czk),
            "amount_orig": float(amount_czk), "currency": currency, "direction": direction, "own_account": client_id,
            "counterparty_token": counterparty_token,
            "payer_country": country if direction != "in" else country, "payee_country": country,
            "channel_type": "remittance" if direction == "remit_out" else ("incoming payment" if direction == "in" else "outgoing payment"),
            "source_dataset": "redteam",
        })
        return txid

    def label(self, client_id: str, label: str, scheme: str, *, persona: str | None = None, instance: int = 0) -> None:
        """label in {'mule','honest','victim','organiser','background'}."""
        bank = self._bank_of[client_id]
        self.labels.append({"client_id": client_id, "bank_id": bank, "label": label, "scheme": scheme, "persona": persona,
                            "instance": instance})

    def random_time(self, day_from: int = 1, day_to: int = 28, hour_from: int = 6, hour_to: int = 22) -> datetime:
        d = int(self.rng.integers(day_from, day_to + 1))
        h = int(self.rng.integers(hour_from, hour_to))
        return datetime(2026, 7, d, h, int(self.rng.integers(0, 60)), int(self.rng.integers(0, 60)), tzinfo=UTC)
