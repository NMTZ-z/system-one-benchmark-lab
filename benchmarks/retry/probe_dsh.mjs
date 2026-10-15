// Phase 8C loopback transport smoke: pinned DSH adapter on synthetic lifecycle events.
// Not an actual provider-backed Agent task.
import { apply } from '../../integrations/deepseek-harness/local-system-one-dsh/dist/index.js'

const endpoint = process.argv[2]
if (typeof endpoint !== 'string' || !/^http:\/\/127\.0\.0\.1:\d+$/.test(endpoint)) {
  throw Error('expected local loopback endpoint')
}
const callbacks = new Map()
const observations = []
const ctx = {
  on(name, callback) {callbacks.set(name, callback)},
  logger: {info(text) {observations.push(text)}},
}
apply(ctx, {
  mode: 'shadow',service_url: endpoint, timeout_ms: 2500,
  search_gate_enabled:false,model_tier_gate_enabled:false,
  notification_gate_enabled:false,completion_gate_enabled:false,
  retry_escalation_gate_enabled:true,
})
const handler = callbacks.get('session/event')
if (!handler) throw Error('missing DSH native session event observer')
handler({id:'isolated-retry-transport'}, {
  type:'tool/call', data:{
    turn:1,step:1,callId:'test-side-effect-a',name:'write',
    arguments:'{"neverSend":"private data"}',
  },
})
handler({id:'isolated-retry-transport'}, {
  type:'tool/result',data:{
    turn:1,step:1,
    message:{
      isError:true,role:'tool',source:{callId:'test-side-effect-a'},
      content:[{type:'text',text:'private data must not reach Runtime'}],
    },
    error:{name:'NetworkError',code:'ETIMEDOUT',reason:'PRIVATE'},
  },
})
let found
for (let i=0;i<60;i++){
  await new Promise(resolve=>setTimeout(resolve,50))
  found=observations.find(item=>item.includes('"gate":"retry_escalation"')
    && item.includes('"action_status":"observed"'))
  if(found)break
}
if (!found || !found.includes('"value":"verify_state"')) {
  throw Error('DSH retry typed recommendation not observed')
}
if (observations.join(' ').includes('PRIVATE') || observations.join(' ').includes('private data')) {
  throw Error('privacy violation in DSH telemetry')
}
handler({id:'isolated-retry-transport'}, {
  type:'turn/end',data:{turn:1,reason:{kind:'completed'}},
})
console.log(JSON.stringify({dsh_loopback:'PASS',shadow:true,observed:'verify_state'}))
