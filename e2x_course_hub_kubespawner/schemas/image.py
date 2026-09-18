from typing import Self

from e2x_course_hub.contract import (
    ImageFamilyOption,
    ImageFamilyOptions,
    ImageTagInfo,
    SpawnRole,
    SpawnSelection,
)
from pydantic import BaseModel, model_validator


class Image(BaseModel):
    """A single image in the catalog."""

    name: str
    tag: str
    pullPolicy: str = "IfNotPresent"

    @property
    def full_image_name(self) -> str:
        return f"{self.name}:{self.tag}"


class ImageFamilyDefinition(BaseModel):
    """A definition for a family of images."""

    display_name: str
    description: str
    default_tag: str
    pullPolicy: str | None = None
    registry: str | None = None
    images: dict[SpawnRole, str]
    tags: dict[str, ImageTagInfo]

    @model_validator(mode="after")
    def _validate_default_tag(self) -> Self:
        if self.default_tag not in self.tags:
            raise ValueError(
                f"default_tag '{self.default_tag}' not in tags: {list(self.tags.keys())}"
            )
        return self

    def to_option(self) -> ImageFamilyOption:
        return ImageFamilyOption(
            display_name=self.display_name,
            description=self.description,
            default_tag=self.default_tag,
            tags=self.tags,
        )


class ImageFamilyDefinitions(BaseModel):
    """Definitions for all image families, including default registry and pull policy."""

    default_registry: str
    default_pull_policy: str | None = None
    default_family: str
    families: dict[str, ImageFamilyDefinition]

    @model_validator(mode="after")
    def _validate_default_family(self) -> Self:
        if self.default_family not in self.families:
            raise ValueError(
                f"default_family '{self.default_family}' not in families: "
                f"{list(self.families.keys())}"
            )
        return self

    def _get_family(self, family_name: str) -> ImageFamilyDefinition:
        try:
            return self.families[family_name]
        except KeyError:
            raise ValueError(
                f"Image family '{family_name}' not found. Available: {list(self.families)}"
            ) from None

    def _get_image_name(
        self,
        family_name: str,
        spawn_role: SpawnRole,
    ) -> str:
        family = self._get_family(family_name)
        image_name = family.images.get(spawn_role)
        if not image_name:
            raise ValueError(
                f"No image defined for spawn role '{spawn_role}' in family '{family_name}'"
            )
        return image_name

    def _get_pull_policy(self, family: ImageFamilyDefinition) -> str:
        return family.pullPolicy or self.default_pull_policy or "IfNotPresent"

    def assert_image_selection_exists(self, family_name: str, tag: str | None = None) -> None:
        family = self._get_family(family_name)
        if tag is not None and tag not in family.tags:
            raise ValueError(
                f"Tag '{tag}' does not exist for image family '{family_name}' in the catalog."
            )

    def to_options(self) -> ImageFamilyOptions:
        return ImageFamilyOptions(
            default_family=self.default_family,
            families={name: family.to_option() for name, family in self.families.items()},
        )

    def _build_image(
        self,
        family_name: str,
        spawn_role: SpawnRole,
        tag: str | None = None,
    ) -> Image:
        family = self._get_family(family_name)
        image_name = family.images.get(spawn_role)
        tag = tag or family.default_tag
        if tag not in family.tags:
            raise ValueError(
                f"Tag '{tag}' does not exist for image family '{family_name}' in the catalog."
            )

        registry = family.registry or self.default_registry

        return Image(
            name=f"{registry}/{image_name}",
            tag=tag,
            pullPolicy=self._get_pull_policy(family),
        )

    def get_default_image_for_role(self, spawn_role: SpawnRole) -> Image:
        return self._build_image(family_name=self.default_family, spawn_role=spawn_role)

    def get_image_for_selection(self, selection: SpawnSelection) -> Image:
        if selection.image is None:
            return self.get_default_image_for_role(selection.spawn_role)

        return self._build_image(
            family_name=selection.image.family,
            spawn_role=selection.spawn_role,
            tag=selection.image.tag,
        )
