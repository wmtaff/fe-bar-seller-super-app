"""Lakebase connection helpers for the integration tests (Task 8).

Auth: an OAuth database credential (1 h) for the caller's own identity, generated from the CLI
profile. Nothing is hard-coded: the endpoint is resolved from the project/branch names.

macOS: Python's resolver can fail on the long Lakebase hostnames, so if getaddrinfo fails the
host is resolved with `dig` and passed as `hostaddr` (the `host` stays set for TLS SNI).
"""

import shutil
import socket
import subprocess

import psycopg
from databricks.sdk.service.postgres import EndpointType


def rw_endpoint(ws, branch_path: str):
    eps = [e for e in ws.postgres.list_endpoints(parent=branch_path)
           if e.status and e.status.endpoint_type == EndpointType.ENDPOINT_TYPE_READ_WRITE]
    if not eps:
        raise RuntimeError(f"no read-write endpoint on {branch_path}")
    return eps[0]


def _hostaddr(host: str) -> str | None:
    try:
        socket.getaddrinfo(host, 5432)
        return None
    except socket.gaierror:
        if not shutil.which("dig"):
            raise
        out = subprocess.run(["dig", "+short", host], capture_output=True, text=True, check=True).stdout
        ips = [line for line in out.split() if line[:1].isdigit()]
        if not ips:
            raise
        return ips[-1]


def connect(ws, branch_path: str, dbname: str = "databricks_postgres") -> psycopg.Connection:
    ep = rw_endpoint(ws, branch_path)
    host = ep.status.hosts.host
    token = ws.postgres.generate_database_credential(endpoint=ep.name).token
    kwargs = dict(host=host, dbname=dbname, user=ws.current_user.me().user_name, password=token,
                  sslmode="require", connect_timeout=30, autocommit=True)
    addr = _hostaddr(host)
    if addr:
        kwargs["hostaddr"] = addr
    return psycopg.connect(**kwargs)
