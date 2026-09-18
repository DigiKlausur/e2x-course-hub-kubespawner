from typing import Callable

from e2x_course_hub.contract import CourseReference, SpawnOffering, SpawnOfferingProvider, UserLike

from .loading import load_infrastructure_catalog, load_mount_catalog
from .schemas.config import Config
from .schemas.mount import Mount
from .schemas.spawning import (
    KubeSpawnerProfileChoice,
    KubeSpawnerProfileEntry,
    KubeSpawnerProfileOptions,
    OfferingNotAvailableError,
    ResolvedSpawnProfile,
    Runtime,
    SpawnChoiceSlug,
    SpawnOfferings,
)
from .settings import K8sSpawnerSettings
from .sorting import parse_term_for_sorting
from .utils import PlaceholderContext


class K8sSpawnerAPI:
    def __init__(
        self,
        spawn_offering_provider: SpawnOfferingProvider,
        config: Config | None = None,
        sorter: Callable[[str], str] | None = None,
    ):
        settings = K8sSpawnerSettings()  # pyright: ignore[reportCallIssue], config_file comes from env
        config = config or Config.from_yaml(settings.config_file)
        self.catalog_definitions = load_infrastructure_catalog(config)
        self.mount_catalog = load_mount_catalog(config)
        self.spawn_offering_provider = spawn_offering_provider
        self.sorter = sorter or parse_term_for_sorting

    def _get_offerings(self, user: UserLike) -> SpawnOfferings:
        return SpawnOfferings(self.spawn_offering_provider.get_spawn_offerings(user))

    def _build_kubespawner_profile_entry(
        self, user: UserLike, course: CourseReference, offerings: list[SpawnOffering]
    ) -> KubeSpawnerProfileEntry:
        choices = {}
        for offering in offerings:
            role = offering.selection.spawn_role.value
            choice_slug = SpawnChoiceSlug(
                course_id=course.course_id,
                term_id=course.term_id,
                role=offering.selection.spawn_role,
                readonly=offering.selection.course_readonly,
            ).to_str()

            display_name = f"{role} (read-only)" if offering.selection.course_readonly else role

            choices[choice_slug] = KubeSpawnerProfileChoice(
                display_name=display_name,
                kubespawner_override=self._get_runtime_for_offering(
                    user, offering
                ).to_kubespawner_override(),
                omit_details=offering.selection.course_readonly,
            )

        return KubeSpawnerProfileEntry(
            display_name=f"{course.course_id} - {course.term_id}",
            term=course.term_id,
            sort_key=self.sorter(course.term_id),
            metadata={
                "course_name": offerings[0].course.course_display_name,
                "course_description": offerings[0].course.course_description,
            },
            profile_options={
                "profile-slug": KubeSpawnerProfileOptions(display_name="Profile", choices=choices)
            },
        )

    def _get_mounts_for_offering(
        self, user: UserLike, offering: SpawnOffering, offerings: SpawnOfferings
    ) -> list[Mount]:
        profile = self.catalog_definitions.get_profile_for_selection(offering.selection)
        ctx = PlaceholderContext(
            username=user.username,
            course_id=offering.course.course_id,
            term_id=offering.course.term_id,
        )

        resolved_mounts = self.mount_catalog.resolve_many(names=profile.mounts, ctx=ctx)
        course_readonly = offering.selection.course_readonly
        if course_readonly and "course_term" in resolved_mounts:
            resolved_mounts["course_term"] = resolved_mounts["course_term"].as_readonly()
        mounts = list(resolved_mounts.values())

        if profile.has_archive_mounts:
            mounts.extend(
                self.mount_catalog.resolve_archive_mounts(
                    ctx=ctx,
                    term_ids=offerings.archive_terms_for(offering),
                )
            )
        return mounts

    def _get_runtime_for_offering(self, user: UserLike, offering: SpawnOffering) -> Runtime:
        selection = offering.selection
        resources = self.catalog_definitions.get_resources_for_selection(selection)
        profile = self.catalog_definitions.get_profile_for_selection(selection)
        image = self.catalog_definitions.get_image_for_selection(selection)
        ctx = PlaceholderContext(
            username=user.username,
            course_id=offering.course.course_id,
            term_id=offering.course.term_id,
        )

        return Runtime(
            image=image,
            resources=resources,
            environment=profile.resolve_environment(ctx),
        )

    def get_kubespawner_profile_list(self, user: UserLike) -> list[KubeSpawnerProfileEntry]:
        offerings = self._get_offerings(user)
        return [
            self._build_kubespawner_profile_entry(
                user,
                course,
                offerings.for_course(
                    course.course_id,
                    course.term_id,
                ),
            )
            for course in offerings.courses
        ]

    def get_offering_from_choice_slug(self, user: UserLike, choice_slug: str) -> SpawnOffering:
        slug = SpawnChoiceSlug.from_str(choice_slug)
        offerings = self._get_offerings(user)

        return offerings.get_for_course_role(
            course_id=slug.course_id,
            term_id=slug.term_id,
            role=slug.role,
            course_readonly=slug.readonly,
        )

    def resolve(self, user: UserLike, offering: SpawnOffering) -> ResolvedSpawnProfile:
        offerings = self._get_offerings(user)
        # Validate that the offering is in the user's offerings
        if offering not in offerings.for_course(
            course_id=offering.course.course_id, term_id=offering.course.term_id
        ):
            raise OfferingNotAvailableError(
                username=user.username,
                offering=offering,
            )
        return ResolvedSpawnProfile(
            course=offering.course,
            runtime=self._get_runtime_for_offering(user, offering),
            mounts=self._get_mounts_for_offering(user, offering, offerings),
        )
