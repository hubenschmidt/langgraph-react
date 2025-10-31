import logging, sys

def configure_logging(level=logging.INFO) -> None:
    # Make this idempotent
    root = logging.getLogger()
    if getattr(root, "_configured_by_app", False):
        return

    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler(stream=sys.stdout)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s:%(lineno)d - %(message)s"
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)
    root.setLevel(level)
    root._configured_by_app = True  # sentinel

    # Quiet noisy libs if you want
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
