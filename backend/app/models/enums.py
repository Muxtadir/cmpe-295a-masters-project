"""Domain enumerations."""

from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    STORE_MANAGER = "store_manager"
