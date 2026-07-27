# tests/api_clients/base_client.py
"""HTTP 基础客户端：封装请求、响应解析、Schema 校验"""
import httpx
import jsonschema


class BaseClient:
    """HTTP 基础客户端，供 WebClient / ApiClient 继承"""

    def __init__(self, base_url: str, headers: dict | None = None, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(
            base_url=self.base_url,
            headers=headers or {},
            timeout=timeout,
            verify=False,  # 测试环境可能用自签证书
        )

    def get(self, path: str, params: dict | None = None) -> dict:
        """发送 GET 请求，返回解析后的 JSON"""
        resp = self.client.get(path, params=params)
        return self._parse_response(resp)

    def post(self, path: str, json: dict | None = None) -> dict:
        """发送 POST 请求"""
        resp = self.client.post(path, json=json)
        return self._parse_response(resp)

    def put(self, path: str, json: dict | None = None) -> dict:
        """发送 PUT 请求"""
        resp = self.client.put(path, json=json)
        return self._parse_response(resp)

    def delete(self, path: str, params: dict | None = None) -> dict:
        """发送 DELETE 请求"""
        resp = self.client.delete(path, params=params)
        return self._parse_response(resp)

    def validate_schema(self, data: dict, schema: dict) -> None:
        """用 JSON Schema 校验响应结构，不符合则抛出 ValidationError"""
        jsonschema.validate(instance=data, schema=schema)

    def close(self):
        """释放 HTTP 连接"""
        self.client.close()

    def _parse_response(self, resp: httpx.Response) -> dict:
        """统一解析响应：检查状态码 + 解析 JSON"""
        resp.raise_for_status()
        return resp.json()
