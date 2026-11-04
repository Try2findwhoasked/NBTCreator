export function workerExit({phase,pid,code,signal,stdout='',stderr=''}){
 return {phase:String(phase).slice(0,64),...(Number.isInteger(pid)?{pid}:{}),exit_code:code,signal:signal??null,stdout_bytes:Buffer.byteLength(stdout),stderr_bytes:Buffer.byteLength(stderr),...(Number.isInteger(code)?{exit_hex:'0x'+(code>>>0).toString(16).padStart(8,'0')}:{})}
}
export function parseWorkerResult(stdout,exit){
 const ending=exit.exit_hex??exit.signal??String(exit.exit_code)
 if(!stdout.trim())throw Error('本地建模进程未返回结果（退出状态 '+ending+'）；没有可用的工具结果，请查看任务记录中的进程退出信息。')
 try{return JSON.parse(stdout)}catch{throw Error('本地建模进程返回的数据不完整或格式无效（退出状态 '+ending+'，'+exit.stdout_bytes+' 字节）；请查看任务记录，不要把此结果当作已完成。')}
}
