import json

from lib.constants import BASE_DIR
from lib.logging import logger
from models.station_preset import Station, StationPreset


class StationPresetStore:
    """A data store for managing station presets."""

    def __init__(self, paginate_func):
        self._presets: dict[str, StationPreset] = {}
        self._paginate = paginate_func
        self.load()

    def load(self):
        """Load station presets from the station-presets directory."""
        presets_dir = BASE_DIR / "station-presets"
        for preset_file in presets_dir.glob("*.json"):
            with open(preset_file, "r", encoding="utf-8") as f:
                stations_data = json.load(f)
                preset_id = preset_file.stem
                self._presets[preset_id] = StationPreset(
                    id=preset_id,
                    name=preset_id.replace("_", " ").title(),
                    stations=[
                        Station(title=s["name"], url=s["url"]) for s in stations_data
                    ],
                )
        logger.info("Loaded %d station presets", len(self._presets))

    def get(
        self, preset_id: str, account_id: str | None = None
    ) -> StationPreset | None:
        """
        Return a single station preset by its ID.
        If account_id is provided, it only returns the preset if it's owned
        by that account or if it's a global preset.
        """
        preset = self._presets.get(preset_id)
        if not preset:
            return None

        if preset.account_id is None:
            return preset

        if account_id and preset.account_id == account_id:
            return preset

        return None

    def list(
        self,
        page: int,
        per_page: int,
        account_id: str | None = None,
        include_globals: bool = False,
    ):
        """
        Return a paginated list of station presets.
        - If account_id is provided, it returns presets for that account.
        - If include_globals is True, it also includes global presets.
        - If account_id is None, it returns only global presets.
        """
        results = []
        if account_id:
            results.extend(
                p for p in self._presets.values() if p.account_id == account_id
            )

        if include_globals or not account_id:
            results.extend(p for p in self._presets.values() if p.account_id is None)

        return self._paginate(results, page, per_page)

    def register(
        self, preset_id: str, preset_data: dict, account_id: str | None = None
    ) -> StationPreset:
        """Registers or updates a station preset."""
        if account_id:
            preset_data["account_id"] = account_id

        existing_preset = self.get(preset_id)
        if existing_preset:
            if "name" in preset_data:
                existing_preset.name = preset_data["name"]
            if "stations" in preset_data:
                existing_preset.stations = [
                    Station(**s) for s in preset_data["stations"]
                ]
            if "account_id" in preset_data:
                existing_preset.account_id = preset_data["account_id"]
            if "category" in preset_data:
                existing_preset.category = preset_data["category"]
            if "description" in preset_data:
                existing_preset.description = preset_data["description"]
            preset = existing_preset
        else:
            preset = StationPreset(
                id=preset_id,
                **preset_data,
            )
        self._presets[preset_id] = preset
        return preset
