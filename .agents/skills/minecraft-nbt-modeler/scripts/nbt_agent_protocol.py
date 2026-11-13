"""Shared lease fencing and durable mutation receipts for local Agent interfaces."""
import copy,hashlib,hmac,json,re,time,uuid
from pathlib import Path

PROTOCOL_VERSION=1
class ProtocolError(ValueError):
    def __init__(self,code,message,*,retryable=False,details=None):
        super().__init__(message);self.code=code;self.retryable=retryable;self.details=details or {}

def error(code,message,**kwargs):raise ProtocolError(code,message,**kwargs)
def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8')
def request_key(request):
    key=request.get('request_id')
    if key is not None and (not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,128}',key)):error('INVALID_REQUEST','request_id 须为16～128位字母、数字、横线或下划线')
    return key
def fingerprint(action,request):return hashlib.sha256(canonical([action,request])).hexdigest()
def replay(workspace,index,action,request):
    key=request_key(request)
    if key is None:return None
    receipt=index.get('operation_receipts',{}).get(key)
    if receipt is None:return None
    if receipt['fingerprint']!=fingerprint(action,request):error('IDEMPOTENCY_CONFLICT','相同 request_id 不能用于不同请求')
    from nbt_prompts import inside
    file=inside(workspace,receipt['path']);raw=file.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=receipt['sha256']:error('RECEIPT_CHANGED','原操作回执已变化，未重复执行')
    result=json.loads(raw)
    def relocate(value):
        if isinstance(value,dict):
            if 'absolute_source' in value and 'source' in value:value['absolute_source']=str(inside(workspace,value['source']))
            for child in value.values():relocate(child)
        elif isinstance(value,list):
            for child in value:relocate(child)
    relocate(result);return result
def receipt(workspace,index,action,request,result):
    key=request_key(request)
    if key is None:return
    if len(index.get('operation_receipts',{}))>=20000:error('RECEIPT_LIMIT','操作回执索引达到上限，请归档后继续')
    from nbt_prompts import inside,relative
    raw=canonical(result);sha=hashlib.sha256(raw).hexdigest()
    file=inside(workspace,Path('nbt_models/_workspaces/agent_protocol/receipts')/(sha+'.json'));file.parent.mkdir(parents=True,exist_ok=True)
    try:
        with file.open('xb') as stream:stream.write(raw)
    except FileExistsError:
        if file.read_bytes()!=raw:error('RECEIPT_CHANGED','操作回执文件损坏，未覆盖')
    index.setdefault('operation_receipts',{})[key]=dict(fingerprint=fingerprint(action,request),path=relative(workspace,file),sha256=sha)

def public_lease(task):
    lease=task.get('lease')
    return {k:v for k,v in lease.items() if k!='token'} if lease else None
def redact(task):
    result=copy.deepcopy(task)
    if result.get('lease'):result['lease']=public_lease(task)
    if result.get('lease') and result['lease']['expires_at']<=time.time():
        result['lease_expired']=True
        if result.get('status')=='in_progress':result['status']='pending'
    return result
def check_lease(task,request,*,required=False,now=None):
    now=time.time() if now is None else now;lease=task.get('lease')
    if not lease:
        if required or task.get('lease_managed'):error('LEASE_REQUIRED','请先领取任务')
        return
    if lease['expires_at']<=now:error('LEASE_EXPIRED','领取已超时，请使用新的请求编号重新领取',retryable=True)
    token=request.get('lease_token')
    if not isinstance(token,str) or not hmac.compare_digest(token,lease['token']):error('LEASE_NOT_OWNER','领取令牌不属于当前执行者')
    if request.get('fence')!=lease['fence']:error('LEASE_FENCE_CONFLICT','任务已被重新领取，旧执行者不能提交')
def lease_action(task,action,request,*,now=None):
    now=time.time() if now is None else now
    ttl=request.get('ttl_seconds',900)
    if type(ttl) is not int or not 60<=ttl<=3600:error('INVALID_REQUEST','租约时长须为60～3600秒')
    if action=='claim':
        owner=request.get('owner')
        if not isinstance(owner,str) or not 1<=len(owner.strip())<=120:error('INVALID_REQUEST','领取须声明1～120字执行者名称')
        if task.get('status')=='completed':error('TASK_COMPLETED','已完成任务不能重新领取')
        if task.get('lease',{}).get('expires_at',0)>now:error('TASK_CLAIMED','任务已被领取',retryable=True,details={'lease':public_lease(task)})
        fence=task.get('lease_epoch',0)+1;task['lease_epoch']=fence;task['lease_managed']=True
        task['lease']=dict(owner=owner.strip(),token=uuid.uuid4().hex,fence=fence,expires_at=now+ttl)
        task['status']='in_progress'
    elif action=='heartbeat':
        check_lease(task,request,required=True,now=now);task['lease']['expires_at']=now+ttl
    elif action=='release':
        check_lease(task,request,required=True,now=now);task.pop('lease',None);task['status']='pending'
    else:error('INVALID_REQUEST','未知租约动作')
    result=dict(id=task['id'],status=task['status'],lease=public_lease(task),lease_epoch=task.get('lease_epoch',0))
    if action in ('claim','heartbeat'):result['lease_token']=task['lease']['token']
    return result
