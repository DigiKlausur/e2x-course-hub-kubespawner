# e2x-course-hub-kubespawner

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

`e2x-course-hub-kubespawner` is the **Kubernetes infrastructure provider** for [`e2x-course-hub`](https://github.com/Digiklausur/e2x-course-hub). It translates the courses and roles that `e2x-course-hub` says a user is allowed to spawn into concrete [KubeSpawner](https://jupyterhub-kubespawner.readthedocs.io/) profile options: which container image to use, how much CPU/memory to grant, which volumes to mount, and which environment variables to set.

`e2x-course-hub` owns *who* may spawn *what* (courses, terms, roles). This package owns *how* a given role is actually realized on Kubernetes (images, resources, mounts). The two communicate through a small, provider-based contract so that either side can be swapped out independently — e.g. a different LMS could reuse this Kubernetes provider, or `e2x-course-hub` could be paired with a different spawner backend.

```text
┌──────────────────────────┐          ┌──────────────────────────────────┐
│      e2x-course-hub      │          │  e2x-course-hub-kubespawner      │
│                          │          │                                  │
│  Courses, Terms, Roles   │          │  Image / Resource / Mount        │
│  SpawnOfferingProvider  ─┼─────────▶│  catalogs (YAML)                 │
│  (who may spawn what)    │          │  K8sInfrastructureCatalogProvider│
│                          │◀─────────┼─ (what a role gets, in K8s terms)│
└────────────┬─────────────┘          └─────────────────┬────────────────┘
             │                                          │
             │        profile list / pre-spawn hooks    │
             └──────────────────────┬───────────────────┘
                                    ▼
                          ┌───────────────────────┐
                          │  JupyterHub +         │
                          │  KubeSpawner          │
                          └───────────────────────┘
```

* `e2x-course-hub` implements `SpawnOfferingProvider`: given a user, it returns the list of `(course, term, role)` combinations they may spawn.
* This package implements `InfrastructureCatalogProvider` (registered as a plugin entry point) and consumes those offerings to build KubeSpawner's `profile_list`, resolve volume mounts before spawn, and drive the "Your Courses" spawn page.

---

## What does it provide?

* **Catalog schemas & loading** (`e2x_course_hub_kubespawner.schemas`, `.loading`) — Pydantic models and YAML loaders for image families, resource tiers, per-role profiles, and volume mounts, plus a top-level `config.yaml` that ties them together.
* **`K8sInfrastructureCatalogProvider`** (`.catalog_provider`) — implements `e2x_course_hub`'s `InfrastructureCatalogProvider` protocol, exposing the catalog (image families, resource tiers, per-role profiles) so `e2x-course-hub` can render its own choices.
* **`K8sSpawnerAPI`** (`.spawner_api`) — takes a `SpawnOfferingProvider` (supplied by `e2x-course-hub`) and turns each offering into a KubeSpawner `profile_list` entry, and resolves the concrete image/resources/mounts for a chosen offering at spawn time.
* **JupyterHub hooks** (`.hooks`) — ready-made `Spawner.profile_list` and `Spawner.pre_spawn_hook` callables, plus `configure_autospawn()` for enabling single-course auto-spawn from `jupyterhub_config.py`.
* **Spawn page templates** (`share/e2x_k8s_spawner/templates/`) — a JupyterHub `spawn.html` and a KubeSpawner `form.html` for the "Your Courses" selection page, with support for auto-spawning when a user only has one course.

---

## Installation

This package is not yet published; install it from source alongside `e2x-course-hub`:

```bash
git clone https://github.com/Digiklausur/e2x-course-hub-kubespawner.git
cd e2x-course-hub-kubespawner
pip install -e .
```

It depends on `e2x-course-hub` being installed in the same environment, since it consumes and implements types from `e2x_course_hub.contract`.

---

## Configuration

Configuration is split across a top-level `config.yaml` and the catalog files it points to. Paths inside `config.yaml` may be relative; they are resolved against the directory containing `config.yaml` itself.

### `config.yaml`

```yaml
mount_catalog_file: "mount_catalog.yaml"
image_catalog_file: "image_catalog.yaml"
resource_tier_catalog_file: "resource_tiers.yaml"

profiles:
  student:
    default_profile: basic
    profiles:
      basic: "profiles/student.yaml"
  grader:
    default_profile: basic
    profiles:
      basic: "profiles/grader.yaml"
```

`profiles` is keyed by spawn role (`student`, `grader`, ...) as defined by `e2x_course_hub.contract.SpawnRole`. Each role points to one or more named profile files and declares which one is the default.

The package reads the path to this file from the `E2X_K8S_SPAWNER_CONFIG_FILE` environment variable.

### Image catalog (`image_catalog_file`)

Defines image families, their tags, and which concrete image each spawn role maps to:

```yaml
default_registry: ghcr.io/digiklausur/docker-stacks
default_pull_policy: IfNotPresent
default_family: "datascience"

families:
  datascience:
    display_name: "Datascience Notebook"
    description: "Comes with numpy, scipy, etc."
    default_tag: "2026-07-01"
    images:
      student: datascience-notebook-student
      grader: datascience-notebook-teacher
    tags:
      "2026-07-01": { status: active }
      "2026-04-02": { status: deprecated }
```

### Resource tiers (`resource_tier_catalog_file`)

Defines selectable CPU/memory tiers per spawn role:

```yaml
student:
  default_tier: normal
  tiers:
    low:
      display_name: "Low"
      description: "Low resources, for courses that mostly use textbooks"
      resources: { cpu_limit: 1.0, mem_guarantee: 0.5G, mem_limit: 1G }
    normal:
      display_name: "Normal"
      description: "Standard resources sufficient for everything"
      resources: { cpu_limit: 2.0, mem_guarantee: 1G, mem_limit: 2G }
```

### Profiles (per role, referenced from `config.yaml`)

Each profile declares the environment variables to inject and which named mounts to attach, using `${{inputs.*}}` placeholders resolved at spawn time from the username, course ID, and term ID:

```yaml
display_name: "Student"
environment:
  NB_USER: "${{inputs.username}}"
  NBGRADER_COURSE_ID: "${{inputs.course_id}}-${{inputs.term_id}}"
mounts:
  - student_home
  - nbgrader_exchange_outbound
has_archive_mounts: false
```

### Mount catalog (`mount_catalog_file`)

Declares the volumes available to reference by name from profiles. Three mounts are required (`student_home`, `grader_home`, `course_term`); `archived_term` is automatically derived from `course_term` as read-only. Any further mounts go under `extra`:

```yaml
student_home:
  name: disk2
  mountPath: "/home/${{inputs.username}}"
  subPath: "homes/students/${{inputs.course_id}}-${{inputs.term_id}}/${{inputs.username}}"
  readOnly: false

grader_home:
  name: disk2
  mountPath: "/home/${{inputs.username}}"
  subPath: "homes/graders/${{inputs.username}}"
  readOnly: false

course_term:
  name: disk2
  mountPath: "/home/${{inputs.username}}/courses/${{inputs.course_id}}/${{inputs.course_id}}-${{inputs.term_id}}"
  subPath: "courses/${{inputs.course_id}}/${{inputs.course_id}}-${{inputs.term_id}}"
  readOnly: false

extra:
  nbgrader_exchange_outbound:
    name: disk3
    mountPath: "/srv/nbgrader/exchange/${{inputs.course_id}}-${{inputs.term_id}}/outbound"
    subPath: "nbgrader/exchanges/${{inputs.course_id}}/${{inputs.course_id}}-${{inputs.term_id}}/outbound"
    readOnly: true
```

A profile with `has_archive_mounts: true` (typically graders) additionally gets a read-only `archived_term` mount for every other term in which the user holds the same role, so graders retain read access to past terms of the same course.

---

## JupyterHub integration

### 1. Register the catalog provider

`e2x-course-hub` discovers this package's catalog automatically through the `e2x_course_hub.infrastructure_catalog_providers` entry point declared in `pyproject.toml`. Installing the package is enough — no manual wiring is needed on that side.

### 2. Wire up the spawner hooks

In `jupyterhub_config.py`:

```python
from e2x_course_hub_kubespawner._data import JUPYTERHUB_TEMPLATE_PATH, KUBESPAWNER_TEMPLATE_PATH
from e2x_course_hub_kubespawner.hooks import (
    configure_autospawn,
    get_pre_spawn_hook,
    get_profile_list_hook,
)
import os

# set the environment variable pointing to the config.yaml
os.environ["E2X_KUBESPAWNER_CONFIG_FILE"] = "/path/to/my/config.yaml"

# spawn_offering_provider comes from e2x-course-hub
c.KubeSpawner.profile_list = get_profile_list_hook(spawn_offering_provider)
c.KubeSpawner.pre_spawn_hook = get_pre_spawn_hook(spawn_offering_provider)

# Optional: auto-spawn a user's single course without showing the picker
configure_autospawn(c, auto_spawn_single_course=True, auto_spawn_countdown=5)

c.JupyterHub.template_paths = [JUPYTERHUB_TEMPLATE_PATH]
c.KubeSpawner.additional_profile_form_template_paths = [KUBESPAWNER_TEMPLATE_PATH]
```

* `get_profile_list_hook` builds one `profile_list` entry per (course, term) the user has access to, with one selectable choice per role/read-only combination.
* `get_pre_spawn_hook` resolves the chosen offering's image, resources, and volume mounts and applies the mounts to the spawner right before the pod is created (the image and resources are already applied through the `kubespawner_override` returned by the profile list).
* `configure_autospawn` exposes `auto_spawn_single_course`/`auto_spawn_countdown` to the Jinja templates so the spawn page can skip the picker when only one option exists.

Each selectable choice is identified by a `SpawnChoiceSlug` of the form `<course_id>.<term_id>.<role>[.ro]`, round-tripped through `to_str()`/`from_str()` — this is the value KubeSpawner stores in `user_options["profile-slug"]`.

---

## Development

```bash
git clone https://github.com/Digiklausur/e2x-course-hub-kubespawner.git
cd e2x-course-hub-kubespawner
pip install -e ".[dev,test]"
pre-commit install
pytest
```

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
