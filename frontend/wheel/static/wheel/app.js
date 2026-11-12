'use strict';
const $=id=>document.getElementById(id);
let palette=['#24594e','#725039','#454f78','#5b4265','#3a615c','#684b4c','#525c38','#344b68'];
let wheelColors={empty:'#25302e',stroke:'#ffffff28',text:'#f2f5f3',light:'#f2f5f3'};
const demo='intNeo\nmoonlight\nplayer_01\nlucky_cat\nAlex\nstarboy\ncoffee_break\nneo.exe';
let saved={};try{saved=JSON.parse(localStorage.getItem('fortuna-v1')||'{}')}catch{}
$('names').value=typeof saved.names==='string'?saved.names:demo;
let mode=['normal','weighted','inverse'].includes(saved.mode)?saved.mode:'normal';
$('duration').value=Math.max(3,Math.min(20,Number(saved.duration)||8));
let history=Array.isArray(saved.history)?saved.history.filter(x=>typeof x.name==='string'&&typeof x.date==='string').slice(0,50):[];
let sectors=[],busy=false,angle=0,lastWinner=null,sound=false,audio=null;
const canvas=$('wheel'),ctx=canvas.getContext('2d'),tau=Math.PI*2;
function lines(){return $('names').value.split(/\r?\n/).map(s=>s.trim()).filter(Boolean)}
function buildSectors(list,kind){const counts=new Map();list.forEach(n=>counts.set(n,(counts.get(n)||0)+1));return kind==='normal'?list.map(name=>({name,weight:1})):Array.from(counts,([name,count])=>({name,weight:kind==='inverse'?1/count:count}))}
function randomUnit(){const a=new Uint32Array(1);crypto.getRandomValues(a);return a[0]/4294967296}
function persist(){try{localStorage.setItem('fortuna-v1',JSON.stringify({names:$('names').value,mode,duration:$('duration').value,history}))}catch{}}
function draw(){ctx.clearRect(0,0,1200,1200);const total=sectors.reduce((s,x)=>s+x.weight,0);ctx.save();ctx.translate(600,600);ctx.rotate(angle);let start=-Math.PI/2;const items=sectors.length?sectors:[{name:'Добавьте ники',weight:1}];for(let i=0;i<items.length;i++){const item=items[i],arc=item.weight/(total||1)*tau;ctx.beginPath();ctx.moveTo(0,0);ctx.arc(0,0,590,start,start+arc);ctx.closePath();ctx.fillStyle=sectors.length?palette[i%palette.length]:wheelColors.empty;ctx.fill();ctx.strokeStyle=wheelColors.stroke;ctx.lineWidth=2;ctx.stroke();if(arc>.035){ctx.save();ctx.rotate(start+arc/2);ctx.textAlign='right';ctx.textBaseline='middle';ctx.fillStyle=[0,3,7].includes(i%8)?wheelColors.light:wheelColors.text;const fontSize=Math.min(36,Math.max(15,arc*160));ctx.font=`500 ${fontSize}px 'Golos Text',Arial`;let label=item.name;while(ctx.measureText(label).width>380&&label.length>1)label=label.slice(0,-1);if(label!==item.name)label=label.slice(0,-1)+'…';ctx.fillText(label,535,0);ctx.restore()}start+=arc}ctx.restore()}
const helps={normal:'Каждая строка — отдельный сектор одинакового размера. Повторяющиеся ники остаются на колесе.',weighted:'Один сектор на ник. Вес равен числу повторов: 3 строки → вес 3. Шанс такой же, как в обычном режиме.',inverse:'Один сектор на ник. Вес = 1 / число повторов: 3 строки → 1/3, 2 строки → 1/2, 1 строка → 1.'};
function update(){const list=lines();sectors=buildSectors(list,mode);$('entryCount').textContent=list.length+' записей';$('uniqueCount').textContent=new Set(list).size;$('sectorCount').textContent=sectors.length;$('modeHelp').textContent=helps[mode];$('durationValue').innerHTML=$('duration').value+' <span>сек</span>';$('spin').disabled=busy||!list.length;$('wheelStatus').textContent=list.length?'ВСЁ ГОТОВО К РОЗЫГРЫШУ':'ДОБАВЬТЕ УЧАСТНИКОВ';document.querySelectorAll('.mode').forEach(b=>{const selected=b.dataset.mode===mode;b.classList.toggle('selected',selected);b.setAttribute('aria-checked',selected)});draw();persist()}
function renderHistory(){$('historyList').replaceChildren();$('historyCount').textContent=history.length;$('roundCount').textContent=history.length;$('clearHistory').disabled=!history.length;if(!history.length){const e=document.createElement('span');e.className='empty-history';e.textContent='Здесь появятся ваши победители. Кто будет первым?';$('historyList').append(e)}history.forEach((h,i)=>{const e=document.createElement('div');e.className='history-item';const n=document.createElement('span');n.className='history-number';n.textContent=String(history.length-i).padStart(2,'0');const name=document.createElement('b');name.textContent=h.name;const time=document.createElement('small');time.textContent=new Date(h.date).toLocaleTimeString('ru-RU',{hour:'2-digit',minute:'2-digit'});e.append(n,name,time);$('historyList').append(e)})}
function lock(value){busy=value;document.querySelectorAll('.mode,#names,#duration,#clear').forEach(e=>e.disabled=value);$('spin').disabled=value||!sectors.length}
function beep(freq=600){if(!sound)return;try{audio=audio||new(window.AudioContext||window.webkitAudioContext)();if(audio.state==='suspended')audio.resume();const o=audio.createOscillator(),g=audio.createGain();o.connect(g);g.connect(audio.destination);o.frequency.value=freq;g.gain.setValueAtTime(.035,audio.currentTime);g.gain.exponentialRampToValueAtTime(.001,audio.currentTime+.07);o.start();o.stop(audio.currentTime+.08)}catch{}}
function confetti(){if(matchMedia('(prefers-reduced-motion: reduce)').matches)return;for(let i=0;i<65;i++){const el=document.createElement('i');el.className='confetti';el.style.left=Math.random()*100+'vw';el.style.background=palette[i%palette.length];el.style.animationDelay=Math.random()*.5+'s';el.style.setProperty('--dx',(Math.random()-.5)*300+'px');document.body.append(el);setTimeout(()=>el.remove(),3300)}}
async function spin(){
if(busy||!sectors.length)return;
const names=lines();
if(names.length>5000||names.some(n=>n.length>100)){ $('spinHint').textContent='Максимум 5000 записей, до 100 символов в нике.';return; }
lock(true);$('wheelStatus').textContent='ЗАПРАШИВАЕМ РЕЗУЛЬТАТ…';
let result;
try{
 const csrf=document.cookie.split('; ').find(c=>c.startsWith('csrftoken='))?.split('=')[1]||'';
 const response=await fetch('/api/spin',{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':decodeURIComponent(csrf)},body:JSON.stringify({names,mode,duration:Number($('duration').value)}),signal:AbortSignal.timeout(10000)});
 if(response.status===401){window.location.assign('/login/');return;}
 result=await response.json().catch(()=>({error:'Сервер отклонил запрос. Проверьте доступ или повторите позже.'}));if(response.status===429)result.error+=' Ожидание: '+(response.headers.get('Retry-After')||'60')+' сек.';if(!response.ok)throw new Error(result.error||'Не удалось выполнить розыгрыш.');
 if(!Number.isInteger(result.selected_index)||!sectors[result.selected_index]||sectors[result.selected_index].name!==result.winner)throw new Error('Некорректный ответ сервера.');
}catch(error){lock(false);$('wheelStatus').textContent='НЕ УДАЛОСЬ ПРОВЕСТИ РОЗЫГРЫШ';$('spinHint').textContent=error.name==='TimeoutError'?'Сервер не ответил вовремя. Попробуйте ещё раз.':(error.message||'Ошибка соединения.');return;}
$('wheelStatus').textContent='ФОРТУНА ВЫБИРАЕТ ПОБЕДИТЕЛЯ…';$('spin').firstElementChild.textContent='Колесо вращается…';$('spinHint').textContent='Скоро узнаем, кому улыбнулась удача';
const selected=result.selected_index,total=sectors.reduce((s,x)=>s+x.weight,0);let prior=0;for(let i=0;i<selected;i++)prior+=sectors[i].weight;
const position=(prior+sectors[selected].weight*(.22+randomUnit()*.56))/total*tau;
const from=angle,target=from+tau*6+((tau-position-from%tau)%tau+tau)%tau;
const start=performance.now(),duration=result.duration*1000;let lastTick=-1;beep();
function frame(now){const p=Math.min(1,(now-start)/duration),ease=1-Math.pow(1-p,4);angle=from+(target-from)*ease;draw();const tick=Math.floor(angle*8);if(tick!==lastTick&&p<.99){beep(300+150*p);lastTick=tick}if(p<1)requestAnimationFrame(frame);else{angle%=tau;finish(selected,total,result)}}requestAnimationFrame(frame)
}
function finish(selected,total,result){lastWinner=sectors[selected].name;history.unshift({name:lastWinner,date:result.created_at,id:result.id});history=history.slice(0,50);renderHistory();persist();lock(false);$('wheelStatus').textContent='ПОБЕДИТЕЛЬ ВЫБРАН';$('spin').firstElementChild.textContent='Крутить ещё раз';$('spinHint').textContent='Новый розыгрыш — новая возможность';$('winnerName').textContent=lastWinner;$('winnerDetails').textContent='Шанс в этом розыгрыше: '+(result.probability*100).toLocaleString('ru-RU',{maximumFractionDigits:2})+' %';$('announcement').textContent='Победитель: '+lastWinner;$('winnerDialog').showModal();confetti();beep(900)}
$('names').addEventListener('input',()=>{angle=0;update()});$('duration').addEventListener('input',update);document.querySelectorAll('.mode').forEach(b=>b.addEventListener('click',()=>{mode=b.dataset.mode;angle=0;update()}));$('clear').onclick=()=>{$('names').value='';angle=0;update();$('names').focus()};$('spin').onclick=spin;$('sound').onclick=()=>{sound=!sound;$('sound').textContent=sound?'Звук вкл.':'Звук выкл.';$('sound').setAttribute('aria-label',sound?'Выключить звук':'Включить звук');beep()};$('clearHistory').onclick=()=>{history=[];renderHistory();persist()};$('closeWinner').onclick=()=>$('winnerDialog').close();$('again').onclick=()=>{$('winnerDialog').close();spin()};$('removeWinner').onclick=()=>{$('names').value=lines().filter(n=>n!==lastWinner).join('\n');$('winnerDialog').close();angle=0;update()};$('winnerDialog').addEventListener('click',e=>{if(e.target===$('winnerDialog')){const r=e.target.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)e.target.close()}});document.addEventListener('keydown',e=>{if(e.code==='Space'&&!['TEXTAREA','INPUT','BUTTON'].includes(document.activeElement.tagName)&&!$('winnerDialog').open){e.preventDefault();spin()}});update();renderHistory();if(document.fonts)document.fonts.ready.then(draw);

function syncWheelTheme() {
    const style = getComputedStyle(document.documentElement);
    const color = name => style.getPropertyValue(name).trim();
    palette = Array.from({length: 8}, (_, i) => color('--wheel-' + i) || palette[i]);
    wheelColors = {
        empty: color('--wheel-empty') || '#25302e',
        stroke: color('--wheel-stroke') || '#ffffff28',
        text: color('--wheel-text') || '#f2f5f3',
        light: color('--wheel-text-light') || '#f2f5f3',
    };
    draw();
}
window.addEventListener('fortune-theme-change', syncWheelTheme);
syncWheelTheme();
