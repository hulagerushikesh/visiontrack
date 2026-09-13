"""Contract tests for the incremental React migration."""
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_product_routes_use_react_shell() -> None:
    config = json.loads((ROOT / "vercel.json").read_text())
    routes = {route["src"]: route["dest"] for route in config["routes"]}
    assert routes["/"] == "/app/index.html"
    assert routes["/teaching/?"] == "/app/index.html"
    assert routes["/video/?"] == "/app/index.html"


def test_high_risk_interactive_routes_remain_standalone() -> None:
    config = json.loads((ROOT / "vercel.json").read_text())
    routes = {route["src"]: route["dest"] for route in config["routes"]}
    assert routes["/live/?"] == "/web/live.html"
    assert routes["/study/?"] == "/learning/LEARNING_PATH.html"
    assert routes["/roadmap/?"] == "/learning/CV_ROADMAP.html"
    assert routes["/demo/?"] == "/viz/webdemo/index.html"
