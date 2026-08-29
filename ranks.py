# -*- coding: utf-8 -*-
"""
Система рангов MTR TEAM — по сумме профита пользователя (users.profit).
Пороги и названия взяты с промо-картинки заказчика.
"""

# (название ранга, порог в рублях — от него ранг присваивается)
# Отсортировано по возрастанию, самый высокий подходящий порог и есть ранг.
RANKS: list[tuple[str, float]] = [
    ("Новичок", 0),
    ("Растущий", 50_000),
    ("Уверенный", 100_000),
    ("Амбициозный", 200_000),
    ("Настойчивый", 500_000),
    ("Признанный", 750_000),
    ("Высоко оцененный", 900_000),
    ("Легендарный", 1_000_000),
    ("Элита", 1_500_000),
]


def get_rank(profit: float) -> str:
    """Возвращает название ранга по сумме профита."""
    profit = profit or 0
    current = RANKS[0][0]
    for name, threshold in RANKS:
        if profit >= threshold:
            current = name
        else:
            break
    return current


def format_ranks_list(current_profit: float = 0) -> str:
    """Полный список рангов текстом, с пометкой ✅ у уже достигнутых и 👉 у текущего."""
    current_name = get_rank(current_profit)
    lines = []
    for name, threshold in RANKS:
        threshold_display = f"{threshold:,}".replace(",", " ") + " RUB"
        marker = "👉 " if name == current_name else ("✅ " if current_profit >= threshold else "◻️ ")
        lines.append(f"{marker}{name} — {threshold_display}")
    return "\n".join(lines)
