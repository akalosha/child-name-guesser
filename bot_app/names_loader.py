from pathlib import Path
from typing import List


def load_names(names_file: Path) -> List[str]:
    names: List[str] = []
    with names_file.open("r", encoding="utf-8") as f:
        for line in f:
            name = line.strip()
            if name:
                names.append(name)
    return names