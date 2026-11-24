"""Attach actionable scope to authoring protocol errors without exposing credentials."""
from nbt_agent.protocol import fingerprint


RECOVERY = {
    'WRITE_OUT_OF_SCOPE': ('component', '复核写区及局部原点，按全局 XYZ 回传。'),
    'PROTECTED_POSITION': ('component', '让上级核对该保护坐标与安装方式。'),
    'PATCH_BASE_MISMATCH': ('component', '重读对应页，核对坐标、旧方块和墙层。'),
    'READ_PAGE_REQUIRED': ('component', '读取列出的必要页，并随补丁回传各页回执。'),
    'READ_PAGE_INVALID': ('component', '使用当前包、修订及租约重新读取对应页。'),
    'WRITE_SCOPE_OVERLAP': ('region', '重新划分两个工作包的写区或向上级申报共享接口。'),
    'READ_DEPENDENCY_CHANGED': ('region', '核对被改动的支点，调整划分后重新签发。'),
    'PATCH_OVERLAP': ('region', '由上级分配重叠坐标后重新签发。'),
    'STALE_PARENT': ('lead', '从当前制作版新建运行并重新签发需要的范围。'),
    'ROUTE_FAILED': ('lead', '查看目标脚位与静态路线报告，重新安排冲突候选。'),
    'ROUTE_LEG_FAILED': ('lead', '查看失败的声明路线段与受影响位置。'),
    'EVIDENCE_INVALID': ('lead', '核对原源、机位和图像哈希，补做对应复验。'),
    'RENDER_CONFIG_MISMATCH': ('lead', '使用同一固定机位和预构建纹理配置重新出图。'),
}


def annotate(method, params, code, details):
    audience, next_check = RECOVERY.get(code, ('caller', '按回执中的校验结果检查本次输入。'))
    package = params.get('package_id') or params.get('parent_id')
    issue = fingerprint('authoring_issue', [method, package, code, details])[:24]
    return dict(details, feedback=dict(issue_id=issue, code=code, stage=method.split('.', 1)[1],
                                       audience=audience, package_id=package, next_check=next_check))
