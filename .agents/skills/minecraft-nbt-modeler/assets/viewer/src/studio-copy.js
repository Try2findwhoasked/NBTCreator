// UI wording lives here for the rebuilt shell. Input nodes and help-dialog
// containers stay mounted so editing, metadata and existing handlers survive.
export function applyStudioCopy(){
 const $=id=>document.getElementById(id)
 const texts={
  'update-preview':'更新修改预览','validate-preview':'检查这次修改','export-revision':'定稿导出 NBT',
  'compare-before':'原始建筑','compare-after':'本次修改','studio-ai-settings':'AI 与知识库',
  'studio-panel-tools':'建造','studio-panel-notes':'标注','studio-panel-checks':'检查','studio-panel-more':'交接',
  'studio-project-new':'打开创作方案','studio-new-design':'编写创作方案','studio-browse-projects':'打开建筑库',
  'plan':'整理建筑修改任务','copy-agent-plan':'复制给建造助手','agent-return-open':'查看助手完成的版本',
  'save-preset':'保存这组效果设置','load-preset':'读取效果设置','open-settings-history':'查看本次编辑记录',
  'render':'生成多角度图片','studio-photo-toggle':'切换图片','studio-note-pick':'在建筑上标记位置',
  'save-feedback':'开始下一条标注','refresh-reference':'刷新参考文件','comment-tasks-open':'整理这些修改意见',
  'project-refresh':'刷新列表','project-generate-thumbnails':'补齐预览图','asset-refresh':'刷新列表',
  'project-preview-edit':'打开编辑器','project-preview-render':'查看 3D','project-preview-close':'返回列表',
  'asset-place':'放入当前建筑','asset-pick':'在建筑上选择位置','asset-use-range':'使用当前选区',
  'asset-adjust-3d':'用手柄调整','asset-inspector-close':'返回素材库','open-assets':'从素材库选择',
  'save-selection-asset':'将选区保存为素材','copy-selection-3d':'复制选区并调整','move-selection-3d':'移动选区并调整',
  'prompt-new':'新增提示词','sync-prompt':'为当前建筑写修改要求','prompt-save':'下载方案','prompt-import':'导入方案','prompt-reset':'另起一份',
  'refresh-task-list':'刷新记录','api-save':'保存连接','api-models':'连接测试与模型列表',
  'api-clear':'移除密钥','ai-generate':'生成修改建议','ai-generate-preview':'生成并预览构件',
  'ai-copy':'复制建议','ai-download':'下载建议','ai-apply':'采用建议并预览',
  'settings-skill-copy':'复制外部助手使用说明','settings-skill-preview':'查看助手可读的资料'
 }
 for(const [id,text]of Object.entries(texts))if($(id))$(id).textContent=text
 function label(id,text){const input=$(id),parent=input?.closest('label');if(!parent)return;const node=[...parent.childNodes].find(n=>n.nodeType===Node.TEXT_NODE&&n.textContent.trim());if(node)node.textContent=text}
 const labels={
  strength:'整体效果强度',seed:'随机编号（相同编号可复现效果）','style-note':'这组设置的备注',
  'pattern-fraction':'替换比例','pattern-mode':'分布方式','pattern-scope':'处理范围','pattern-from':'要替换的方块','noise-scale':'混搭块的大小',
  moss:'苔藓比例',cracks:'裂纹比例','weather-from':'要旧化的方块','moss-state':'苔藓材质','crack-state':'裂纹材质',
  'moss-min':'最小苔藓面积','moss-max':'最大苔藓面积','crack-min':'最短裂纹','crack-max':'最长裂纹',
  'floor-profile':'地面效果','floor-fraction':'破损比例','slab-share':'半砖占比','floor-min':'最小破损面积','floor-max':'最大破损面积','pit-depth':'下陷深度','route-margin':'通道两侧留空',
  'replace-from':'原方块','replace-to':'替换为','replace-scope':'处理范围',
  'whole-region':'作用于整座建筑','budget':'最多允许修改的方块数','structure-mode':'要怎样修改选区','structure-state':'使用的方块','structure-classification':'这部分属于主体还是墙体','structure-thickness':'边框或外壳厚度（格）',
  'move-x':'X 方向移动','move-y':'Y 方向移动','move-z':'Z 方向移动',
  'save-root':'效果设置的保存位置','effect-name':'这组效果的名称',
  'api-enabled':'启用 AI 连接','api-provider':'服务类型','api-base':'服务地址','api-model':'模型名称','api-key':'访问密钥',
  'ai-instruction':'描述你要添加或修改的内容','setting-start-page':'启动页面','setting-restore-session':'自动保存编辑进度','setting-auto-preview':'参数改变后自动更新预览','setting-preview-delay':'等待多久再更新（毫秒）','setting-zoom':'界面大小','setting-color-scheme':'界面颜色'
 }
 for(const [id,text]of Object.entries(labels))label(id,text)
 const placeholders={'model-search':'搜索建筑名称或版本','project-search':'搜索建筑、项目或版本','asset-search':'搜索素材名称、标签或尺寸','comment-search':'查找标注内容或坐标','task-search':'查找操作、进度或生成的文件','materials-search':'搜索方块名称或 ID','effect-name':'例如：工坊石墙轻度旧化','ai-instruction':'例如：在选区里增加两根石柱，柱脚加厚，保留中间通道。','feedback-text':'例如：1 号位置的梁缺少支撑，请补一根石柱，保留旁边通道。文字和标记会自动保存；Ctrl+Enter 开始下一条。'}
 for(const [id,text]of Object.entries(placeholders))if($(id))$(id).placeholder=text
 for(const [workspace,label]of [['project','建筑库'],['assets','素材库'],['prompt','创作方案'],['model','建筑编辑'],['tasks','运行记录']])document.querySelector(`.creator-workspaces button[data-workspace="${workspace}"]`).textContent=label
 for(const [prefix,title]of [['project','建筑库'],['asset','素材库']]){const h=$(prefix+'-workspace').querySelector('.library-heading h1');h.textContent=title}
 $('model-library').querySelector('h2').textContent='切换建筑'
 document.querySelector('.task-workspace-heading h2').textContent='运行记录'
 document.querySelector('.task-workspace-heading p').textContent='查看本软件生成预览、检查建筑和保存文件的进度与结果。'
 document.querySelector('.task-current-heading').textContent='最近一次编辑的记录'
 const summaries={
  'studio-model-menu':'选择要编辑的建筑','studio-tool-menu':'选择要使用的工具','studio-view-menu':'调整图层、剖切与显示质量',
  'studio-note-menu':'管理标注和引用文件'
 }
 for(const [id,title]of Object.entries(summaries))$(id).querySelector('summary').title=title
 const help=(selector,html,keep=[])=>{const host=document.querySelector(selector);if(!host)return;const retained=keep.map(id=>$(id));host.innerHTML=html;for(const node of retained)if(node)host.append(node)}
 // Preserve the original advanced inputs and live model statistics.
 const modelHelp=$('model-info').querySelector('.info-popover'),advanced=$('source').closest('details'),stats=[$('catalog-summary'),$('model-summary')]
 modelHelp.innerHTML='<h3>打开哪座建筑？</h3><p>在建筑库里选择一座建筑进入编辑器，也可以用“打开 NBT”选择单个文件。这里的搜索用于切换当前工作区内的建筑。</p><h3>当前文件</h3><p>尺寸单位为方块，顺序是 X × Y × Z。每次预览都从当前原始文件重新计算；参数改变不会覆盖原稿。</p>'
 modelHelp.append(...stats);advanced.querySelector('summary').textContent='手动指定源文件与坐标配置';modelHelp.append(advanced)
 help('#image-toolbar .info-popover','<h3>图片与 3D</h3><p>图片是固定视角，适合标注；3D 可旋转、选取方块和剖切。切换显示不会修改建筑。</p><p>在“交接”面板生成原建筑的多角度图片。修改工具设置后，点击顶部“更新修改预览”查看效果。</p>',['workspace-context','image-count'])
 help('#feedback-card .info-popover','<h3>标注会自动保存</h3><p>在图片或 3D 上选择位置并填写修改要求。停下输入后，文字和位置会自动写入当前建筑版本的“修改意见”目录，供外部 Agent 读取。</p><p>继续输入会更新同一条标注；点击“开始下一条标注”或按 Ctrl+Enter 开始另一条。点击列表中的“编辑”可以修改已有标注。保存标注不会修改建筑，也不代表批准精修。</p><h3>引用与导出</h3><p>输入 @ 可以引用已保存的效果文件。“标注工具”中可刷新引用、下载标注或将多条标注整理为任务。</p>',['feedback-file'])
 help('.action-info','<h3>手动编辑</h3><p>选择工具并调参 → 更新预览 → 对比原始建筑与本次修改 → 另存新版本。预览不会生成正式建筑。</p><h3>检查这次修改</h3><p>“检查这次修改”核对参数、改动上限、保护区和结构约束。检查通过后仍请查看预览；游戏中的实际表现需要另行确认。</p><h3>交给 Agent</h3><p>在“交接”面板整理修改任务并复制给 Agent。Agent 完成后，在建筑库刷新并打开新版本。</p><h3>文件位置</h3><p>新建筑版本保存在原建筑的工作目录。参数文件使用“输出位置”里的文件夹；任务说明与审阅图放在该建筑的 Agent交接 文件夹。实际路径见运行记录。</p>')
 const review=$('review-help-dialog'),reviewHeader=review.querySelector('.review-help-heading');review.replaceChildren(reviewHeader);review.insertAdjacentHTML('beforeend','<h3>什么时候用这个流程？</h3><p>当 Agent 要继续精修已有建筑时，先准备审阅图，让你确认它看到的是哪一版建筑。普通手动调参可以直接预览，再另存新版本。</p><h3>如何继续精修？</h3><ol><li>点击“准备审阅图”，打开并查看生成的图片。</li><li>在 Agent 对话中明确确认这份图和修改范围。Agent 根据你的真实回复记录确认。</li><li>整理修改任务并交给 Agent。完成后回到建筑库，刷新并打开新版本。</li></ol><p>如果希望由应用执行已确认的计划，再展开“执行已确认计划”。保存评论、采用 AI 建议、检查通过，都不会自动生成精修批准。</p><details><summary>文件与校验细节</summary><p>审阅目录中的 review.json 绑定原建筑和图片；approval.json 记录真实看图确认。源文件、参数或保护范围改变后，旧确认不再适用，需要重新准备图片和确认。普通手动调参不需要填写这个目录。</p></details>')
 reviewHeader.querySelector('h2').textContent='与建造助手协作'
 const helpTexts=[
  ['#settings>.card:nth-child(1) .studio-form-help:last-child','整体强度会按比例缩放各项效果。它不会改变建筑尺寸或材质配比。'],
  ['#replace-panel .studio-form-help','只替换选定范围内的匹配方块，保护区保持原样。替换先于混搭和旧化执行。'],
  ['#structure-panel .studio-form-help','先设置作用范围，再选择填充、挖空或移动。新增方块会记入所选图层；通道和其他保护区保持原样。'],
  ['#operation-panel .studio-form-help','步骤从上到下执行。添加后可以修改参数、调整顺序或撤销。先预览结果，再另存建筑。']
 ]
 for(const [selector,text]of helpTexts){const root=document.querySelector(selector);if(root){const summary=root.querySelector('summary');root.replaceChildren(summary);const p=document.createElement('p');p.textContent=text;root.append(p)}}
}
