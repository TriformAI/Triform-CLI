"""Triform API client with all endpoints."""

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Generator, Optional

from .config import Config


class APIError(Exception):
    """API request error."""
    def __init__(self, status_code: int, message: str, details: Any = None):
        self.status_code = status_code
        self.message = message
        self.details = details
        super().__init__(f"HTTP {status_code}: {message}")


@dataclass
class APIResponse:
    """API response wrapper."""
    success: bool
    data: Any = None
    error: Optional[str] = None


class TriformAPI:
    """Triform API client."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config.load()
        self._ssl_context = ssl.create_default_context()

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict] = None,
        params: Optional[dict] = None
    ) -> Any:
        """Make an authenticated API request."""
        if not self.config.auth_token:
            raise APIError(401, "Not authenticated. Run 'triform auth login' first.")

        url = f"{self.config.api_base_url}{endpoint}"
        if params:
            url += "?" + urllib.parse.urlencode(params)

        headers = {
            "Content-Type": "application/json",
            "Cookie": f"__Secure-better-auth.session_token={self.config.auth_token}"
        }

        body = json.dumps(data).encode() if data else None

        req = urllib.request.Request(url, data=body, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, context=self._ssl_context, timeout=300) as response:
                response_data = response.read().decode()
                if response_data:
                    return json.loads(response_data)
                return None
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else ""
            error_data = None
            try:
                error_data = json.loads(error_body)
                message = error_data.get("error", error_body)
            except json.JSONDecodeError:
                message = error_body or str(e)
            raise APIError(e.code, message, error_data)
        except urllib.error.URLError as e:
            raise APIError(0, f"Network error: {e.reason}")

    # ----- Projects -----

    def list_projects(self) -> list[dict]:
        """List all projects."""
        response = self._make_request("GET", "/projects")
        return response.get("data", [])

    def get_project(self, project_id: str) -> dict:
        """Get a project with resolved spec."""
        response = self._make_request("GET", f"/projects/{project_id}")
        return response.get("data", {})

    def create_project(self, meta: dict, spec: dict) -> dict:
        """Create a new project."""
        response = self._make_request("POST", "/projects", {
            "resource": "project/v1",
            "meta": meta,
            "spec": spec
        })
        return response.get("data", {})

    def update_project(self, project_id: str, meta: Optional[dict] = None, spec: Optional[dict] = None) -> dict:
        """Update a project."""
        data = {}
        if meta:
            data["meta"] = meta
        if spec:
            data["spec"] = spec
        response = self._make_request("PATCH", f"/projects/{project_id}", data)
        return response.get("data", {})

    def delete_project(self, project_id: str) -> dict:
        """Delete a project."""
        response = self._make_request("DELETE", f"/projects/{project_id}")
        return response.get("data", {})

    def deploy_project(self, project_id: str) -> dict:
        """Deploy a project."""
        response = self._make_request("POST", f"/projects/{project_id}/deploy")
        return response.get("data", {})

    def get_deployments(self, project_id: str) -> list[dict]:
        """Get project deployments."""
        response = self._make_request("GET", f"/projects/{project_id}/deployments")
        return response.get("data", [])

    def get_deployment_spec(self, project_id: str) -> dict:
        """Get the full spec from the latest active deployment."""
        # The deployments endpoint returns limited data, we need to query the deployed_projects table
        # For now, return what we can get from deployments
        deployments = self.get_deployments(project_id)
        if deployments:
            return deployments[0]  # Most recent
        return {}

    def get_project_requirements(self, project_id: str) -> dict:
        """Get project requirements."""
        response = self._make_request("GET", f"/projects/{project_id}/requirements")
        return response.get("data", {})

    def update_project_requirements(self, project_id: str, requirements: dict) -> dict:
        """Update project requirements."""
        response = self._make_request("PATCH", f"/projects/{project_id}/requirements", requirements)
        return response.get("data", {})

    # ----- Components -----

    def list_components(self) -> list[dict]:
        """List all components."""
        response = self._make_request("GET", "/components")
        return response.get("data", [])

    def get_component(self, component_id: str, depth: int = 0) -> dict:
        """Get a component with optional nested resolution."""
        params = {"depth": depth} if depth > 0 else None
        response = self._make_request("GET", f"/components/{component_id}", params=params)
        return response.get("data", {})

    def create_component(self, resource: str, meta: dict, spec: dict) -> dict:
        """Create a new component."""
        response = self._make_request("POST", "/components", {
            "resource": resource,
            "meta": meta,
            "spec": spec
        })
        return response.get("data", {})

    def update_component(self, component_id: str, meta: Optional[dict] = None, spec: Optional[dict] = None) -> dict:
        """Update a component."""
        data = {}
        if meta:
            data["meta"] = meta
        if spec:
            data["spec"] = spec
        response = self._make_request("PATCH", f"/components/{component_id}", data)
        return response.get("data", {})

    def delete_component(self, component_id: str) -> dict:
        """Delete a component."""
        response = self._make_request("DELETE", f"/components/{component_id}")
        return response.get("data", {})

    def build_component(self, component_id: str) -> dict:
        """Build an action's dependencies."""
        response = self._make_request("POST", f"/components/{component_id}/build")
        return response.get("data", {})

    def get_component_requirements(self, component_id: str) -> dict:
        """Get component requirements."""
        response = self._make_request("GET", f"/components/{component_id}/requirements")
        return response.get("data", {})

    def update_component_requirements(self, component_id: str, requirements: dict) -> dict:
        """Update component requirements."""
        response = self._make_request("PATCH", f"/components/{component_id}/requirements", requirements)
        return response.get("data", {})

    def generate_mock_inputs(self, component_id: str) -> dict:
        """Generate mock inputs for a component."""
        response = self._make_request("GET", f"/components/{component_id}/mock/inputs")
        return response.get("data", {})

    # ----- Users / Organizations -----

    def get_memberships(self) -> list[dict]:
        """Get current user's organization memberships."""
        response = self._make_request("GET", "/users/@me/memberships")
        return response.get("data", [])

    # ----- Execution -----

    def execute_run(self, execution: dict) -> dict:
        """Execute synchronously and return result."""
        response = self._make_request("POST", "/execute/run", execution)
        return response

    def execute_trace(self, execution: dict) -> Generator[dict, None, None]:
        """Execute with SSE tracing. Yields events as they arrive."""
        if not self.config.auth_token:
            raise APIError(401, "Not authenticated. Run 'triform auth login' first.")

        url = f"{self.config.api_base_url}/execute/trace"
        headers = {
            "Content-Type": "application/json",
            "Cookie": f"__Secure-better-auth.session_token={self.config.auth_token}",
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache"
        }

        body = json.dumps(execution).encode()
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, context=self._ssl_context, timeout=600) as response:
                buffer = ""
                # Read in chunks for chunked transfer encoding
                while True:
                    try:
                        chunk = response.read(4096)
                        if not chunk:
                            # End of stream - process any remaining buffer
                            if buffer.strip():
                                event = self._parse_sse_event(buffer)
                                if event:
                                    yield event
                            break

                        buffer += chunk.decode('utf-8', errors='replace')

                        # Parse SSE events (separated by double newlines)
                        while "\n\n" in buffer:
                            event_str, buffer = buffer.split("\n\n", 1)
                            event = self._parse_sse_event(event_str)
                            if event:
                                yield event
                    except Exception:
                        # Try to yield any remaining buffered event
                        if buffer.strip():
                            event = self._parse_sse_event(buffer)
                            if event:
                                yield event
                        break
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else ""
            raise APIError(e.code, error_body or str(e))

    def _parse_sse_event(self, event_str: str) -> Optional[dict]:
        """Parse an SSE event string into a dict."""
        event_type = None
        data = None

        for line in event_str.split("\n"):
            if line.startswith("event:"):
                event_type = line[6:].strip()
            elif line.startswith("data:"):
                data = line[5:].strip()

        if data:
            try:
                parsed_data = json.loads(data)
                if event_type:
                    parsed_data["event"] = event_type
                return parsed_data
            except json.JSONDecodeError:
                return {"event": event_type, "raw": data}
        return None

    def cancel_execution(self, execution_id: str) -> dict:
        """Cancel an execution."""
        response = self._make_request("POST", "/execute/cancel", {"id": execution_id})
        return response

    # ----- Executions History -----

    def list_executions(self, limit: int = 50) -> list[dict]:
        """List recent executions."""
        response = self._make_request("GET", "/executions", params={"limit": limit})
        return response.get("data", [])

    # ----- Auth -----

    def verify_auth(self) -> bool:
        """Verify the current auth token is valid."""
        try:
            self.list_projects()
            return True
        except APIError as e:
            if e.status_code == 401:
                return False
            raise

