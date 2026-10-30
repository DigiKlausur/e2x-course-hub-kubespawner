from collections.abc import Callable
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def catalog_data() -> dict[str, dict]:
    """A minimal valid catalog, as file name -> YAML content. Tests break it on purpose."""
    return {
        "config.yaml": {
            "mount_catalog_file": "mounts.yaml",
            "image_catalog_file": "images.yaml",
            "resource_tier_catalog_file": "tiers.yaml",
            "profiles": {
                "student": {"default_profile": "basic", "profiles": {"basic": "student.yaml"}},
                "grader": {"default_profile": "basic", "profiles": {"basic": "grader.yaml"}},
            },
        },
        "images.yaml": {
            "default_registry": "registry.example.org",
            "default_family": "datascience",
            "families": {
                "datascience": {
                    "display_name": "Datascience",
                    "description": "Numpy and friends",
                    "default_tag": "2026-07-14",
                    "images": {"student": "ds-student", "grader": "ds-grader"},
                    "tags": {"2026-07-14": {"status": "latest"}},
                }
            },
        },
        "tiers.yaml": {
            role: {
                "default_tier": "normal",
                "tiers": {
                    "normal": {
                        "display_name": "Normal",
                        "description": "Standard resources",
                        "resources": {"mem_limit": "2G"},
                    }
                },
            }
            for role in ("student", "grader")
        },
        "mounts.yaml": {
            "student_home": {
                "name": "disk",
                "mountPath": "/home/${{inputs.username}}",
                "subPath": "students/${{inputs.course_id}}/${{inputs.username}}",
                "readOnly": False,
            },
            "grader_home": {
                "name": "disk",
                "mountPath": "/home/${{inputs.username}}",
                "subPath": "graders/${{inputs.username}}",
                "readOnly": False,
            },
            "course_term": {
                "name": "disk",
                "mountPath": "/home/${{inputs.username}}/courses/${{inputs.term_id}}",
                "subPath": "courses/${{inputs.course_id}}-${{inputs.term_id}}",
                "readOnly": False,
            },
        },
        "student.yaml": {
            "display_name": "Student",
            "environment": {"NB_USER": "${{inputs.username}}"},
            "mounts": ["student_home"],
        },
        "grader.yaml": {
            "display_name": "Grader",
            "has_archive_mounts": True,
            "mounts": ["grader_home", "course_term"],
        },
    }


@pytest.fixture
def write_catalog(tmp_path: Path) -> Callable[[dict[str, dict]], Path]:
    """Write the catalog files to a temporary directory and return the config.yaml path."""

    def write(data: dict[str, dict]) -> Path:
        for file_name, content in data.items():
            (tmp_path / file_name).write_text(yaml.safe_dump(content))
        return tmp_path / "config.yaml"

    return write
