import argparse
import asyncio
import os
from pathlib import Path
from typing import Any, AsyncGenerator
from contextlib import asynccontextmanager
import structlog

from app.config import settings
from app.utils.browser_stealth import (
    DEFAULT_STEALTH_USER_AGENT,
    apply_stealth_context,
    configure_resource_filters,
)

logger = structlog.get_logger(__name__)


def resolve_user_data_dir(custom_path: str | Path | None = None) -> Path:
    """
    Resolves and ensures the absolute path for persistent browser profiles.
    Defaults to settings.BROWSER_USER_DATA_DIR (~/.config/job_agent_browser_profile).
    """
    raw_path = custom_path or settings.BROWSER_USER_DATA_DIR
    resolved = Path(os.path.expanduser(str(raw_path))).resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


@asynccontextmanager
async def persistent_browser_session(
    user_data_dir: str | Path | None = None,
    headless: bool | None = None,
    proxy: dict[str, str] | None = None,
    enable_stealth: bool = True,
    block_heavy_resources: bool = True,
    args: list[str] | None = None,
) -> AsyncGenerator[Any, None]:
    """
    Asynchronous context manager providing a hardened, persistent Playwright Chromium context.
    Maintains cookies, session storage, and cache across runs to bypass login walls and CAPTCHAs.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError as err:
        raise RuntimeError(
            "Playwright is not installed. Install via `pip install playwright && playwright install chromium`"
        ) from err

    profile_dir = resolve_user_data_dir(user_data_dir)
    is_headless = settings.BROWSER_HEADLESS if headless is None else headless

    launch_args = [
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    if args:
        launch_args.extend(args)

    logger.info(
        "launching_persistent_browser_context",
        profile_dir=str(profile_dir),
        headless=is_headless,
        has_proxy=bool(proxy),
    )

    async with async_playwright() as pw:
        context = await pw.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=is_headless,
            proxy=proxy,
            args=launch_args,
            user_agent=DEFAULT_STEALTH_USER_AGENT,
            slow_mo=settings.BROWSER_SLOW_MO if not is_headless else None,
        )

        if enable_stealth:
            await apply_stealth_context(context)

        # Apply resource filters on page creation if requested
        if block_heavy_resources:
            context.on("page", lambda page: asyncio.create_task(configure_resource_filters(page)))

        try:
            yield context
        finally:
            await context.close()


async def launch_interactive_login(
    platform_url: str,
    user_data_dir: str | Path | None = None,
) -> None:
    """
    Launches a visible (non-headless) browser session targeting the specified login URL.
    Allows manual authentication, 2FA, and CAPTCHA solving.
    Session tokens are persisted to user_data_dir for subsequent headless operations.
    """
    logger.info("interactive_login_session_starting", url=platform_url)
    profile_dir = resolve_user_data_dir(user_data_dir)

    print("\n" + "=" * 70)
    print(f" INTERACTIVE LOGIN SESSION: {platform_url}")
    print(f" Profile Storage: {profile_dir}")
    print("=" * 70)
    print(" 1. Log in with your credentials.")
    print(" 2. Complete any 2FA / CAPTCHA challenges.")
    print(" 3. When logged in, close the browser window or press Enter here.")
    print("=" * 70 + "\n")

    async with persistent_browser_session(
        user_data_dir=profile_dir,
        headless=False,
        block_heavy_resources=False,  # Allow full images/CSS for manual login
    ) as context:
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto(platform_url, wait_until="domcontentloaded")

        loop = asyncio.get_running_loop()
        # Wait for user input in console or browser closure
        try:
            await loop.run_in_executor(None, input, "Press Enter once you have logged in successfully: ")
        except (EOFError, KeyboardInterrupt):
            pass

    logger.info("interactive_login_session_saved", profile_dir=str(profile_dir))
    print(f"\n[+] Session successfully saved to {profile_dir}. Ready for headless scraping.\n")


def main() -> None:
    """CLI entrypoint for interactive login and session management."""
    parser = argparse.ArgumentParser(description="Job Agent Browser Session & Stealth Manager")
    parser.add_argument("--login", type=str, help="Target URL for manual login (e.g. https://www.linkedin.com/login)")
    parser.add_argument("--dir", type=str, default=None, help="Custom profile directory path")
    args = parser.parse_args()

    if args.login:
        asyncio.run(launch_interactive_login(args.login, user_data_dir=args.dir))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
