import argparse
import asyncio
import sys

import uvicorn

from webcontrol.api.app import create_app
from webcontrol.config import Settings


def cli() -> None:
    parser = argparse.ArgumentParser(description="WebControl — browser automation for LLM agents")
    subparsers = parser.add_subparsers(dest="command")

    serve_parser = subparsers.add_parser("serve", help="Start the HTTP server (REST + MCP)")
    serve_parser.add_argument("--host", default=None)
    serve_parser.add_argument("--port", type=int, default=None)

    subparsers.add_parser("mcp-stdio", help="Run MCP server over stdio (for local clients)")

    args = parser.parse_args()

    if args.command == "serve" or args.command is None:
        _run_serve(args)
    elif args.command == "mcp-stdio":
        _run_mcp_stdio()
    else:
        parser.print_help()
        sys.exit(1)


def _run_serve(args) -> None:
    settings = Settings()
    if hasattr(args, "host") and args.host:
        settings.host = args.host
    if hasattr(args, "port") and args.port:
        settings.port = args.port

    app = create_app(settings)
    uvicorn.run(app, host=settings.host, port=settings.port)


def _run_mcp_stdio() -> None:
    from webcontrol.core.service import WebControlService
    from webcontrol.mcp_server.server import create_mcp_server

    settings = Settings()
    service = WebControlService(settings)

    async def run():
        await service.startup()
        try:
            mcp = create_mcp_server(lambda: service)
            await mcp.run_stdio_async()
        finally:
            await service.shutdown()

    asyncio.run(run())


if __name__ == "__main__":
    cli()
