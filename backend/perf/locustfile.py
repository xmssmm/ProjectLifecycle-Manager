from __future__ import annotations

import os
from datetime import date, timedelta
from random import randint
from typing import Any
from uuid import uuid4

from gevent.lock import Semaphore
from locust import HttpUser, between, task
from locust.clients import ResponseContextManager

API_PREFIX = os.getenv("PERF_API_PREFIX", "/api/v1")
ADMIN_USERNAME = os.getenv("PERF_ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("PERF_ADMIN_PASSWORD", "ChangeMe123!")
PERF_PASSWORD = os.getenv("PERF_TEST_PASSWORD", "PerfPass123!")
USER_PREFIX = os.getenv("PERF_USER_PREFIX", "perf")
PROMOTE_POOL_SIZE = int(os.getenv("PERF_PROMOTE_POOL_SIZE", "80"))
PDF_BYTES = b"%PDF-1.7\n1 0 obj<</Type/Catalog>>endobj\n%%EOF\n"


class SharedScenario:
    ready = False
    lock = Semaphore()
    data: dict[str, Any] = {}
    headers: dict[str, dict[str, str]] = {}
    promotable_phase_ids: list[str] = []


class ManagementApiLoadUser(HttpUser):
    wait_time = between(0.2, 1.0)

    admin_headers: dict[str, str]
    manager_headers: dict[str, str]
    leader_headers: dict[str, str]
    finance_headers: dict[str, str]
    data: dict[str, Any]

    def on_start(self) -> None:
        with SharedScenario.lock:
            if not SharedScenario.ready:
                self.admin_headers = self._login(
                    ADMIN_USERNAME,
                    ADMIN_PASSWORD,
                    name="setup login admin",
                )
                SharedScenario.data = self._provision_dataset()
                self.data = SharedScenario.data
                SharedScenario.headers = {
                    "admin": self.admin_headers,
                    "manager": self._login(
                        self.data["manager_a_username"],
                        PERF_PASSWORD,
                        name="setup login manager",
                    ),
                    "leader": self._login(
                        self.data["leader_username"],
                        PERF_PASSWORD,
                        name="setup login leader",
                    ),
                    "finance": self._login(
                        self.data["finance_username"],
                        PERF_PASSWORD,
                        name="setup login finance",
                    ),
                }
                self._load_shared_headers()
                SharedScenario.promotable_phase_ids = self._create_promotable_phase_pool(
                    PROMOTE_POOL_SIZE
                )
                SharedScenario.ready = True
        self.data = SharedScenario.data
        self._load_shared_headers()

    def _load_shared_headers(self) -> None:
        self.admin_headers = SharedScenario.headers["admin"]
        self.manager_headers = SharedScenario.headers["manager"]
        self.leader_headers = SharedScenario.headers["leader"]
        self.finance_headers = SharedScenario.headers["finance"]

    @task(2)
    def login(self) -> None:
        self._login(self.data["leader_username"], PERF_PASSWORD, name="POST /auth/login")

    @task(8)
    def list_main_projects(self) -> None:
        self.client.get(
            f"{API_PREFIX}/main-projects",
            headers=self.manager_headers,
            name="GET /main-projects",
            params={"page": 1, "page_size": 20},
        )

    @task(4)
    def upload_document(self) -> None:
        document_key = uuid4().hex
        files = {
            "file": (
                f"perf-upload-{document_key}.pdf",
                PDF_BYTES,
                "application/pdf",
            )
        }
        data = {
            "sub_project_id": self.data["sub_project_id"],
            "phase_id": self.data["upload_phase_id"],
            "doc_type": f"perf_attachment_{document_key}",
        }
        self.client.post(
            f"{API_PREFIX}/documents",
            headers=self.leader_headers,
            name="POST /documents",
            data=data,
            files=files,
        )

    @task(3)
    def promote_phase(self) -> None:
        phase_id = self._pop_promotable_phase_id()
        self.client.post(
            f"{API_PREFIX}/phases/{phase_id}/promote",
            headers=self.leader_headers,
            name="POST /phases/{id}/promote",
        )

    @task(4)
    def create_payment(self) -> None:
        files = {
            "files": (
                f"payment-{uuid4().hex}.pdf",
                PDF_BYTES,
                "application/pdf",
            )
        }
        data = {
            "amount": str(randint(10, 99)),
            "payment_date": date.today().isoformat(),
            "remark": "locust baseline payment",
        }
        self.client.post(
            f"{API_PREFIX}/sub-projects/{self.data['sub_project_id']}/payments",
            headers=self.finance_headers,
            name="POST /sub-projects/{id}/payments",
            data=data,
            files=files,
        )

    def _pop_promotable_phase_id(self) -> str:
        with SharedScenario.lock:
            if not SharedScenario.promotable_phase_ids:
                SharedScenario.promotable_phase_ids.extend(self._create_promotable_phase_pool(20))
            return SharedScenario.promotable_phase_ids.pop()

    def _provision_dataset(self) -> dict[str, Any]:
        department_id = self._ensure_department()
        manager_a = self._ensure_user("manager-a", "dept_manager", department_id)
        manager_b = self._ensure_user("manager-b", "dept_manager", department_id)
        leader = self._ensure_user("leader", "proj_leader", department_id)
        finance = self._ensure_user("finance", "finance_manager", department_id)

        manager_headers = self._login(manager_a["username"], PERF_PASSWORD, name="setup login")
        leader_headers = self._login(leader["username"], PERF_PASSWORD, name="setup login")
        reviewer_headers = self._login(manager_b["username"], PERF_PASSWORD, name="setup login")

        main_project = self._create_approved_main_project(
            department_id,
            manager_headers,
            reviewer_headers,
        )
        sub_project = self._create_approved_sub_project(
            department_id=department_id,
            main_project_id=main_project["id"],
            leader_headers=leader_headers,
            reviewer_headers=reviewer_headers,
        )
        phases = self._list_phases(sub_project["id"], leader_headers)
        phase_by_no = {phase["phase_no"]: phase for phase in phases}
        self._upload_required_phase_one_documents(
            sub_project["id"],
            phase_by_no[1]["id"],
            leader_headers,
        )

        return {
            "department_id": department_id,
            "manager_a_username": manager_a["username"],
            "leader_username": leader["username"],
            "finance_username": finance["username"],
            "main_project_id": main_project["id"],
            "sub_project_id": sub_project["id"],
            "upload_phase_id": phase_by_no[1]["id"],
        }

    def _create_promotable_phase_pool(self, count: int) -> list[str]:
        phase_ids: list[str] = []
        for _ in range(count):
            sub_project = self._create_approved_sub_project(
                department_id=self.data_or_shared("department_id"),
                main_project_id=self.data_or_shared("main_project_id"),
                leader_headers=self.leader_headers,
                reviewer_headers=self.manager_headers,
            )
            phases = self._list_phases(sub_project["id"], self.leader_headers)
            phase_one = next(phase for phase in phases if phase["phase_no"] == 1)
            self._upload_required_phase_one_documents(
                sub_project["id"], phase_one["id"], self.leader_headers
            )
            phase_ids.append(phase_one["id"])
        return phase_ids

    def data_or_shared(self, key: str) -> str:
        source = self.data if hasattr(self, "data") else SharedScenario.data
        return str(source[key])

    def _ensure_department(self) -> str:
        departments = self._get_json(
            f"{API_PREFIX}/departments",
            headers=self.admin_headers,
            name="setup GET /departments",
        )
        for department in departments:
            if department["code"] == f"{USER_PREFIX}-dept":
                return str(department["id"])
        created = self._post_json(
            f"{API_PREFIX}/departments",
            headers=self.admin_headers,
            json={"code": f"{USER_PREFIX}-dept", "name": "性能基线部门"},
            name="setup POST /departments",
        )
        return str(created["id"])

    def _ensure_user(self, suffix: str, role: str, department_id: str) -> dict[str, Any]:
        username = f"{USER_PREFIX}-{suffix}"
        users = self._get_json(
            f"{API_PREFIX}/users",
            headers=self.admin_headers,
            name="setup GET /users",
            params={"role": role, "page": 1, "page_size": 100},
        )
        for user in users["items"]:
            if user["username"] == username:
                self._post_json(
                    f"{API_PREFIX}/users/{user['id']}/reset-password",
                    headers=self.admin_headers,
                    json={"new_password": PERF_PASSWORD},
                    name="setup POST /users/{id}/reset-password",
                )
                return dict(user)
        return self._post_json(
            f"{API_PREFIX}/users",
            headers=self.admin_headers,
            json={
                "username": username,
                "password": PERF_PASSWORD,
                "role": role,
                "email": f"{username}@example.local",
                "dept_id": department_id,
            },
            name="setup POST /users",
        )

    def _create_approved_main_project(
        self,
        department_id: str,
        manager_headers: dict[str, str],
        reviewer_headers: dict[str, str],
    ) -> dict[str, Any]:
        created = self._post_json(
            f"{API_PREFIX}/main-projects",
            headers=manager_headers,
            json={
                "name": f"性能基线主项目-{uuid4().hex[:8]}",
                "dept_id": department_id,
                "total_budget": "1000000000000.00",
                "expected_finish_date": (date.today() + timedelta(days=90)).isoformat(),
                "remark": "locust baseline",
            },
            name="setup POST /main-projects",
        )
        self._post_json(
            f"{API_PREFIX}/main-projects/{created['id']}/submit",
            headers=manager_headers,
            json={},
            name="setup POST /main-projects/{id}/submit",
        )
        return self._post_json(
            f"{API_PREFIX}/main-projects/{created['id']}/review",
            headers=reviewer_headers,
            json={"decision": "approve", "review_comment": "locust approve"},
            name="setup POST /main-projects/{id}/review",
        )

    def _create_approved_sub_project(
        self,
        *,
        department_id: str,
        main_project_id: str,
        leader_headers: dict[str, str],
        reviewer_headers: dict[str, str],
    ) -> dict[str, Any]:
        created = self._post_json(
            f"{API_PREFIX}/sub-projects",
            headers=leader_headers,
            json={
                "name": f"性能基线子项目-{uuid4().hex[:8]}",
                "main_project_id": main_project_id,
                "dept_id": department_id,
                "budget": "1000000.00",
                "plan_end_date": (date.today() + timedelta(days=45)).isoformat(),
                "remark": "locust baseline",
            },
            name="setup POST /sub-projects",
        )
        self._post_json(
            f"{API_PREFIX}/sub-projects/{created['id']}/submit",
            headers=leader_headers,
            json={},
            name="setup POST /sub-projects/{id}/submit",
        )
        return self._post_json(
            f"{API_PREFIX}/sub-projects/{created['id']}/review",
            headers=reviewer_headers,
            json={"decision": "approve", "review_comment": "locust approve"},
            name="setup POST /sub-projects/{id}/review",
        )

    def _list_phases(self, sub_project_id: str, headers: dict[str, str]) -> list[dict[str, Any]]:
        payload = self._get_json(
            f"{API_PREFIX}/phases",
            headers=headers,
            params={"sub_project_id": sub_project_id},
            name="setup GET /phases",
        )
        return list(payload["items"])

    def _upload_required_phase_one_documents(
        self,
        sub_project_id: str,
        phase_id: str,
        headers: dict[str, str],
    ) -> None:
        for doc_type in ("meeting_material", "meeting_minutes"):
            files = {"file": (f"{doc_type}-{uuid4().hex}.pdf", PDF_BYTES, "application/pdf")}
            data = {"sub_project_id": sub_project_id, "phase_id": phase_id, "doc_type": doc_type}
            self._post_form(
                f"{API_PREFIX}/documents",
                headers=headers,
                data=data,
                files=files,
                name="setup POST /documents",
            )

    def _login(self, username: str, password: str, *, name: str) -> dict[str, str]:
        data = self._post_json(
            f"{API_PREFIX}/auth/login",
            headers={},
            json={"username": username, "password": password},
            name=name,
        )
        return {"Authorization": f"Bearer {data['access_token']}"}

    def _get_json(
        self,
        path: str,
        *,
        headers: dict[str, str],
        name: str,
        params: dict[str, object] | None = None,
    ) -> Any:
        with self.client.get(
            path,
            headers=headers,
            name=name,
            params=params,
            catch_response=True,
        ) as response:
            return self._unwrap(response)

    def _post_json(
        self,
        path: str,
        *,
        headers: dict[str, str],
        json: dict[str, object],
        name: str,
    ) -> Any:
        with self.client.post(
            path,
            headers=headers,
            json=json,
            name=name,
            catch_response=True,
        ) as response:
            return self._unwrap(response)

    def _post_form(
        self,
        path: str,
        *,
        headers: dict[str, str],
        data: dict[str, object],
        files: dict[str, tuple[str, bytes, str]],
        name: str,
    ) -> Any:
        with self.client.post(
            path,
            headers=headers,
            data=data,
            files=files,
            name=name,
            catch_response=True,
        ) as response:
            return self._unwrap(response)

    @staticmethod
    def _unwrap(response: ResponseContextManager) -> Any:
        try:
            payload = response.json()
        except ValueError:
            response.failure(f"non-json response: HTTP {response.status_code}")
            return {}
        if response.status_code >= 400 or payload.get("code") != 0:
            response.failure(f"HTTP {response.status_code}: {payload}")
            return {}
        response.success()
        return payload.get("data", {})
