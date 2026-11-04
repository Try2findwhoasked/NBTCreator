import http from 'node:http'
import {randomUUID} from 'node:crypto'

// Some Windows test environments allocate port 6000 for listen(0), which Fetch
// rejects before connecting. Probe the actual loopback route instead of assuming
// every dynamically assigned port can be used by the application request layer.
export async function createFetchServer(handler){
 const held=[],nonce=randomUUID()
 try{
  for(let attempt=0;attempt<16;attempt++){
   const server=http.createServer((req,res)=>{if(req.headers['x-nbt-fixture-probe']===nonce){res.writeHead(204);res.end();return}handler(req,res)})
   await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve)})
   try{const response=await fetch(`http://127.0.0.1:${server.address().port}`,{headers:{'x-nbt-fixture-probe':nonce},signal:AbortSignal.timeout(1000)});if(response.status===204)return server}catch{}
   held.push(server)
  }
  throw Error('No Fetch-accessible loopback test port was available')
 }finally{for(const server of held){server.closeAllConnections();await new Promise(resolve=>server.close(resolve))}}
}
