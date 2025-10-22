# src/agent/cust_logger.py
import inspect
import logging
import sys
from colorama import Fore, Style, init
from datetime import datetime

# Make ANSI colors work in Docker (and Windows)
init(autoreset=True, convert=True, strip=False)

class ColorFormatter(logging.Formatter):
    COLORS = {
        logging.INFO: Fore.GREEN,
        logging.ERROR: Fore.RED,
        logging.WARNING: Fore.YELLOW,
        logging.DEBUG: Fore.CYAN,
    }
    FILE_COLOR = Fore.CYAN + Style.BRIGHT
    MESSAGE_COLOR_BY_FILE: dict[str, str] = {}

    def format(self, record: logging.LogRecord) -> str:
        # Level color
        log_color = self.COLORS.get(record.levelno, Style.RESET_ALL)
        levelname = f"{log_color}{record.levelname}{Style.RESET_ALL}"

        # File:line
        filename = getattr(record, "filename", "?")
        lineno = getattr(record, "lineno", 0)
        filename_lineno = f"{self.FILE_COLOR}{filename}:{lineno:<5}{Style.RESET_ALL}"

        # Message color, per-file override
        message_color = self.MESSAGE_COLOR_BY_FILE.get(filename, Style.RESET_ALL)
        msg = record.getMessage()
        colored_message = f"{message_color}{msg}{Style.RESET_ALL}"

        # Timestamp (not using asctime to keep custom format simple)
        ts = datetime.now().isoformat(timespec="milliseconds")

        return f"{ts} {levelname}:     {filename_lineno} - {colored_message}"

# Create a module-scoped logger
logger = logging.getLogger("app")

def _install_stream_handler(level: int = logging.INFO) -> None:
    # Avoid duplicate handlers on reloads
    if any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        return

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(ColorFormatter())
    handler.setLevel(level)

    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False  # don’t double-log via root

    # Quiet some noisy libs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

_install_stream_handler()

# Simple color map for caller files
COLOR_MAP = {
    "BLACK": Fore.BLACK,
    "RED": Fore.RED,
    "GREEN": Fore.GREEN,
    "YELLOW": Fore.YELLOW,
    "PURPLE": Fore.BLUE,   # (Purple-ish)
    "MAGENTA": Fore.MAGENTA,
    "CYAN": Fore.CYAN,
    "WHITE": Fore.WHITE,
    "RESET": Style.RESET_ALL,
}

def set_files_message_color(color_name: str) -> None:
    """Set the default message color for logs emitted *from the calling file*."""
    try:
        caller_filename = inspect.stack()[1].filename.split("/")[-1]
    except Exception:
        caller_filename = "unknown"

    color = COLOR_MAP.get(color_name.upper(), Style.RESET_ALL)

    # Find our formatter on our stream handler
    for h in logger.handlers:
        fmt = getattr(h, "formatter", None)
        if isinstance(fmt, ColorFormatter):
            current = fmt.MESSAGE_COLOR_BY_FILE.get(caller_filename)
            if current != color:
                fmt.MESSAGE_COLOR_BY_FILE[caller_filename] = color
                logger.info(f"Set message color for {caller_filename} to {color_name.upper()}")
            return

    # Fallback if formatter wasn’t attached for some reason
    logger.warning("ColorFormatter not attached; cannot set per-file message color")
