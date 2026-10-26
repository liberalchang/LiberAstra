"""无限画布：图算法单元测试 + 画布 CRUD/分组/上传建档/隐藏过滤/发布的 API 测试。

执行链路只测「纯文本输入」这种不需要外部服务的分支；
功能节点的 ComfyUI 分发在 test_comfy.py 的 mock 体系之外,这里不覆盖。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from liberastra.providers.base import ProviderError
from liberastra.services.canvas_run import _family_tokens
from liberastra.services.canvas_graph import (
    canonical_fingerprint,
    detect_cycle,
    leaf_nodes,
    resolve_scope,
    substitute_prompt,
    topo_order,
)


def _graph(nodes: list[dict], edges: list[dict]) -> dict:
    return {"nodes": nodes, "edges": edges, "viewport": {"x": 0, "y": 0, "zoom": 1}}


def _node(nid: str, ntype: str = "input") -> dict:
    return {"id": nid, "type": ntype, "position": {"x": 0, "y": 0}, "data": {}}


def _edge(source: str, target: str) -> dict:
    return {"id": f"{source}-{target}", "source": source, "target": target}


# ---- 图算法 ----


def test_detect_cycle_none() -> None:
    graph = _graph([_node("a"), _node("b", "function")], [_edge("a", "b")])
    assert detect_cycle(graph) is None


def test_detect_cycle_found() -> None:
    graph = _graph(
        [_node("a", "function"), _node("b", "function")],
        [_edge("a", "b"), _edge("b", "a")],
    )
    assert detect_cycle(graph) in ("a", "b")


def test_leaf_nodes() -> None:
    graph = _graph(
        [_node("a"), _node("b", "function"), _node("c", "concat")],
        [_edge("a", "b"), _edge("b", "c")],
    )
    assert leaf_nodes(graph) == ["c"]


def test_resolve_scope_ancestors() -> None:
    graph = _graph(
        [_node("a"), _node("b", "function"), _node("c", "function"), _node("d", "function")],
        [_edge("a", "b"), _edge("b", "c"), _edge("c", "d")],
    )
    # 只执行到 b:b 后面的 c/d 不在范围内
    assert set(resolve_scope(graph, ["b"])) == {"a", "b"}


def test_resolve_scope_default_leaf() -> None:
    graph = _graph([_node("a"), _node("b", "function")], [_edge("a", "b")])
    assert set(resolve_scope(graph, None)) == {"a", "b"}


def test_resolve_scope_missing_target() -> None:
    graph = _graph([_node("a")], [])
    with pytest.raises(ProviderError):
        resolve_scope(graph, ["ghost"])


def test_topo_order() -> None:
    graph = _graph(
        [_node("a"), _node("b", "function"), _node("c", "concat")],
        [_edge("a", "b"), _edge("b", "c")],
    )
    order = topo_order(graph, ["a", "b", "c"])
    assert order.index("a") < order.index("b") < order.index("c")


def test_substitute_prompt() -> None:
    assert substitute_prompt("画一只{{animal}}", {"animal": "猫"}) == "画一只猫"
    with pytest.raises(ProviderError):
        substitute_prompt("{{missing}}", {})


def test_family_tokens() -> None:
    # 同家族不同量化/转换版本应共享词元
    assert _family_tokens("qwen3vl_4b_int8_convrot.safetensors") & _family_tokens(
        "qwen3vl_4b_int8.safetensors"
    )
    # 跨家族(flux3 vs qwen_image)无交集 → 触发回落
    assert not (
        _family_tokens("flux3-image-klein-int8-convrot.safetensors")
        & _family_tokens("qwen_image_21.safetensors")
    )


def test_fingerprint_stable_and_sensitive() -> None:
    a = canonical_fingerprint({"pack": "p", "inputs": {"x": 1, "y": 2}})
    b = canonical_fingerprint({"inputs": {"y": 2, "x": 1}, "pack": "p"})
    c = canonical_fingerprint({"pack": "p", "inputs": {"x": 1, "y": 3}})
    assert a == b
    assert a != c


# ---- API ----


def _create_canvas(client: TestClient, auth_header: dict[str, str], graph: dict | None = None) -> dict:
    resp = client.post(
        "/api/v1/canvases",
        json={"name": "测试画布", "graph": graph},
        headers=auth_header,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_canvas_crud_duplicate(client: TestClient, auth_header: dict[str, str]) -> None:
    graph = _graph([_node("n1"), _node("n2", "function")], [_edge("n1", "n2")])
    created = _create_canvas(client, auth_header, graph)
    assert created["name"] == "测试画布"
    assert created["graph"]["nodes"][0]["id"] == "n1"

    listed = client.get("/api/v1/canvases", headers=auth_header).json()
    assert any(c["id"] == created["id"] and c["node_count"] == 2 for c in listed)

    fetched = client.get(f"/api/v1/canvases/{created['id']}", headers=auth_header)
    assert fetched.status_code == 200
    assert fetched.json()["node_runs"] == []

    updated = client.put(
        f"/api/v1/canvases/{created['id']}",
        json={"name": "改名"},
        headers=auth_header,
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "改名"

    dup = client.post(f"/api/v1/canvases/{created['id']}/duplicate", headers=auth_header)
    assert dup.status_code == 201
    assert dup.json()["name"] == "改名 副本"
    assert dup.json()["id"] != created["id"]

    deleted = client.delete(f"/api/v1/canvases/{dup.json()['id']}", headers=auth_header)
    assert deleted.status_code == 204


def test_canvas_reject_cycle(client: TestClient, auth_header: dict[str, str]) -> None:
    graph = _graph(
        [_node("a", "function"), _node("b", "function")],
        [_edge("a", "b"), _edge("b", "a")],
    )
    resp = client.post(
        "/api/v1/canvases", json={"name": "环", "graph": graph}, headers=auth_header
    )
    assert resp.status_code == 400


def test_canvas_reject_duplicate_var_names(client: TestClient, auth_header: dict[str, str]) -> None:
    """输出变量名是画布级命名空间:重名拒绝保存。"""
    a = _node("a")
    a["data"] = {"mediaKind": "text", "text": "x", "varName": "input_text_1"}
    b = _node("b")
    b["data"] = {"mediaKind": "text", "text": "y", "varName": "input_text_1"}
    resp = client.post(
        "/api/v1/canvases",
        json={"name": "重名", "graph": _graph([a, b], [])},
        headers=auth_header,
    )
    assert resp.status_code == 400
    assert "变量名" in resp.json()["detail"]


def test_canvas_groups_autoinit(client: TestClient, auth_header: dict[str, str]) -> None:
    resp = client.get("/api/v1/canvases/groups", headers=auth_header)
    assert resp.status_code == 200
    groups = resp.json()
    # 内置包至少会初始化出文生图分组
    assert "文生图" in groups
    assert groups["文生图"]

    groups["自定义组"] = [groups["文生图"][0]]
    saved = client.put("/api/v1/canvases/groups", json=groups, headers=auth_header)
    assert saved.status_code == 200
    reread = client.get("/api/v1/canvases/groups", headers=auth_header).json()
    assert "自定义组" in reread

    # 不存在的包名会被清洗掉
    dirty = client.put(
        "/api/v1/canvases/groups", json={"组": ["no_such_pack"]}, headers=auth_header
    )
    assert dirty.json() == {"组": []}


def test_upload_as_asset_and_publish(client: TestClient, auth_header: dict[str, str]) -> None:
    resp = client.post(
        "/api/v1/uploads?as_asset=true&kind=image",
        files={"file": ("pixel.png", b"\x89PNG\r\n\x1a\nfake", "image/png")},
        headers=auth_header,
    )
    assert resp.status_code == 201, resp.text
    asset_id = resp.json()["asset_id"]
    assert asset_id

    # 上传建档默认不隐藏,资源库可见
    listed = client.get("/api/v1/assets?kind=image&limit=200", headers=auth_header).json()
    assert any(a["id"] == asset_id for a in listed)
    target = next(a for a in listed if a["id"] == asset_id)
    assert target["hidden"] is False

    # publish 幂等:公开资产再发布依然 200
    pub = client.post(f"/api/v1/assets/{asset_id}/publish", headers=auth_header)
    assert pub.status_code == 200
    assert pub.json()["hidden"] is False


def test_run_text_only_chain(client: TestClient, auth_header: dict[str, str]) -> None:
    """纯文本输入节点链无需外部服务即可执行成功。"""
    text_node = _node("t1")
    text_node["data"] = {"mediaKind": "text", "text": "一只猫", "varName": "animal"}
    graph = _graph([text_node], [])
    created = _create_canvas(client, auth_header, graph)

    resp = client.post(
        f"/api/v1/canvases/{created['id']}/run", json={}, headers=auth_header
    )
    assert resp.status_code == 202, resp.text
    plan = resp.json()["plan"]
    assert [p["node_id"] for p in plan] == ["t1"]

    import time

    runs: dict = {}
    for _ in range(50):
        detail = client.get(f"/api/v1/canvases/{created['id']}", headers=auth_header).json()
        runs = {r["node_id"]: r for r in detail["node_runs"]}
        if runs.get("t1", {}).get("status") == "succeeded":
            break
        time.sleep(0.1)
    assert runs["t1"]["status"] == "succeeded"

    client.delete(f"/api/v1/canvases/{created['id']}", headers=auth_header)


def test_run_unknown_node_type_fails(client: TestClient, auth_header: dict[str, str]) -> None:
    """功能节点没选包 → 执行标记失败而不是拖垮整个画布。"""
    func = _node("f1", "function")
    graph = _graph([func], [])
    created = _create_canvas(client, auth_header, graph)
    resp = client.post(
        f"/api/v1/canvases/{created['id']}/run", json={}, headers=auth_header
    )
    assert resp.status_code == 202

    import time

    runs: dict = {}
    for _ in range(50):
        detail = client.get(f"/api/v1/canvases/{created['id']}", headers=auth_header).json()
        runs = {r["node_id"]: r for r in detail["node_runs"]}
        if runs.get("f1", {}).get("status") == "failed":
            break
        time.sleep(0.1)
    assert runs["f1"]["status"] == "failed"
    assert "工作流包" in (runs["f1"]["error"] or "")

    client.delete(f"/api/v1/canvases/{created['id']}", headers=auth_header)


def test_run_missing_target_400(client: TestClient, auth_header: dict[str, str]) -> None:
    created = _create_canvas(client, auth_header)
    resp = client.post(
        f"/api/v1/canvases/{created['id']}/run",
        json={"node_ids": ["ghost"]},
        headers=auth_header,
    )
    assert resp.status_code == 400
    client.delete(f"/api/v1/canvases/{created['id']}", headers=auth_header)


def _wait_node(client: TestClient, auth_header: dict[str, str], canvas_id: str, node_id: str) -> dict:
    import time

    for _ in range(60):
        detail = client.get(f"/api/v1/canvases/{canvas_id}", headers=auth_header).json()
        runs = {r["node_id"]: r for r in detail["node_runs"]}
        status = runs.get(node_id, {}).get("status")
        if status in ("succeeded", "failed", "canceled"):
            return runs[node_id]
        time.sleep(0.1)
    raise AssertionError(f"节点 {node_id} 未到达终态: {runs}")


def test_run_speech_asr_requires_audio(client: TestClient, auth_header: dict[str, str]) -> None:
    """asr 节点不连音频输入 → 明确报错而不是崩溃。"""
    asr = _node("s1", "speech")
    asr["data"] = {"mode": "asr", "language": ""}
    created = _create_canvas(client, auth_header, _graph([asr], []))
    resp = client.post(f"/api/v1/canvases/{created['id']}/run", json={}, headers=auth_header)
    assert resp.status_code == 202
    run = _wait_node(client, auth_header, created["id"], "s1")
    assert run["status"] == "failed"
    assert "音频" in (run["error"] or "")
    client.delete(f"/api/v1/canvases/{created['id']}", headers=auth_header)


def test_run_speech_tts_without_provider_fails_cleanly(
    client: TestClient, auth_header: dict[str, str]
) -> None:
    """测试环境没有 tts Provider:任务失败且节点状态落库,错误可读。"""
    tts = _node("s1", "speech")
    tts["data"] = {"mode": "tts", "text": "你好"}
    created = _create_canvas(client, auth_header, _graph([tts], []))
    resp = client.post(f"/api/v1/canvases/{created['id']}/run", json={}, headers=auth_header)
    assert resp.status_code == 202
    run = _wait_node(client, auth_header, created["id"], "s1")
    assert run["status"] == "failed"
    assert run["job_id"]  # 提交了真实 Job(任务页可见)
    client.delete(f"/api/v1/canvases/{created['id']}", headers=auth_header)
