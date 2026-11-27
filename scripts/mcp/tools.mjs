import { createEngineSession } from '../../.agents/skills/minecraft-nbt-modeler/assets/viewer/engine-session.mjs'
import { python } from '../paths.mjs'
import { engineScript, runPython } from './python.mjs'
import { failure, isObject } from './stdio.mjs'
import { renderModel } from './artifacts.mjs'

const machineMethods = new Set([
  'model.inspect', 'model.candidate', 'model.preview', 'model.commit',
  'tasks.list', 'tasks.get', 'tasks.discover', 'tasks.revalidate', 'tasks.reuse', 'tasks.create', 'tasks.record',
  'tasks.claim', 'tasks.heartbeat', 'tasks.release', 'tasks.recover',
  'prompts.list', 'prompts.get', 'prompts.task-status', 'prompts.claim', 'prompts.heartbeat', 'prompts.release',
  'annotations.scan', 'annotations.collect', 'annotation-tasks.list', 'annotation-tasks.evidence',
  'annotation-tasks.create', 'annotation-tasks.update', 'annotation-tasks.merge',
  'authoring.create', 'authoring.inspect', 'authoring.brief', 'authoring.block_state', 'authoring.report_region',
  'authoring.bind_reference', 'authoring.bind_baseline', 'authoring.issue', 'authoring.reissue', 'authoring.claim',
  'authoring.heartbeat', 'authoring.release', 'authoring.context', 'authoring.submit', 'authoring.plan_merge',
  'authoring.save_draft', 'authoring.prepare_review', 'authoring.record_observation'
])
const scopeFields = new Set(['batch_id', 'run_id', 'package_id', 'parent_id', 'package_revision', 'lease_token', 'fence'])
const hash = { type: 'string', pattern: '^[0-9a-f]{64}$' }
const dimension = { type: 'integer', minimum: 64, maximum: 4096 }
const safePath = { type: 'string', maxLength: 1000 }
const renderOptions = { width: dimension, height: dimension, quality: { type: 'string', enum: ['balanced', 'high'] } }
const outputSchema = { type: 'object', required: ['ok', 'data', 'error'], properties: {
  ok: { type: 'boolean' }, data: {}, error: { type: ['object', 'null'] }
} }

function validate(schema, input, label = 'arguments') {
  const { type, properties, required, enum: choices, pattern, maxLength, minimum, maximum } = schema
  const validType = type === 'object' ? isObject(input) : type === 'array' ? Array.isArray(input) :
    type === 'integer' ? Number.isSafeInteger(input) : typeof input === type
  if (!validType || choices && !choices.includes(input) || pattern && !new RegExp(pattern).test(input) ||
    maxLength !== undefined && input.length > maxLength ||
    minimum !== undefined && input < minimum || maximum !== undefined && input > maximum) {
    throw failure('INVALID_ARGUMENTS', '参数类型或取值无效：' + label)
  }
  if (!properties) return
  for (const key of required) if (!Object.hasOwn(input, key)) throw failure('INVALID_ARGUMENTS', '缺少参数：' + key)
  for (const [key, value] of Object.entries(input)) {
    if (!Object.hasOwn(properties, key)) throw failure('INVALID_ARGUMENTS', '未知参数：' + key)
    validate(properties[key], value, key)
  }
}

export async function createTools({ workspace, workspaceAlias, profile, allowWrite, sessionPath, startupSignal }) {
  const index = new Map()
  const machine = [engineScript('nbt_machine.py'), '--workspace', workspace,
    ...(sessionPath ? ['--package-session', sessionPath] : [])]
  const dependencyProbe = await runPython(workspace, ['-P', '-c', 'import json, numpy, PIL, nbtlib; print(json.dumps({"ready": True}))'],
    { signal: startupSignal }).catch(error => {
    if (error.code !== 'ENGINE_FAILED') throw error
    throw failure('ENGINE_UNAVAILABLE', 'Python 依赖不可用，请检查引擎 requirements.txt')
  })
  if (dependencyProbe.code !== 0 || dependencyProbe.data.ready !== true) {
    throw failure('ENGINE_UNAVAILABLE', 'Python 依赖不可用，请检查引擎 requirements.txt')
  }
  const schema = await runPython(workspace, [...machine, '--schema'], { signal: startupSignal })
  if (schema.code !== 0) throw failure(schema.data.error?.code ?? 'ENGINE_UNAVAILABLE', schema.data.error?.message ?? '无法读取 machine 工具目录')
  if (schema.data.protocol_version !== 1 || !isObject(schema.data.methods)) {
    throw failure('MACHINE_VERSION_UNSUPPORTED', '需要 machine protocol version 1')
  }

  function add(name, description, properties, required, annotations, operation) {
    const inputSchema = { type: 'object', properties, required, additionalProperties: false }
    index.set(name, {
      tool: { name, description, inputSchema, outputSchema, annotations },
      call(args, signal) { validate(inputSchema, args); return operation(args, signal) }
    })
  }
  for (const [name, definition] of Object.entries(schema.data.methods)) {
    const desktopModelWrite = profile === 'desktop' && ['model.preview', 'model.commit'].includes(name)
    if (!machineMethods.has(name) || definition.mutation && !allowWrite && !desktopModelWrite) continue
    const fields = Object.fromEntries(Object.entries(definition.fields)
      .filter(([key]) => !sessionPath || !scopeFields.has(key))
      .map(([key, type]) => [key, { type }]))
    const required = definition.required.filter(key => Object.hasOwn(fields, key))
    if (definition.mutation) {
      fields.request_id = { type: 'string', pattern: '^[A-Za-z0-9_-]{16,128}$' }
      required.push('request_id')
    }
    add(name, definition.description ?? ('NBTCreator machine ' + name), fields, required,
      definition.mutation ? { readOnlyHint: false, idempotentHint: true, openWorldHint: false } :
        { readOnlyHint: true, openWorldHint: false },
      async ({ request_id, ...params }, signal) => {
        const input = { protocol_version: 1, request_id, method: name, params }
        if (Buffer.byteLength(JSON.stringify(input)) > 2 * 1024 * 1024) {
          throw failure('REQUEST_TOO_LARGE', 'machine 请求超过 2 MiB')
        }
        const { data } = await runPython(workspace, [...machine, '--request', '-'], { input, signal })
        if (data.protocol_version !== 1 || data.request_id !== (request_id ?? null) || typeof data.ok !== 'boolean') {
          throw failure('INVALID_ENGINE_RESPONSE', 'machine 回执缺少有效版本或请求编号')
        }
        if (!data.ok) throw Object.assign(failure(data.error.code, data.error.message, data.error.details), { retryable: data.error.retryable })
        return { data: data.data, request_id: data.request_id, protocol_version: data.protocol_version }
      })
  }

  let engine
  if (!sessionPath) {
    const retrievalNames = profile === 'desktop' || allowWrite ? ['search', 'source', 'bundle', 'read'] : ['search', 'source', 'read']
    for (const action of retrievalNames) {
      const readOnlyHint = action !== 'bundle' && (action !== 'search' || profile === 'desktop')
      add('retrieve.' + action, 'NBTCreator 参考检索 ' + action, { request: { type: 'object' } }, ['request'],
        { readOnlyHint, openWorldHint: false }, async ({ request }, signal) => {
          if (Buffer.byteLength(JSON.stringify(request)) > 256 * 1024) throw failure('REQUEST_TOO_LARGE', '检索请求超过 256 KiB')
          const { code, data } = await runPython(workspace, [engineScript('nbt_retrieval.py'), '--workspace', workspace,
            action, '--request', '-', '--audience', profile === 'desktop' ? 'internal_ai' : 'external_agent'], { input: request, signal })
          if (code !== 0) throw failure('RETRIEVAL_FAILED', data.error)
          return { data }
        })
    }
    add('candidate.validate', '共享引擎的几何预检', {
      mode: { type: 'string', enum: ['component', 'workbench', 'structure', 'small_structure', 'selection_edit'] },
      result: { type: 'object' }, context: { type: 'object' }
    }, ['mode', 'result', 'context'], { readOnlyHint: true, openWorldHint: false }, async (args, signal) => {
      engine ??= createEngineSession({ workspace, python })
      const value = await engine.request('validate', args, { signal })
      if (!value.ok) throw failure(value.code, value.error, { issue: value.issue })
      return { data: value.result }
    })
    add('render.model', '用固定源与机位 SHA256 生成 Minecraft 实纹理审阅图', {
      source: safePath, source_sha256: hash, cameras: safePath, cameras_sha256: hash, ...renderOptions
    }, ['source', 'source_sha256', 'cameras', 'cameras_sha256'], { readOnlyHint: false, openWorldHint: false },
    async (args, signal) => ({ data: await renderModel(workspace, workspaceAlias, args, signal) }))

    const preview = index.get('model.preview')
    if (preview) {
      const { properties, required } = preview.tool.inputSchema
      add('render.candidate', '物化指定候选后生成绑定该候选的 Minecraft 实纹理审阅图',
        { ...properties, ...renderOptions }, required, { readOnlyHint: false, openWorldHint: false },
        async ({ width = 960, height = 640, quality = 'balanced', ...args }, signal) => {
          const { data } = await preview.call(args, signal)
          if (data.candidate_sha256 !== args.candidate_sha256 || data.visual_review !== 'pending' || data.nbt_exported !== false) {
            throw failure('INVALID_ENGINE_RESPONSE', '候选预览回执没有绑定请求指纹和待审阅状态')
          }
          const render = index.get('render.model')
          const result = await render.call({
            source: data.source, source_sha256: data.source_sha256, cameras: data.cameras, cameras_sha256: data.cameras_sha256,
            width, height, quality
          }, signal)
          return { data: { ...result.data, preview: data } }
        })
    }
  }
  return { index, close: () => engine?.close() }
}
