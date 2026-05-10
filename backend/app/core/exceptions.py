from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.responses import error_response


class BusinessException(Exception):
    def __init__(
        self,
        *,
        code: int,
        message: str,
        status_code: int = 400,
        data: Any = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.data = data


class AuthenticationError(BusinessException):
    def __init__(self, message: str = "认证失败", data: Any = None) -> None:
        super().__init__(code=1001, message=message, status_code=401, data=data)


class AccountLockedError(BusinessException):
    def __init__(self, message: str = "Account is locked", data: Any = None) -> None:
        super().__init__(code=1002, message=message, status_code=423, data=data)


class PermissionDeniedError(BusinessException):
    def __init__(self, message: str = "权限不足", data: Any = None) -> None:
        super().__init__(code=1003, message=message, status_code=403, data=data)


class ValidationFailedError(BusinessException):
    def __init__(self, message: str = "参数错误", data: Any = None) -> None:
        super().__init__(code=2003, message=message, status_code=422, data=data)


class ResourceNotFoundError(BusinessException):
    def __init__(self, message: str = "资源不存在", data: Any = None) -> None:
        super().__init__(code=4001, message=message, status_code=404, data=data)


class ResourceConflictError(BusinessException):
    def __init__(self, message: str = "资源已存在", data: Any = None) -> None:
        super().__init__(code=4002, message=message, status_code=409, data=data)


async def business_exception_handler(
    _request: Request,
    exc: Exception,
) -> JSONResponse:
    if not isinstance(exc, BusinessException):
        raise exc

    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(code=exc.code, message=exc.message, data=exc.data),
    )
