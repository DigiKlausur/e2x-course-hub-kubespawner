"""Errors raised by the spawner's infrastructure catalog.

All errors derive from ``ValueError``, so pydantic turns them into a ``ValidationError``
when they are raised inside a validator.
"""

from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Only for type hints: schemas.mount imports this module at runtime
    from .schemas.mount import Mount


class CatalogError(ValueError):
    """Base class for errors in the spawner's infrastructure catalog."""


class UnknownSelectionError(CatalogError):
    """Base class for a selection (e.g. of a semester) that names something not in the catalog.

    Once the catalog is validated, these are the only errors left when spawning: the
    selection is outdated and has to be fixed by the instructor.
    """


class UnknownImageFamilyError(UnknownSelectionError):
    """Raised when an image family is not in the catalog."""

    def __init__(self, family_name: str, available: Iterable[str]):
        super().__init__(f"Image family '{family_name}' not found. Available: {list(available)}")


class UnknownImageTagError(UnknownSelectionError):
    """Raised when an image tag is not in the catalog for its family."""

    def __init__(self, family_name: str, tag: str):
        super().__init__(
            f"Tag '{tag}' does not exist for image family '{family_name}' in the catalog."
        )


class UnknownResourceTierError(UnknownSelectionError):
    """Raised when a resource tier is not in the catalog."""

    def __init__(self, tier_name: str, available: Iterable[str]):
        super().__init__(f"Resource tier '{tier_name}' not found. Available: {list(available)}")


class UnknownProfileError(UnknownSelectionError):
    """Raised when a profile is not in the catalog."""

    def __init__(self, profile_name: str, available: Iterable[str]):
        super().__init__(f"Profile '{profile_name}' not found. Available: {list(available)}")


class UnknownMountError(CatalogError):
    """Raised when a profile references a mount that is not in the mount catalog."""

    def __init__(self, mount_name: str, available: Iterable[str]):
        super().__init__(f"Mount '{mount_name}' not found. Available: {list(available)}")


class MissingSpawnRoleError(CatalogError):
    """Raised when something in the catalog is not defined for every spawn role."""

    def __init__(self, what: str, missing_roles: Iterable[str]):
        super().__init__(
            f"{what} must be defined for every spawn role, missing: {list(missing_roles)}"
        )


class UnresolvedPlaceholderError(CatalogError):
    """Raised when a placeholder references an unknown key or is malformed."""


class MountPathConflictError(CatalogError):
    """Raised when two different mounts resolve to the same mount path."""

    def __init__(self, mount_path: str, existing: "Mount", conflicting: "Mount"):
        super().__init__(
            f"Conflicting mounts for path '{mount_path}': "
            f"{existing.name}:{existing.subPath} (readOnly={existing.readOnly}) vs "
            f"{conflicting.name}:{conflicting.subPath} (readOnly={conflicting.readOnly})"
        )


class CatalogValidationError(CatalogError):
    """Raised when loading the catalog finds problems; collects every problem found."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("\n".join(errors))
