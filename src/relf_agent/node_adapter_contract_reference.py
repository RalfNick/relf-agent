"""Independent SQLite test supplier; application observations are not Run authority."""

import asyncio
import json
import sqlite3
import uuid
from contextlib import closing
from pathlib import Path

from .errors import DefinitionMismatch, ValidationError
from .types import canonical, digest


def _detached(value):
    try:
        return json.loads(canonical(value))
    except (ValueError, TypeError, RecursionError, UnicodeError, OverflowError):
        raise ValidationError("Reference node requires finite JSON") from None


class ReferenceNodeSource:
    """Implement the async component port directly, borrowing no SDK implementation."""

    def __init__(self, path):
        self.path = self._path = str(Path(path).resolve())
        self._closed, self._active, self._fault, self._gate = False, 0, None, None
        self._version = "1"
        self._connection = sqlite3.connect(self._path)
        try:
            with self._connection:
                self._connection.executescript(
                    "CREATE TABLE IF NOT EXISTS node_resource(id INTEGER PRIMARY KEY,dataset TEXT);"
                    "CREATE TABLE IF NOT EXISTS node_setting(id INTEGER PRIMARY KEY,result TEXT);"
                    "CREATE TABLE IF NOT EXISTS node_calls(id INTEGER PRIMARY KEY,input TEXT,config TEXT,effect_key TEXT);"
                    "CREATE TABLE IF NOT EXISTS node_audit(kind TEXT PRIMARY KEY,count INTEGER);"
                )
                self._connection.execute(
                    "INSERT OR IGNORE INTO node_resource VALUES (1,?)", (uuid.uuid4().hex,)
                )
                self._dataset = self._connection.execute(
                    "SELECT dataset FROM node_resource WHERE id=1"
                ).fetchone()[0]
            info = Path(self._path).stat()
            self._physical = info.st_dev, info.st_ino
        except BaseException:
            self._connection.close()
            raise

    @property
    def identity(self):
        return {
            "kind": "independent-sqlite-node",
            "version": self._version,
            "backend_id": digest([self.path, self._dataset]),
        }

    def _check_file(self):
        try:
            info = Path(self._path).stat(follow_symlinks=False)
            if self.path != self._path or (info.st_dev, info.st_ino) != self._physical:
                raise DefinitionMismatch("Original reference node source changed")
        except OSError:
            raise DefinitionMismatch("Original reference node source unavailable") from None

    def _check(self):
        if self._closed:
            raise ValidationError("Reference node client is closed")
        self._check_file()

    def _count(self, kind):
        self._connection.execute(
            "INSERT INTO node_audit VALUES (?,1) ON CONFLICT(kind) DO UPDATE SET count=count+1",
            (kind,),
        )

    def configure(self, kind, data):
        self._check()
        if kind == "reset" and data == {}:
            self.inject_fault("reset")
            return
        if kind != "output" or type(data) is not dict or set(data) != {"result"}:
            raise ValidationError("Reference output configuration requires result")
        result = canonical(_detached(data["result"]))
        with self._connection:
            self._connection.execute(
                "INSERT INTO node_setting VALUES (1,?) ON CONFLICT(id) DO UPDATE SET result=excluded.result",
                (result,),
            )

    async def execute(self, input, config, context):
        self._check()
        input, config = _detached(input), _detached(config)
        if type(config) is not dict:
            raise ValidationError("Reference node config requires an object")
        self._active += 1
        try:
            with self._connection:
                self._connection.execute(
                    "INSERT INTO node_calls(input,config,effect_key) VALUES (?,?,?)",
                    (canonical(input), canonical(config), context.effect_key),
                )
                self._count("execute_calls")
            if self._fault == "handler-error":
                raise RuntimeError("private-node-fixture-secret")
            gate = self._gate
            if gate is not None:
                entered, released = gate
                entered.set()
                while not released.is_set():
                    try:
                        await released.wait()
                    except asyncio.CancelledError:
                        # Actual work deliberately outlives observer cancellation.
                        continue
            self._check()
            row = self._connection.execute("SELECT result FROM node_setting WHERE id=1").fetchone()
            return None if row is None else json.loads(row[0])
        finally:
            self._active -= 1

    def inject_fault(self, kind):
        self._check()
        if kind == "identity-drift":
            self._version = "changed"
        elif kind == "method-drift":

            async def changed(input, config, context):
                raise AssertionError("A replacement handler must never run")

            self.execute = changed
        elif kind == "handler-error":
            self._fault = kind
        elif kind == "reset":
            self._version, self._fault = "1", None
            self.__dict__.pop("execute", None)
        else:
            raise ValidationError("Unknown reference node fault")

    def pause(self, operation):
        from .node_adapter_contract import NodeContractPause

        self._check()
        if operation != "execute" or self._gate is not None:
            raise ValidationError("Reference node supports one execute pause")
        entered, released = self._gate = asyncio.Event(), asyncio.Event()

        async def wait_entered():
            await entered.wait()

        async def release():
            released.set()

        return NodeContractPause(wait_entered, release)

    def audit(self):
        # Diagnostic reads do not reopen the original closed application client.
        self._check_file()
        with closing(sqlite3.connect(self._path)) as connection:
            values = dict(connection.execute("SELECT kind,count FROM node_audit"))
        return {
            name: values.get(name, 0)
            for name in ("execute_calls", "reconcile_calls", "close_calls")
        }

    def requests(self):
        self._check_file()
        with closing(sqlite3.connect(self._path)) as connection:
            rows = connection.execute(
                "SELECT input,config,effect_key FROM node_calls ORDER BY id"
            ).fetchall()
        return [
            {"input": json.loads(input), "config": json.loads(config), "effect_key": effect_key}
            for input, config, effect_key in rows
        ]

    def close(self):
        if self._closed:
            return
        if self._active:
            raise ValidationError("Actual reference node work remains active")
        self._check_file()
        with self._connection:
            self._count("close_calls")
        self._connection.close()
        self._closed = True

    def reopen(self):
        self.close()
        self._check_file()
        connection = sqlite3.connect(self._path)
        try:
            row = connection.execute("SELECT dataset FROM node_resource WHERE id=1").fetchone()
            if row is None or row[0] != self._dataset:
                raise DefinitionMismatch("Original reference node dataset changed")
        except BaseException:
            connection.close()
            raise
        self._connection, self._closed = connection, False


class _OfflineFixture:
    def prepare(self, case_id, workspace):
        from .adapter_contract_catalog import catalog_for

        if (
            type(case_id) is not str
            or case_id not in catalog_for("node-executor", "1", "core").case_ids
        ):
            raise ValidationError("Unknown node contract case")
        from .node_adapter_contract import NodeContractResource, NodeContractSession

        source = ReferenceNodeSource(Path(workspace) / "node-source.sqlite")
        try:
            return NodeContractSession(
                component=source,
                resources=(NodeContractResource(source),),
                configure=source.configure,
                inject_fault=source.inject_fault,
                pause=source.pause,
                audit=source.audit,
                reopen=source.reopen,
            )
        except BaseException:
            source.close()
            raise


def offline_node_fixture():
    """Return an inert fixture; opening SQLite requires explicit preparation."""
    return _OfflineFixture()
