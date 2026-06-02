import pytest


@pytest.mark.asyncio
async def test_graph_builds():
    from app.graph.builder import build_graph
    g = build_graph()
    assert g is not None
    assert len(g.nodes) > 0


def test_graph_routing_crisis():
    from app.graph.builder import route_by_phase
    assert route_by_phase({"phase": "Кризис"}) == "crisis_node"


def test_graph_routing_defense():
    from app.graph.builder import route_by_phase
    assert route_by_phase({"phase": "Защита"}) == "defense_node"


def test_graph_routing_wings():
    from app.graph.builder import route_by_phase
    assert route_by_phase({"phase": "Крылья"}) == "wings_interviewer_node"


def test_graph_routing_unknown():
    from app.graph.builder import route_by_phase
    assert route_by_phase({"phase": "unknown"}) == "wings_interviewer_node"
