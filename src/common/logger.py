import logging
import sys
import time

import colorlog
from rich.console import Console
from rich.table import Table


# Ensure UTF-8 encoding on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        # Python < 3.7 doesn't have reconfigure
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

console = Console(force_terminal=True, legacy_windows=False)


class Logger:
    def __init__(self):
        self.status = None
        self.start_time = None
        self._setup_standard_logging()

    def _setup_standard_logging(self):
        """Setup colorlog for standard Python logging integration"""
        if not logging.getLogger().handlers:  # Only setup if not already configured
            handler = colorlog.StreamHandler()
            handler.setFormatter(
                colorlog.ColoredFormatter(
                    "%(log_color)s%(levelname)-8s%(reset)s %(blue)s%(name)s%(reset)s: %(message)s",
                )
            )
            logging.basicConfig(level=logging.INFO, handlers=[handler])

    def _format_message(self, text, elapsed=None, status=None):
        elapsed_str = f"{elapsed:>8}" if elapsed else ""
        if status == "success":
            text = f"[bold green]{text}[/]"
            elapsed_str = f"[bold green]{elapsed_str}[/]" if elapsed_str else ""
        elif status == "fail":
            text = f"[bold red]{text}[/]"
            elapsed_str = f"[bold red]{elapsed_str}[/]" if elapsed_str else ""
        else:
            text = f"[bold blue]{text}[/]"
            elapsed_str = f"[blue]{elapsed_str}[/]" if elapsed_str else ""
        return text, elapsed_str

    def _get_emoji(self, status: str | None = None) -> str:
        if status == "success":
            return "[bold green]✔[/]"
        elif status == "fail":
            return "[bold red]✖[/]"
        elif status == "loading":
            return "[bold yellow]⠋[/]"
        else:
            return "[bold blue]ℹ[/]"

    def _rich_log(self, text, elapsed=None, status=None):
        text, elapsed_str = self._format_message(text, elapsed, status)
        table = Table.grid(expand=True)
        table.add_column(justify="left", width=32, ratio=2, no_wrap=False)
        table.add_column(justify="right", width=12, ratio=1, no_wrap=True, highlight=True)
        table.add_row(text, elapsed_str)
        try:
            console.print(table)
        except Exception as e:
            # Defensive: fallback if LiveError or similar occurs
            if e.__class__.__module__.startswith("rich.") and "Live" in e.__class__.__name__:
                print(f"[FALLBACK LOG]: {text} {elapsed_str}")
            else:
                raise

    def start(self, text):
        if self.status:
            # End previous status if still active
            self.status.__exit__(None, None, None)
            self.status = None
        self.start_time = time.monotonic()
        self.status = console.status(text)
        self.status.__enter__()

    def succeed(self, text):
        elapsed = None
        if self.start_time is not None:
            elapsed = f"{time.monotonic() - self.start_time:.2f}s"
            self.start_time = None
        if self.status:
            self.status.__exit__(None, None, None)
            self.status = None
        self._rich_log(f"{self._get_emoji('success')} {text}", elapsed, "success")

    def fail(self, text):
        elapsed = None
        if self.start_time is not None:
            elapsed = f"{time.monotonic() - self.start_time:.2f}s"
            self.start_time = None
        if self.status:
            try:
                self.status.__exit__(None, None, None)
            except Exception:
                # If status exit fails, just set to None and continue
                pass
            finally:
                self.status = None
        self._rich_log(f"{self._get_emoji('fail')} {text}", elapsed, "fail")

    def info(self, text):
        self._rich_log(f"{self._get_emoji('info')} {text}")

    def warning(self, text):
        self._rich_log(f"[bold yellow]⚠[/] {text}")

    def debug(self, text):
        self._rich_log(f"[dim]🐛 {text}[/]")

    def error(self, text):
        """Alias for fail() method to maintain compatibility"""
        self.fail(text)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.status:
            self.status.__exit__(exc_type, exc_val, exc_tb)
            self.status = None


# Create a single logger instance that can be imported throughout the codebase
logger = Logger()
