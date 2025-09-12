from rich.console import Console
from rich.theme import Theme

THEME = Theme(
    {
        "time": "cyan",
        "speaker": "bold green",
        "text": "white",
        "error": "bold red",
        "title": "bold magenta",
        "muted": "dim",
        "ok": "bold green",
        "warn": "yellow",
    }
)


console = Console(theme=THEME)
