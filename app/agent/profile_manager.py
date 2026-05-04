import yaml
from app.config.settings import get_settings


class ProfileManager:
    def __init__(self) -> None:
        self._profiles: dict = {}
        self._load()

    def _load(self) -> None:
        settings = get_settings()
        path = settings.config_dir / "profiles.yaml"
        with open(path) as f:
            data = yaml.safe_load(f)
        self._profiles = data.get("profiles", {})

    def get_profile(self, name: str) -> dict | None:
        return self._profiles.get(name)

    def list_profiles(self) -> list[str]:
        return list(self._profiles.keys())

    def validate_profile(self, name: str) -> bool:
        return name in self._profiles
