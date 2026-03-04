"""CLI interface for the poker agent."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import structlog
import typer

from poker_agent.agent import PokerAgent
from poker_agent.config import AgentConfig

app = typer.Typer(
    name="poker-agent",
    help="Autonomous poker-playing agent for Telegram mini-app.",
)


def _setup_logging(log_level: str) -> None:
    """Configure structured logging."""
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.dev.ConsoleRenderer(colors=True),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


@app.command()
def start(
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Run without executing clicks (log what would happen).",
    ),
    max_hands: Optional[int] = typer.Option(
        None,
        "--max-hands",
        help="Stop after this many hands.",
    ),
    stop_loss: Optional[int] = typer.Option(
        None,
        "--stop-loss",
        help="Stop if down this many big blinds.",
    ),
    max_cost: Optional[float] = typer.Option(
        None,
        "--max-cost",
        help="Stop if API cost exceeds this amount in USD.",
    ),
    env_file: Path = typer.Option(
        Path(".env"),
        "--env-file",
        help="Path to .env file with configuration.",
    ),
) -> None:
    """Start the poker agent."""
    config = AgentConfig(_env_file=str(env_file))

    # Override with CLI options
    if max_hands is not None:
        config.max_hands = max_hands
    if stop_loss is not None:
        config.stop_loss_bb = stop_loss
    if max_cost is not None:
        config.max_api_cost_usd = max_cost

    _setup_logging(config.log_level)

    agent = PokerAgent(config, dry_run=dry_run)
    asyncio.run(agent.run())


@app.command()
def preflight(
    env_file: Path = typer.Option(
        Path(".env"),
        "--env-file",
        help="Path to .env file with configuration.",
    ),
) -> None:
    """Run preflight checks only (don't start playing)."""
    from poker_agent.preflight import PreflightChecker

    config = AgentConfig(_env_file=str(env_file))
    _setup_logging(config.log_level)

    checker = PreflightChecker(config)
    results = checker.run_all_checks()

    all_passed = True
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(f"  [{status}] {result.name}: {result.message}")
        if not result.passed:
            all_passed = False

    if all_passed:
        typer.echo("\nAll checks passed. Ready to play.")
    else:
        typer.echo("\nSome checks failed. Fix the issues above before starting.")
        raise typer.Exit(code=1)


@app.command()
def screenshot(
    env_file: Path = typer.Option(
        Path(".env"),
        "--env-file",
        help="Path to .env file with configuration.",
    ),
    output: Path = typer.Option(
        Path("test_screenshot.png"),
        "--output",
        "-o",
        help="Output path for the screenshot.",
    ),
) -> None:
    """Take a test screenshot of the Telegram window."""
    config = AgentConfig(_env_file=str(env_file))
    _setup_logging(config.log_level)

    from poker_agent.capture import ScreenCapture, WindowManager

    wm = WindowManager(config.telegram_window_title)
    window = wm.find_window()

    if window is None:
        typer.echo("Could not find Telegram window. Is it running?")
        raise typer.Exit(code=1)

    typer.echo(
        f"Found window: {window.title} at ({window.left}, {window.top}) "
        f"size {window.width}x{window.height}"
    )

    capture = ScreenCapture(retina_scale=config.retina_scale)
    img = capture.take_screenshot(window)
    img.save(str(output), "PNG")
    capture.close()

    typer.echo(f"Screenshot saved to {output} ({img.size[0]}x{img.size[1]} pixels)")
