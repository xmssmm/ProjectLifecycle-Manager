from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.v1.payments import get_payment_service
from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.exceptions import BusinessException, ValidationFailedError
from app.core.middleware import InMemoryRateLimitStore
from app.main import create_app
from app.models.main_projects import MainProject, MainProjectStatus
from app.models.payments import Payment, PaymentType
from app.models.phases import Phase, PhaseStatus
from app.models.sub_projects import SubProject, SubProjectStatus
from app.models.users import User, UserRole, UserStatus
from app.services.notifications import InMemoryNotificationRepository, NotificationService
from app.services.payments import (
    InMemoryPaymentRepository,
    PaymentService,
    PaymentVoucherUpload,
)
from app.storage.base import StorageBackend


class RecordingStorage(StorageBackend):
    def __init__(self) -> None:
        self.saved: list[tuple[str, str, str, bytes]] = []
        self.deleted: list[str] = []

    def save(self, *, sub_id: str, phase_id: str, filename: str, content: bytes) -> str:
        self.saved.append((sub_id, phase_id, filename, content))
        return f"{sub_id}/{phase_id}/{len(self.saved)}-{filename}"

    def read(self, storage_key: str) -> bytes:
        raise NotImplementedError

    def delete(self, storage_key: str) -> None:
        self.deleted.append(storage_key)

    def get_url(self, storage_key: str) -> str:
        return f"/storage/{storage_key}"


def make_user(role: UserRole, *, username: str, dept_id: UUID | None = None) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        username=username,
        email=f"{username}@example.local",
        password_hash="hashed",
        role=role,
        dept_id=dept_id,
        status=UserStatus.active,
        password_changed_at=now,
        last_login_at=None,
        created_at=now,
        updated_at=now,
    )


def make_main_project(*, dept_id: UUID, creator_id: UUID) -> MainProject:
    now = datetime.now(UTC)
    return MainProject(
        id=uuid4(),
        project_no="Z-2026-0001",
        name="主项目",
        dept_id=dept_id,
        status=MainProjectStatus.in_progress,
        total_budget=Decimal("1000.00"),
        expected_finish_date=date(2026, 12, 31),
        spent_amount=Decimal("0.00"),
        remark=None,
        creator_id=creator_id,
        created_at=now,
        updated_at=now,
    )


def make_sub_project(main_project: MainProject, manager: User) -> SubProject:
    now = datetime.now(UTC)
    return SubProject(
        id=uuid4(),
        project_no="Z-2026-0001-ZX-001",
        name="采购实施",
        main_project_id=main_project.id,
        dept_id=main_project.dept_id,
        budget=Decimal("1000.00"),
        manager_id=manager.id,
        creator_id=manager.id,
        status=SubProjectStatus.in_progress,
        plan_end_date=date(2026, 10, 31),
        actual_end_date=None,
        spent_amount=Decimal("0.00"),
        remark=None,
        created_at=now,
        updated_at=now,
    )


def make_payment_phase(sub_project: SubProject) -> Phase:
    now = datetime.now(UTC)
    return Phase(
        id=uuid4(),
        sub_project_id=sub_project.id,
        phase_no=5,
        code="payment",
        name="付款",
        status=PhaseStatus.in_progress,
        enter_at=now,
        finish_at=None,
        procurement_type=None,
        created_at=now,
        updated_at=now,
    )


def make_service() -> tuple[
    PaymentService,
    InMemoryPaymentRepository,
    RecordingStorage,
    User,
    SubProject,
    MainProject,
    InMemoryNotificationRepository,
]:
    dept_id = uuid4()
    finance = make_user(UserRole.finance_manager, username="finance", dept_id=dept_id)
    leader = make_user(UserRole.proj_leader, username="leader", dept_id=dept_id)
    manager = make_user(UserRole.dept_manager, username="manager", dept_id=dept_id)
    admin = make_user(UserRole.admin, username="admin")
    main_project = make_main_project(dept_id=dept_id, creator_id=manager.id)
    sub_project = make_sub_project(main_project, leader)
    phase = make_payment_phase(sub_project)
    repository = InMemoryPaymentRepository(
        main_projects=[main_project],
        phases=[phase],
        sub_projects=[sub_project],
        users=[finance, leader, manager, admin],
    )
    notifications = InMemoryNotificationRepository()
    storage = RecordingStorage()
    service = PaymentService(
        repository=repository,
        storage=storage,
        max_file_size_bytes=1024,
        notification_service=NotificationService(repository=notifications),
    )
    return service, repository, storage, finance, sub_project, main_project, notifications


@pytest.mark.asyncio
async def test_create_payment_uploads_voucher_and_updates_spent_amounts() -> None:
    service, repository, storage, finance, sub_project, main_project, notifications = make_service()

    payment = await service.create_payment(
        actor=finance,
        sub_project_id=sub_project.id,
        amount=Decimal("120.50"),
        payment_date=date(2026, 5, 10),
        remark="首付款",
        voucher_files=[
            PaymentVoucherUpload(
                file_name="voucher.pdf",
                content_type="application/pdf",
                content=b"%PDF-1.7\nvoucher",
            ),
        ],
    )

    assert payment.payment_no == "Z-2026-0001-ZX-001-PAY-001"
    assert payment.payment_type == PaymentType.normal
    assert sub_project.spent_amount == Decimal("120.50")
    assert main_project.spent_amount == Decimal("120.50")
    assert len(repository.documents) == 1
    assert repository.documents[0].doc_type == "payment_voucher"
    assert len(repository.payment_vouchers) == 1
    assert repository.payment_vouchers[0].payment_id == payment.id
    assert storage.saved == [
        (
            str(sub_project.id),
            str(repository.payment_phase.id),
            "voucher.pdf",
            b"%PDF-1.7\nvoucher",
        ),
    ]
    assert [notification.scenario for notification in notifications.notifications] == [
        "payment_created",
    ]


@pytest.mark.asyncio
async def test_create_payment_requires_voucher_and_over_budget_confirmation() -> None:
    service, _repository, _storage, finance, sub_project, _main_project, _notifications = (
        make_service()
    )

    with pytest.raises(ValidationFailedError):
        await service.create_payment(
            actor=finance,
            sub_project_id=sub_project.id,
            amount=Decimal("10.00"),
            payment_date=date(2026, 5, 10),
            voucher_files=[],
        )

    with pytest.raises(BusinessException) as exc_info:
        await service.create_payment(
            actor=finance,
            sub_project_id=sub_project.id,
            amount=Decimal("1001.00"),
            payment_date=date(2026, 5, 10),
            voucher_files=[
                PaymentVoucherUpload(
                    file_name="voucher.pdf",
                    content_type="application/pdf",
                    content=b"%PDF-1.7\nvoucher",
                ),
            ],
        )

    assert exc_info.value.code == 3001
    assert exc_info.value.data["budget"] == "1000.00"
    assert exc_info.value.data["over_amount"] == "1.00"


@pytest.mark.asyncio
async def test_confirmed_over_budget_payment_notifies_manager_and_admin() -> None:
    service, _repository, _storage, finance, sub_project, _main_project, notifications = (
        make_service()
    )

    await service.create_payment(
        actor=finance,
        sub_project_id=sub_project.id,
        amount=Decimal("1001.00"),
        payment_date=date(2026, 5, 10),
        over_budget_reason="专项审批通过",
        confirm_over_budget=True,
        voucher_files=[
            PaymentVoucherUpload(
                file_name="voucher.pdf",
                content_type="application/pdf",
                content=b"%PDF-1.7\nvoucher",
            ),
        ],
    )

    assert sorted(notification.scenario for notification in notifications.notifications) == [
        "over_budget_warning",
        "over_budget_warning",
        "payment_created",
    ]


@pytest.mark.asyncio
async def test_concurrent_payments_do_not_drift_spent_amount() -> None:
    service, repository, _storage, finance, sub_project, main_project, _notifications = (
        make_service()
    )

    async def create_payment(index: int) -> Payment:
        return await service.create_payment(
            actor=finance,
            sub_project_id=sub_project.id,
            amount=Decimal("10.00"),
            payment_date=date(2026, 5, 10),
            remark=f"batch-{index}",
            voucher_files=[
                PaymentVoucherUpload(
                    file_name=f"voucher-{index}.pdf",
                    content_type="application/pdf",
                    content=b"%PDF-1.7\nvoucher",
                ),
            ],
        )

    payments = await asyncio.gather(*(create_payment(index) for index in range(10)))

    assert len(payments) == 10
    assert sorted(payment.payment_no for payment in payments) == [
        f"Z-2026-0001-ZX-001-PAY-{index:03d}" for index in range(1, 11)
    ]
    assert sub_project.spent_amount == Decimal("100.00")
    assert main_project.spent_amount == Decimal("100.00")
    assert sum(payment.amount for payment in repository.payments) == Decimal("100.00")


def test_create_payment_endpoint_accepts_multipart_payload() -> None:
    finance = make_user(UserRole.finance_manager, username="finance")
    sub_project_id = uuid4()
    expected_sub_project_id = sub_project_id
    payment = Payment(
        id=uuid4(),
        payment_no="Z-2026-0001-ZX-001-PAY-001",
        sub_project_id=sub_project_id,
        amount=Decimal("120.50"),
        payment_date=date(2026, 5, 10),
        remark="首付款",
        payment_type=PaymentType.normal,
        reverses_payment_id=None,
        operator_id=finance.id,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    class FakePaymentService:
        async def create_payment(
            self,
            *,
            actor: User,
            sub_project_id: UUID,
            amount: Decimal,
            payment_date: date,
            voucher_files: list[PaymentVoucherUpload],
            remark: str | None = None,
            confirm_over_budget: bool = False,
            over_budget_reason: str | None = None,
        ) -> Payment:
            assert actor.id == finance.id
            assert sub_project_id == expected_sub_project_id
            assert amount == Decimal("120.50")
            assert payment_date == date(2026, 5, 10)
            assert remark == "首付款"
            assert confirm_over_budget is True
            assert over_budget_reason == "专项审批通过"
            assert voucher_files[0].file_name == "voucher.pdf"
            assert voucher_files[0].content == b"%PDF-1.7\nvoucher"
            return payment

    async def fake_db_session() -> AsyncIterator[object]:
        yield object()

    async def fake_current_user() -> User:
        return finance

    async def fake_payment_service() -> FakePaymentService:
        return FakePaymentService()

    app = create_app(rate_limit_store=InMemoryRateLimitStore())
    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_payment_service] = fake_payment_service
    client = TestClient(app)

    response = client.post(
        f"/api/v1/sub-projects/{sub_project_id}/payments",
        data={
            "amount": "120.50",
            "payment_date": "2026-05-10",
            "remark": "首付款",
            "confirm_over_budget": "true",
            "over_budget_reason": "专项审批通过",
        },
        files=[("files", ("voucher.pdf", b"%PDF-1.7\nvoucher", "application/pdf"))],
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["payment_no"] == "Z-2026-0001-ZX-001-PAY-001"
    assert payload["amount"] == "120.50"
