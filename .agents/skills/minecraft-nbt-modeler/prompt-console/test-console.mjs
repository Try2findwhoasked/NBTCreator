// Offline file:// browser regression; synthetic parameter data only.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {launchRenderBrowser} from '../assets/viewer/browser-launch.mjs';
import './catalog.js';
import './core.js';
const root=path.dirname(fileURLToPath(import.meta.url));
const output=process.argv[2];if(!output)throw Error('Pass a NEW output directory');
await fs.mkdir(output,{recursive:false});
const C=globalThis.NbtPrompt;
const defaults=C.defaults();assert.deepEqual(C.validate(defaults),[]);
for(const kind of Object.keys(C.catalog)){const s=C.defaults();s.operations=[C.operation(kind)];assert.deepEqual(C.validate(s),[],kind);assert.equal(C.plan(s).operations[0].kind,kind);}
assert.ok(!('lo' in C.operation('auto_floor')));
assert.ok(C.prompt(defaults).includes('等待真实用户同意精修'));
const refinement=C.defaults();refinement.project.stage='refine';assert.ok(C.prompt(refinement).includes('本提示词与参数文件自身不构成看图确认'));
await fs.writeFile(path.join(output,'default-prompt.md'),C.prompt(defaults));
const browser=await launchRenderBrowser();const checks={catalogue_and_stage_boundaries:true};
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:true});const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto(pathToFileURL(path.join(root,'index.html')).href);
 assert.ok((await page.locator('#result').inputValue()).includes('新建完整建筑初稿'));
 await page.screenshot({path:path.join(output,'start.png')});
 await page.locator('[data-field=name]').fill('测试拱厅');
 await page.getByRole('button',{name:/02 工具序列/}).click();
 await page.locator('#kind').selectOption('geometry');await page.locator('#add').click();
 await page.locator('[data-field=radius]').fill('2.5');
 assert.ok((await page.locator('#result').inputValue()).includes('"radius": 2.5'));
 await page.locator('[data-field=shape]').selectOption('sphere');
 assert.ok((await page.locator('#result').inputValue()).includes('"shape": "sphere"'));
 await page.locator('#kind').selectOption('explosion');await page.locator('#add').click();
 await page.locator('.step').last().getByRole('button',{name:'↑',exact:true}).click();
 assert.ok((await page.locator('.step').first().textContent()).includes('静态爆炸'));
 await page.locator('.step').first().getByRole('button',{name:'复制',exact:true}).click();assert.equal(await page.locator('.step').count(),3);
 await page.locator('.step').first().getByRole('button',{name:'删除',exact:true}).click();
 const downloadPromise=page.waitForEvent('download');await page.locator('#save').click();const download=await downloadPromise;const preset=path.join(output,'saved-settings.json');await download.saveAs(preset);
 const before=await page.locator('#result').inputValue();
 await page.locator('.step').first().getByRole('button',{name:'删除',exact:true}).click();
 await page.locator('#file').setInputFiles(preset);await page.waitForFunction(()=>document.querySelectorAll('.step').length===2);
 assert.equal(await page.locator('#result').inputValue(),before);checks.reorder_copy_delete_import_roundtrip=true;
 await page.locator('.step').first().locator('[data-field=radius]').fill('-1');assert.ok(await page.locator('#copy').isDisabled());
 await page.locator('.step').first().locator('[data-field=radius]').fill('3');assert.ok(await page.locator('#copy').isEnabled());
 await page.getByRole('button',{name:'03 验证上下文'}).click();await page.locator('#context-json').fill('{');assert.ok(await page.locator('#plan').isDisabled());
 await page.locator('#context-json').fill(JSON.stringify(defaults.project.context));assert.ok(await page.locator('#plan').isEnabled());checks.invalid_parameters_block_export=true;
 const planPromise=page.waitForEvent('download');await page.locator('#plan').click();const plan=await planPromise;await plan.saveAs(path.join(output,'plan.json'));
 const data=JSON.parse(await fs.readFile(path.join(output,'plan.json'),'utf8'));assert.equal(data.operations[0].kind,'explosion');assert.equal(data.operations.length,2);checks.actual_plan_download=true;
 await page.reload();assert.equal(await page.locator('#result').inputValue(),before);checks.local_persistence=true;
 await page.getByRole('button',{name:/02 工具序列/}).click();
 for(const kind of Object.keys(C.catalog)){await page.locator('#kind').selectOption(kind);await page.locator('#add').click();}
 assert.ok(await page.locator('#copy').isEnabled());checks.all_18_tools_render=true;
 await page.screenshot({path:path.join(output,'desktop.png')});
 await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:path.join(output,'mobile.png')});checks.mobile_no_overflow=true;
 assert.deepEqual(errors,[]);checks.no_browser_errors=true;
 await fs.writeFile(path.join(output,'results.json'),JSON.stringify({passed:true,checks},null,2));
 console.log(JSON.stringify({passed:true,checks:Object.keys(checks).length,output:path.resolve(output)}));
}finally{await browser.close();}
