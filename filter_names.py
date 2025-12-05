import argparse
import re
from pathlib import Path


CORE = {
    "Александр","Аляксандр","Алексей","Аляксей","Анатолий","Анатоль","Андрей","Андрэй","Антон","Аркадий","Арсений","Арсен","Артём","Арцём","Артем","Артемий","Артур","Адам","Адриан","Аким","Альберт","Альфред",
    "Богдан","Багдан","Борис","Бронислав",
    "Вадим","Вадзім","Валентин","Валерий","Валерый","Василий","Васіль","Виктор","Віктар","Виталий","Віталь","Владимир","Уладзімір","Владислав","Уладзіслаў","Вячеслав","Вячаслаў",
    "Гавриил","Георгий","Юрий","Юры","Геннадий","Герман","Глеб","Григорий","Грыгорый",
    "Давид","Даниил","Данила","Денис","Дмитрий","Добрыня","Демид","Демьян","Даниэль",
    "Евгений","Яўген","Егор","Ягор","Елисей","Емельян","Ефим","Яўхім",
    "Иван","Іван","Игорь","Ігар","Илья","Ілля","Иосиф","Язэп",
    "Казимир","Казімір","Кирилл","Кірыл","Клим","Климент","Константин","Канстанцін","Корней","Кузьма",
    "Лев","Леон","Леонид","Леонард","Лукьян","Любомир",
    "Макар","Максим","Максім","Марк","Марко","Марат","Матвей","Мацвей","Михаил","Міхаіл","Микита","Мікіта","Николай","Мікалай","Мирон","Мирослав","Мстислав",
    "Назар","Никита","Нестор","Наум","Никодим","Никон",
    "Олег","Алесь","Остап","Осип",
    "Павел","Павал","Пётр","Пятро","Платон","Прокопий","Потап",
    "Радослав","Роберт","Роман","Раман","Ростислав","Руслан","Родион",
    "Савелий","Савва","Святослав","Святаслаў","Семён","Сцяпан","Сергей","Сяргей","Станислав","Станіслаў","Степан","Стефан",
    "Тарас","Тимофей","Цімафей","Тихон","Трофим",
    "Фёдор","Федор","Феликс","Филипп","Фома","Франтишек","Францішак",
    "Харитон","Христофор",
    "Юлиан","Юстин",
    "Яков","Якаў","Ярослав","Ян",
    # Explicitly include examples marked Normal
    "Павел","Андрей","Алексей","Сергей"
}

BELARUS_FORMS = {
    "Аляксандр","Аляксей","Андрэй","Арцём","Сяргей","Уладзімір","Уладзіслаў","Канстанцін",
    "Мікалай","Мікіта","Мацвей","Максім","Яўген","Іван","Ігар","Ілля","Раман","Сцяпан","Цімафей","Юры","Якаў"
}

GOOD_SUFFIXES = [
    "ий","ей","ай","ый","ён","ан","ор","ар","ур","ир","иль","ль","слав","мир","яр","гер","вей","чик","вий","дар","тан","ган"
]

# Heuristics to penalize unlikely names for Belarus
BAD_PATTERNS = [
    r"дж",        # e.g. Улджабай, Аджебай
    r"ман$",     # e.g. Локман
    r"бек$",     # Turkic endings
    r"бай$",     # Turkic endings
    r"хан$",     # Turkic endings
    r"ио$",      # e.g. Григорио
    r"ь$",       # rare male given names ending with soft sign
    r"\-",      # hyphenated names
    r"[^А-Яа-яЁёІіЎў]"  # non-Cyrillic chars
]

# Cyrillic (RU+BY) letters only, first capital then lowercase. Apostrophes excluded.
CYRILLIC_FULL = re.compile(r"^[А-ЯЁІЎ][а-яёіў]+$", re.UNICODE)


def score_name(name: str) -> int:
    score = 0

    if name in CORE:
        score += 100
    if name in BELARUS_FORMS:
        score += 40

    if CYRILLIC_FULL.match(name):
        score += 15
    else:
        score -= 60

    lower = name.lower()
    for s in GOOD_SUFFIXES:
        if lower.endswith(s):
            score += 4

    n = len(name)
    if 4 <= n <= 10:
        score += 6
    elif n > 12:
        score -= 5
    elif n < 3:
        score -= 10

    for pat in BAD_PATTERNS:
        if re.search(pat, name):
            score -= 40

    return score


def read_unique_names(path: Path) -> list[str]:
    seen = set()
    out = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            name = line.strip()
            if not name:
                continue
            if name in seen:
                continue
            seen.add(name)
            out.append(name)
    return out


def write_names(path: Path, names: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for n in names:
            f.write(n + "\n")


def main():
    parser = argparse.ArgumentParser(description="Filter Belarus-friendly male names to 1000 entries.")
    parser.add_argument("--input", default=str(Path("names.txt").resolve()), help="Input names file (UTF-8, one per line).")
    parser.add_argument("--output", default=str(Path("names_1000.txt").resolve()), help="Output file for curated 1000 names.")
    parser.add_argument("--count", type=int, default=1000, help="Target count (default 1000).")
    args = parser.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)

    names = read_unique_names(in_path)
    scored = [(name, score_name(name)) for name in names]
    scored.sort(key=lambda x: (x[1], x[0]), reverse=True)

    # If fewer than target, relax penalties (remove some patterns except non-Cyrillic)
    if len(scored) < args.count:
        relaxed = []
        for name in names:
            # Only keep names that match Cyrillic baseline
            if not CYRILLIC_FULL.match(name):
                continue
            # Re-score with a reduced penalty set (keep non-Cyrillic guard only)
            relaxed_score = 0
            if name in CORE:
                relaxed_score += 100
            if name in BELARUS_FORMS:
                relaxed_score += 40
            relaxed_score += 15  # Cyrillic bonus
            lower = name.lower()
            for s in GOOD_SUFFIXES:
                if lower.endswith(s):
                    relaxed_score += 4
            n = len(name)
            if 4 <= n <= 10:
                relaxed_score += 6
            elif n > 12:
                relaxed_score -= 5
            elif n < 3:
                relaxed_score -= 10
            relaxed.append((name, relaxed_score))
        relaxed.sort(key=lambda x: (x[1], x[0]), reverse=True)
        scored = relaxed

    selected = [n for n, _ in scored[:args.count]]
    write_names(out_path, selected)

    # Summary
    print(f"Input names: {len(names)}")
    print(f"Selected: {len(selected)} -> {out_path}")
    print("Top 10 preview:")
    for n, s in scored[:10]:
        print(f"{s:4d} | {n}")


if __name__ == "__main__":
    main()