import argparse
import asyncio
import socket
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


_MAX_PORT_ATTEMPTS = 10


def _port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host if host != "0.0.0.0" else "127.0.0.1", port))
            return True
        except OSError:
            return False


def _run_serve(args) -> None:
    settings = Settings()
    if hasattr(args, "host") and args.host:
        settings.host = args.host
    if hasattr(args, "port") and args.port:
        settings.port = args.port

    port = settings.port
    for _ in range(_MAX_PORT_ATTEMPTS):
        if _port_available(settings.host, port):
            break
        print(f"Port {port} is in use, trying {port + 1}...")
        port += 1
    else:
        print(f"No available port found in range {settings.port}–{port - 1}", file=sys.stderr)
        sys.exit(1)

    if port != settings.port:
        print(f"Using fallback port {port}")

    app = create_app(settings)
    uvicorn.run(app, host=settings.host, port=port)


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
