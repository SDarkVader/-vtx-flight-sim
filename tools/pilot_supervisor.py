"""Run-scoped supervisor for JSON-lines pilot adapters.

An adapter is an external process that reads state packets on stdin and writes
JSON action packets on stdout.  The supervisor never starts a flight and never
uses a command timeout as a provider failure. It reports an actual process exit
and, when configured, attaches the next adapter to the same objective.
"""
from __future__ import annotations
import argparse
import json
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
if __package__:
    from .persistent_pilot import request
else:
    from persistent_pilot import request


class Provider:
    def __init__(self, spec):
        self.id = spec['id']
        self.command = spec['command']
        if not isinstance(self.id, str) or not self.id.strip() or len(self.id) > 100:
            raise ValueError('Provider id must contain 1 to 100 characters')
        if not isinstance(self.command, list) or not self.command or not all(isinstance(x, str) and x for x in self.command):
            raise ValueError('Provider command must be a nonempty array of arguments')
        self.process = None
        self.inbox = queue.Queue(maxsize=1)
        self.outbox = queue.Queue(maxsize=32)

    def start(self):
        self.process = subprocess.Popen(self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=None, text=True, encoding='utf-8', bufsize=1)
        threading.Thread(target=self._writer, daemon=True).start()
        threading.Thread(target=self._reader, daemon=True).start()

    def _writer(self):
        while self.process.poll() is None:
            packet = self.inbox.get()
            if packet is None: return
            try:
                self.process.stdin.write(json.dumps(packet, allow_nan=False, separators=(',', ':')) + '\n')
                self.process.stdin.flush()
            except (BrokenPipeError, OSError, ValueError):
                return

    def _reader(self):
        try:
            for line in self.process.stdout:
                try:
                    value = json.loads(line)
                    if isinstance(value, dict): self.outbox.put(value)
                except (ValueError, TypeError):
                    # Keep the adapter alive; malformed messages are not flight actions.
                    continue
        except (OSError, ValueError):
            pass

    def send_latest(self, packet):
        try: self.inbox.put_nowait(packet)
        except queue.Full:
            try: self.inbox.get_nowait()
            except queue.Empty: pass
            try: self.inbox.put_nowait(packet)
            except queue.Full: pass

    def close(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try: self.process.wait(timeout=2)
            except subprocess.TimeoutExpired: pass
        try: self.inbox.put_nowait(None)
        except queue.Full: pass


class Supervisor:
    def __init__(self, base, run_id, providers, *, call=request, provider_factory=Provider):
        if not run_id or not providers: raise ValueError('A run ID and at least one provider are required')
        ids = [p.get('id') for p in providers]
        if len(set(ids)) != len(ids): raise ValueError('Provider ids must be distinct')
        self.base, self.run_id, self.specs = base, run_id, list(providers)
        self.call, self.factory = call, provider_factory
        self.index = -1
        self.provider = None
        self.epoch = None
        self.failure = None
        self.state = 'connecting'
        self.last_error = None

    def api(self, path, data=None):
        return self.call(self.base, path, data)

    def _start_next(self):
        while self.index + 1 < len(self.specs):
            self.index += 1
            child = self.factory(self.specs[self.index])
            try: child.start()
            except OSError as exc:
                self.last_error = f'Provider {child.id} could not start: {exc}'
                continue
            self.provider = child
            self.epoch = None
            return True
        self.provider = None
        self.state = 'providers_exhausted'
        return False

    def tick(self):
        """One nonblocking step. Transport errors propagate and are retried by the caller."""
        view = self.api('/api/view')
        if view.get('run_id') != self.run_id or not view.get('active'):
            self.state = 'flight_ended_or_changed'
            return False
        if view.get('authority') != 'colin':
            self.state = 'manual_authority'
            return False
        if self.failure is not None:
            # A server outage must not be confused with an adapter failure; this
            # payload exists only after observing the child's actual exit.
            if (view.get('pilot_epoch') == self.failure['pilot_epoch'] and
                self.failure['pilot_id'] in (view.get('pilot_owner'), view.get('pending_pilot'))):
                result = self.api('/api/pilot/failure', self.failure)
                self.last_error = json.dumps(result.get('fallback'))
            self.failure = None
            self.provider = None
            self.epoch = None
            if not self._start_next(): return False
            view = self.api('/api/view')
        if self.provider is None and not self._start_next(): return False
        child = self.provider
        if child.process.poll() is not None:
            code = child.process.returncode
            # The handover may have succeeded even if its response was lost.
            if self.epoch is None and child.id in (view.get('pilot_owner'), view.get('pending_pilot')):
                self.epoch = view['pilot_epoch']
            if self.epoch is not None:
                self.failure = dict(run_id=self.run_id, pilot_id=child.id, pilot_epoch=self.epoch,
                                    reason=f'Pilot provider process exited with status {code}')
                self.state = 'reporting_provider_failure'
            else:
                self.provider = None
            return True
        if self.epoch is None:
            owner = view.get('pilot_owner')
            if owner not in (None, 'r6-deterministic-hold', child.id):
                self.state = 'pilot_owned_elsewhere'
                return False
            if owner == child.id:
                self.epoch = view['pilot_epoch']
            else:
                answer = self.api('/api/pilot/handover', dict(run_id=self.run_id, pilot_id=child.id,
                                                               expected_epoch=view['pilot_epoch']))
                self.epoch = answer['pilot_epoch']
        elif (view.get('pilot_epoch') != self.epoch or
              child.id not in (view.get('pilot_owner'), view.get('pending_pilot'))):
            self.state = 'ownership_changed'
            return False
        if view.get('paused'):
            self.state = 'paused'
            return True
        observation = self.api('/api/observe')
        child.send_latest(dict(type='state', run_id=self.run_id, objective=view.get('objective'),
                               observation=observation))
        try: packet = child.outbox.get_nowait()
        except queue.Empty:
            self.state = 'awaiting_provider'
            return True
        if packet.get('type') == 'failure':
            reason = packet.get('reason')
            if not isinstance(reason, str) or not reason.strip():
                self.state = 'invalid_provider_message'
                return True
            self.failure = dict(run_id=self.run_id, pilot_id=child.id, pilot_epoch=self.epoch,
                                reason=reason.strip()[:500])
            child.close()
            self.state = 'reporting_provider_failure'
            return True
        if packet.get('type') != 'action' or not isinstance(packet.get('action'), dict):
            self.state = 'invalid_provider_message'
            return True
        action = dict(packet['action'])
        # Never trust an adapter to choose or retain another flight's ownership.
        action.update(authority='colin', pilot_id=child.id, pilot_epoch=self.epoch, pilot_run_id=self.run_id)
        self.api('/api/action', action)
        self.state = 'active'
        return True

    def close(self):
        if self.provider: self.provider.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True)
    parser.add_argument('--run-id', required=True, help='Existing flight to attach to; never creates a flight')
    parser.add_argument('--providers', required=True, help='JSON file: {"providers": [{"id": ..., "command": [...]}]}')
    args = parser.parse_args()
    providers = json.loads(Path(args.providers).read_text(encoding='utf-8'))['providers']
    supervisor = Supervisor(args.base, args.run_id, providers)
    previous = None
    try:
        while True:
            try:
                keep_running = supervisor.tick()
            except (URLError, HTTPError, OSError, ValueError, KeyError) as exc:
                # A transient server disconnect leaves the child and ownership intact.
                supervisor.state = 'connection_or_response_error'
                supervisor.last_error = str(exc)
                keep_running = True
            status = (supervisor.state, supervisor.last_error)
            if status != previous:
                print(json.dumps(dict(state=status[0], detail=status[1]), ensure_ascii=False), flush=True)
                previous = status
            if not keep_running: break
            time.sleep(0.5)
    except KeyboardInterrupt:
        print(json.dumps(dict(state='supervisor_stopped', detail='Last applied controls remain held')), flush=True)
    finally:
        supervisor.close()


if __name__ == '__main__': main()
