"""Local creation workflow for a claimed, frozen building brief."""

from pathlib import Path
from time import monotonic

from nbt_agent.creation_execution import (Execution, StageError, prepare_review, read, readback,
    reference, saved_binding)
from nbt_agent.creation_inputs import evidence, fields, gates, local_repair, model_request, options, routes, text
from nbt_agent.creation_policy import describe
from nbt_agent.protocol import error
from nbt_agent.task_client import TaskClient
from nbt_building.plan import build, fingerprint
from nbt_composition.working_model import ModelConflict
from nbt_project.prompts import index_lock, inside, read_task
from nbt_project.queues import write


class Creation:
    def __init__(self, workspace, session):
        self.workspace = Path(workspace).resolve()
        self.client = TaskClient(workspace, session)
        state = self.client.load()
        if state['kind'] != 'prompts':
            error('INVALID_REQUEST', '创作执行需要一条已领取的提示词任务')
        self.id = state['id']
        self.fence = state['lease']['fence'] if state.get('lease') else state.get('lease_epoch')
        # Persist the original fence in the job pointer so a completed session
        # can still reopen its evidence without acquiring another lease.
        self.pointer = self.client.file.parent/'creation-job.json'
        if self.fence is None:
            self.fence = read(self.pointer)['fence'] if self.pointer.is_file() else None
        if type(self.fence) is not int or self.fence < 1:
            error('SESSION_NOT_ACTIVE', '请先领取显式指定的创作任务')
        self.directory = inside(workspace, f'nbt_models/_workspaces/creation/{self.id}/{self.fence}')
        self.file = self.directory/'workflow.json'

    def live(self):
        state = self.client.load()
        if (state['phase']!='active' or not state.get('lease') or state['lease']['fence']!=self.fence or state['id']!=self.id):
            error('SESSION_NOT_ACTIVE', '创作会话的领取权已变化')
        if state.get('pending') and not state['pending']['method'].endswith('.heartbeat'):
            error('REQUEST_PENDING', '先用 task-client retry 恢复原请求')
        # A keepalive can complete between load and check_live.
        for _ in range(3):
            from nbt_agent.protocol import ProtocolError
            try:
                self.client.check_live(state)
                return
            except ProtocolError as failure:
                latest = self.client.load()
                if failure.code!='REVISION_CONFLICT' or (latest.get('lease') or {}).get('fence')!=self.fence or latest==state:
                    raise
                state = latest
        self.client.check_live(state)

    def frozen(self):
        data = read_task(self.workspace, self.id, diagnostic=True)
        if not data['ready_for_execution']:
            error('TASK_EVIDENCE_CHANGED', '任务附件或源已变化')
        if data['task']['stage'] != 'draft' or data['task'].get('source'):
            error('INVALID_REQUEST', '此执行流程用于整栋初稿；已有建筑继续使用原审阅及受管修改入口')
        return data

    def state(self):
        if not self.file.is_file():
            error('CREATION_NOT_STARTED', '请先运行 creation start')
        return read(self.file)

    def save(self, state):
        write(self.file, state)

    def start(self, request):
        self.live()
        frozen = self.frozen()
        policy = describe(frozen['task'].get('creation'))
        self.directory.mkdir(parents=True, exist_ok=True)
        with index_lock(self.workspace,self.directory):
            if self.file.is_file():
                state = self.state()
                if request and request != state['options']:
                    error('IDEMPOTENCY_CONFLICT', '当前会话已冻结不同的比较条件')
            else:
                request = options(self.workspace, policy, request)
                state = dict(schema_version=1, task=self.id, revision=frozen['task']['revision'], policy=policy,
                             options=request, requests=routes(policy), attempts=[], ready={})
                self.save(state)
                write(self.pointer, dict(fence=self.fence))
        return self.brief()

    def brief(self, expand=False):
        state = self.state()
        frozen = self.frozen()
        if frozen['task']['revision'] != state['revision']:
            error('TASK_EVIDENCE_CHANGED', '交接修订与创作会话不一致')
        compact = read_task(self.workspace,self.id,view='compact',diagnostic=True)
        document = frozen['document']
        interrupted = {row['slot']:row for row in state['attempts']
                       if not row.get('outcome') or row['outcome'].get('category')=='local_execution'}
        result = dict(task=self.id, revision=state['revision'], workflow=state['policy'],
                      user_requirements=document.get('user_requirements',''),
                      hard_constraints=dict(effective={key:compact['effective'][key] for key in (
                          'size','size_policy','integration','mode','require_enclosure','openings_policy','opening_size')
                          if key in compact['effective']}, selected=document.get('constraints',[])),
                      design=compact['brief'], options=state['options'],
                      requests=[row for row in state['requests'] if row['slot'] not in interrupted],
                      local_retries=[dict(slot=slot,request=reference(self.directory/'attempts'/row['id']/'request.json'))
                                     for slot,row in interrupted.items()],
                      expand=['text','document','plan','context'], approval_created=False)
        if expand:
            result['design']= {key:document['project'][key] for key in compact['brief']}
            result['prompt']=frozen['text']
            result['context']=frozen['context']
        return result

    def status(self):
        state = self.state()
        counts = dict(candidates=len(state['attempts']), local_retries=sum(row.get('local_retries',0) for row in state['attempts']),
                      reported_model_calls=sum(row.get('model_usage',{}).get('calls',0) for row in state['attempts']),
                      usage_reports=sum('model_usage' in row for row in state['attempts']))
        return dict(state, metrics=counts, workflow_file=reference(self.file), approval_created=False, nbt_exported=False)

    def next_request(self, state, slot):
        return next((row for row in state['requests'] if row['slot']==slot), None)

    def replace_request(self, state, slot, request=None):
        state['requests'] = [row for row in state['requests'] if row['slot']!=slot]
        if request:
            state['requests'].append(request)

    def route_failure(self, state, attempt, failure, request):
        slot = attempt['slot']
        policy = state['policy']
        if failure['category']!='design':
            return self.next_request(state, slot) if failure['category']=='local_execution' else None
        diagnostics = failure.get('diagnostics',{})
        issues = diagnostics.get('new',[]) + diagnostics.get('ongoing',[])
        start = request.get('plan',{}).get('context',{}).get('start')
        cross_layer = start and any(abs(row.get('evidence',{}).get('feet',start)[1]-start[1])>2
                                    for row in issues if row.get('code')=='ROUTE_FAILED' and row.get('evidence',{}).get('feet'))
        semantic = cross_layer or failure['code'] in ('STAIR_ROUTE_FAILED','ASSEMBLY_INVALID','REPAIR_SCOPE') or any(
            row['code']=='ACTIVITY_ROUTE_FAILED' for row in issues)
        last = attempt['request']
        history = [row for row in state['attempts'] if row['slot']==slot]
        local = sum(row['request']['phase']=='local_repair' for row in history)
        upgraded = any(row['request']['phase']=='semantic_review' for row in history)
        role, phase = last['role'], 'local_repair'
        if policy['mode']=='economy' and semantic and last['role']=='economy' and not upgraded:
            role, phase = 'strong', 'semantic_review'
        elif local>=policy['local_repairs']:
            return None
        ref = dict(report=failure['receipt'], issues=issues)
        if diagnostics.get('report'):
            ref['evidence']=dict(diagnostics['report'],kind=diagnostics['kind'])
        ref['prior_candidate']=attempt['id']
        if phase=='local_repair':
            ref['scope']='保留硬约束、路线目标和质量清单，只修证据指向的少数设计目标。'
        return model_request(policy, slot, role, phase, **ref)

    def escalate(self, state, request):
        fields(request,('reason','kind'))
        if state['policy']['mode']!='economy' or state.get('selected'):
            raise ValueError('只可在性价比的候选阶段升级')
        if request['kind'] not in ('cross_floor','shared_structure','ambiguous_constraint'):
            raise ValueError('升级需要跨层动线、共享构造或关键约束疑问')
        reason = text(request['reason'])
        old = self.next_request(state,'1')
        if not old or old['role']!='economy' or any(row['request']['phase']=='semantic_review' for row in state['attempts']):
            raise ValueError('没有可升级的待处理请求')
        if any(not row.get('outcome') or row['outcome'].get('category')=='local_execution' for row in state['attempts']):
            raise ValueError('请先恢复本机失败的原请求')
        new = model_request(state['policy'],'1','strong','semantic_review',reason=reason,
                            **{key:old[key] for key in ('report','issues','evidence','prior_candidate') if key in old})
        self.replace_request(state,'1',new)
        self.save(state)
        return new

    def candidate(self, state, request, working=None, retry=False):
        fields(request,('slot',),('plan','variation','view_overrides','model_usage','working_id'))
        slot = request['slot']
        if type(slot) is not str or slot not in {row['slot'] for row in routes(state['policy'])}:
            raise ValueError('候选号须来自创作简报')
        scripted = working is not None or 'working_id' in request
        if scripted == ('plan' in request):
            raise ValueError('选择建筑方案或通过 Python 接入 WorkingModel')
        if scripted and 'working_id' not in request:
            raise ValueError('WorkingModel 候选需要可重试的 working_id')
        if scripted:
            text(request['working_id'],160)
        if state['policy']['mode']=='maximum':
            variation = fields(request.get('variation'),('axis','decision'))
            if variation['axis'] not in state['options']['axes']:
                raise ValueError('候选差异需要引用已登记的设计轴')
            text(variation['decision'])
        if 'model_usage' in request:
            usage = fields(request['model_usage'],('calls',),('input_tokens','output_tokens'))
            if any(type(value) is not int or not 0 <= value <= 10**9 for value in usage.values()):
                raise ValueError('用量仅记录宿主实际提供的数字')
        key = fingerprint(request)
        attempt = next((item for item in state['attempts'] if item['id']==key),None)
        if retry and attempt is None:
            raise ValueError('retry 需要本会话原候选请求')
        if attempt is not None and attempt.get('outcome',{}).get('category')!='local_execution' and attempt.get('outcome'):
            return attempt['outcome']
        requested = self.next_request(state,slot)
        if not requested or state.get('selected') or attempt is None and any(
                row['slot']==slot and (not row.get('outcome') or row['outcome'].get('category')=='local_execution')
                for row in state['attempts']):
            raise ValueError('当前阶段没有此候选请求；本机错误须先 retry 原请求')
        if attempt is None:
            attempt = dict(id=key, slot=slot, request=requested, **{key:request[key] for key in ('model_usage','variation') if key in request})
            state['attempts'].append(attempt)
        elif attempt.get('outcome',{}).get('category')=='local_execution':
            attempt['local_retries'] = attempt.get('local_retries',0)+1
        folder = inside(self.workspace,self.directory/'attempts'/key)
        folder.mkdir(parents=True,exist_ok=True)
        write(folder/'request.json',request)
        self.save(state)
        run = Execution(self.workspace,folder,self.live)
        frozen = self.frozen()
        reference_constraints=state['options'].get('reference')
        previous = requested.get('evidence') if requested.get('phase') in ('local_repair','semantic_review') else None
        begin = monotonic()

        def compile_candidate():
            if working is None and scripted:
                raise RuntimeError('请用原 WorkingModel 脚本重试未完成的候选保存')
            if scripted:
                model = working
                if model.workspace!=self.workspace or model.source is not None or model.kind!='building' or model.phase!='opened':
                    raise ValueError('需要在本工作区新建、已完成开口检查的完整 WorkingModel')
                if not model.context.get('start') or not model.context.get('targets'):
                    raise ValueError('完整 WorkingModel 需要实际路线起点与必要目标')
                result = dict(checks=model.validate())
            else:
                if requested['phase']=='local_repair' and (prior:=requested.get('prior_candidate')):
                    previous_request=read(self.directory/'attempts'/prior/'request.json')
                    local_repair(previous_request.get('plan'), request['plan'])
                model, result = build(self.workspace,dict(plan=request['plan']),return_model=True)
            gates(frozen,model,reference_constraints)
            result['saved']=model.save_draft(name_zh=frozen['task']['name'], _draft_directory=folder/'draft',
                _staged=True, before_publish=self.live)
            return result

        try:
            saved = run.step('candidate-save',compile_candidate,design=True,diagnostic='model',previous=previous)['saved']
            check = run.step('readback-check',lambda: readback(self.workspace,saved,frozen,reference_constraints),diagnostic='model',previous=previous)
            whole = check['validation'].get('whole_model') or {}
            review = prepare_review(run,saved,request.get('view_overrides'),previous)
            comparison = review['render']
            if comp := state['options'].get('comparison'):
                comparison=run.step('comparison-render',lambda: run.render(saved,evidence(self.workspace,comp['cameras']),comparison=comp))['render']

            def distinct_geometry():
                other = [self.ready(state,other_slot) for other_slot in state['ready'] if other_slot!=slot]
                if any(row['geometry_sha256']==saved['geometry_sha256'] or row.get('variation')==attempt.get('variation') for row in other):
                    raise ModelConflict('DUPLICATE_CANDIDATE',[dict(reason='比较候选需要实际几何或材质差异及不同的设计决定')])
                return dict(passed=True)

            run.step('candidate-gate',distinct_geometry,diagnostic='model')
            outcome = dict(status='ready_for_review',slot=slot, candidate=key,source=saved_binding(saved),
                           geometry_sha256=saved['geometry_sha256'], variation=attempt.get('variation'),
                           geometry_checks=dict(whole_model=whole.get('passed',True),
                               route_targets=len(whole.get('routes',{}).get('targets',[])),
                               openings=len(whole.get('openings',[])), review_views=len(review['awaiting_views'])),
                           review=review, comparison_render=comparison, steps=run.steps)
            if 'quality' in check:
                outcome['quality']=check['quality'].get('summary',{})
            state['ready'][slot]=key
            self.replace_request(state,slot)
        except StageError as failure:
            outcome = failure.outcome
            next_request = self.route_failure(state,attempt,outcome,request)
            self.replace_request(state,slot,next_request)
            outcome.update(slot=slot,candidate=key,next_request=next_request if outcome['category']=='design' else None,
                           recovery='creation retry --request <同一请求文件>' if outcome['category']=='local_execution' else None)
        outcome['elapsed_ms']=round((monotonic()-begin)*1000)
        outcome['approval_created']=False
        attempt['outcome']=outcome
        self.save(state)
        return outcome

    def ready(self, state, slot):
        identifier = state['ready'].get(slot)
        if identifier is None:
            raise ValueError('候选未通过共同检查与实图出图')
        return next(row['outcome'] for row in state['attempts'] if row['id']==identifier)

    def act(self, action, request, working=None):
        if action=='finish' and self.client.load()['phase']=='completed':
            fields(request)
            completion=self.client.status().get('completion')
            target=self.state().get('published')
            if target and completion and completion.get('evidence',{}).get('source_sha256')==target['source']['source_sha256']:
                return dict(completion,status='completed',approval_created=False,nbt_exported=False)
        self.live()
        self.state()
        with index_lock(self.workspace,self.directory):
            self.live()
            state=self.state()
            try:
                current_options={key:value for key,value in state['options'].items()
                                 if key!='retained_review' or action=='retest'}
                options(self.workspace,state['policy'],current_options)
            except (OSError,ValueError) as failure:
                if isinstance(failure,ModelConflict):
                    raise
                raise ModelConflict('STALE_SOURCE',[dict(reason=str(failure))]) from failure
            if action in ('candidate','retry'):
                return self.candidate(state,request,working,retry=action=='retry')
            if action=='escalate':
                return self.escalate(state,request)
            from nbt_agent import creation_review
            return getattr(creation_review,action)(self,state,request)
