"""
Command-line interface for the Playwright WebSocket Reporter.

Commands:
- run: Execute a test command with the plugin enabled
- send: Send a test support request without running tests
"""

import asyncio
import logging
import os
import sys
from typing import Optional

import click

from pw_ws_reporter.ws_client import (
    Config,
    ControlTarget,
    SupportRequestPayload,
    WsClient,
    create_meta,
)

# Setup logging
logger = logging.getLogger("pw_ws_reporter")


def setup_logging(verbose: bool = False):
    """Configure logging based on verbosity level."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="[%(levelname)s] %(name)s: %(message)s",
    )


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def cli(verbose: bool):
    """Playwright WebSocket Reporter CLI."""
    setup_logging(verbose)


@cli.command()
@click.argument("command", nargs=-1, required=True)
def run(command: tuple):
    """
    Run a test command with the plugin enabled.
    
    The pytest plugin will auto-load via the entry point and report
    failures to the Flutter app.
    
    Example:
        pw-ws-reporter run pytest tests/test_login.py -v
    """
    logger.info(f"Running command: {' '.join(command)}")
    
    # Execute the command and pass through the exit code
    cmd_str = " ".join(command)
    exit_code = os.system(cmd_str)
    
    # os.system returns the exit code shifted left by 8 bits on Unix
    if os.name != "nt":
        exit_code = exit_code >> 8
    
    sys.exit(exit_code)


@cli.command()
@click.option("--desc", required=True, help="Error description")
@click.option("--url", help="Page URL")
@click.option("--title", help="Page title")
@click.option("--target-id", help="CDP target ID")
@click.option("--test-name", default="manual_test", help="Test name")
def send(
    desc: str,
    url: Optional[str],
    title: Optional[str],
    target_id: Optional[str],
    test_name: str,
):
    """
    Send a test support request without running tests.
    
    This is useful for testing connectivity and the WebSocket protocol.
    
    Example:
        pw-ws-reporter send --desc "Test error" --url "https://example.com"
    """
    logger.info("Sending test support request...")
    
    # Run the async send
    result = asyncio.run(_send_request(desc, url, title, target_id, test_name))
    
    if result:
        click.echo(f"✓ Success!")
        click.echo(f"  Room ID: {result['roomId']}")
        click.echo(f"  Request ID: {result['requestId']}")
    else:
        click.echo("✗ Failed to send support request", err=True)
        sys.exit(1)


async def _send_request(
    desc: str,
    url: Optional[str],
    title: Optional[str],
    target_id: Optional[str],
    test_name: str,
) -> Optional[dict]:
    """
    Helper to send a support request.
    
    Args:
        desc: Error description.
        url: Page URL (optional).
        title: Page title (optional).
        target_id: CDP target ID (optional).
        test_name: Test name.
    
    Returns:
        Result dictionary with roomId and requestId, or None on failure.
    """
    try:
        config = Config()
        
        # Build control target if we have any info
        control_target = None
        if url or title or target_id:
            control_target = ControlTarget(
                browser=config.BROWSER,
                debugPort=config.DEBUG_PORT,
                urlContains=url,
                titleContains=title,
                targetId=target_id,
            )
        
        # Build payload
        meta = create_meta(test_name=test_name)
        payload = SupportRequestPayload(
            description=desc,
            controlTarget=control_target,
            meta=meta,
        )
        
        # Send via WebSocket
        client = WsClient(config)
        try:
            result = await client.send_support_request(payload)
            logger.info(f"Support request sent: {result}")
            return result
        finally:
            await client.aclose()
    
    except Exception as e:
        logger.error(f"Failed to send support request: {e}", exc_info=True)
        return None


if __name__ == "__main__":
    cli()

