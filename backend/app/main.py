"""FastAPI 应用入口。

启动时初始化数据库表；浏览器侧静态资源由前端 nginx 容器提供，
``/api/*`` 反向代理到本服务。
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import router
from .db import repository

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("latex-editor")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 数据库可能晚于后端容器启动，做有限次重试
    for attempt in range(30):
        try:
            await repository.init_db()
            log.info("database ready")
            break
        except Exception as exc:  # noqa: BLE001
            log.warning("waiting for database (%s): %s", attempt + 1, exc)
            import asyncio
            await asyncio.sleep(1)
    yield
    await repository.close_db()


app = FastAPI(title="LaTeX Math Editor API", version="1.0.0",
              lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
