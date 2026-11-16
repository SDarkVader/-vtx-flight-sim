"""Run the marine solver outside the aircraft clock and persist complete fleet snapshots."""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import threading
import time
import uuid


def _encode(fleet):
    raw = json.dumps(fleet.serialize(), allow_nan=False, separators=(",", ":")).encode()
    return gzip.compress(raw, compresslevel=1, mtime=0)


def _publish(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("." + path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _run(connection, rate, seed, snapshot):
    """Only this process mutates the fleet. Commands and snapshots run between solver steps."""
    try:
        from .world import make_world
        from .harbour_fleet import DT, HarbourFleet

        world = make_world("airport", seed=seed)
        fleet = (
            HarbourFleet.restore(world, json.loads(gzip.decompress(snapshot)))
            if snapshot is not None
            else HarbourFleet(world)
        )
        connection.send((True, None))
    except Exception as exc:
        connection.send((False, str(exc)))
        connection.close()
        return
    current = None
    fault = None
    last = time.monotonic()
    due = 0.0
    published = last
    try:
        while True:
            # A timed pipe poll on Windows can round 1 ms up to a full 15 ms.
            # Check commands immediately while running and pace only unused time.
            if connection.poll(0.0 if current and rate.value and not fault else 0.1):
                action, body = connection.recv()
                try:
                    if action == "close":
                        connection.send((True, None))
                        return
                    if action == "attach":
                        path = Path(body)
                        _publish(path, _encode(fleet))
                        current = path
                        last = published = time.monotonic()
                        result = None
                    elif action == "snapshot":
                        result = _encode(fleet)
                    elif action == "model":
                        result = fleet.visual_geometry(body)
                    elif action == "status":
                        result = fleet.public()
                        result["physics"]["scheduler_backlog_s"] = max(0.0, due)
                        if fault:
                            result["error"] = fault
                    else:
                        if fault:
                            raise ValueError("Harbour simulation stopped: " + fault)
                        boat = body["boatId"]
                        if action == "select":
                            fleet.select(boat)
                        elif action == "command":
                            fleet.action(boat, body["command"])
                        elif action == "dock":
                            fleet.dock(boat, body["berthId"])
                        elif action == "undock":
                            fleet.release(boat)
                        else:
                            raise ValueError("Unknown harbour action")
                        # Ownership changes survive a process exit independently of the flight.
                        if action != "command" and current:
                            _publish(current, _encode(fleet))
                            published = time.monotonic()
                        result = fleet.public()
                    connection.send((True, result))
                except (ValueError, KeyError, TypeError, IndexError, OSError) as exc:
                    connection.send((False, str(exc)))
            now = time.monotonic()
            speed = rate.value
            if not current or not speed or fault:
                last = now
                due = 0.0
                continue
            due += (now - last) * speed
            last = now
            try:
                # Check the pipe between steps even if the water solver is behind wall time.
                if due >= DT:
                    fleet.step()
                    due -= DT
                else:
                    time.sleep(min((DT - due) / speed, 0.01))
                if now - published >= 2.0:
                    _publish(current, _encode(fleet))
                    published = now
            except Exception as exc:
                fault = str(exc)
    except (EOFError, BrokenPipeError):
        pass
    finally:
        connection.close()


class FleetWorker:
    def __init__(self, seed, payload):
        ctx = multiprocessing.get_context("spawn")
        self.generation = uuid.uuid4().hex
        self.rate = ctx.Value("d", 0.0, lock=False)
        self.pipe, child = ctx.Pipe()
        self.process = ctx.Process(target=_run, args=(child, self.rate, seed, payload), daemon=True)
        try:
            self.process.start()
            child.close()
            self._receive()
        except BaseException:
            child.close()
            self.close()
            raise

    def _receive(self):
        if not self.pipe.poll(120):
            self.close(force=True)
            raise ValueError("Harbour worker timed out")
        try:
            ok, value = self.pipe.recv()
        except (OSError, EOFError) as exc:
            raise ValueError("Harbour worker stopped") from exc
        if not ok:
            raise ValueError(value)
        return value

    def request(self, action, body=None):
        if not self.process.is_alive():
            raise ValueError("Harbour worker is unavailable")
        self.pipe.send((action, body))
        return self._receive()

    def close(self, force=False):
        if self.process.pid is not None:
            if self.process.is_alive() and not force:
                try:
                    self.pipe.send(("close", None))
                    self.process.join(2)
                except (EOFError, OSError):
                    pass
            if self.process.is_alive():
                self.process.terminate()
                self.process.join()
        self.pipe.close()


class HarbourSession:
    def __init__(self, data_root):
        self.directory = Path(data_root) / "pilot"
        self.worker = None
        self.lock = threading.RLock()
        self.rate = 0.0

    @property
    def current(self):
        return self.directory / "airport-harbour-current.json.gz"

    @property
    def saved(self):
        return self.directory / "airport-harbour-save.json.gz"

    def set_rate(self, rate):
        self.rate = rate
        worker = self.worker
        if worker:
            worker.rate.value = rate

    def _replace(self, seed, payload):
        incoming = FleetWorker(seed, payload)
        self.install(incoming)

    def install(self, incoming):
        """A rejected fleet is never attached. The outgoing fleet remains usable on failure."""
        with self.lock:
            outgoing = self.worker
            if outgoing:
                outgoing.rate.value = 0.0
                outgoing.request("status")  # barrier before replacing the durable current snapshot
            try:
                incoming.request("attach", str(self.current))
            except BaseException:
                if outgoing:
                    outgoing.rate.value = self.rate
                incoming.close()
                raise
            self.worker = incoming
            self.worker.rate.value = self.rate
            if outgoing:
                outgoing.close()

    def _recover(self, seed):
        if self.worker is None and self.current.is_file():
            self._replace(seed, self.current.read_bytes())

    def status(self, world, *, resume=True):
        with self.lock:
            available = bool(getattr(world, "harbour", None))
            if available and resume:
                self._recover(world.seed)
            status = (
                self.worker.request("status")
                if available and self.worker
                else dict(boats=[], berths=[], selectedId=None)
            )
            return dict(
                status,
                available=available,
                initialized=bool(available and self.worker),
                generation=self.worker.generation if available and self.worker else None,
                saved=self.saved.is_file(),
            )

    def act(self, world, action, body):
        if not getattr(world, "harbour", None):
            raise ValueError("Harbour controls require Main Airport")
        with self.lock:
            if action == "restore":
                if not self.saved.is_file():
                    raise ValueError("No saved harbour fleet")
                self._replace(world.seed, self.saved.read_bytes())
            else:
                self._recover(world.seed)
                if action == "activate" and not self.worker:
                    self._replace(world.seed, None)
                elif not self.worker:
                    raise ValueError("Activate the harbour fleet first")
                elif action == "save":
                    blob = self.worker.request("snapshot")
                    _publish(self.saved, blob)
                elif action != "activate":
                    self.worker.request(action, body)
            return self.status(world, resume=False)

    def model(self, world, boat_id):
        with self.lock:
            if not getattr(world, "harbour", None) or not self.worker:
                raise ValueError("Harbour fleet is unavailable")
            return self.worker.request("model", boat_id)

    def flight_snapshot(self, force=False):
        # Regular aircraft checkpoints read the most recent completed water step snapshot
        # without invoking or waiting on the water solver. Explicit saves capture a fresh barrier.
        if force:
            with self.lock:
                payload = self.worker.request("snapshot") if self.worker else None
        else:
            payload = None
        if payload is None:
            if not self.current.is_file():
                return None
            payload = self.current.read_bytes()
        return dict(
            schema="airport-harbour-gzip-1",
            sha256=hashlib.sha256(payload).hexdigest(),
            data=base64.b64encode(payload).decode("ascii"),
        )

    @staticmethod
    def stage(seed, envelope):
        if not isinstance(envelope, dict):
            raise ValueError("Invalid harbour checkpoint")
        if envelope.get("schema") != "airport-harbour-gzip-1":
            raise ValueError("Unrecognized harbour checkpoint format")
        payload = base64.b64decode(envelope["data"], validate=True)
        if hashlib.sha256(payload).hexdigest() != envelope.get("sha256"):
            raise ValueError("Harbour checkpoint digest mismatch")
        return FleetWorker(seed, payload)

    def restore_flight(self, state, staged):
        if "harbour_fleet" not in state:
            return
        if staged is not None:
            self.install(staged)
            return
        with self.lock:
            if self.worker:
                self.worker.close()
                self.worker = None
            self.current.unlink(missing_ok=True)

    def take_over(self, staged_session):
        """Adopt a validated checkpoint fork after its evidence has been published."""
        staged = staged_session.worker
        if staged is not None:
            self.install(staged)
            staged_session.worker = None
        else:
            self.restore_flight({"harbour_fleet": None}, None)

    def close(self):
        with self.lock:
            if self.worker:
                try:
                    _publish(self.current, self.worker.request("snapshot"))
                finally:
                    self.worker.close()
                    self.worker = None
