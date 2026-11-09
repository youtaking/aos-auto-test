# tests/api_suites/test_model_gateway_api.py
"""Model Gateway 接口测试

覆盖：
- Web 控制台 /web/model-gateway/:providerId/usage（session cookie）
- System API /api/system/model-gateway/*（System API Key，只读）

用量查询需要 YYYY-MM-DD 的 startAt/endAt；上游网关不可达时返回 400 MODEL_GATEWAY_ERROR，
因此只对参数契约做断言，不把上游可用性作为用例前提。
"""
import httpx
import pytest


def _get_gateway_provider_id(web_client) -> str:
    """取一个 provider id 用于路径参数（不可见时接口会返回 403/400，同样能覆盖契约）。"""
    data = web_client.list_providers()
    providers = data.get("providers", data) if isinstance(data, dict) else data
    if not providers:
        pytest.skip("Provider 列表为空，无法测试模型网关用量")
    return providers[0]["id"]


class TestModelGatewayWebAPI:
    """/web/model-gateway 控制台接口测试"""

    @pytest.mark.p1
    def test_usage_missing_start_at(self, web_client):
        """用量查询缺少 startAt：应返回 400 VALIDATION_ERROR"""
        provider_id = _get_gateway_provider_id(web_client)
        resp = web_client.client.get(f"/web/model-gateway/{provider_id}/usage")
        assert resp.status_code == 400, f"期望 400，实际 {resp.status_code}: {resp.text[:200]}"
        err = resp.json().get("error", {})
        assert err.get("type") == "VALIDATION_ERROR"
        assert "startAt" in err.get("message", "")

    @pytest.mark.p1
    def test_usage_missing_end_at(self, web_client):
        """用量查询缺少 endAt：应返回 400 VALIDATION_ERROR"""
        provider_id = _get_gateway_provider_id(web_client)
        resp = web_client.client.get(
            f"/web/model-gateway/{provider_id}/usage", params={"startAt": "2026-01-01"}
        )
        assert resp.status_code == 400, f"期望 400，实际 {resp.status_code}: {resp.text[:200]}"
        err = resp.json().get("error", {})
        assert err.get("type") == "VALIDATION_ERROR"
        assert "endAt" in err.get("message", "")

    @pytest.mark.p2
    def test_usage_invalid_date_format(self, web_client):
        """用量查询日期格式非法：应返回 400 VALIDATION_ERROR"""
        provider_id = _get_gateway_provider_id(web_client)
        resp = web_client.client.get(
            f"/web/model-gateway/{provider_id}/usage",
            params={"startAt": "2026/01/01", "endAt": "2026/02/01"},
        )
        assert resp.status_code == 400, f"期望 400，实际 {resp.status_code}: {resp.text[:200]}"
        err = resp.json().get("error", {})
        assert err.get("type") == "VALIDATION_ERROR"
        assert "startAt" in err.get("message", "")


class TestModelGatewaySystemAPI:
    """/api/system/model-gateway 只读接口测试（System API Key）"""

    @pytest.mark.p1
    def test_get_config(self, api_client, system_access):
        """获取模型网关配置：provider 结构与 adminUiUrl"""
        data = api_client.get_system_model_gateway_config()
        provider = data.get("provider", {})
        assert isinstance(provider.get("id"), str)
        assert isinstance(provider.get("name"), str)
        assert isinstance(provider.get("baseUrl"), str)
        assert "adminUiUrl" in data

    @pytest.mark.p1
    def test_list_keys(self, api_client, system_access):
        """获取模型网关 Key 列表：items 为数组"""
        data = api_client.list_system_model_gateway_keys(params={"page": 1, "pageSize": 10})
        assert isinstance(data.get("items"), list)
        assert isinstance(data.get("total"), int)

    @pytest.mark.p1
    def test_list_budgets(self, api_client, system_access):
        """获取模型网关预算列表：items 为数组"""
        data = api_client.list_system_model_gateway_budgets(params={"page": 1, "pageSize": 10})
        assert isinstance(data.get("items"), list)
        assert isinstance(data.get("total"), int)

    @pytest.mark.p1
    def test_get_models_status(self, api_client, system_access):
        """获取模型同步状态：status/models 字段存在"""
        data = api_client.get_system_model_gateway_models_status()
        assert isinstance(data.get("status"), str)
        assert isinstance(data.get("models"), list)
        assert isinstance(data.get("changes"), list)

    @pytest.mark.p1
    def test_list_subject_users(self, api_client, system_access):
        """获取计费主体（用户）：items 为数组"""
        data = api_client.list_system_model_gateway_subjects_users(
            params={"page": 1, "pageSize": 10}
        )
        assert isinstance(data.get("items"), list)

    @pytest.mark.p1
    def test_list_subject_agents(self, api_client, system_access):
        """获取计费主体（Agent）：返回数组"""
        data = api_client.list_system_model_gateway_subjects_agents()
        assert isinstance(data, list)

    @pytest.mark.p2
    def test_usage_missing_start_at(self, api_client, system_access):
        """系统用量查询缺少 startAt：应返回 400 VALIDATION_ERROR"""
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            api_client.get_system_model_gateway_usage()
        assert exc_info.value.response.status_code == 400
        err = exc_info.value.response.json().get("error", {})
        assert err.get("type") == "VALIDATION_ERROR"
        assert "startAt" in err.get("message", "")
