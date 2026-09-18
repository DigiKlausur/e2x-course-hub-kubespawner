from pathlib import Path
from typing import Self

from e2x_course_hub.contract import SpawnRole
from pydantic import BaseModel, ValidationInfo, field_validator, model_validator

from ..utils import load_yaml


def resolve_path(root: Path, path: str) -> Path:
    return (root / path).resolve()


def _resolve_in_context(value: Path, info: ValidationInfo) -> Path:
    """Resolve a path against the 'root' directory passed via validation context, if any."""
    root = (info.context or {}).get("root")
    return resolve_path(root, str(value)) if root else value


class ProfileConfig(BaseModel):
    """Paths to the per-role profile definition files, as declared in the top-level config."""

    default_profile: str
    profiles: dict[str, Path]

    @field_validator("profiles", mode="after")
    @classmethod
    def _resolve_profile_paths(
        cls, value: dict[str, Path], info: ValidationInfo
    ) -> dict[str, Path]:
        return {name: _resolve_in_context(path, info) for name, path in value.items()}

    @model_validator(mode="after")
    def _validate_default_profile(self) -> Self:
        if self.default_profile not in self.profiles:
            raise ValueError(
                f"default_profile '{self.default_profile}' "
                f"not in profiles: {list(self.profiles.keys())}"
            )
        return self


class Config(BaseModel):
    """Paths to the catalog source files, as declared in the top-level config file."""

    mount_catalog_file: Path
    image_catalog_file: Path
    resource_tier_catalog_file: Path
    profiles: dict[SpawnRole, ProfileConfig]

    @field_validator(
        "mount_catalog_file", "image_catalog_file", "resource_tier_catalog_file", mode="after"
    )
    @classmethod
    def _resolve_catalog_file(cls, value: Path, info: ValidationInfo) -> Path:
        return _resolve_in_context(value, info)

    @classmethod
    def from_yaml(cls, file_path: Path) -> Self:
        """Load a Config from a YAML file, resolving relative paths against its directory."""
        data = load_yaml(file_path)
        return cls.model_validate(data, context={"root": file_path.parent})
