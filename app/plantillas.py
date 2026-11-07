from pathlib import Path

from fastapi.templating import Jinja2Templates

BASE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE / "templates"))


def fmt(valor, decimales: int = 2) -> str:
    """Formato colombiano: 1.234,5 (punto para miles, coma para decimales)."""
    try:
        n = float(valor or 0)
    except (TypeError, ValueError):
        n = 0.0
    s = f"{n:,.{decimales}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if "," in s:
        s = s.rstrip("0").rstrip(",")
    return s


templates.env.filters["fmt"] = fmt