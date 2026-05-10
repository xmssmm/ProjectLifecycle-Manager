from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    BusinessException,
    PermissionDeniedError,
    ResourceNotFoundError,
    ValidationFailedError,
)
from app.models.documents import Document
from app.models.main_projects import MainProject
from app.models.payments import Payment, PaymentType, PaymentVoucher
from app.models.phases import Phase
from app.models.sub_projects import SubProject
from app.models.users import User, UserRole, UserStatus
from app.services.notifications import NotificationService
from app.storage.base import StorageBackend, StorageSecurityError
from app.validators.file_validator import DefaultFileValidator, FileValidationError, FileValidator

PAYMENT_PHASE_NO = 5
PAYMENT_VOUCHER_DOC_TYPE = "payment_voucher"
TWO_PLACES = Decimal("0.01")


@dataclass(frozen=True)
class PaymentVoucherUpload:
    file_name: str
    content_type: str | None
    content: bytes


class PaymentRepository(Protocol):
    async def get_sub_project_for_update(self, sub_project_id: UUID) -> SubProject | None:
        ...

    async def get_main_project_for_update(self, main_project_id: UUID) -> MainProject | None:
        ...

    async def get_payment_phase(self, sub_project_id: UUID) -> Phase | None:
        ...

    async def list_group_documents_for_update(
        self,
        *,
        sub_project_id: UUID,
        phase_id: UUID,
        doc_type: str,
    ) -> list[Document]:
        ...

    async def next_payment_sequence(self, sub_project_id: UUID) -> int:
        ...

    async def sum_payments(self, sub_project_id: UUID) -> Decimal:
        ...

    async def sum_sub_project_spent(self, main_project_id: UUID) -> Decimal:
        ...

    async def list_active_user_ids_by_role(
        self,
        *,
        role: UserRole,
        dept_id: UUID | None = None,
    ) -> list[UUID]:
        ...

    def add_payment(self, payment: Payment) -> None:
        ...

    def add_document(self, document: Document) -> None:
        ...

    def add_payment_voucher(self, payment_voucher: PaymentVoucher) -> None:
        ...

    async def flush(self) -> None:
        ...

    async def commit(self) -> None:
        ...

    async def rollback(self) -> None:
        ...

    async def refresh_payment(self, payment: Payment) -> None:
        ...


class SqlAlchemyPaymentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_sub_project_for_update(self, sub_project_id: UUID) -> SubProject | None:
        sub_project = await self._session.scalar(
            select(SubProject).where(SubProject.id == sub_project_id).with_for_update(),
        )
        return sub_project if isinstance(sub_project, SubProject) else None

    async def get_main_project_for_update(self, main_project_id: UUID) -> MainProject | None:
        main_project = await self._session.scalar(
            select(MainProject).where(MainProject.id == main_project_id).with_for_update(),
        )
        return main_project if isinstance(main_project, MainProject) else None

    async def get_payment_phase(self, sub_project_id: UUID) -> Phase | None:
        phase = await self._session.scalar(
            select(Phase)
            .where(
                Phase.sub_project_id == sub_project_id,
                Phase.phase_no == PAYMENT_PHASE_NO,
            )
            .with_for_update(),
        )
        return phase if isinstance(phase, Phase) else None

    async def list_group_documents_for_update(
        self,
        *,
        sub_project_id: UUID,
        phase_id: UUID,
        doc_type: str,
    ) -> list[Document]:
        result = await self._session.scalars(
            select(Document)
            .where(
                Document.sub_project_id == sub_project_id,
                Document.phase_id == phase_id,
                Document.doc_type == doc_type,
            )
            .order_by(Document.version.desc())
            .with_for_update(),
        )
        return list(result.all())

    async def next_payment_sequence(self, sub_project_id: UUID) -> int:
        result = await self._session.scalars(
            select(Payment.payment_no)
            .where(Payment.sub_project_id == sub_project_id)
            .with_for_update(),
        )
        return next_sequence_from_payment_numbers(result.all())

    async def sum_payments(self, sub_project_id: UUID) -> Decimal:
        total = await self._session.scalar(
            select(func.coalesce(func.sum(Payment.amount), Decimal("0.00"))).where(
                Payment.sub_project_id == sub_project_id,
            ),
        )
        return to_money(total)

    async def sum_sub_project_spent(self, main_project_id: UUID) -> Decimal:
        total = await self._session.scalar(
            select(func.coalesce(func.sum(SubProject.spent_amount), Decimal("0.00"))).where(
                SubProject.main_project_id == main_project_id,
            ),
        )
        return to_money(total)

    async def list_active_user_ids_by_role(
        self,
        *,
        role: UserRole,
        dept_id: UUID | None = None,
    ) -> list[UUID]:
        conditions = [User.role == role, User.status == UserStatus.active]
        if dept_id is not None:
            conditions.append(User.dept_id == dept_id)
        result = await self._session.scalars(select(User.id).where(*conditions))
        return list(result.all())

    def add_payment(self, payment: Payment) -> None:
        self._session.add(payment)

    def add_document(self, document: Document) -> None:
        self._session.add(document)

    def add_payment_voucher(self, payment_voucher: PaymentVoucher) -> None:
        self._session.add(payment_voucher)

    async def flush(self) -> None:
        await self._session.flush()

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()

    async def refresh_payment(self, payment: Payment) -> None:
        await self._session.refresh(payment)


class InMemoryPaymentRepository:
    def __init__(
        self,
        *,
        payments: Sequence[Payment] | None = None,
        payment_vouchers: Sequence[PaymentVoucher] | None = None,
        documents: Sequence[Document] | None = None,
        main_projects: Sequence[MainProject] | None = None,
        sub_projects: Sequence[SubProject] | None = None,
        phases: Sequence[Phase] | None = None,
        users: Sequence[User] | None = None,
    ) -> None:
        self.payments = list(payments or [])
        self.payment_vouchers = list(payment_vouchers or [])
        self.documents = list(documents or [])
        self.main_projects = list(main_projects or [])
        self.sub_projects = list(sub_projects or [])
        self.phases = list(phases or [])
        self.users = list(users or [])
        self._lock = asyncio.Lock()
        self._locked = False

    @property
    def payment_phase(self) -> Phase:
        phase = next((item for item in self.phases if item.phase_no == PAYMENT_PHASE_NO), None)
        if phase is None:
            raise ResourceNotFoundError("Payment phase does not exist")
        return phase

    async def get_sub_project_for_update(self, sub_project_id: UUID) -> SubProject | None:
        await self._lock.acquire()
        self._locked = True
        return next(
            (sub_project for sub_project in self.sub_projects if sub_project.id == sub_project_id),
            None,
        )

    async def get_main_project_for_update(self, main_project_id: UUID) -> MainProject | None:
        return next(
            (
                main_project
                for main_project in self.main_projects
                if main_project.id == main_project_id
            ),
            None,
        )

    async def get_payment_phase(self, sub_project_id: UUID) -> Phase | None:
        return next(
            (
                phase
                for phase in self.phases
                if phase.sub_project_id == sub_project_id and phase.phase_no == PAYMENT_PHASE_NO
            ),
            None,
        )

    async def list_group_documents_for_update(
        self,
        *,
        sub_project_id: UUID,
        phase_id: UUID,
        doc_type: str,
    ) -> list[Document]:
        documents = [
            document
            for document in self.documents
            if document.sub_project_id == sub_project_id
            and document.phase_id == phase_id
            and document.doc_type == doc_type
        ]
        return sorted(documents, key=lambda document: document.version, reverse=True)

    async def next_payment_sequence(self, sub_project_id: UUID) -> int:
        payment_numbers = [
            payment.payment_no
            for payment in self.payments
            if payment.sub_project_id == sub_project_id
        ]
        return next_sequence_from_payment_numbers(payment_numbers)

    async def sum_payments(self, sub_project_id: UUID) -> Decimal:
        return to_money(
            sum(
                (
                    payment.amount
                    for payment in self.payments
                    if payment.sub_project_id == sub_project_id
                ),
                Decimal("0.00"),
            ),
        )

    async def sum_sub_project_spent(self, main_project_id: UUID) -> Decimal:
        return to_money(
            sum(
                (
                    sub_project.spent_amount
                    for sub_project in self.sub_projects
                    if sub_project.main_project_id == main_project_id
                ),
                Decimal("0.00"),
            ),
        )

    async def list_active_user_ids_by_role(
        self,
        *,
        role: UserRole,
        dept_id: UUID | None = None,
    ) -> list[UUID]:
        return [
            user.id
            for user in self.users
            if user.role == role
            and user.status == UserStatus.active
            and (dept_id is None or user.dept_id == dept_id)
        ]

    def add_payment(self, payment: Payment) -> None:
        self.payments.append(payment)

    def add_document(self, document: Document) -> None:
        self.documents.append(document)

    def add_payment_voucher(self, payment_voucher: PaymentVoucher) -> None:
        self.payment_vouchers.append(payment_voucher)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self._release_lock()

    async def rollback(self) -> None:
        self._release_lock()

    async def refresh_payment(self, payment: Payment) -> None:
        _ = payment
        return None

    def _release_lock(self) -> None:
        if not self._locked:
            return
        self._locked = False
        self._lock.release()


class PaymentService:
    def __init__(
        self,
        *,
        repository: PaymentRepository,
        storage: StorageBackend,
        max_file_size_bytes: int,
        notification_service: NotificationService | None = None,
        file_validator: FileValidator | None = None,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._max_file_size_bytes = max_file_size_bytes
        self._notification_service = notification_service
        self._file_validator = file_validator or DefaultFileValidator()

    async def create_payment(
        self,
        *,
        actor: User,
        sub_project_id: UUID,
        amount: Decimal,
        payment_date: date,
        voucher_files: Sequence[PaymentVoucherUpload],
        remark: str | None = None,
        confirm_over_budget: bool = False,
        over_budget_reason: str | None = None,
    ) -> Payment:
        self._ensure_can_create(actor)
        cleaned_amount = self._clean_amount(amount)
        cleaned_remark = self._clean_optional_text(remark)
        cleaned_reason = self._clean_optional_text(over_budget_reason)
        uploads = self._clean_voucher_uploads(voucher_files)
        saved_storage_keys: list[str] = []
        over_budget = False

        try:
            sub_project = await self._get_sub_project_for_update(sub_project_id)
            main_project = await self._get_main_project_for_update(sub_project.main_project_id)
            phase = await self._get_payment_phase(sub_project.id)
            over_budget = self._ensure_budget_confirmation(
                sub_project=sub_project,
                amount=cleaned_amount,
                confirm_over_budget=confirm_over_budget,
                over_budget_reason=cleaned_reason,
            )

            sequence = await self._repository.next_payment_sequence(sub_project.id)
            now = datetime.now(UTC)
            payment = Payment(
                id=uuid4(),
                payment_no=f"{sub_project.project_no}-PAY-{sequence:03d}",
                sub_project_id=sub_project.id,
                amount=cleaned_amount,
                payment_date=payment_date,
                remark=cleaned_remark,
                payment_type=PaymentType.normal,
                reverses_payment_id=None,
                operator_id=actor.id,
                created_at=now,
                updated_at=now,
            )
            documents = await self._create_voucher_documents(
                actor=actor,
                sub_project=sub_project,
                phase=phase,
                uploads=uploads,
                saved_storage_keys=saved_storage_keys,
                now=now,
            )
            self._repository.add_payment(payment)
            for document in documents:
                self._repository.add_document(document)
                self._repository.add_payment_voucher(
                    PaymentVoucher(
                        id=uuid4(),
                        payment_id=payment.id,
                        document_id=document.id,
                        created_at=now,
                        updated_at=now,
                    ),
                )

            await self._repository.flush()
            sub_project.spent_amount = await self._repository.sum_payments(sub_project.id)
            sub_project.updated_at = now
            await self._repository.flush()
            main_project.spent_amount = await self._repository.sum_sub_project_spent(
                main_project.id,
            )
            main_project.updated_at = now
            await self._repository.commit()
        except Exception:
            await self._repository.rollback()
            self._delete_saved_contents(saved_storage_keys)
            raise

        await self._repository.refresh_payment(payment)
        await self._send_notifications(
            payment=payment,
            sub_project=sub_project,
            main_project=main_project,
            over_budget=over_budget,
        )
        return payment

    @staticmethod
    def _ensure_can_create(actor: User) -> None:
        if actor.role != UserRole.finance_manager:
            raise PermissionDeniedError()

    async def _get_sub_project_for_update(self, sub_project_id: UUID) -> SubProject:
        sub_project = await self._repository.get_sub_project_for_update(sub_project_id)
        if sub_project is None:
            raise ResourceNotFoundError("Sub project does not exist")
        return sub_project

    async def _get_main_project_for_update(self, main_project_id: UUID) -> MainProject:
        main_project = await self._repository.get_main_project_for_update(main_project_id)
        if main_project is None:
            raise ResourceNotFoundError("Main project does not exist")
        return main_project

    async def _get_payment_phase(self, sub_project_id: UUID) -> Phase:
        phase = await self._repository.get_payment_phase(sub_project_id)
        if phase is None:
            raise ResourceNotFoundError("Payment phase does not exist")
        return phase

    @classmethod
    def _clean_amount(cls, amount: Decimal) -> Decimal:
        cleaned = to_money(amount)
        if cleaned <= Decimal("0.00"):
            raise ValidationFailedError("Payment amount must be greater than zero")
        return cleaned

    @staticmethod
    def _clean_optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    def _clean_voucher_uploads(
        self,
        voucher_files: Sequence[PaymentVoucherUpload],
    ) -> list[PaymentVoucherUpload]:
        if not voucher_files:
            raise ValidationFailedError("Payment voucher is required")
        cleaned_uploads: list[PaymentVoucherUpload] = []
        for upload in voucher_files:
            file_name = self._clean_file_name(upload.file_name)
            self._ensure_file_size_allowed(upload.content)
            self._validate_file(
                file_name=file_name,
                content_type=upload.content_type,
                content=upload.content,
            )
            cleaned_uploads.append(
                PaymentVoucherUpload(
                    file_name=file_name,
                    content_type=upload.content_type,
                    content=upload.content,
                ),
            )
        return cleaned_uploads

    @staticmethod
    def _clean_file_name(file_name: str) -> str:
        cleaned = file_name.strip()
        if not cleaned:
            raise ValidationFailedError("File name is required")
        return cleaned

    def _ensure_file_size_allowed(self, content: bytes) -> None:
        if len(content) > self._max_file_size_bytes:
            raise ValidationFailedError("File exceeds maximum upload size")

    def _validate_file(self, *, file_name: str, content_type: str | None, content: bytes) -> None:
        try:
            self._file_validator.validate(
                filename=file_name,
                content_type=content_type,
                content=content,
            )
        except FileValidationError:
            raise

    @staticmethod
    def _ensure_budget_confirmation(
        *,
        sub_project: SubProject,
        amount: Decimal,
        confirm_over_budget: bool,
        over_budget_reason: str | None,
    ) -> bool:
        new_total = to_money(sub_project.spent_amount + amount)
        if new_total <= sub_project.budget:
            return False

        data = {
            "budget": format_money(sub_project.budget),
            "current_spent": format_money(sub_project.spent_amount),
            "this_amount": format_money(amount),
            "over_amount": format_money(new_total - sub_project.budget),
        }
        if confirm_over_budget and over_budget_reason:
            return True
        raise BusinessException(
            code=3001,
            message="Payment exceeds sub project budget and requires confirmation",
            status_code=409,
            data=data,
        )

    async def _create_voucher_documents(
        self,
        *,
        actor: User,
        sub_project: SubProject,
        phase: Phase,
        uploads: Sequence[PaymentVoucherUpload],
        saved_storage_keys: list[str],
        now: datetime,
    ) -> list[Document]:
        documents: list[Document] = []
        group_documents = await self._repository.list_group_documents_for_update(
            sub_project_id=sub_project.id,
            phase_id=phase.id,
            doc_type=PAYMENT_VOUCHER_DOC_TYPE,
        )
        latest_version = max((document.version for document in group_documents), default=0)

        for upload in uploads:
            latest_version += 1
            for document in group_documents:
                if document.is_latest:
                    document.is_latest = False
                    document.updated_at = now

            storage_key = self._save_content(
                sub_project_id=sub_project.id,
                phase_id=phase.id,
                file_name=upload.file_name,
                content=upload.content,
            )
            saved_storage_keys.append(storage_key)
            documents.append(
                Document(
                    id=uuid4(),
                    doc_no=str(uuid4()),
                    sub_project_id=sub_project.id,
                    phase_id=phase.id,
                    acceptance_step_id=None,
                    doc_type=PAYMENT_VOUCHER_DOC_TYPE,
                    file_name=upload.file_name,
                    file_path=storage_key,
                    file_size=len(upload.content),
                    version=latest_version,
                    is_latest=True,
                    is_deleted=False,
                    uploader_id=actor.id,
                    created_at=now,
                    updated_at=now,
                ),
            )
            group_documents.append(documents[-1])
        return documents

    def _save_content(
        self,
        *,
        sub_project_id: UUID,
        phase_id: UUID,
        file_name: str,
        content: bytes,
    ) -> str:
        try:
            return self._storage.save(
                sub_id=str(sub_project_id),
                phase_id=str(phase_id),
                filename=file_name,
                content=content,
            )
        except StorageSecurityError as exc:
            raise ValidationFailedError("File name contains unsafe path characters") from exc

    async def _send_notifications(
        self,
        *,
        payment: Payment,
        sub_project: SubProject,
        main_project: MainProject,
        over_budget: bool,
    ) -> None:
        if self._notification_service is None:
            return
        payload = {
            "payment_id": str(payment.id),
            "payment_no": payment.payment_no,
            "sub_project_id": str(sub_project.id),
            "amount": format_money(payment.amount),
        }
        await self._notification_service.send(
            scenario="payment_created",
            receivers=[sub_project.manager_id],
            source_id=payment.id,
            payload=payload,
        )
        if not over_budget:
            return
        admin_ids = await self._repository.list_active_user_ids_by_role(role=UserRole.admin)
        manager_ids = await self._repository.list_active_user_ids_by_role(
            role=UserRole.dept_manager,
            dept_id=main_project.dept_id,
        )
        await self._notification_service.send(
            scenario="over_budget_warning",
            receivers=[*admin_ids, *manager_ids],
            source_id=payment.id,
            payload={
                **payload,
                "budget": format_money(sub_project.budget),
                "spent_amount": format_money(sub_project.spent_amount),
            },
        )

    def _delete_saved_contents(self, storage_keys: Sequence[str]) -> None:
        for storage_key in storage_keys:
            try:
                self._storage.delete(storage_key)
            except Exception:
                continue


def next_sequence_from_payment_numbers(payment_numbers: Sequence[str]) -> int:
    max_sequence = 0
    for payment_no in payment_numbers:
        try:
            sequence = int(payment_no.rsplit("-PAY-", maxsplit=1)[1])
        except (IndexError, ValueError):
            continue
        max_sequence = max(max_sequence, sequence)
    return max_sequence + 1


def to_money(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value.quantize(TWO_PLACES)
    return Decimal(str(value or "0.00")).quantize(TWO_PLACES)


def format_money(value: Decimal) -> str:
    return f"{to_money(value):.2f}"
