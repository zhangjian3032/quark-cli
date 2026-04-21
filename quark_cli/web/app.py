"""
FastAPI 应用主入口
quark-cli serve 启动的 HTTP 服务
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from quark_cli import __version__


def create_app(config_path=None):
    """创建 FastAPI 应用实例"""
    app = FastAPI(
        title="Quark CLI",
        description="夸克网盘 + 影视中心 管理面板",
        version=__version__,
        docs_url="/api/docs",
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.config_path = config_path

    from quark_cli.web.routes import media, discovery, drive, search, account, scheduler, sync, dashboard, subscribe, rss, torrent, guangya
    app.include_router(dashboard.router, prefix="/api")
    app.include_router(media.router, prefix="/api")
    app.include_router(discovery.router, prefix="/api")
    app.include_router(drive.router, prefix="/api")
    app.include_router(search.router, prefix="/api")
    app.include_router(account.router, prefix="/api")
    app.include_router(scheduler.router, prefix="/api")
    app.include_router(sync.router, prefix="/api")
    app.include_router(subscribe.router, prefix="/api")
    app.include_router(rss.router, prefix="/api")
    app.include_router(torrent.router, prefix="/api")
    app.include_router(guangya.router, prefix="/api")

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": __version__}

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            file_path = static_dir / full_path
            if file_path.is_file():
                return FileResponse(str(file_path))
            return FileResponse(str(static_dir / "index.html"))
    else:
        @app.get("/")
        def no_frontend():
            return {
                "message": "Quark CLI API 已启动，前端未构建",
                "docs": "/api/docs",
                "hint": "cd web && npm install && npm run build",
            }

    return app
