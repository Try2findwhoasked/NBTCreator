import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import {writeFileSync} from 'node:fs'
import path from 'node:path'
import http from 'node:http'
import {spawnSync} from 'node:child_process'
import {createRequire} from 'node:module'
import {root,skill,python} from '../../scripts/paths.mjs'
import {minimizedScreenshots} from '../support/minimized-screenshots.mjs'
const require=createRequire(path.join(skill,'assets/viewer/package.json')),{_electron}=require('playwright'),output=path.join(root,'build','project-constraints-'+Date.now()),workspace=path.join(output,'workspace'),errors=[],checks={}
const executable=process.env.NBTCREATOR_TEST_EXE||path.join(root,'node_modules/electron/dist/electron.exe'),testRoot=process.env.NBTCREATOR_TEST_EXE?path.join(path.dirname(executable),'resources/app'):root,testSkill=path.join(testRoot,'.agents/skills/minecraft-nbt-modeler'),testPython=python
await fs.mkdir(path.join(workspace,'.nbtcreator'),{recursive:true});await fs.writeFile(path.join(workspace,'.nbtcreator/preferences.json'),JSON.stringify({startPage:'project',autoPreview:false}))
const project='nbt_models/SAODG',corner=project+'/l_shape',single=project+'/single',other='nbt_models/另一个项目';
for(const folder of [corner,single])await fs.mkdir(path.join(workspace,folder),{recursive:true});
const agentCandidate={name:'净高与通路',rules:{requirements:'所有主要活动空间净高至少4格，主入口净宽至少3格。'}}
const server=http.createServer(async(req,res)=>{for await(const chunk of req){}res.setHeader('Content-Type','application/json');res.end(JSON.stringify({choices:[{finish_reason:'stop',message:{content:JSON.stringify(agentCandidate)}}]}))})
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));let app,page
const ready=()=>page.waitForFunction(()=>!document.querySelector('#constraint-save').disabled)
const cli=(action,request,folder=project)=>{const args=[path.join(testRoot,'scripts/cli.mjs'),'architect',action,'--workspace',workspace];if(!request){request=path.join(output,'scope-request.json');writeFileSync(request,JSON.stringify({folder}));}args.push('--request',request);const result=spawnSync(process.env.NBTCREATOR_TEST_EXE?executable:process.execPath,args,{cwd:workspace,encoding:'utf8',windowsHide:true,env:{...process.env,NBTCREATOR_PYTHON:testPython,...(process.env.NBTCREATOR_TEST_EXE?{ELECTRON_RUN_AS_NODE:'1'}:{})}});assert.equal(result.status,0,result.stderr||result.stdout);return JSON.parse(result.stdout)}
try{
 const env={...process.env,NBTCREATOR_AUTOMATION:'1'};delete env.ELECTRON_RUN_AS_NODE
 app=await _electron.launch({executablePath:executable,args:[...(process.env.NBTCREATOR_TEST_EXE?[]:[root]),'--workspace',workspace,'--user-data-dir',path.join(output,'profile')],env,timeout:60000});page=await app.firstWindow();page.setDefaultTimeout(30000);await minimizedScreenshots(app,page);page.on('pageerror',error=>errors.push(error.message));await page.setViewportSize({width:1440,height:900});await page.waitForFunction(()=>window.detailControl?.state.catalogReady)
 const tree=page.locator('#project-tree'),rootRow=tree.locator('[data-node-kind=project]');
 assert.equal(await rootRow.count(),1);assert.equal(await rootRow.locator('.project-tree-label').textContent(),'我的项目');
 assert.equal(await tree.getByRole('button',{name:'SAODG',exact:true}).count(),0);
 await tree.getByRole('button',{name:'我的项目',exact:true}).click();
 if(await rootRow.getAttribute('aria-expanded')==='false')await tree.getByRole('button',{name:'我的项目',exact:true}).click();
 await page.locator('#open-project-constraints').click();await ready();assert.equal(await page.locator('#constraint-folder').inputValue(),'nbt_models/SAODG');await page.locator('#constraint-close').click();
 await tree.locator('[data-node-kind=shape][data-shape=l_shape] .project-tree-label').first().click();
 await page.locator('#open-project-constraints').click();await ready();assert.equal(await page.locator('#constraint-folder').inputValue(),corner);assert.match(await page.locator('#constraint-file').textContent(),/SAODG\/l_shape\/项目约束.json/);await page.locator('#constraint-folder').selectOption(single);await ready();assert.equal(await tree.locator('[data-node-kind=shape][data-shape=single]').getAttribute('aria-selected'),'true');await page.locator('#constraint-folder').selectOption(project);await ready();await page.locator('#constraint-template').selectOption({label:'L 形'});await page.locator('#constraint-name').fill('L形32格');await page.locator('#constraint-size').fill('64 × 24 × 64');await page.locator('#constraint-cell-size').fill('32');await page.locator('#constraint-enclosure').selectOption('false');await page.locator('#constraint-openings-policy').selectOption('required');await page.locator('#constraint-opening-size').fill('3 × 4');await page.locator('#constraint-save').click();await page.waitForFunction(()=>document.querySelector('#constraint-status').textContent.includes('已保存'))
 const first=cli('constraints-list');assert.equal(first.items.length,1);assert.equal(first.items[0].rules.cell_size,32);assert.equal(first.items[0].folder,project);assert.deepEqual(cli('constraints-list',null,single).items,[]);assert.equal(JSON.parse(await fs.readFile(path.join(workspace,project,'项目约束.json'),'utf8')).items[0].id,first.items[0].id);checks.project_management_creates_custom_grid_constraints=true
 await page.screenshot();await page.screenshot({path:path.join(output,'project-constraints.png')});await page.locator('#constraint-close').click();await page.evaluate(()=>window.creatorWorkspace.select('prompt'));await page.waitForFunction(()=>document.querySelector('#prompt-frame').contentDocument?.body?.dataset.promptReady==='true');const frame=page.frameLocator('#prompt-frame');await frame.locator('[data-planning-step=review]').click();await frame.locator(`[data-constraint-id="${first.items[0].id}"]`).waitFor()
 assert.equal(await frame.locator('#prompt-constraints legend').textContent(),'我的项目');assert.equal(await frame.locator('#prompt-constraint-folder').count(),0);assert.equal(await frame.locator('[data-field="size.x"]').inputValue(),'48');await frame.locator(`[data-constraint-id="${first.items[0].id}"]`).check();await page.waitForFunction(()=>document.querySelector('#prompt-frame').contentWindow.NbtPromptUI.constraints().length===1);await page.evaluate(()=>document.querySelector('#prompt-frame').contentWindow.NbtPromptUI.flushExport());assert.equal(await frame.locator('[data-field="size.x"]').inputValue(),'64');assert.equal(await frame.locator('[data-field="size.x"]').isDisabled(),true);assert.match(await frame.locator('#result').inputValue(),/L形32格/);assert.equal(await frame.locator('#prompt-queue-list button').count(),1)
 let index=await frame.locator('#prompt-export-state').getAttribute('data-index'),id=(await page.evaluate(()=>JSON.parse(document.querySelector('#prompt-frame').contentWindow.localStorage.getItem('nbt-prompt-console-v2')))).export_id
 const archived=spawnSync(testPython,[path.join(testSkill,'scripts/nbt_prompts.py'),'--workspace',workspace,'read','--index',index,'--id',id],{encoding:'utf8',windowsHide:true});assert.equal(archived.status,0,archived.stderr);const stored=JSON.parse(archived.stdout);assert.equal(stored.document.constraints[0].rules.cell_size,32);assert.equal(stored.context.cell_size,32);assert.equal(stored.context.require_enclosure,false);assert.equal(stored.context.openings_policy,'required');assert.deepEqual(stored.context.opening_size,[3,4]);checks.selecting_constraint_saves_a_real_prompt_and_effective_context=true
 await frame.locator('.constraint-management').evaluate(node=>node.open=true);await frame.getByRole('button',{name:'编辑文件夹约束',exact:true}).click();await ready();await page.locator('#constraint-requirements').fill('缺角必须留作庭院，不允许补齐。');await page.locator('#constraint-save').click();await page.waitForFunction(()=>document.querySelector('#constraint-status').textContent.includes('第 2 版'));await page.locator('#constraint-close').click();assert.ok(!(await frame.locator('#result').inputValue()).includes('不允许补齐'))
 await frame.getByRole('button',{name:'改用第 2 版'}).click();await page.waitForFunction(()=>document.querySelector('#prompt-frame').contentDocument.querySelector('#result').value.includes('不允许补齐'));checks.old_snapshot_survives_project_update_until_explicitly_refreshed=true
 await page.evaluate(baseUrl=>window.nbtDesktop.apiSave({enabled:true,provider:'compatible',baseUrl,model:'constraint-simulation'}),`http://127.0.0.1:${server.address().port}`);await frame.getByRole('button',{name:'Agent 创建约束',exact:true}).click();await ready();await page.locator('#constraint-agent-instruction').fill('创建净高至少4格、入口净宽3格的通路约束');await page.locator('#constraint-agent-generate').click();await page.waitForFunction(()=>document.querySelector('#constraint-status').textContent.includes('Agent 已填好草稿'));assert.equal(cli('constraints-list').items.length,1);await page.locator('#constraint-save').click();await page.waitForFunction(()=>document.querySelector('#constraint-status').textContent.includes('已保存'));assert.equal(cli('constraints-list').items.find(item=>item.name==='净高与通路').actor,'agent');await page.locator('#constraint-close').click();const agent=cli('constraints-list').items.find(item=>item.name==='净高与通路');await frame.locator(`[data-constraint-id="${agent.id}"]`).check();await page.waitForFunction(()=>document.querySelector('#prompt-frame').contentWindow.NbtPromptUI.constraints().length===2);checks.agent_candidate_is_reviewable_and_saved_into_the_same_library=true
 const current=cli('constraints-list'),request=path.join(output,'external-agent-request.json');await fs.writeFile(request,JSON.stringify({folder:project,revision:current.revision,name:'1×1 标准格',rules:{buildingShape:'single',size:[32,24,32],cell_size:32,cells:[[0,0]]},actor:'agent'}));const external=cli('constraints-save',request).saved;assert.equal(await frame.locator(`[data-constraint-id="${external.id}"]`).count(),0);await frame.locator('.constraint-management').evaluate(node=>node.open=true);await frame.getByRole('button',{name:'刷新约束',exact:true}).click();await frame.locator(`[data-constraint-id="${external.id}"]`).waitFor();await frame.locator(`[data-constraint-id="${external.id}"]`).click();await page.waitForFunction(()=>document.querySelector('#prompt-frame').contentDocument.querySelector('#status').textContent.includes('冲突'));assert.equal(await frame.locator(`[data-constraint-id="${external.id}"]`).isChecked(),false);assert.equal(await frame.locator('[data-field="size.x"]').inputValue(),'64');checks.external_agent_uses_public_cli_and_conflicting_selection_is_atomic=true
 await frame.locator(`[data-constraint-id="${first.items[0].id}"]`).click();await page.waitForFunction(()=>document.querySelector('#prompt-frame').contentWindow.NbtPromptUI.constraints().length===1);assert.equal(await frame.locator('[data-field="size.x"]').inputValue(),'48');await frame.locator(`[data-constraint-id="${external.id}"]`).check();await page.waitForFunction(()=>document.querySelector('#prompt-frame').contentWindow.NbtPromptUI.constraints().length===2);await page.evaluate(()=>document.querySelector('#prompt-frame').contentWindow.NbtPromptUI.flushExport());await page.reload();await page.waitForFunction(()=>window.detailControl?.state.catalogReady);await page.evaluate(()=>window.creatorWorkspace.select('prompt'));await page.waitForFunction(()=>document.querySelector('#prompt-frame').contentDocument?.body?.dataset.promptReady==='true');await frame.locator('[data-planning-step=review]').click();assert.equal(await frame.locator(`[data-constraint-id="${external.id}"]`).isChecked(),true);assert.equal(await frame.locator('[data-field="size.x"]').inputValue(),'32');checks.removal_restores_original_parameters_and_references_survive_reload=true
 await page.setViewportSize({width:900,height:650});await frame.locator('.constraint-management').evaluate(node=>node.open=true);await frame.getByRole('button',{name:'编辑文件夹约束',exact:true}).click();await ready();assert.equal(await page.locator('#project-constraints-dialog').evaluate(node=>node.getBoundingClientRect().width<=innerWidth&&node.querySelector('.constraint-body').scrollWidth<=node.querySelector('.constraint-body').clientWidth+1),true);await page.screenshot();await page.screenshot({path:path.join(output,'constraints-compact.png')});checks.compact_dialog_has_no_horizontal_overflow=true
 await page.locator('#constraint-close').click()
 const otherShape=other+'/single',child=otherShape+'/入口大厅',sibling=otherShape+'/旁侧建筑'
 const otherCorner=other+'/l_shape'
 await fs.mkdir(path.join(workspace,otherCorner),{recursive:true})
 for(const [folder,name] of [[child,'入口大厅'],[sibling,'旁侧建筑']]){
  const dir=path.join(workspace,folder,'v01')
  const fixture=spawnSync(testPython,[path.join(root,'tests/support/make_fixture.py'),dir],{encoding:'utf8',windowsHide:true});assert.equal(fixture.status,0,fixture.stderr)
  const file=path.join(dir,'room_description.json'),description=JSON.parse(await fs.readFile(file,'utf8'))
  await fs.writeFile(file,JSON.stringify({...description,name_zh:name,display_name:name,master:'synthetic.master.json.gz'}))
 }
 async function rule(folder,name,rules){
  const file=path.join(output,'fixture-constraint.json'),revision=cli('constraints-list',null,folder).revision
  await fs.writeFile(file,JSON.stringify({folder,revision,name,rules,actor:'human'}))
  return cli('constraints-save',file).saved
 }
 const common=await rule(other,'项目通行要求',{requirements:'保留疏散通路。'})
 const conflicting=await rule(other,'新建建筑的尺寸预设',{size:[32,24,32]})
 const shapeRule=await rule(otherShape,'单格门洞要求',{requirements:'保留门洞净高。'})
 const cornerRule=await rule(otherCorner,'L 形转角要求',{requirements:'保留转角连通。'})
 const childRule=await rule(child,'大厅入口保护',{requirements:'保留南侧主入口。'})
 const siblingRule=await rule(sibling,'旁侧建筑外墙',{requirements:'保留东侧外墙。'})
 await page.evaluate(()=>window.creatorWorkspace.select('project'))
 await page.locator('#project-refresh').evaluate(button=>button.click())
 await page.waitForFunction(()=>document.querySelector('#project-grid').textContent.includes('入口大厅'))
 assert.equal(await tree.locator('.project-tree-heading strong').textContent(),'我的项目')
 await page.locator('#project-tree').getByRole('button',{name:'另一个项目',exact:true}).click()
 await page.evaluate(()=>window.creatorWorkspace.select('prompt'))
 await frame.locator('#prompt-more>summary').click();await frame.locator('#prompt-add').click();await frame.locator('[data-planning-step=review]').click()
 const check=item=>frame.locator(`[data-constraint-id="${item.id}"]`)
 await check(common).waitFor();assert.equal(await check(common).isChecked(),false)
 assert.equal(await check(first.items[0]).count(),0);assert.equal(await check(shapeRule).count(),0);assert.equal(await check(childRule).count(),0)
 checks.blank_prompt_tracks_project_common_rules_without_other_projects=true
 const archiveShape=frame.locator('[data-field=buildingShape]'),shapeStatus=frame.locator('#prompt-shape-constraints')
 await archiveShape.selectOption('single');await check(shapeRule).waitFor()
 assert.match(await shapeStatus.textContent(),/单格 · 1 条形状约束/)
 assert.equal(await check(shapeRule).isChecked(),false);assert.equal(await check(childRule).count(),0)
 await frame.getByRole('link',{name:'查看约束',exact:true}).click()
 assert.equal(await frame.locator('#prompt-constraints').evaluate(node=>node===node.ownerDocument.activeElement),true)
 await check(common).check();await check(shapeRule).check()
 await page.waitForFunction(ids=>ids.every(id=>document.querySelector('#prompt-frame').contentWindow.NbtPromptUI.constraints().some(item=>item.id===id)),[common.id,shapeRule.id])
 await archiveShape.selectOption('l_shape');await check(cornerRule).waitFor()
 await frame.getByText('切换归档形状后已移除 '+shapeRule.name,{exact:true}).waitFor()
 assert.match(await shapeStatus.textContent(),/L形 · 1 条形状约束/)
 assert.equal(await check(shapeRule).count(),0);assert.equal(await check(common).isChecked(),true)
 assert.equal(await frame.locator('body').evaluate((_,id)=>window.NbtPromptUI.constraints().some(item=>item.id===id),shapeRule.id),false)
 checks.archive_shape_updates_visible_constraints_and_keeps_project_common_rules=true

 await page.evaluate(()=>window.creatorWorkspace.select('project'))
 await page.locator('.project-card').filter({hasText:'入口大厅'}).locator('.project-card-edit').click()
 await page.waitForFunction(()=>window.detailControl?.state.info?.source.includes('入口大厅')&&!window.detailControl.state.busy)
 await page.evaluate(()=>window.creatorWorkspace.select('prompt'))
 async function loadBuilding(){
  await frame.locator('#prompt-more>summary').click();await frame.locator('#prompt-load-building').click()
  await page.waitForFunction(()=>document.getElementById('prompt-sync-status').textContent.startsWith('已载入当前建筑'))
 }
 await loadBuilding()
 for(const item of [common,shapeRule,childRule])assert.equal(await check(item).isChecked(),true)
 assert.equal(await check(siblingRule).count(),0);assert.equal(await check(conflicting).isChecked(),false)
 assert.match(await frame.locator('.constraint-choice').filter({has:check(conflicting)}).textContent(),/待选 · .*已有建筑/)
 assert.equal(await frame.locator('[data-field="size.x"]').inputValue(),'48')
 checks.exact_building_receives_only_compatible_project_shape_and_building_rules=true
 await check(childRule).uncheck()
 await page.waitForFunction(id=>!document.querySelector('#prompt-frame').contentWindow.NbtPromptUI.constraints().some(item=>item.id===id),childRule.id)
 await loadBuilding();assert.equal(await check(childRule).isChecked(),false);assert.equal(await check(common).isChecked(),true)
 await page.evaluate(()=>document.querySelector('#prompt-frame').contentWindow.NbtPromptUI.flushExport())
 await page.reload();await page.waitForFunction(()=>window.detailControl?.state.catalogReady)
 await page.evaluate(()=>window.creatorWorkspace.select('prompt'));await page.waitForFunction(()=>document.querySelector('#prompt-frame').contentDocument?.body?.dataset.promptReady==='true')
 await frame.locator('#prompt-queue-list button').filter({hasText:'入口大厅'}).click();await frame.locator('[data-planning-step=review]').click()
 await check(childRule).waitFor();assert.equal(await check(childRule).isChecked(),false);assert.equal(await check(shapeRule).isChecked(),true)
 await check(childRule).locator('..').locator('..').getByText('查看要求').click()
 assert.match(await frame.locator('.constraint-origin:visible').textContent(),/另一个项目\/single\/入口大厅/)
 checks.saved_source_reopens_with_exact_scope_and_manual_uncheck=true
 assert.deepEqual(errors,[]);const files=await fs.readdir(path.join(workspace,'nbt_models'),{recursive:true});assert.ok(!files.some(name=>/\.(?:snbt|nbt)$/.test(name)));await fs.writeFile(path.join(output,'results.json'),JSON.stringify({passed:true,checks},null,2));console.log(JSON.stringify({passed:true,checks,output}))
}catch(error){await page?.screenshot({path:path.join(output,'failure.png')}).catch(()=>{});console.error(JSON.stringify({output,checks,errors,status:await page?.evaluate(()=>({constraint:document.querySelector('#constraint-status')?.textContent,prompt:document.querySelector('#prompt-frame')?.contentDocument?.querySelector('#status')?.textContent})).catch(()=>null)}));throw error}finally{await app?.close();server.closeAllConnections();await new Promise(resolve=>server.close(resolve))}
