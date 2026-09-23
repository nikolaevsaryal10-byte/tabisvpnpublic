#!/usr/bin/env python3
"""
Tabis VPN Management Backend (Modular Edition)
Clean, decoupled architecture:
- config: environment variables, paths, and secrets
- database: SQLite connection pool, schema, and migrations
- models: Pydantic request and response schemas
- core: security, encryption, and FastAPI dependencies
- services: metrics collection, traffic audit, email, and billing
- routers: public, auth, profile, client, and admin endpoints
"""

import uvicorn
import threading
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import HOST, PORT
from database import init_db
from services.metrics_service import metrics_worker_loop
from services.traffic_service import hysteria_journal_collector_worker, traffic_log_retention_worker
from services.billing_service import yookassa_reconciliation_worker_loop, hy2_single_device_watchdog_loop
from services.xray_service import start_xray_background_worker

from routers.public import router as public_router
from routers.auth import router as auth_router
from routers.profile import router as profile_router
from routers.client import router as client_router
from routers.admin import router as admin_router

# 1. Initialize SQLite database schema and run migrations
init_db()

# 2. Start autonomous background workers
metrics_thread = threading.Thread(target=metrics_worker_loop, daemon=True)
metrics_thread.start()

traffic_collector_thread = threading.Thread(target=hysteria_journal_collector_worker, daemon=True)
traffic_collector_thread.start()

traffic_retention_thread = threading.Thread(target=traffic_log_retention_worker, daemon=True)
traffic_retention_thread.start()

billing_reconciliation_thread = threading.Thread(target=yookassa_reconciliation_worker_loop, daemon=True)
billing_reconciliation_thread.start()

hy2_watchdog_thread = threading.Thread(target=hy2_single_device_watchdog_loop, daemon=True)
hy2_watchdog_thread.start()

# Start 3x-ui / Xray sync background worker (VLESS Reality for iOS)
start_xray_background_worker()

# 3. Create FastAPI application
app = FastAPI(
    title="Tabis VPN Management API",
    version="2.5.1",
    description="High-performance, modular VPN management backend for Tabis VPN"
)

# 4. CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 5. Register modular APIRouters
app.include_router(public_router)
app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(client_router)
app.include_router(admin_router)

if __name__ == "__main__":
    uvicorn.run("server:app", host=HOST, port=PORT, reload=False)
