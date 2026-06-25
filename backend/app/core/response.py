"""
Wrapper response chuẩn theo API spec: { status_code, message, data }.
Mọi endpoint trong hệ thống PHẢI trả về qua envelope() để đồng nhất format.
"""
from __future__ import annotations

from typing import Any

from fastapi import status
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder


def envelope(data: Any = None, message: str = "OK", status_code: int = status.HTTP_200_OK) -> JSONResponse:
    """
    Bọc data vào response chuẩn { status_code, message, data }.
    Dùng jsonable_encoder để serialize đúng cho UUID, datetime, Pydantic model...
    """
    return JSONResponse(
        status_code=status_code,
        content={
            "status_code": status_code,
            "message": message,
            "data": jsonable_encoder(data),
        },
    )


def envelope_created(data: Any = None, message: str = "Tạo thành công") -> JSONResponse:
    return envelope(data=data, message=message, status_code=status.HTTP_201_CREATED)
