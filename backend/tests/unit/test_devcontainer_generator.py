"""
tests/unit/test_devcontainer_generator.py

Covers the deterministic DevcontainerGenerator:
  - Language → correct MCR base image
  - Framework → correct feature URLs added
  - Service → correct docker-compose image + port mapping
  - git and docker-in-docker always present
  - Unknown language falls back to base Ubuntu
  - to_json() produces a valid devcontainer.json-shaped dict
"""
from app.services.devcontainer_generator import DevcontainerGenerator


# ── image selection ───────────────────────────────────────────────────────────

def test_python_language_picks_python_image():
    cfg = DevcontainerGenerator.generate(
        languages=["python"], frameworks=[], services=[], custom_features=[]
    )
    assert "python" in cfg.image.lower()


def test_node_language_picks_node_image():
    cfg = DevcontainerGenerator.generate(
        languages=["node"], frameworks=[], services=[], custom_features=[]
    )
    assert "nodejs" in cfg.image.lower()


def test_go_language_picks_go_image():
    cfg = DevcontainerGenerator.generate(
        languages=["go"], frameworks=[], services=[], custom_features=[]
    )
    assert cfg.image == DevcontainerGenerator.LANGUAGE_IMAGES["go"]


def test_unknown_language_falls_back_to_base():
    cfg = DevcontainerGenerator.generate(
        languages=["cobol"], frameworks=[], services=[], custom_features=[]
    )
    assert "base" in cfg.image.lower() or "ubuntu" in cfg.image.lower()


def test_empty_languages_falls_back_to_base():
    cfg = DevcontainerGenerator.generate(
        languages=[], frameworks=[], services=[], custom_features=[]
    )
    assert cfg.image  # non-empty


def test_first_language_wins_for_image():
    cfg = DevcontainerGenerator.generate(
        languages=["go", "python"], frameworks=[], services=[], custom_features=[]
    )
    assert cfg.image == DevcontainerGenerator.LANGUAGE_IMAGES["go"]


# ── git + docker-in-docker always present ─────────────────────────────────────

def test_git_feature_always_included():
    cfg = DevcontainerGenerator.generate(
        languages=["python"], frameworks=[], services=[], custom_features=[]
    )
    assert any("git" in f for f in cfg.features)


def test_docker_in_docker_feature_always_included():
    cfg = DevcontainerGenerator.generate(
        languages=["python"], frameworks=[], services=[], custom_features=[]
    )
    assert any("docker-in-docker" in f for f in cfg.features)


def test_git_not_duplicated_when_already_in_custom():
    custom = ["ghcr.io/devcontainers/features/git:latest"]
    cfg = DevcontainerGenerator.generate(
        languages=["python"], frameworks=[], services=[], custom_features=custom
    )
    git_count = sum(1 for f in cfg.features if "git:latest" in f and "docker" not in f)
    assert git_count == 1


# ── framework → feature mapping ───────────────────────────────────────────────

def test_fastapi_framework_adds_python_feature():
    cfg = DevcontainerGenerator.generate(
        languages=["python"], frameworks=["fastapi"], services=[], custom_features=[]
    )
    assert any("python" in f for f in cfg.features)


def test_nextjs_framework_adds_node_feature():
    cfg = DevcontainerGenerator.generate(
        languages=["node"], frameworks=["nextjs"], services=[], custom_features=[]
    )
    assert any("node" in f for f in cfg.features)


def test_unknown_framework_does_not_raise():
    cfg = DevcontainerGenerator.generate(
        languages=["python"], frameworks=["rails"], services=[], custom_features=[]
    )
    assert cfg  # no exception


# ── service mapping ───────────────────────────────────────────────────────────

def test_postgres_service_maps_correct_image():
    cfg = DevcontainerGenerator.generate(
        languages=["python"], frameworks=[], services=["postgres"], custom_features=[]
    )
    assert "postgres" in cfg.services
    assert cfg.services["postgres"]["image"].startswith("postgres")


def test_redis_service_maps_correct_port():
    cfg = DevcontainerGenerator.generate(
        languages=["python"], frameworks=[], services=["redis"], custom_features=[]
    )
    assert "redis" in cfg.services
    assert 6379 in cfg.services["redis"]["ports"].values()


def test_unknown_service_silently_omitted():
    cfg = DevcontainerGenerator.generate(
        languages=["python"], frameworks=[], services=["cassandra"], custom_features=[]
    )
    assert "cassandra" not in cfg.services


# ── postCreateCommand ─────────────────────────────────────────────────────────

def test_python_post_create_includes_pip():
    cfg = DevcontainerGenerator.generate(
        languages=["python"], frameworks=[], services=[], custom_features=[]
    )
    assert "pip" in cfg.postCreateCommand


def test_node_post_create_includes_npm_install():
    cfg = DevcontainerGenerator.generate(
        languages=["node"], frameworks=[], services=[], custom_features=[]
    )
    assert "npm install" in cfg.postCreateCommand


def test_go_post_create_includes_go_mod_download():
    cfg = DevcontainerGenerator.generate(
        languages=["go"], frameworks=[], services=[], custom_features=[]
    )
    assert "go mod download" in cfg.postCreateCommand


def test_unknown_language_empty_post_create():
    cfg = DevcontainerGenerator.generate(
        languages=["cobol"], frameworks=[], services=[], custom_features=[]
    )
    assert cfg.postCreateCommand == ""


# ── to_json output shape ──────────────────────────────────────────────────────

def test_to_json_contains_required_keys():
    cfg = DevcontainerGenerator.generate(
        languages=["python"], frameworks=["fastapi"], services=["postgres"], custom_features=[]
    )
    result = DevcontainerGenerator.to_json(cfg)
    for key in ("name", "image", "features", "postCreateCommand", "remoteUser"):
        assert key in result, f"missing key: {key}"


def test_to_json_features_are_dict():
    cfg = DevcontainerGenerator.generate(
        languages=["python"], frameworks=[], services=[], custom_features=[]
    )
    result = DevcontainerGenerator.to_json(cfg)
    assert isinstance(result["features"], dict)


def test_to_json_name_contains_language():
    cfg = DevcontainerGenerator.generate(
        languages=["python"], frameworks=[], services=[], custom_features=[]
    )
    result = DevcontainerGenerator.to_json(cfg)
    assert "python" in result["name"]
