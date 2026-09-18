from pathlib import Path
from typing import Self

from pydantic import BaseModel, Field

from ..utils import PlaceholderContext, load_yaml, resolve_placeholders


class Mount(BaseModel):
    """Resolved volume mount ready for Kubernetes."""

    name: str = Field(..., description="Name of the volume")
    mountPath: str = Field(..., description="Path inside the container")
    subPath: str = Field(..., description="Sub-path within the volume")
    readOnly: bool = Field(default=True, description="Whether the mount is read-only")
    description: str | None = Field(
        default=None, description="Human-readable description of the mount"
    )

    def as_readonly(self) -> "Mount":
        return self.model_copy(update={"readOnly": True})


class MountDefinition(BaseModel):
    """Template for a volume mount with placeholder support.

    Uses ${{inputs.username}}, ${{inputs.course_id}}, and ${{inputs.term_id}}
    placeholders that are resolved against a MountContext.

    Example YAML::

        student_home:
          name: disk2
          mountPath: "/home/${{inputs.username}}"
          subPath: "homes/students/${{inputs.course_id}}-${{inputs.term_id}}/${{inputs.username}}"
          readOnly: false
    """

    name: str = Field(..., description="Name of the volume")
    mountPath: str = Field(
        ..., description="Mount path inside the container (supports placeholders)"
    )
    subPath: str = Field(..., description="Sub-path within the volume (supports placeholders)")
    readOnly: bool = Field(default=True, description="Whether the mount is read-only")
    description: str | None = Field(default=None, description="Human-readable description")

    def resolve(self, ctx: PlaceholderContext) -> Mount:
        """Resolve placeholders using the standard context and return a Mount."""
        data = self.model_dump()
        resolved = resolve_placeholders(data, ctx)
        return Mount(**resolved)

    def as_readonly(self) -> Self:
        return self.model_copy(update={"readOnly": True})


class MountDefinitions(BaseModel):
    """Catalog of all mount definitions.

    Includes three required standard mounts and optional extras.
    The ``archived_term`` mount is automatically derived from ``course_term``
    with ``readOnly=True``.
    """

    student_home: MountDefinition = Field(
        ..., description="Mount definition for student home directories"
    )
    grader_home: MountDefinition = Field(
        ..., description="Mount definition for grader home directories"
    )
    course_term: MountDefinition = Field(
        ...,
        description="Mount definition for the current term's course work directory",
    )
    extra: dict[str, MountDefinition] = Field(
        default_factory=dict, description="Additional named mount definitions"
    )

    @classmethod
    def from_config_file(cls, file_path: Path | str) -> Self:
        """Load mount definitions from a YAML file and return a MountDefinitions instance."""
        raw_mounts = load_yaml(file_path)
        return cls(**raw_mounts)

    @property
    def archived_term(self) -> MountDefinition:
        """The course_term mount as read-only, for archived terms."""
        return self.course_term.as_readonly()

    def get_all_definitions(self) -> dict[str, MountDefinition]:
        """Return all named mount definitions including derived ones."""
        defs = {
            "student_home": self.student_home,
            "grader_home": self.grader_home,
            "course_term": self.course_term,
            "archived_term": self.archived_term,
        }
        defs.update(self.extra)
        return defs

    def resolve(self, name: str, ctx: PlaceholderContext) -> Mount:
        """Resolve a single named mount definition."""
        defs = self.get_all_definitions()
        if name not in defs:
            raise KeyError(f"Unknown mount definition: '{name}'")
        return defs[name].resolve(ctx)

    def resolve_many(self, names: list[str], ctx: PlaceholderContext) -> dict[str, Mount]:
        """Resolve multiple mount definitions by name, keyed by definition name."""
        return {name: self.resolve(name, ctx) for name in names}

    def resolve_archive_mounts(self, ctx: PlaceholderContext, term_ids: list[str]) -> list[Mount]:
        """Resolve archived_term (course_term as read-only) for past terms.

        Called at spawn time for grader profiles. For each term_id where the
        user has a grader/admin role, this produces a read-only mount.

        Args:
            ctx: The username/course_id to use, with a term_id per archived term.
            term_ids: Term IDs to mount as archives.

        Returns:
            List of resolved read-only archive mounts.
        """
        archive_def = self.archived_term
        return [archive_def.resolve(ctx.with_term_id(tid)) for tid in term_ids]
