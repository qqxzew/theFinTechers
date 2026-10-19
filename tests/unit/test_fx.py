import pytest

from ingest.fx import load_fx, to_czk


def test_load_and_convert(tmp_path):
    p = tmp_path / "fx.yaml"
    p.write_text("placeholder: true\nsource: test\nrates:\n  CZK: 1.0\n  EUR: 24.5\n")
    fx = load_fx(p)
    assert fx["placeholder"] is True
    assert to_czk(100, "EUR", fx) == pytest.approx(2450.0)
    assert to_czk(5, "CZK", fx) == 5


def test_unknown_currency_raises(tmp_path):
    p = tmp_path / "fx.yaml"
    p.write_text("placeholder: true\nsource: t\nrates:\n  CZK: 1.0\n")
    with pytest.raises(KeyError):
        to_czk(1, "XXX", load_fx(p))


def test_shipped_config_has_all_cnb_currencies():
    fx = load_fx("config/fx.yaml")
    assert fx["placeholder"] is True
    for c in "CZK EUR USD PLN CNY HUF RON GBP SEK DKK CHF JPY TRY NOK KRW AUD BRL CAD INR ISK MXN SGD ZAR".split():
        assert c in fx["rates"]
