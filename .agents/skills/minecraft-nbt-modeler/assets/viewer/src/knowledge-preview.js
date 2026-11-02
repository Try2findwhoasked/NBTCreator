let dialog
export async function previewKnowledge(input){
 if(!dialog){dialog=document.createElement('dialog');dialog.className='review-help-dialog knowledge-preview';dialog.innerHTML='<div class="review-help-heading"><h2></h2><button type="button">关闭</button></div><p class="knowledge-recipient"></p><pre></pre>';dialog.querySelector('button').onclick=()=>dialog.close();document.body.append(dialog)}
 dialog.querySelector('h2').textContent='读取资料…';dialog.querySelector('pre').textContent='';dialog.showModal()
 try{const doc=await window.nbtDesktop.knowledgePreview(input);dialog.querySelector('h2').textContent=doc.title;dialog.querySelector('.knowledge-recipient').textContent=doc.recipient;dialog.querySelector('pre').textContent=doc.text;dialog.scrollTop=0}catch(e){dialog.querySelector('pre').textContent=e.message}
}
export const externalSummaries={
 core:'必读：完整建模顺序、玩家尺度、空间细节、验证、真实看图确认与交付。核心约束不可关闭。',
 architecture:'建筑风格、场所用途、构件语法和布局变化，帮助设计有区别的空间。',organic:'洞穴、曲面、有机轮廓与不规则腔体的整体设计方法。',linked:'跨层、多单元、联动空间和完整模型里的通路组织。',props:'用原版方块组合细小道具，处理安装、支承和使用空间。',materials:'带权混材、成片风化、自动地面和适度破损，保留通路与支撑。',modelling:'几何、布尔、拉伸、复制、旋转、扩散、爆炸等完整工具参数与限制。',rendering:'相机、纹理预览、批量出图与图像审阅；截图不等于验收完成。',saodg:'SAODG房间拼接和模组结构管理，仅要求该集成时适用。',desktop:'桌面、提示词方案、网页参数回导与共享工作区的调用流程。',library:'形状归档、中文名称、资产迁移和结构选择。',handoff:'接手任务、阅读记录和已有授权下的协作要求，不自动授予批准。'}
