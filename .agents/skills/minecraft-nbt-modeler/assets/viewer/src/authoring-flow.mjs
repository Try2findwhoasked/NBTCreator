// Guidance describes the current candidate, never visual approval or export permission.
export function authoringFlow(state, current, saved) {
 const base = {step:0, canSave:false, action:null, tone:'neutral'}
 if (!state.info) return {...base, title:'从一座建筑开始', hint:'打开已有建筑，或先写一份创作方案。', action:'project', label:'打开建筑库'}
 if (state.sessionRestoring) return {...base, title:'正在恢复编辑进度', hint:'恢复完成后，可继续上次的参数与标注。'}
 if (state.versionComparing) return {...base, title:'正在对比两个版本', hint:'这里是只读视图。结束版本对比后继续编辑。'}
 if (state.transforming) return {...base, title:'正在调整构件', hint:'先完成或取消画面中的调整，再预览整座建筑。'}
 if (state.busy || state.previewBusy || state.commitBusy) return {...base, step:1, title:'正在处理本次操作', hint:'完成后会显示结果；具体进度可在底部运行记录中查看。'}
 if (saved) return {...base, step:2, tone:'success', title:saved.draftOnly?'制作版已保存':'NBT 已导出', hint:'当前仍显示保存前的版本。打开新版本后再继续修改或导出；文件位置可在运行记录中查看。', action:'open-saved', label:'打开新版本'}
 if (!current) return {...base, title:state.preview?'参数已改变，预览需要更新':'调整参数，再看效果', hint:state.preview?'画面仍是上一次的结果。更新预览后才能保存这次修改。':'选择建造工具，或从素材库放入构件。原始建筑会保留。', action:'update-preview', label:'更新预览'}
 const ready = {...base, step:1, canSave:true}
 if (state.candidateValidation?.passed === false) return {...ready, tone:'warning', title:'检查发现需要处理的问题', hint:'查看检查报告，调整参数后重新预览。检查结果不代表看图确认。', action:'checks', label:'查看检查问题'}
 if (state.candidateValidation?.passed) return {...ready, step:2, tone:'success', title:'检查通过，请确认画面', hint:'对比原建筑与本次修改。继续制作可保存制作版；确认定稿后再导出 NBT。', action:'save-authoring-version', label:'保存制作版'}
 return {...ready, title:'预览已更新，接着检查', hint:'对比原建筑与本次修改，再检查保护区和改动范围。预览尚未保存为建筑。', action:'validate-preview', label:'检查这次修改'}
}
