def humanize_score(value: int) -> str:
    if value >= 1_000_000:
        return f"{value/1_000_000:.2f}M"
    elif value >= 1_000:
        return f"{value/1_000:.2f}K"
    else:
        return str(value)

def percent(delta: float) -> str:
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta:.1f}%"

def trend_arrow(trend: str) -> str:
    arrows = {
        "rising": "↗",
        "forward momentum": "↗",
        "steady": "→",
        "stable": "→",
        "needs support": "↘",
        "declining": "↘",
        "currently stabilizing performance": "→"
    }
    return arrows.get(trend, "→")
