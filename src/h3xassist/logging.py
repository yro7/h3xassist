import logging
import warnings

from rich.console import Console
from rich.logging import RichHandler


def setup_logging(level: str = "INFO") -> None:
    if level.upper() != "DEBUG":
        warnings.simplefilter("ignore")

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=r"[cyan]\[%(name)s][/cyan] %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            RichHandler(
                level=getattr(logging, level.upper(), logging.INFO),
                console=Console(stderr=True),
                rich_tracebacks=True,
                show_time=True,
                show_path=False,
                markup=True,
            )
        ],
    )
    logging.captureWarnings(True)

    # disable unwanted logging
    logging.getLogger("O365").setLevel(logging.ERROR)
    logging.getLogger("urllib3").setLevel(logging.ERROR)
    logging.getLogger("speechbrain.utils.checkpoints").setLevel(logging.ERROR)
    logging.getLogger("pytorch_lightning").setLevel(logging.ERROR)
