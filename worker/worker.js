const CLIENT_ID = "9289519218";
const REDIRECT_URI = "https://jjjjjjjjjjjjjjae-hub.github.io/QamqorPhone/auth/callback.html";
const ALLOWED_ORIGIN = "https://jjjjjjjjjjjjjjae-hub.github.io";
const ISSUER = "https://oauth.telegram.org";
const TTL = 60 * 60 * 24 * 30;

const headers = {
  "Content-Type": "application/json; charset=utf-8",
  "Cache-Control": "no-store",
  "Access-Control-Allow-Origin": ALLOWED_ORIGIN,
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type"
};
const json = (data, status = 200) => new Response(JSON.stringify(data), { status, headers });
const clean = (v, max = 200) => typeof v === "string" ? v.trim().slice(0, max) : "";
const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const id = () => "QP-" + new Date().toISOString().slice(0,10).replace(/-/g,"") + "-" + crypto.randomUUID().slice(0,8).toUpperCase();
const validId = v => /^QP-\d{8}-[A-F0-9]{8}$/.test(String(v || ""));
const now = () => new Date().toISOString();

function decodeB64(v) {
  const s = v.replace(/-/g,"+").replace(/_/g,"/") + "=".repeat((4-v.length%4)%4);
  return Uint8Array.from(atob(s), c => c.charCodeAt(0));
}
function parsePart(v) { return JSON.parse(new TextDecoder().decode(decodeB64(v))); }
function validRandom(v) { return typeof v === "string" && /^[A-Za-z0-9_-]{32,180}$/.test(v); }

async function verifyIdToken(token, nonce) {
  const p = token.split(".");
  if (p.length !== 3) throw new Error("token");
  const h = parsePart(p[0]), c = parsePart(p[1]);
  if (h.alg !== "RS256") throw new Error("algorithm");
  const r = await fetch(ISSUER + "/.well-known/jwks.json");
  if (!r.ok) throw new Error("jwks");
  const keys = await r.json(), jwk = keys.keys.find(k => k.kid === h.kid);
  if (!jwk) throw new Error("kid");
  const key = await crypto.subtle.importKey("jwk", jwk, {name:"RSASSA-PKCS1-v1_5",hash:"SHA-256"}, false, ["verify"]);
  const ok = await crypto.subtle.verify("RSASSA-PKCS1-v1_5", key, decodeB64(p[2]), new TextEncoder().encode(p[0]+"."+p[1]));
  const aud = Array.isArray(c.aud) ? c.aud : [c.aud];
  if (!ok || c.iss !== ISSUER || !aud.includes(CLIENT_ID) || c.exp <= Date.now()/1000 || c.nonce !== nonce || c.phone_number_verified !== true) throw new Error("claims");
  return {phone:c.phone_number,name:clean(c.name || [c.given_name,c.family_name].filter(Boolean).join(" "),120),username:clean(c.preferred_username,64)};
}
async function telegram(env, method, payload) {
  if (!env.TELEGRAM_BOT_TOKEN) throw new Error("bot_not_configured");
  const r = await fetch("https://api.telegram.org/bot"+env.TELEGRAM_BOT_TOKEN+"/"+method,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
  const data = await r.json();
  if (!r.ok || !data.ok) throw new Error("telegram_api_error");
  return data.result;
}
async function notifyAdmin(env, text) {
  if (!env.CHAT_ID) throw new Error("admin_not_configured");
  return telegram(env,"sendMessage",{chat_id:env.CHAT_ID,text,parse_mode:"HTML",disable_web_page_preview:true});
}
async function getRequest(env, requestId) {
  const raw = await env.QAMQOR_PHONE_DATA.get("request:"+requestId);
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}
async function putRequest(env, data) {
  data.updated_at = now();
  await env.QAMQOR_PHONE_DATA.put("request:"+data.id, JSON.stringify(data), {expirationTtl:TTL});
}
async function webhookSecret(env) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(env.TELEGRAM_BOT_TOKEN || ""));
  return Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2,"0")).join("");
}
async function tokenHash(value) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2,"0")).join("");
}
async function sameHash(a,b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let diff=0; for(let i=0;i<a.length;i++) diff |= a.charCodeAt(i)^b.charCodeAt(i);
  return diff===0;
}
async function authProfile(env, session) {
  if (!/^[0-9a-f-]{36}$/i.test(session || "")) return null;
  const raw = await env.QAMQOR_PHONE_DATA.get("auth:"+session);
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}
function priceSummary(q) {
  const p = q.estimate;
  return p && p.approved ? "Бөлшек: "+p.part+" ₸\nЖеткізу: "+p.delivery+" ₸\nЖұмыс: "+p.labor+" ₸\nЖАЛПЫ: "+p.total+" ₸" : "Смета әлі бекітілмеген";
}
function validMoney(v) { return Number.isSafeInteger(v) && v >= 0 && v <= 100000000; }

async function handleTelegramUpdate(request, env) {
  const update = await request.json().catch(()=>null);
  if (!update) return new Response("Bad JSON",{status:400});
  const msg = update.message;
  if (!msg || !msg.chat || !msg.from || typeof msg.text !== "string") return new Response("OK");
  const chatId = String(msg.chat.id), text = clean(msg.text,1000);
  const supplierKey = "supplier:"+chatId;
  const supplierRaw = await env.QAMQOR_PHONE_DATA.get(supplierKey);
  const supplier = supplierRaw ? JSON.parse(supplierRaw) : null;

  if (text === "/start" || text.startsWith("/start ")) {
    await env.QAMQOR_PHONE_DATA.put(supplierKey, JSON.stringify({chat_id:chatId,name:clean([msg.from.first_name,msg.from.last_name].filter(Boolean).join(" "),100),username:clean(msg.from.username,64),active:true,joined_at:now()}));
    const supplierIds = await env.QAMQOR_PHONE_DATA.get("suppliers:index",{type:"json"}).catch(()=>[]);
    const index = Array.isArray(supplierIds) ? supplierIds : [];
    if (!index.includes(chatId)) { index.push(chatId); await env.QAMQOR_PHONE_DATA.put("suppliers:index",JSON.stringify(index)); }
    await telegram(env,"sendMessage",{chat_id:chatId,text:"QamqorPhone жеткізушілер жүйесіне тіркелдіңіз. Бөлшек бағасын сұрау келгенде осы чатқа жауап беріңіз.\nБаға форматы: /price ӨТІНІМ_ID БӨЛШЕК_АТЫ БАҒА"});
    return new Response("OK");
  }
  if (text.startsWith("/price ")) {
    const parts = text.split(/\s+/);
    const requestId = parts[1], amount = Number(parts[parts.length-1]), partName = clean(parts.slice(2,-1).join(" "),100);
    if (!supplier || !supplier.active || !validId(requestId) || !partName || !validMoney(amount)) {
      await telegram(env,"sendMessage",{chat_id:chatId,text:"Формат: /price QP-YYYYMMDD-XXXXXXXX Бөлшек_атауы Баға"});
      return new Response("OK");
    }
    const q = await getRequest(env,requestId);
    if (!q || !q.supplier_ids?.includes(chatId) || q.status === "cancelled") {
      await telegram(env,"sendMessage",{chat_id:chatId,text:"Бұл өтінім табылмады немесе сізге арналмаған."});
      return new Response("OK");
    }
    q.supplier_quotes = q.supplier_quotes || [];
    q.supplier_quotes.push({supplier_id:chatId,supplier_name:supplier.name,part:partName,price:amount,created_at:now()});
    await putRequest(env,q);
    await notifyAdmin(env,"📦 <b>Жеткізуші бағасы келді</b>\nӨтінім: <code>"+q.id+"</code>\nЖеткізуші: "+esc(supplier.name)+"\nБөлшек: "+esc(partName)+"\nБаға: "+amount+" ₸");
    await telegram(env,"sendMessage",{chat_id:chatId,text:"Баға қабылданды. Рақмет! Өтінім: "+requestId});
    return new Response("OK");
  }

  if (chatId === String(env.CHAT_ID)) {
    const cmd = text.match(/^\/(approve|setprice|cancel)\s+(QP-\d{8}-[A-F0-9]{8})(?:\s+(.+))?$/i);
    if (cmd) {
      const q = await getRequest(env,cmd[2]);
      if (!q) { await notifyAdmin(env,"Өтінім табылмады: "+cmd[2]); return new Response("OK"); }
      if (cmd[1].toLowerCase()==="cancel") {
        q.status="cancelled"; q.cancelled_at=now(); await putRequest(env,q);
        await notifyAdmin(env,"Өтінім "+q.id+" тоқтатылды."); return new Response("OK");
      }
      const vals=(cmd[3]||"").trim().split(/[\s,]+/).map(Number);
      if (vals.length!==3 || !vals.every(validMoney)) {
        await notifyAdmin(env,"Формат: /approve "+q.id+" БӨЛШЕК ЖЕТКІЗУ ЖҰМЫСЫ"); return new Response("OK");
      }
      q.estimate=q.estimate||{history:[]};
      const old={part:q.estimate.part,delivery:q.estimate.delivery,labor:q.estimate.labor,total:q.estimate.total,changed_at:now(),source:"previous"};
      if (q.estimate.approved || q.estimate.part!==undefined) q.estimate.history=[...(q.estimate.history||[]),old];
      q.estimate={part:vals[0],delivery:vals[1],labor:vals[2],total:vals.reduce((a,b)=>a+b,0),approved:true,approved_at:now(),history:q.estimate.history||[]};
      q.status="estimate_approved"; await putRequest(env,q);
      await notifyAdmin(env,"✅ Смета бекітілді: "+q.id+"\n"+priceSummary(q)+"\nКлиент сметаны /estimate?id="+q.id+" сілтемесі арқылы қарай алады.");
      return new Response("OK");
    }
    if (text.startsWith("/suppliers")) {
      await notifyAdmin(env,"Жеткізушілер тізімі KV ішінде сақталады. Жаңа жеткізуші ботқа /start жіберуі керек.");
      return new Response("OK");
    }
  }
  return new Response("OK");
}

export default {
 async fetch(request,env) {
  const url=new URL(request.url), origin=request.headers.get("Origin");
  if(origin && origin!==ALLOWED_ORIGIN) return new Response("Forbidden",{status:403});
  if(request.method==="OPTIONS") return new Response(null,{headers});
  if(!env.QAMQOR_PHONE_DATA) return json({ok:false,error:"storage_not_configured"},503);

  if(url.pathname==="/health" && request.method==="GET") return json({ok:true,status:env.TELEGRAM_BOT_TOKEN&&env.CHAT_ID&&env.TELEGRAM_CLIENT_SECRET?"ready":"configuration_required",workflow:"estimate-v1"});
  if(url.pathname==="/telegram/webhook" && request.method==="POST") {
    const supplied=request.headers.get("X-Telegram-Bot-Api-Secret-Token") || "";
    if (!await sameHash(supplied,await webhookSecret(env))) return new Response("Forbidden",{status:403});
    try { return await handleTelegramUpdate(request,env); } catch { return new Response("Webhook processing failed",{status:500}); }
  }

  if(url.pathname==="/auth/url" && request.method==="GET") {
    const state=url.searchParams.get("state"),nonce=url.searchParams.get("nonce"),challenge=url.searchParams.get("challenge");
    if(!validRandom(state)||!validRandom(nonce)||!validRandom(challenge)) return json({ok:false,error:"invalid_parameters"},400);
    const p=new URLSearchParams({client_id:CLIENT_ID,redirect_uri:REDIRECT_URI,response_type:"code",scope:"openid profile phone",state,nonce,code_challenge:challenge,code_challenge_method:"S256"});
    return json({ok:true,url:ISSUER+"/auth?"+p});
  }
  if(url.pathname==="/auth/exchange" && request.method==="POST") {
    const body=await request.json().catch(()=>null);
    if(!body||typeof body.code!=="string"||!validRandom(body.verifier)||!validRandom(body.nonce)) return json({ok:false,error:"invalid_parameters"},400);
    const p=new URLSearchParams({grant_type:"authorization_code",code:body.code,redirect_uri:REDIRECT_URI,client_id:CLIENT_ID,code_verifier:body.verifier});
    const r=await fetch(ISSUER+"/token",{method:"POST",headers:{Authorization:"Basic "+btoa(CLIENT_ID+":"+env.TELEGRAM_CLIENT_SECRET),"Content-Type":"application/x-www-form-urlencoded"},body:p});
    const token=await r.json().catch(()=>({}));
    if(!r.ok||!token.id_token) return json({ok:false,error:"telegram_token_exchange_failed"},401);
    try {
      const profile=await verifyIdToken(token.id_token,body.nonce),session=crypto.randomUUID();
      await env.QAMQOR_PHONE_DATA.put("auth:"+session,JSON.stringify(profile),{expirationTtl:900});
      return json({ok:true,authenticated:true,session_id:session});
    } catch { return json({ok:false,error:"telegram_identity_verification_failed"},401); }
  }
  if(url.pathname==="/request" && request.method==="POST") {
    const body=await request.json().catch(()=>null);
    if(!body) return json({ok:false,error:"invalid_json"},400);
    const profile=await authProfile(env,body.session_id);
    if(!profile) return json({ok:false,error:"auth_session_expired"},401);
    const brand=clean(body.brand,90),problem=clean(body.problem,120),details=clean(body.details,500),address=clean(body.address,180);
    const phone=(details.match(/WhatsApp нөмірі \(клиент көрсеткен\):\s*([^\n]+)/i)||[])[1]||"";
    const coords=details.match(/maps\.google\.com\/?\?q=(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/i);
    if(!brand||!problem||details.length<5||address.length<5||!phone) return json({ok:false,error:"required_fields_missing"},400);
    const requestId=id(),created=now(),clientToken=Array.from(crypto.getRandomValues(new Uint8Array(32)),b=>b.toString(16).padStart(2,"0")).join("");
    const q={id:requestId,created_at:created,updated_at:created,status:"awaiting_supplier",customer:{name:clean(profile.name,120),username:clean(profile.username,64),telegram_phone:clean(profile.phone,24),whatsapp:clean(phone,24)},device:{model:brand,problem,details},location:{address,lat:coords?Number(coords[1]):null,lng:coords?Number(coords[2]):null},supplier_ids:[],supplier_quotes:[],client_token_hash:await tokenHash(clientToken),estimate:{approved:false,history:[]},consent:null};
    const list=await env.QAMQOR_PHONE_DATA.get("suppliers:index",{type:"json"}).catch(()=>[]);
    const suppliers=Array.isArray(list)?list:[];
    q.supplier_ids=suppliers;
    await putRequest(env,q);
    const msg=["🛠 <b>ЖАҢА ӨТІНІМ</b>","ID: <code>"+requestId+"</code>","Клиент: "+esc(q.customer.name),"Телефон: "+esc(q.customer.telegram_phone),"WhatsApp: "+esc(q.customer.whatsapp),"Модель: "+esc(brand),"Жөндеу: "+esc(problem),"Мекенжай: "+esc(address),"Карта: "+(coords?"https://maps.google.com/?q="+coords[1]+","+coords[2]:"көрсетілмеген"),"Мәлімет: "+esc(details),"Смета: бекітілмеген"].join("\n");
    try {
      await notifyAdmin(env,msg);
      for(const sid of suppliers) {
        await telegram(env,"sendMessage",{chat_id:sid,text:"📦 Бөлшек бағасын жіберу\nӨтінім: "+requestId+"\nМодель: "+brand+"\nҚажет: "+problem+"\nЖауап: /price "+requestId+" Бөлшек_атауы Баға"}).catch(()=>{});
      }
      await env.QAMQOR_PHONE_DATA.delete("auth:"+body.session_id);
      return json({ok:true,submitted:true,request_id:requestId,client_token:clientToken,status:q.status});
    } catch {
      return json({ok:false,error:"telegram_delivery_failed"},502);
    }
  }
  if(url.pathname==="/estimate" && request.method==="GET") {
    const requestId=clean(url.searchParams.get("id"),40);
    if(!validId(requestId)) return json({ok:false,error:"invalid_request_id"},400);
    const q=await getRequest(env,requestId);
    if(!q) return json({ok:false,error:"not_found"},404);
    const suppliedToken=url.searchParams.get("token")||"";
    if(!await sameHash(q.client_token_hash,await tokenHash(suppliedToken))) return json({ok:false,error:"not_found"},404);
    if(!q.estimate?.approved) return json({ok:true,approved:false,status:q.status});
    return json({ok:true,approved:true,estimate:{id:q.id,model:q.device.model,problem:q.device.problem,part:q.estimate.part,delivery:q.estimate.delivery,labor:q.estimate.labor,total:q.estimate.total,created_at:q.estimate.approved_at,notice:"Бұл — алдын ала есеп. Соңғы баға бөлшектің қолжетімділігі мен телефонды тексергеннен кейін нақтыланады"}});
  }
  if(url.pathname==="/estimate/decision" && request.method==="POST") {
    const body=await request.json().catch(()=>null);
    if(!body||!validId(body.request_id)||!["accept","decline"].includes(body.decision)||typeof body.client_token!=="string") return json({ok:false,error:"invalid_parameters"},400);
    const q=await getRequest(env,body.request_id);
    if(!q||!await sameHash(q.client_token_hash,await tokenHash(body.client_token))||!q.estimate?.approved) return json({ok:false,error:"estimate_not_available"},404);
    if(q.consent) return json({ok:false,error:"decision_already_recorded"},409);
    q.consent={decision:body.decision,created_at:now()}; q.status=body.decision==="accept"?"customer_accepted":"customer_declined";
    await putRequest(env,q);
    await notifyAdmin(env,(body.decision==="accept"?"✅ Клиент сметамен келісті":"❌ Клиент бас тартты")+"\nID: <code>"+q.id+"</code>\n"+priceSummary(q));
    return json({ok:true,decision:q.consent.decision,created_at:q.consent.created_at});
  }
  return json({ok:false,error:"not_found"},404);
 }
};
