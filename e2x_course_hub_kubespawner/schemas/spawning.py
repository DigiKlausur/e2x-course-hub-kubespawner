from dataclasses import dataclass
from typing import Any, ClassVar, Iterable, Iterator

from e2x_course_hub.contract import CourseReference, SpawnOffering
from pydantic import BaseModel, ConfigDict

from .image import Image
from .mount import Mount
from .resources import Resources


class SlugComponentError(ValueError):
    """Raised when a spawn-choice slug contains an invalid component."""


class OfferingNotFoundError(ValueError):
    """Raised when a requested spawn offering does not exist."""

    def __init__(
        self,
        course_id: str,
        term_id: str,
        role: str,
        readonly: bool,
    ):
        self.course_id = course_id
        self.term_id = term_id
        self.role = role
        self.readonly = readonly

        super().__init__(
            f"Offering not found for course_id={course_id!r}, "
            f"term_id={term_id!r}, role={role!r}, "
            f"readonly={readonly!r}"
        )


class OfferingNotAvailableError(ValueError):
    """Raised when a spawn offering is not available to a user."""

    def __init__(self, username: str, offering: SpawnOffering):
        self.username = username
        self.offering = offering

        super().__init__(
            f"Offering not available for user {username!r}: "
            f"course_id={offering.course.course_id!r}, "
            f"term_id={offering.course.term_id!r}, "
            f"role={offering.selection.spawn_role!r}, "
            f"readonly={offering.selection.course_readonly!r}"
        )


@dataclass(frozen=True, slots=True)
class SpawnChoiceSlug:
    """A deterministic, round-trippable representation of a spawn choice."""

    course_id: str
    term_id: str
    role: str
    readonly: bool = False

    _SEPARATOR: ClassVar[str] = "."
    _READONLY_TOKEN: ClassVar[str] = "ro"

    @classmethod
    def _validate_component(cls, name: str, value: str) -> None:
        if not value:
            raise SlugComponentError(f"{name!r} must be a non-empty string")
        if cls._SEPARATOR in value:
            raise SlugComponentError(f"{name!r} may not contain {cls._SEPARATOR!r}: {value!r}")

    @classmethod
    def from_str(cls, raw: str) -> "SpawnChoiceSlug":
        parts = raw.split(cls._SEPARATOR)

        if len(parts) not in (3, 4):
            raise SlugComponentError(f"Expected 3 or 4 parts, got {len(parts)}: {raw!r}")

        course_id, term_id, role = parts[:3]
        readonly_token = parts[3] if len(parts) == 4 else None

        cls._validate_component("course_id", course_id)
        cls._validate_component("term_id", term_id)
        cls._validate_component("role", role)

        if readonly_token is not None and readonly_token != cls._READONLY_TOKEN:
            raise SlugComponentError(f"Unexpected token after role: {readonly_token!r}")

        return cls(
            course_id=course_id,
            term_id=term_id,
            role=role,
            readonly=readonly_token == cls._READONLY_TOKEN,
        )

    def to_str(self) -> str:
        base = self._SEPARATOR.join([self.course_id, self.term_id, self.role])
        return f"{base}{self._SEPARATOR}{self._READONLY_TOKEN}" if self.readonly else base


class Runtime(BaseModel):
    """The runtime configuration for a specific spawn offering."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    image: Image
    resources: Resources
    environment: dict[str, str | float | int | bool] = {}

    def to_kubespawner_override(self) -> dict[str, Any]:
        overrides: dict[str, Any] = {
            "image": self.image.full_image_name,
            "image_pull_policy": self.image.pullPolicy,
            **self.resources.model_dump(),
            "environment": {k: str(v) for k, v in self.environment.items()},
        }
        return overrides


class ResolvedSpawnProfile(BaseModel):
    """A resolved spawn profile for a specific course and spawn offering."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    course: CourseReference
    runtime: Runtime
    mounts: list[Mount]


class SpawnOfferings:
    """A collection of spawn offerings for a specific user."""

    def __init__(self, offerings: Iterable[SpawnOffering]):
        self._offerings = tuple(offerings)

    def __iter__(self) -> Iterator[SpawnOffering]:
        return iter(self._offerings)

    @property
    def courses(self) -> set[CourseReference]:
        return {
            offering.course
            for offering in self._offerings  # pyright: ignore[reportUnhashable], is a frozen pydantic model, so hashable
        }

    def get_for_course_role(
        self, course_id: str, term_id: str, role: str, course_readonly: bool
    ) -> SpawnOffering:
        for offering in self.for_course(course_id=course_id, term_id=term_id):
            if (
                offering.selection.spawn_role.value == role
                and offering.selection.course_readonly == course_readonly
            ):
                return offering
        raise OfferingNotFoundError(
            course_id=course_id,
            term_id=term_id,
            role=role,
            readonly=course_readonly,
        )

    def for_course(self, course_id: str, term_id: str) -> list[SpawnOffering]:
        return [
            offering
            for offering in self._offerings
            if offering.course.course_id == course_id and offering.course.term_id == term_id
        ]

    def archive_terms_for(
        self,
        offering: SpawnOffering,
    ) -> list[str]:
        return [
            other.course.term_id
            for other in self._offerings
            if (
                other.course.course_id == offering.course.course_id
                and other.selection.spawn_role is offering.selection.spawn_role
                and other.course.term_id != offering.course.term_id
            )
        ]


class KubeSpawnerProfileChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str
    kubespawner_override: dict[str, Any]
    omit_details: bool = False
    """Whether the form should skip showing the kubespawner override details for this
    choice, e.g. because they are identical to those of the non-read-only role."""


class KubeSpawnerProfileOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str
    choices: dict[str, KubeSpawnerProfileChoice]


class KubeSpawnerProfileEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str
    term: str
    sort_key: str
    metadata: dict[str, str | None]
    profile_options: dict[str, KubeSpawnerProfileOptions]
