from dataclasses import dataclass
from typing import Literal

ImportStatus = Literal["created", "updated", "skipped", "failed"]


@dataclass
class ImportResult:
    tab_id: str
    title: str = ""
    status: ImportStatus = "failed"
    reason: str = ""
