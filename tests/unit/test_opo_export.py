from copilot.opo_draft import SECTIONS, TITLES, build_opo, load_settings, to_markdown
from export.opo_export import opo_to_pdf
from tests.unit.test_copilot_core import CASE


def test_opo_has_ten_sections_no_analyst_and_exports_pdf(tmp_path):
    sv = {"sentences": [{"text": "Příchozí platba 250000 Kč byla do 24 h odeslána dál.", "refs": ["D1:R00001"]}], "violations": []}
    opo = build_opo(CASE, sv, load_settings(), "ab" * 32, "2026-10-19")
    assert [s["no"] for s in opo["sections"]] == SECTIONS and len(opo["sections"]) == 10
    text = to_markdown(opo)
    assert "DOPLNÍ ČLOVĚK" in opo["sections"][5]["text"] and "DOPLNÍ ČLOVĚK" in opo["sections"][8]["text"]   # VI and IX are for the human
    assert "NÁVRH" in text and "SYNTETICK" in text.upper()
    assert all(TITLES[k] in text for k in SECTIONS)
    out = opo_to_pdf(opo, str(tmp_path / "opo.pdf"))
    data = open(out, "rb").read()
    assert data[:5] == b"%PDF-" and len(data) > 3000
