"""Load conference entries that have an accepted_papers_url registered.

Source of truth is the YAML files under src/data/conferences/ — the same files
the frontend consumes. Only entries with accepted_papers_url are returned; the
rest are ignored by the monitor.
"""

from dataclasses import dataclass
from typing import Iterator

import yaml

from backend.config import CONFERENCES_DIR


@dataclass(frozen=True)
class MonitoredConference:
    id: str
    title: str
    year: int
    url: str


def _iter_yaml_entries() -> Iterator[dict]:
    for path in sorted(CONFERENCES_DIR.glob("*.yml")):
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, list):
            continue
        for entry in data:
            if isinstance(entry, dict):
                yield entry


def load_monitored() -> list[MonitoredConference]:
    """Return conferences that declare an accepted_papers_url."""
    monitored: list[MonitoredConference] = []
    for entry in _iter_yaml_entries():
        url = entry.get("accepted_papers_url")
        if not url:
            continue
        conf_id = entry.get("id")
        title = entry.get("title")
        year = entry.get("year")
        if not (conf_id and title and year):
            continue
        monitored.append(
            MonitoredConference(
                id=str(conf_id),
                title=str(title),
                year=int(year),
                url=str(url).strip(),
            )
        )
    return monitored
