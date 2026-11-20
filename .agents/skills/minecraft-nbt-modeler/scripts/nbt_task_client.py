"""Explicit local client for one task lease and its durable mutation requests."""

import argparse
import json
import os
from pathlib import Path
import re
import time
import uuid

from nbt_agent_protocol import PROTOCOL_VERSION, ProtocolError, error
from nbt_machine import dispatch
from nbt_prompts import TASK_VIEWS, inside, index_lock, relative

TRANSIENT = ('IO_ERROR', 'LOCK_BUSY')
STALE = ('SOURCE_CHANGED', 'STALE_SOURCE', 'STALE_PARENT', 'REVISION_CONFLICT', 'LEASE_EXPIRED',
         'LEASE_FENCE_CONFLICT', 'LEASE_REQUIRED', 'LEASE_NOT_OWNER', 'RECEIPT_CHANGED', 'IDEMPOTENCY_CONFLICT', 'TASK_SUPERSEDED')


def request(method, params):
    return dict(protocol_version=PROTOCOL_VERSION, method=method, params=params)


def result(reply):
    if not reply['ok']:
        failure = reply['error']
        error(failure['code'], failure['message'], retryable=failure['retryable'], details=failure['details'])
    return reply['data']


def inspect(workspace, kind, identifier, view='compact'):
    params = dict(id=identifier)
    if kind == 'prompts':
        params['view'] = view
    elif view not in ('compact', 'full'):
        error('INVALID_REQUEST', '建筑修改任务提供完整视图')
    return result(dispatch(workspace, request(kind + '.get', params)))


class TaskClient:
    def __init__(self, workspace, session):
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', session):
            error('INVALID_REQUEST', '本地会话名须为1～64位小写字母、数字或横线')
        self.workspace = Path(workspace).resolve()
        self.file = inside(self.workspace, Path('nbt_models/_workspaces/agent_protocol/clients') / ('session-' + session) / 'state.json')

    def load(self):
        if not self.file.is_file():
            error('SESSION_NOT_FOUND', '请先 start 启动本地任务会话')
        return json.loads(self.file.read_text(encoding='utf8'))

    def lock(self):
        if not self.file.parent.is_dir():
            error('SESSION_NOT_FOUND', '请先 start 启动本地任务会话')
        return index_lock(self.workspace, self.file.parent)

    def save(self, state):
        path = self.file.with_name(uuid.uuid4().hex + '.tmp')
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, 'w', encoding='utf8') as stream:
                json.dump(state, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(path, self.file)
        finally:
            path.unlink(missing_ok=True)

    def public(self, state):
        data = {key: state[key] for key in ('kind','id','phase','revision','lease','completion') if key in state}
        if state.get('pending'):
            data['pending'] = {key: state['pending'][key] for key in ('request_id','method')}
        if state.get('blocked'):
            data['blocked'] = state['blocked']
        return data

    def status(self):
        with self.lock():
            return self.status_data(self.load())

    def status_data(self, state):
        data = self.public(state)
        if state['phase'] == 'active' and not state.get('pending'):
            self.check_live(state)
        return data

    def check_live(self, state):
        live = inspect(self.workspace, state['kind'], state['id'])
        if state['kind'] == 'prompts':
            if live['source_matches'] is False:
                error('SOURCE_CHANGED', '任务原建筑已变化')
            live = live['task']
        lease = live.get('lease')
        if not lease or lease['fence'] != state['lease']['fence']:
            error('LEASE_FENCE_CONFLICT', '本地会话的租约已失效或被替换')
        if lease['expires_at'] <= time.time():
            error('LEASE_EXPIRED', '本地会话的租约已到期')
        self.check_revision(state, live)

    def revision_field(self, state):
        return 'expected_revision' if state['kind'] == 'prompts' else 'revision'

    def response_revision(self, state, data):
        return data.get('state_revision', 0) if state['kind'] == 'prompts' else data['revision']

    def check_revision(self, state, live):
        if self.response_revision(state, live) != state['revision']:
            error('REVISION_CONFLICT', '任务状态已改变，请核对当前修订')

    def send(self, state, *, replay=False):
        pending = state['pending']
        reply = dispatch(self.workspace, pending)
        if not reply['ok']:
            failure = reply['error']
            if failure['code'] not in TRANSIENT:
                state.pop('pending')
                if failure['code'] in STALE or state['phase'] == 'starting':
                    state.update(phase='blocked', blocked=failure['code'])
                    state.pop('lease_token', None)
                self.save(state)
            result(reply)
        data = reply['data']
        action = pending['method'].split('.')[1]
        state.pop('pending')
        state['revision'] = self.response_revision(state, data)
        if action in ('claim','heartbeat'):
            state.update(phase='active', lease_token=data['lease_token'], lease=data['lease'])
        else:
            state.update(phase='released' if action == 'release' else 'completed', lease=None)
            state.pop('lease_token', None)
            if state['phase'] == 'completed':
                state['completion'] = dict(approval=data['approval'])
                if state['kind'] == 'tasks':
                    returned = data['returns'][-1]
                    state['completion']['return'] = {key: returned[key] for key in ('id','source','source_sha256','acceptance')}
                    self.record_history_status(state,data.get('version_history',{}))
                elif 'evidence' in data:
                    state['completion'].update(evidence=data['evidence'],acceptance=data['acceptance'])
        self.save(state)
        if replay and state['phase'] == 'active':
            try:
                self.check_live(state)
            except ProtocolError as failure:
                if failure.code in STALE:
                    state.update(phase='blocked', blocked=failure.code)
                    state.pop('lease_token', None)
                    self.save(state)
                raise
        return self.public(state)

    def queue(self, state, action, params):
        state['pending'] = dict(request(state['kind'] + '.' + action, params), request_id=uuid.uuid4().hex)
        self.save(state)
        return self.send(state)

    def start(self, kind, identifier, owner, ttl):
        self.file.parent.mkdir(parents=True, exist_ok=True)
        ignore = inside(self.workspace, self.file.parent.parent / '.gitignore')
        try:
            with ignore.open('x', encoding='utf8') as stream:
                stream.write('/session-*/\n')
        except FileExistsError:
            pass
        with self.lock():
            if self.file.exists():
                old = self.load()
                if old.get('pending') or (old['phase'] == 'active' and old['lease']['expires_at'] > time.time()):
                    error('SESSION_IN_USE', '本地会话仍有待恢复的请求或有效任务，请先查看 status')
            live = inspect(self.workspace, kind, identifier)
            if kind == 'prompts' and live['source_matches'] is False:
                error('SOURCE_CHANGED', '任务原建筑已变化')
            state = dict(kind=kind, id=identifier, phase='starting', ttl=ttl, generation=uuid.uuid4().hex)
            revision = self.response_revision(state, live['task'] if kind == 'prompts' else live)
            return self.queue(state, 'claim', dict(id=identifier, owner=owner, ttl_seconds=ttl,
                **{self.revision_field(state): revision}))

    def retry(self):
        with self.lock():
            state = self.load()
            if state.get('pending'):
                return self.send(state, replay=True)
            completion=state.get('completion',{})
            if state['kind']=='tasks' and completion.get('history_pending'):
                from nbt_agent_tasks import repair_return_history
                history=repair_return_history(self.workspace,state['id'],completion['return']['id'])
                self.record_history_status(state,history)
                self.save(state)
            return self.status_data(state)

    def record_history_status(self,state,history):
        completion=state['completion']
        completion['history_pending']=history.get('recorded') is False
        if completion['history_pending']:
            completion['history_error']=history['error']
        else:
            completion.pop('history_error',None)

    def lease_params(self, state):
        return dict(id=state['id'], lease_token=state['lease_token'], fence=state['lease']['fence'],
                    **{self.revision_field(state): state['revision']})

    def change(self, action, **params):
        with self.lock():
            state = self.load()
            if state.get('pending'):
                error('REQUEST_PENDING', '有未确认响应，请先 retry 重放原请求')
            if state['phase'] != 'active':
                error('SESSION_NOT_ACTIVE', '当前本地会话没有可用租约', details=self.public(state))
            common = self.lease_params(state)
            if action == 'heartbeat':
                params = dict(ttl_seconds=state['ttl'])
            elif action == 'complete':
                if state['kind'] == 'prompts':
                    if set(params)=={'review'}:
                        from nbt_refine import digest
                        review=inside(self.workspace,params['review'])
                        params=dict(review=relative(self.workspace,review),review_sha256=digest(review/'review.json'))
                    elif set(params)!={'summary'}:
                        error('EVIDENCE_REQUIRED','制作任务须提供 --review <审阅目录>，只读计划须提供 --summary <检查结果>')
                    action,params='task-status',dict(params,status='completed')
                else:
                    if params.get('review') or not params.get('new_source') or not params.get('summary'):
                        error('INVALID_REQUEST', '建筑修改任务须提供 new-source 和 summary')
                    from nbt_agent_tasks import sha
                    target = inside(self.workspace, params['new_source'])
                    params.update(new_source=relative(self.workspace, target), new_source_sha256=sha(target))
                    action = 'record'
            return self.queue(state, action, dict(common, **params))

    def keepalive(self):
        """Run in a separate terminal while the agent works on the same session."""
        with self.lock():
            state = self.load()
        generation = state['generation']
        while True:
            delay = 5
            try:
                with self.lock():
                    state = self.load()
                    if generation != state['generation'] or state['phase'] in ('released','completed','blocked'):
                        return self.public(state)
                    if state.get('pending'):
                        if not state['pending']['method'].endswith('.heartbeat'):
                            error('REQUEST_PENDING', '有待恢复请求，请先 retry')
                        self.send(state, replay=True)
                    else:
                        due = state['lease']['expires_at'] - state['ttl'] * 2 / 3 - time.time()
                        if due <= 0:
                            self.queue(state, 'heartbeat', dict(self.lease_params(state), ttl_seconds=state['ttl']))
                        else:
                            delay = min(due, delay)
            except (ProtocolError,OSError) as failure:
                if getattr(failure, 'code', 'IO_ERROR') not in TRANSIENT:
                    raise
                if (state.get('lease') or {}).get('expires_at', 0) <= time.time():
                    raise
            time.sleep(delay)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=Path.cwd())
    parser.add_argument('--session', default='default')
    sub = parser.add_subparsers(dest='action', required=True)
    for action in ('inspect','start'):
        command = sub.add_parser(action)
        command.add_argument('kind', choices=['prompts','tasks'])
        command.add_argument('id')
        if action == 'inspect':
            command.add_argument('--view', choices=TASK_VIEWS, default='compact')
        else:
            command.add_argument('--owner', required=True)
            command.add_argument('--ttl', type=int, default=900)
    for action in ('status','retry','renew','keepalive','release'):
        sub.add_parser(action)
    complete = sub.add_parser('complete')
    complete.add_argument('--new-source')
    complete.add_argument('--summary')
    complete.add_argument('--review')
    complete.add_argument('--comments', type=Path, help='JSON array of handled comments')
    args = parser.parse_args()
    try:
        if args.action == 'inspect':
            data = inspect(args.workspace.resolve(), args.kind, args.id, args.view)
        else:
            client = TaskClient(args.workspace, args.session)
            if args.action == 'start':
                data = client.start(args.kind, args.id, args.owner, args.ttl)
            elif args.action in ('status','retry','keepalive'):
                data = getattr(client, args.action)()
            elif args.action == 'complete':
                params = {key: getattr(args, key) for key in ('new_source','summary','review') if getattr(args, key) is not None}
                if args.comments is not None:
                    with args.comments.open(encoding='utf-8-sig') as stream:
                        raw = stream.read(2 * 1024 * 1024 + 1)
                    if len(raw.encode('utf8')) > 2 * 1024 * 1024:
                        error('INVALID_REQUEST', '批注登记超过2MiB')
                    params['comments'] = json.loads(raw)
                data = client.change('complete', **params)
            else:
                data = client.change('heartbeat' if args.action == 'renew' else args.action)
        print(json.dumps(dict(ok=True, data=data), ensure_ascii=False))
        return 0
    except KeyboardInterrupt:
        return 130
    except (ValueError,OSError,KeyError,TypeError) as failure:
        print(json.dumps(dict(ok=False, error=dict(code=getattr(failure,'code','IO_ERROR' if isinstance(failure,OSError) else 'VALIDATION_ERROR'),
            message=str(failure), details=getattr(failure,'details',{}))), ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
