Param(
    [string]$InputPath = "c:\\Projects\\child-name-guesser\\names_full_backup.txt",
    [string]$OutputPath = "c:\\Projects\\child-name-guesser\\names.txt",
    [int]$TargetCount = 1000
)

# Load names from backup
if (!(Test-Path $InputPath)) {
    Write-Error "Input file not found: $InputPath"
    exit 1
}

$names = Get-Content -LiteralPath $InputPath |
    Where-Object { $_ -match "\S" } |
    ForEach-Object { $_.Trim() } |
    Where-Object { $_ -ne "" } |
    Select-Object -Unique

# High-confidence Belarus/Russian male names (core whitelist)
$Core = @(
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
    "Савелий","Савва","Святослав","Святаслаў","Семён","Семён","Сцяпан","Сергей","Сяргей","Станислав","Станіслаў","Степан","Стефан",
    "Тарас","Тимофей","Цімафей","Тихон","Трофим",
    "Фёдор","Федор","Феликс","Филипп","Фома","Франтишек","Францішак",
    "Харитон","Христофор",
    "Юлиан","Юстин",
    "Яков","Якаў","Ярослав","Ян"
)

# Belarus-specific spellings (extra boost)
$BelarusForms = @(
    "Аляксандр","Аляксей","Андрэй","Арцём","Сяргей","Уладзімір","Уладзіслаў","Канстанцін",
    "Мікалай","Мікіта","Мацвей","Максім","Яўген","Іван","Ігар","Ілля","Раман","Сцяпан","Цімафей","Юры","Якаў"
)

# Common Slavic endings and stems
$GoodSuffixes = @("ий","ей","ай","ый","ён","ан","ор","ар","ур","ир","иль","ль","слав","мир","яр","гер","вей","чик","вий","дар","тан","ган")

# Patterns typical for non-Slavic/rare in Belarus (penalize)
$BadPatterns = @(
    "дж",     # e.g. Улджабай, Аджебай
    "ман$",  # e.g. Локман
    "бек$",  # Turkic endings
    "бай$",  # Turkic endings
    "хан$",  # Turkic endings
    "ь$",    # rare male given names ending with soft sign
    "ио$",   # e.g. Григорио
    "\-",   # hyphenated or compound – often not canonical
    "[^А-Яа-яЁёІіЎў]" # non-Cyrillic characters
)

function Get-NameScore([string]$name) {
    $score = 0
    # Exact whitelist
    if ($Core -contains $name) { $score += 100 }
    if ($BelarusForms -contains $name) { $score += 40 }

    # Cyrillic check (only Belarus/Russian letters)
    if ($name -match "^[А-ЯЁІЎ][а-яёіў]+$") { $score += 15 } else { $score -= 60 }

    # Typical Slavic endings
    foreach ($s in $GoodSuffixes) { if ($name.ToLower().EndsWith($s)) { $score += 4 } }

    # Length preference
    if ($name.Length -ge 4 -and $name.Length -le 10) { $score += 6 }
    elseif ($name.Length -gt 12) { $score -= 5 }
    elseif ($name.Length -lt 3) { $score -= 10 }

    # Penalize strange patterns
    foreach ($p in $BadPatterns) { if ($name -match $p) { $score -= 40 } }

    return $score
}

$scored = $names | ForEach-Object {
    [PSCustomObject]@{ Name = $_; Score = Get-NameScore($_) }
}

$sorted = $scored | Sort-Object -Property Score -Descending

# Ensure we have enough names; if not, relax criteria slightly
if ($sorted.Count -lt $TargetCount) {
    Write-Warning "Only $($sorted.Count) candidates found; relaxing criteria by removing some penalties."
    $BadPatterns = @("[^А-Яа-яЁёІіЎў]")
    $scored = $names | ForEach-Object {
        [PSCustomObject]@{ Name = $_; Score = Get-NameScore($_) }
    }
    $sorted = $scored | Sort-Object -Property Score -Descending
}

$selected = $sorted | Select-Object -First $TargetCount | Select-Object -ExpandProperty Name

# Ensure output file exists, then write
New-Item -ItemType File -Force -Path $OutputPath | Out-Null
Set-Content -LiteralPath $OutputPath -Value $selected -Encoding UTF8

Write-Host "Input names: $($names.Count)" -ForegroundColor Cyan
Write-Host "Selected: $($selected.Count) -> $OutputPath" -ForegroundColor Green
Write-Host "Top 10 preview:" -ForegroundColor Yellow
$sorted | Select-Object -First 10 | ForEach-Object { Write-Host ("{0,4} | {1}" -f $_.Score, $_.Name) }