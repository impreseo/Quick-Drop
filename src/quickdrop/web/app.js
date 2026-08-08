const $ = (id) => document.getElementById(id);
const authView = $("authView");
const appView = $("appView");
const TRUST_KEY = "quickdrop-trusted-v2";
let timerHandle = null;
let permissions = {downloads:true,uploads:true,text:true,trusted_devices:true,max_upload_mb:2048};

function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B","KB","MB","GB","TB"];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const n = bytes / Math.pow(1024, i);
  return `${n >= 10 || i === 0 ? n.toFixed(0) : n.toFixed(1)} ${units[i]}`;
}
function escapeHtml(s){return String(s).replace(/[&<>'"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]));}
function setTimer(seconds){clearInterval(timerHandle);let left=Math.max(0,Number(seconds)||0);const draw=()=>{const m=Math.floor(left/60),s=left%60;$("timerText").textContent=`${m}:${String(s).padStart(2,"0")} left`;if(left>0)left--;};draw();timerHandle=setInterval(draw,1000);}
function trustedValue(){try{return JSON.parse(localStorage.getItem(TRUST_KEY)||"null");}catch{return null;}}
function saveTrusted(value){if(value)localStorage.setItem(TRUST_KEY,JSON.stringify(value));else localStorage.removeItem(TRUST_KEY);}

async function postJson(url, payload){const r=await fetch(url,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});let data={};try{data=await r.json();}catch{}if(!r.ok)throw new Error(data.error||`Request failed (${r.status})`);return data;}

async function tryTrusted(){const t=trustedValue();if(!t?.id||!t?.secret)return false;try{await postJson("/api/trusted-auth",t);return true;}catch{saveTrusted(null);return false;}}

async function session(){
  const r=await fetch("/api/session",{cache:"no-store"}); const data=await r.json();
  $("computerName").textContent=data.computer||"QuickDrop PC"; permissions=data.permissions||permissions;
  $("rememberDevice").disabled=!permissions.trusted_devices;
  if(data.authenticated){authView.classList.add("hidden");appView.classList.remove("hidden");await refresh();return;}
  if(await tryTrusted()){await session();return;}
  authView.classList.remove("hidden");appView.classList.add("hidden");
}

$("pinForm").addEventListener("submit",async(e)=>{e.preventDefault();$("authError").textContent="";const pin=$("pinInput").value.replace(/\D/g,"").slice(0,6);try{const data=await postJson("/api/auth",{pin,device_name:$("deviceName").value||"My phone",remember:$("rememberDevice").checked});if(data.trusted_device)saveTrusted(data.trusted_device);await session();}catch(err){$("authError").textContent=err.message;}});
$("pinInput").addEventListener("input",e=>e.target.value=e.target.value.replace(/\D/g,"").slice(0,6));

function activateTab(name){document.querySelectorAll(".tab").forEach(x=>x.classList.toggle("active",x.dataset.tab===name));["download","upload","text"].forEach(n=>$(n+"Tab").classList.toggle("hidden",n!==name));}
document.querySelectorAll(".tab").forEach(btn=>btn.addEventListener("click",()=>activateTab(btn.dataset.tab)));

function applyPermissions(){
  $("downloadDisabled").classList.toggle("hidden",permissions.downloads); $("fileList").classList.toggle("hidden",!permissions.downloads); $("emptyFiles").classList.toggle("hidden",!permissions.downloads || Number($("fileCount").textContent)>0);
  $("uploadZone").classList.toggle("hidden",!permissions.uploads); $("uploadDisabled").classList.toggle("hidden",permissions.uploads);
  $("quickText").disabled=!permissions.text; $("saveTextBtn").disabled=!permissions.text; $("textDisabled").classList.toggle("hidden",permissions.text); $("textTab").querySelector(".text-card").classList.toggle("hidden",!permissions.text);
  $("uploadLimit").textContent=`Maximum per file: ${permissions.max_upload_mb} MB`;
  const allowed=[permissions.downloads?"download":null,permissions.uploads?"upload":null,permissions.text?"text":null].filter(Boolean);
  $("permissionSummary").textContent=allowed.length?`Allowed: ${allowed.join(" • ")}`:"PC owner has paused all transfer actions";
  document.querySelectorAll(".tab").forEach(btn=>{const key=btn.dataset.tab;const ok=key==="download"?permissions.downloads:key==="upload"?permissions.uploads:permissions.text;btn.disabled=!ok;});
  const active=document.querySelector(".tab.active"); if(active?.disabled&&allowed.length)activateTab(allowed[0]);
}

async function refresh(){try{const r=await fetch("/api/state",{cache:"no-store"});if(r.status===401){await session();return;}const data=await r.json();permissions=data.permissions||permissions;$("connectedTitle").textContent=`Connected as ${data.client?.name||"phone"}`;renderFiles(data.files||[]);if(document.activeElement!==$("quickText"))$("quickText").value=data.quick_text||"";setTimer(data.expires_in);applyPermissions();}catch{$("statusPill").textContent="Connection lost";}}
function renderFiles(files){$("fileCount").textContent=files.length;$("emptyFiles").classList.toggle("hidden",files.length>0||!permissions.downloads);$("downloadAll").classList.toggle("hidden",files.length<2||!permissions.downloads);$("fileList").innerHTML=files.map(f=>`<div class="file"><div class="file-icon">${f.kind==="folder-zip"?"▣":"↓"}</div><div class="file-meta"><div class="file-name">${escapeHtml(f.name)}</div><div class="tiny muted">${formatBytes(f.size)}${f.kind==="folder-zip"?" · folder ZIP":""}</div></div><a class="download" href="/api/download/${encodeURIComponent(f.id)}">Download</a></div>`).join("");}
$("refreshBtn").addEventListener("click",refresh);

$("fileInput").addEventListener("change",async(e)=>{for(const file of [...e.target.files])await uploadFile(file);e.target.value="";});
const zone=$("uploadZone");["dragenter","dragover"].forEach(ev=>zone.addEventListener(ev,e=>{e.preventDefault();zone.classList.add("dragging");}));["dragleave","drop"].forEach(ev=>zone.addEventListener(ev,e=>{e.preventDefault();zone.classList.remove("dragging");}));zone.addEventListener("drop",async e=>{for(const file of [...e.dataTransfer.files])await uploadFile(file);});
function uploadFile(file){return new Promise(resolve=>{if(!permissions.uploads){resolve();return;}if(file.size>permissions.max_upload_mb*1024*1024){const row=document.createElement("div");row.className="file";row.innerHTML=`<div class="file-icon">!</div><div class="file-meta"><div class="file-name">${escapeHtml(file.name)}</div><div class="tiny error-inline">Exceeds ${permissions.max_upload_mb} MB limit</div></div>`;$("uploadList").prepend(row);resolve();return;}const row=document.createElement("div");row.className="file";row.innerHTML=`<div class="file-icon">↑</div><div class="file-meta"><div class="file-name">${escapeHtml(file.name)}</div><div class="tiny muted label">Waiting…</div><div class="progress-wrap"><div class="progress"></div></div></div>`;$("uploadList").prepend(row);const bar=row.querySelector(".progress"),label=row.querySelector(".label");const xhr=new XMLHttpRequest();xhr.open("POST","/api/upload");xhr.setRequestHeader("X-QuickDrop-Filename",encodeURIComponent(file.name));xhr.upload.onprogress=(ev)=>{if(ev.lengthComputable){const p=Math.round(ev.loaded/ev.total*100);bar.style.width=p+"%";label.textContent=`${p}% · ${formatBytes(ev.loaded)} of ${formatBytes(ev.total)}`;}};xhr.onload=()=>{if(xhr.status>=200&&xhr.status<300){bar.style.width="100%";label.textContent=`Sent · ${formatBytes(file.size)}`;}else{try{label.textContent=JSON.parse(xhr.responseText).error||"Upload failed";}catch{label.textContent="Upload failed";}}resolve();};xhr.onerror=()=>{label.textContent="Connection failed";resolve();};xhr.send(file);});}

$("saveTextBtn").addEventListener("click",async()=>{$("textStatus").textContent="Sending…";try{await postJson("/api/text",{text:$("quickText").value});$("textStatus").textContent="Sent to PC";}catch(err){$("textStatus").textContent=err.message;}});
$("copyTextBtn").addEventListener("click",async()=>{try{await navigator.clipboard.writeText($("quickText").value);$("textStatus").textContent="Copied";}catch{$("quickText").select();document.execCommand("copy");$("textStatus").textContent="Copied";}});
$("forgetDevice").addEventListener("click",()=>{saveTrusted(null);$("forgetDevice").textContent="Remembered device cleared";});

session();setInterval(()=>{if(!appView.classList.contains("hidden"))refresh();},10000);
