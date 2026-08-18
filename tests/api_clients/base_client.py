# tests/api_clients/base_client.py
"""HTTP 基础客户端：封装请求、响应解析、Schema 校验"""
import time
import json
import httpx
import jsonschema

try:
    import allure
except ImportError:
    allure = None


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
        self._last_request_time = 0  # 请求节流：记录上次请求时间

    def get(self, path: str, params: dict | None = None) -> dict:
        """发送 GET 请求，返回解析后的 JSON"""
        resp = self._request_with_retry("get", path, params=params)
        return self._parse_response(resp)

    def post(self, path: str, params: dict | None = None, json: dict | None = None) -> dict:
        """发送 POST 请求"""
        resp = self._request_with_retry("post", path, params=params, json=json)
        return self._parse_response(resp)

    def put(self, path: str, params: dict | None = None, json: dict | None = None) -> dict:
        """发送 PUT 请求"""
        resp = self._request_with_retry("put", path, params=params, json=json)
        return self._parse_response(resp)

    def delete(self, path: str, params: dict | None = None, json: dict | None = None) -> dict:
        """发送 DELETE 请求"""
        resp = self._request_with_retry("delete", path, params=params, json=json)
        return self._parse_response(resp)

    def patch(self, path: str, params: dict | None = None, json: dict | None = None) -> dict:
        """发送 PATCH 请求"""
        resp = self._request_with_retry("patch", path, params=params, json=json)
        return self._parse_response(resp)

    def validate_schema(self, data: dict, schema: dict) -> None:
        """用 JSON Schema 校验响应结构，不符合则抛出 ValidationError"""
        jsonschema.validate(instance=data, schema=schema)

    def close(self):
        """释放 HTTP 连接"""
        self.client.close()

    def _request_with_retry(self, method: str, path: str, **kwargs) -> httpx.Response:
        """带重试的请求：遇到 500/502/503/429 自动重试
        - 请求节流：最小间隔 0.7s（服务端限流 100 req/min）
        - 5xx：重试 2 次（1s, 2s）
        - 429（限流）：按 Retry-After 头等待，最多重试 5 次
        """
        min_interval = 0.7  # 请求最小间隔（秒），避免撞 100 req/min 限流
        max_retries = 2
        rate_limit_retries = 5
        for attempt in range(max_retries + rate_limit_retries + 1):
            # 请求节流：距上次请求不足 min_interval 则等待
            now = time.time()
            if self._last_request_time and attempt == 0:
                elapsed = now - self._last_request_time
                if elapsed < min_interval:
                    time.sleep(min_interval - elapsed)
            self._last_request_time = time.time()

            # httpx 的 delete 方法不支持 json 参数，统一走 request
            if method == "delete" and "json" in kwargs:
                resp = self.client.request(method.upper(), path, **kwargs)
            else:
                resp = getattr(self.client, method)(path, **kwargs)

            # 429 限流：按 Retry-After 等待后重试
            if resp.status_code == 429 and attempt < rate_limit_retries:
                retry_after = int(resp.headers.get("Retry-After", "5"))
                time.sleep(min(retry_after, 65))  # 最多等 65s（服务端窗口 60s）
                continue

            if resp.status_code < 500 or attempt >= rate_limit_retries + max_retries:
                break
            time.sleep(1 * (attempt + 1))  # 递增延迟：1s, 2s
        self._attach_allure(method, path, kwargs, resp)
        return resp

    def _attach_allure(self, method: str, path: str, kwargs: dict, resp: httpx.Response):
        """将请求和响应信息附加到 Allure 报告"""
        if allure is None:
            return
        try:
            url = str(resp.request.url)
            # 请求信息
            req_parts = [
                f"{method.upper()} {url}",
                "",
                "── Headers ──",
            ]
            for k, v in resp.request.headers.items():
                req_parts.append(f"  {k}: {v}")
            req_body = kwargs.get("json")
            if req_body:
                req_parts += ["", "── Body ──", json.dumps(req_body, ensure_ascii=False, indent=2)]
            params = kwargs.get("params")
            if params:
                req_parts += ["", "── Params ──", json.dumps(params, ensure_ascii=False, indent=2)]
            allure.attach("\n".join(req_parts), name="请求", attachment_type=allure.attachment_type.TEXT)

            # 响应信息
            resp_parts = [
                f"Status: {resp.status_code}",
                "",
                "── Headers ──",
            ]
            for k, v in resp.headers.items():
                resp_parts.append(f"  {k}: {v}")
            resp_parts += ["", "── Body ──"]
            try:
                body = resp.json()
                resp_parts.append(json.dumps(body, ensure_ascii=False, indent=2))
            except Exception:
                resp_parts.append(resp.text[:2000])
            allure.attach("\n".join(resp_parts), name="响应", attachment_type=allure.attachment_type.TEXT)
        except Exception:
            pass  # Allure 附加不应影响测试执行

    def _parse_response(self, resp: httpx.Response) -> dict:
        """统一解析响应：检查状态码 + 解析 JSON"""
        resp.raise_for_status()
        try:
            return resp.json()
        except (ValueError, Exception):
            # 非 JSON 响应（如 SSE 流、纯文本）返回空 dict
            return {}
