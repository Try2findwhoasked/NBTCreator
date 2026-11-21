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
         'LEASE_FENCE_CONFLICT', 'LEASE_REQUIRED', 'LEASE_NOT_OWNER', 'RECEIPT_CHANGED', 'IDEMPOTENCY_CONFLICT', 'TASK_SUPERSEDED',
         'TASK_EVIDENCE_CHANGED')


def request(method, params):
    return dict(protocol_version=PROTOCOL_VERSION, method=method, params=params)


def result(reply):
    if not reply['ok']:
        failure = reply['error']
        error(failure['code'], failure['message'], retryable=failure['retryable'], details=failure['details'])
    return reply['data']


def next_step(kind, task, source_matches, attachment_issues=()):
    identifier=task['id']
    if source_matches is False or attachment_issues:
        return dict(action='stop',reason='任务源或绑定附件已变化。原会话可释放租约，核对交接后建立新任务。',
                    **({'recovery':f'task-client inspect tasks {identifier} --view candidates'} if kind=='tasks' else {}))
    if task['status'] in ('completed','superseded','returned','reviewed','failed','cancelled'):
        return dict(action='stop',reason='此任务已结束或正在等待审阅')
    if task.get('lease') and not task.get('lease_expired') and task['lease']['expires_at']>time.time():
        return dict(action='check_lease',command='task-client --session <会话名> status',
                    then='task-client --session <会话名> renew（长任务可用 keepalive）',
                    reason='已有有效租约；仅持有者能续租或回传')
    first='text' if kind=='prompts' else 'comments' if task['comment_count'] else 'context'
    return dict(action='inspect',command=f'task-client inspect {kind} {identifier} --view {first}',
                then=f'task-client --session <会话名> start {kind} {identifier} --owner <执行者>')


def inspect(workspace, kind, identifier, view='compact'):
    if kind == 'prompts':
        from nbt_prompts import read_task
        data=read_task(workspace,identifier,view=view,diagnostic=True)
        if view in ('compact','full') or not data['ready_for_execution']:
            data['next']=next_step(kind,data.get('task',{'id':identifier}),data['source_matches'],data['attachment_issues'])
        return data
    if view not in ('compact','full','comments','context','candidates'):
        error('INVALID_REQUEST','建筑修改任务视图为 compact、comments、context、candidates 或 full')
    from nbt_agent_tasks import dispatch as tasks_action, load_index, task_for, verify, output
    workspace=Path(workspace).resolve()
    if view=='candidates':
        found=tasks_action(workspace,'discover',dict(id=identifier))
        return dict(found,view=view,id=identifier,policy='这些文件待核对亲缘、模型和审阅证据，重新交接后才可回传')
    _,index=load_index(workspace); task=task_for(workspace,index,identifier);matches=True;issue=None
    try:verify(workspace,task)
    except ProtocolError as failure:
        if failure.code!='SOURCE_CHANGED':raise
        matches=False;issue=dict(code=failure.code,error=str(failure),details=failure.details)
    task=output(workspace,task)
    state=dict(source_matches=matches,ready_for_execution=matches,issue=issue)
    if view=='full':return dict(task,**state)
    if view=='comments':
        return dict(id=identifier,view=view,**state,comments=task['comments'])
    if view=='context':
        fields=('source','source_sha256','absolute_source','input_binding','origins','size','camera','approval')
        return dict(id=identifier,view=view,**state,**{key:task[key] for key in fields if key in task})
    fields=('id','name','status','revision','source','source_sha256','size','lease','lease_expired','approval')
    compact={key:task[key] for key in fields if key in task}
    compact.update(view=view,stage='modification',**state,comment_count=len(task['comments']),
                   return_count=len(task['returns']),expand=['comments','context','candidates','full'])
    compact['next']=next_step(kind,compact,matches)
    return compact


def discover_tasks(workspace,kind,pending):
    from nbt_agent_tasks import dispatch as tasks_action
    from nbt_prompts import tasks
    entries=[];issues=[]
    if kind in ('all','prompts'):
        entries.extend(dict(id=item['id'],kind='prompts',name=item['name'],stage=item['stage'],status=item['status'])
                       for item in tasks(workspace,status='pending' if pending else None)['items'])
    if kind in ('all','tasks'):
        found=tasks_action(workspace,'list',{})
        entries.extend(dict(id=item['id'],kind='tasks',name=item['name'],stage='modification',status=item['status'])
                       for item in found['tasks'] if not pending or item['status']=='pending')
        issues.extend(found['errors'])
    for item in entries:
        item['read']=f"task-client inspect {item['kind']} {item['id']}"
    return dict(tasks=entries,issues=issues)


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
        if state['phase']=='blocked' and state.get('lease_token') and state['lease']['expires_at']>time.time():
            data['next'] = dict(action='release', reason='来源变化后可用同一会话释放租约')
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
        if live['source_matches'] is False:
            issue=live.get('issue') or {}
            error('SOURCE_CHANGED',issue.get('error','任务原建筑已变化'),details=dict(issue.get('details',{}),next=live['next']))
        if live.get('attachment_issues'):
            error('TASK_EVIDENCE_CHANGED','任务绑定附件已变化',details={'attachment_issues':live['attachment_issues']})
        if state['kind'] == 'prompts':
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

    def block(self, state, code):
        state.update(phase='blocked', blocked=code)
        if code not in ('SOURCE_CHANGED','TASK_EVIDENCE_CHANGED'):
            state.pop('lease_token', None)

    def send(self, state, *, replay=False):
        pending = state['pending']
        reply = dispatch(self.workspace, pending)
        if not reply['ok']:
            failure = reply['error']
            if failure['code'] not in TRANSIENT:
                state.pop('pending')
                if failure['code'] in STALE or state['phase'] == 'starting':
                    self.block(state,failure['code'])
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
            state.pop('blocked', None)
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
                    self.block(state,failure.code)
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
            if live['source_matches'] is False:
                error('SOURCE_CHANGED', '任务原建筑已变化')
            if live.get('attachment_issues'):
                error('TASK_EVIDENCE_CHANGED','任务绑定附件已变化',details={'attachment_issues':live['attachment_issues']})
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
            can_release = action=='release' and state['phase']=='blocked' and bool(state.get('lease_token'))
            if state['phase'] != 'active' and not can_release:
                error('SESSION_NOT_ACTIVE', '当前本地会话没有可用租约', details=self.public(state))
            common = self.lease_params(state)
            if action == 'heartbeat':
                params = dict(ttl_seconds=state['ttl'])
            elif action == 'complete':
                if state['kind'] == 'prompts':
                    if set(params)=={'review'}:
                        from nbt_refine import digest
                        review=inside(self.workspace,params['review'])
                        if (review/'review.json').is_file():
                            params=dict(review=relative(self.workspace,review),review_sha256=digest(review/'review.json'))
                        else:
                            params=dict(review=relative(self.workspace,review),review_kind='architecture',review_sha256=digest(review/'review-notes.json'))
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
    listing=sub.add_parser('list',help='查找提示词和建筑修改任务')
    listing.add_argument('--kind',choices=['all','prompts','tasks'],default='all')
    listing.add_argument('--pending',action='store_true',help='只列待领取任务')
    recovery=sub.add_parser('recover-registration',help='按当前索引哈希恢复完全相同的任务登记')
    recovery.add_argument('id')
    recovery.add_argument('--expected',required=True,help='list 错误详情中的 expected_sha256')
    recovery.add_argument('--backup',help='可选的 nbt_models 内原登记备份')
    recovery.add_argument('--request-id',help='重试须沿用原编号')
    for action in ('inspect','start'):
        command = sub.add_parser(action)
        command.add_argument('kind', choices=['prompts','tasks'])
        command.add_argument('id')
        if action == 'inspect':
            command.add_argument('--view', choices=(*TASK_VIEWS,'comments','candidates'), default='compact')
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
        if args.action == 'list':
            data = discover_tasks(args.workspace.resolve(),args.kind,args.pending)
        elif args.action=='recover-registration':
            params=dict(id=args.id,expected_sha256=args.expected)
            if args.backup:params['backup']=args.backup
            key=args.request_id or uuid.uuid4().hex
            data=result(dispatch(args.workspace.resolve(),dict(request('tasks.recover',params),request_id=key)))
            data=dict(data,request_id=key)
        elif args.action == 'inspect':
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
