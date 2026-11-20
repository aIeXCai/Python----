const $ = id => document.getElementById(id);
const clamp = (n, lo, hi) => Math.max(lo, Math.min(n, hi));
const fmt = n => Math.round(n).toLocaleString('en-US');
const clock = n => [Math.floor(n/60),Math.floor(n%60)].map(v=>String(v).padStart(2,'0')).join(':');
const canvas = $('map'), ctx = canvas.getContext('2d');
const terrain = document.createElement('canvas'), terrainCtx = terrain.getContext('2d');
const reduced = matchMedia('(prefers-reduced-motion: reduce)');
let lang = 'zh', mode = 'idle', seconds = 0, input = '', composing = false;
let chars = [], summitAt = null, shown = 0;
let lastDraw = -Infinity, terrainKey = '';
const artSources = {};
let peakPair = {zh:'01-everest',en:'02-k2'};
const art = {};
let lastMapFrame = '', drawCount = 0, meterStart = performance.now();

// x and y are normalized positions on the panorama. Camp elevations control
// the progress thresholds; intermediate drawing points are illustrative.
function makeRoute(peak, english, region, name, description, source, camps, bends){
  return {
    peak, english, region, name, description, source, bends,
    camps:camps.map(([label,m,x,y,side=1])=>({label,m,x,y,side,feature:label==='BC'?'大本营':label==='ABC'?'前进营地':label==='峰顶'?peak:''}))
  };
}
const routes = {
  '01-everest':{
    peak:'珠穆朗玛峰', english:'Everest', region:'喜马拉雅山脉',
    description:'珠穆朗玛峰位于中国与尼泊尔交界，是世界最高峰。本版采用尼泊尔一侧的南坳路线，沿途经过昆布冰瀑、西冰斗和洛子壁。',
    source:'https://sevensummittreks.com/uploads/doc/everfb26cl-687c79efe79fd.pdf#page=12',
    name:'南坳 · 东南山脊',
    camps:[
      {label:'BC', m:5400, x:.34, y:.81, feature:'大本营', side:-1},
      {label:'C1', m:6065, x:.46, y:.69, feature:'昆布冰瀑上方', side:-1},
      {label:'C2', m:6750, x:.57, y:.63, feature:'西冰斗', side:1},
      {label:'C3', m:7300, x:.64, y:.51, feature:'洛子壁', side:-1},
      {label:'C4', m:7900, x:.71, y:.42, feature:'南坳', side:1},
      {label:'峰顶', m:8848.86, x:.643, y:.265, feature:'珠穆朗玛峰', side:1}
    ],
    bends:[[[.34,.39,.78],[.61,.416,.744],[.8,.438,.754]],[[.33,.49,.674],[.70,.545,.649]],[[.3,.596,.603],[.72,.613,.548]],[[.38,.665,.476],[.67,.69,.468]],[[.28,.713,.397],[.48,.693,.359],[.72,.675,.325],[.88,.656,.292]]]
  },
  '02-k2':{
    peak:'乔戈里峰', english:'K2', region:'喀喇昆仑山脉',
    description:'乔戈里峰是世界第二高峰，位于中国与巴基斯坦边界的喀喇昆仑山脉。阿布鲁齐山脊路线以豪斯烟囱、黑色金字塔、肩部与瓶颈等地标著称。',
    source:'https://madisonmountaineering.com/expedition/k2/',
    name:'阿布鲁齐山脊',
    camps:[
      {label:'BC', m:4970, x:.89, y:.82, feature:'大本营', side:1},
      {label:'ABC', m:5300, x:.81, y:.77, feature:'前进营地', side:1},
      {label:'C1', m:6070, x:.72, y:.68, feature:'阿布鲁齐山脊', side:1},
      {label:'C2', m:6700, x:.65, y:.59, feature:'豪斯烟囱上方', side:1},
      {label:'C3', m:7250, x:.61, y:.49, feature:'黑色金字塔上方', side:1},
      {label:'C4', m:7710, x:.57, y:.42, feature:'肩部', side:1},
      {label:'峰顶', m:8611, x:.523, y:.260, feature:'乔戈里峰', side:1}
    ],
    bends:[[[.48,.849,.801]],[[.32,.783,.741],[.72,.744,.706]],[[.34,.702,.655],[.68,.676,.626]],[[.50,.628,.551]],[[.36,.596,.455],[.71,.587,.428]],[[.24,.564,.382],[.46,.551,.352],[.66,.542,.326],[.87,.53,.286]]]
  },
  '03-kangchenjunga': makeRoute('干城章嘉峰', 'Kangchenjunga', '喜马拉雅山脉', '亚隆冰川南侧',
    '世界第三高峰，位于尼泊尔与印度边境。它的山体宽阔，由一组相连的高峰和山脊组成。示意路线从亚隆冰川一侧接近主峰。',
    'https://www.sevensummittreks.com/page/mt-kangchenjunga-expedition-8586m.html',
    [['BC',5475,.36,.82],['C1',6200,.47,.70],['C2',6400,.56,.62],['C3',7100,.64,.50],['C4',7570,.68,.36],['峰顶',8586,.601,.170]],
    [[[.52,.414,.748]],[[.47,.51,.65]],[[.42,.591,.565]],[[.54,.66,.445]],[[.32,.672,.318],[.70,.628,.227]]]),
  '04-lhotse': makeRoute('洛子峰', 'Lhotse', '喜马拉雅山脉', '洛子壁 · 洛子沟',
    '洛子峰与珠峰隔南坳相望。部分登山队与珠峰队共走昆布冰瀑和西冰斗，后段转向洛子沟，这条狭窄的雪沟是它的典型地标。',
    'https://sevensummittreks.com/public/page/mt-lhotse-expedition-8516m.html',
    [['BC',5364,.37,.82],['C1',6065,.45,.73],['C2',6750,.53,.69],['C3',7300,.60,.45],['C4',7900,.64,.28],['峰顶',8516,.68,.083]],
    [[[.48,.398,.773]],[[.58,.50,.705]],[[.45,.568,.57]],[[.50,.618,.367]],[[.35,.646,.22],[.72,.662,.142]]]),
  '05-makalu': makeRoute('马卡鲁峰', 'Makalu', '喜马拉雅山脉', '西北山脊',
    '马卡鲁峰位于喜马拉雅山脉中段，主峰常被形容为一座陡峭的金字塔。原型选择西北山脊路线，按同一份线路图标出四座高营。',
    'https://www.sevensummittreks.com/uploads/doc/makalu-fb-23-637c47177e854.pdf#page=7',
    [['BC',5600,.84,.79],['C1',6100,.74,.71],['C2',6500,.62,.62],['C3',7400,.69,.47],['C4',7800,.70,.33],['峰顶',8485,.635,.144]],
    [[[.50,.794,.746]],[[.47,.68,.658]],[[.35,.645,.55],[.72,.681,.52]],[[.5,.72,.40]],[[.46,.674,.219]]]),
  '06-cho-oyu': makeRoute('卓奥友峰', 'Cho Oyu', '喜马拉雅山脉', '西面 · 西山脊',
    '卓奥友峰位于中国和尼泊尔交界，顶部是一片宽广的雪坡。示意路线从西藏一侧进入，途经冰川、宽缓的雪地和峰顶高原。',
    'https://adventureconsultants.com/files/Trip-Notes-Himalaya/Cho-Oyu-2025-Trip-Notes.pdf#page=3',
    [['BC',4800,.30,.83],['ABC',5650,.39,.76],['C1',6400,.47,.62],['C2',7000,.56,.50],['C3',7400,.61,.39],['峰顶',8201,.59,.236]],
    [[[.58,.346,.797]],[[.38,.428,.712],[.73,.456,.674]],[[.61,.524,.533]],[[.67,.595,.431]],[[.49,.622,.308],[.76,.609,.254]]]),
  '07-dhaulagiri-i': makeRoute('道拉吉里Ⅰ峰', 'Dhaulagiri I', '喜马拉雅山脉', '东北山脊',
    '道拉吉里Ⅰ峰位于尼泊尔西部，是道拉吉里山群的最高点。本版采用从第三营冲顶的东北山脊方案。登山队也会根据山况使用其他营地安排。',
    'https://www.lamaadventure.com.np/expedition/dhaulagiri-expedition',
    [['BC',4750,.31,.82],['C1',5900,.48,.70],['C2',6400,.59,.56],['C3',7400,.68,.34],['峰顶',8167,.665,.078]],
    [[[.42,.376,.751],[.75,.444,.732]],[[.53,.548,.627]],[[.45,.648,.478],[.73,.663,.406]],[[.33,.70,.26],[.69,.68,.155]]]),
  '08-manaslu': makeRoute('马纳斯卢峰', 'Manaslu', '喜马拉雅山脉', '东北面',
    '马纳斯卢峰位于尼泊尔，雪坡与上方的狭窄山脊形成鲜明对比。图中采用东北面的四营方案，最终点标在主峰。',
    'https://sevensummittreks.com/uploads/doc/manaslu-fb-62c3c63a8e9f7.pdf#page=7',
    [['BC',4700,.26,.81],['C1',5500,.42,.70],['C2',6200,.52,.61],['C3',6800,.59,.49],['C4',7400,.64,.36],['峰顶',8163,.63,.174]],
    [[[.48,.349,.759]],[[.48,.484,.654]],[[.5,.573,.563]],[[.39,.615,.455],[.74,.623,.409]],[[.44,.658,.282],[.78,.649,.222]]]),
  '09-nanga-parbat': makeRoute('南迦帕尔巴特峰', 'Nanga Parbat', '喜马拉雅山脉', '迪亚米尔面 · 金斯霍弗',
    '南迦帕尔巴特峰位于巴基斯坦，是喜马拉雅山脉西端的高峰。登山资料选择西侧迪亚米尔面的金斯霍弗路线。背景是山体艺术插画。',
    'https://www.discoverkarakoram.com/nanga-parbat-8126m-kinshofer-route-expedition-guide/',
    [['BC',4200,.34,.82],['C1',5000,.45,.72],['C2',6000,.52,.51],['C3',6800,.55,.40],['C4',7300,.63,.31],['峰顶',8126,.615,.124]],
    [[[.51,.391,.785]],[[.42,.48,.652],[.74,.503,.557]],[[.51,.527,.451]],[[.55,.594,.367]],[[.42,.637,.231],[.77,.623,.165]]]),
  '10-annapurna-i': makeRoute('安纳普尔纳Ⅰ峰', 'Annapurna I', '喜马拉雅山脉', '北壁',
    '安纳普尔纳Ⅰ峰是尼泊尔安纳普尔纳山群的主峰。登山资料选用北壁的四营路线。插画呈现山群的冰雪地形，红线只用于练习示意。',
    'https://mail.sevensummittreks.com/page/mt-annapurna-i-expedition-8091m.html',
    [['BC',4190,.32,.82],['C1',5150,.46,.73],['C2',5700,.56,.66],['C3',6500,.63,.49],['C4',7400,.70,.33],['峰顶',8091,.662,.098]],
    [[[.56,.414,.775]],[[.55,.511,.695]],[[.42,.587,.606],[.73,.610,.533]],[[.55,.68,.408]],[[.45,.715,.232],[.80,.68,.158]]]),
  '11-gasherbrum-i': makeRoute('加舒尔布鲁木Ⅰ峰', 'Gasherbrum I', '喀喇昆仑山脉', '日本沟路线',
    '也被称为“隐秘峰”，与加舒尔布鲁木Ⅱ峰相邻。两峰的常用路线可共用大本营和部分冰川路段。Ⅰ峰这条线路在高处经过日本沟。',
    'https://chogoriadventure.com/tour/gasherbrum-1-expedition/',
    [['BC',5100,.22,.82],['C1',6000,.39,.71],['C2',6450,.50,.64],['C3',7100,.59,.39],['峰顶',8080,.69,.075]],
    [[[.37,.283,.781],[.73,.352,.757]],[[.52,.447,.68]],[[.42,.543,.535],[.76,.573,.454]],[[.38,.629,.271],[.74,.659,.158]]]),
  '12-broad-peak': makeRoute('布洛阿特峰', 'Broad Peak', '喀喇昆仑山脉', '西山脊',
    'Broad Peak 的英文名意为“宽阔的山峰”。它和 K2 同在喀喇昆仑山脉。西山脊路线经过山坳后，还需要沿长山脊前往主峰。',
    'https://assets.publishing.service.gov.uk/media/65cdf20a1305490011867a79/Investigation_into_the_death_of_a_Royal_Air_Force__RAF__service_person_and_serious_injuries_during_British_Services_Mountaineering_Expedition__Pakistan_July_2022.pdf',
    [['BC',4850,.85,.82],['C1',5500,.76,.74],['C2',6250,.67,.62],['C3',7050,.55,.42],['峰顶',8047,.62,.252]],
    [[[.51,.81,.776]],[[.45,.71,.685]],[[.44,.625,.55],[.76,.588,.474]],[[.35,.52,.346],[.63,.558,.314],[.85,.601,.274]]]),
  '13-gasherbrum-ii': makeRoute('加舒尔布鲁木Ⅱ峰', 'Gasherbrum II', '喀喇昆仑山脉', '南面 · 西南山脊',
    'Ⅱ峰与Ⅰ峰相邻，常用路线从南面接近西南山脊。走到较高处，路线资料会标出一段称为 Banana Ridge 的山脊。',
    'https://sevensummittreks.com/public/uploads/doc/gasherbrum-ii-fb-23-6396bd9d99a59.pdf#page=7',
    [['BC',5000,.28,.82],['C1',5900,.41,.74],['C2',6400,.49,.63],['C3',7400,.55,.38],['峰顶',8035,.577,.159]],
    [[[.5,.359,.771]],[[.56,.448,.684]],[[.35,.532,.568],[.71,.519,.477]],[[.43,.575,.30],[.72,.568,.218]]]),
  '14-shishapangma': makeRoute('希夏邦马峰', 'Shishapangma', '喜马拉雅山脉', '北坡 · 经中峰至主峰',
    '希夏邦马峰位于中国西藏。北侧线路资料区分中峰和主峰。本版参考设有三座高营的队伍方案，经过上部山脊后以主峰为终点。',
    'https://www.nepalhimalayanhiker.com/expeditions/shishapangma-expedition',
    [['BC',5000,.25,.82],['ABC',5640,.39,.75],['C1',6300,.47,.65],['C2',6900,.52,.53],['C3',7400,.60,.42],['峰顶',8027,.65,.221]],
    [[[.55,.335,.783]],[[.52,.429,.694]],[[.63,.506,.571]],[[.48,.557,.475]],[[.46,.612,.313],[.78,.628,.251]]])
};
const activePeak = () => peakPair[lang];
const activeRoute = () => routes[activePeak()];
function showArtStatus(){
  const state=art[activePeak()]?.state;
  $('imageStatus').textContent=state==='ok'?'背景已加载':state==='error'?'背景加载失败，已启用简图':'背景加载中';
}
function loadArt(){
  const key=activePeak();
  for(const cached of Object.keys(art)){
    if(cached!==peakPair.zh&&cached!==peakPair.en) delete art[cached];
  }
  if(!art[key]){
    const image=new Image(), entry={image,state:'loading'};
    art[key]=entry;
    image.onload=()=>{entry.state='ok';if(activePeak()===key) showArtStatus();};
    image.onerror=()=>{entry.state='error';if(activePeak()===key) showArtStatus();};
    image.src=artSources[key]||'../typing-peaks/'+key+'.webp';
  }
  showArtStatus();
}
function height(p){
  const camps=activeRoute().camps;
  const base=camps[0].m;
  return base+(camps.at(-1).m-base)*p;
}
function routePath(route){
  return route.camps.flatMap((camp,i)=>{
    const next=route.camps[i+1];
    const bends=next?route.bends[i].map(([ratio,x,y])=>({x,y,m:camp.m+(next.m-camp.m)*ratio})):[];
    return [camp,...bends];
  });
}
function positionAt(points, metres){
  const i=points.findIndex(point=>point.m>=metres);
  if(i<=0) return i===0?points[0]:points.at(-1);
  const a=points[i-1], b=points[i];
  const fraction=(metres-a.m)/(b.m-a.m);
  return {x:a.x+(b.x-a.x)*fraction,y:a.y+(b.y-a.y)*fraction,m:metres};
}

function paintTerrain(ctx){
  const english=lang==='en';
  if(art[activePeak()]?.state==='ok'){
    ctx.setTransform(1,0,0,1,0,0);
    ctx.drawImage(art[activePeak()].image,0,0,terrain.width,terrain.height);
    const shade=ctx.createLinearGradient(0,0,terrain.width*.52,0);
    shade.addColorStop(0,'#101d298a');
    shade.addColorStop(1,'#101d2900');
    ctx.fillStyle=shade;ctx.fillRect(0,0,terrain.width,terrain.height);
    return;
  }
  ctx.setTransform(terrain.width,0,0,terrain.height,0,0);
  const sky=ctx.createLinearGradient(0,0,0,1);
  sky.addColorStop(0,english?'#273b56':'#31574e');
  sky.addColorStop(.75,english?'#a19491':'#7d9d86');
  sky.addColorStop(1,english?'#30415c':'#213f35');
  ctx.fillStyle=sky;ctx.fillRect(0,0,1,1);
  const ridge = (points, color) => {
    ctx.beginPath();
    points.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));
    ctx.closePath();ctx.fillStyle=color;ctx.fill();
  };
  if(english){
    ridge([[0,.57],[.15,.44],[.24,.50],[.35,.32],[.43,.48],[.54,.53],[.71,.38],[.85,.41],[1,.55],[1,1],[0,1]],'#778097');
    ridge([[0,.84],[.15,.72],[.24,.62],[.33,.59],[.42,.41],[.46,.33],[.53,.13],[.58,.22],[.64,.38],[.67,.41],[.74,.54],[.82,.68],[.92,.74],[1,.67],[1,1],[0,1]],'#517087');
    ridge([[.53,.13],[.58,.22],[.64,.38],[.67,.41],[.74,.54],[.82,.68],[.92,.74],[.94,.85],[.78,.83],[.64,.72],[.58,.57],[.51,.41],[.55,.35],[.51,.25]],'#354863');
    ridge([[.53,.13],[.58,.22],[.64,.38],[.67,.41],[.65,.46],[.59,.39],[.56,.43],[.53,.34],[.49,.38],[.46,.33],[.42,.41],[.46,.30]],'#e3e7ec');
    ridge([[.53,.13],[.58,.22],[.64,.38],[.59,.31],[.55,.34],[.51,.25]],'#a8bbd0');
    ridge([[0,.79],[.13,.75],[.23,.81],[.35,.71],[.51,.79],[.64,.78],[.75,.84],[.89,.75],[1,.81],[1,1],[0,1]],'#384e68bb');
  }else{
  ridge([[0,.57],[.09,.48],[.17,.54],[.26,.38],[.36,.49],[.43,.41],[.5,.50],[.63,.44],[.77,.42],[.86,.30],[1,.54],[1,1],[0,1]],'#769283');
  ridge([[0,.76],[.15,.64],[.24,.69],[.33,.49],[.43,.55],[.5,.37],[.54,.39],[.64,.16],[.71,.28],[.75,.45],[.8,.39],[.88,.58],[.94,.55],[1,.65],[1,1],[0,1]],'#496e60');
  ridge([[.64,.16],[.71,.28],[.75,.45],[.8,.39],[.88,.58],[.94,.55],[1,.65],[1,1],[.45,1],[.56,.77],[.59,.55],[.57,.41],[.66,.32]],'#294b41');
  ridge([[.64,.16],[.71,.28],[.75,.45],[.80,.39],[.83,.46],[.76,.46],[.71,.39],[.69,.41],[.67,.31],[.64,.34],[.61,.31],[.57,.42],[.50,.45],[.54,.39]],'#d6ded0');
  ridge([[.64,.16],[.71,.28],[.75,.45],[.70,.36],[.67,.36],[.66,.32]],'#94ad9c');
  ridge([[0,.85],[.16,.75],[.26,.78],[.38,.70],[.46,.71],[.61,.63],[.70,.70],[.85,.62],[1,.71],[1,1],[0,1]],'#315447bb');
  }
  for(let i=0;i<14;i++){
    ctx.beginPath();
    const y=.42+i*.038;
    ctx.moveTo(0,y+.12);ctx.bezierCurveTo(.28,y+.2,.38,y-.14,.58,y-.024);ctx.bezierCurveTo(.75,y+.12,.85,y-.10,1,y+.02);
    ctx.strokeStyle='#dcebd42b';ctx.lineWidth=.002;ctx.stroke();
  }
}
function drawRoute(w,h,progress,animationTime){
  const route=activeRoute(), points=routePath(route);
  const compact=w<660;
  const xy=point=>[point.x*w,point.y*h];
  ctx.beginPath();
  points.forEach((point,i)=>{
    const [x,y]=xy(point);
    if(i) ctx.lineTo(x,y);
    else ctx.moveTo(x,y);
  });
  ctx.lineJoin='round';ctx.lineCap='round';
  ctx.strokeStyle='#18262cbb';ctx.lineWidth=3.4;ctx.stroke();
  ctx.strokeStyle='#ff635d';ctx.lineWidth=1.65;ctx.stroke();

  const metres=height(progress);
  ctx.textBaseline='middle';ctx.textAlign='left';
  ctx.font=(compact?'600 10px':'600 12px')+' system-ui';
  route.camps.forEach(camp=>{
    const [x,y]=xy(camp), reached=metres>=camp.m-0.001;
    ctx.beginPath();ctx.arc(x,y,compact?2.6:3.3,0,Math.PI*2);
    ctx.fillStyle=reached?'#ffe29b':'#192a31';ctx.fill();
    ctx.strokeStyle=reached?'#ffe6ad':'#ff9a93';ctx.lineWidth=1.2;ctx.stroke();
    const label=camp.label;
    const labelWidth=ctx.measureText(label).width;
    const offset=compact?6:8;
    const labelX=clamp(camp.side<0?x-labelWidth-offset:x+offset,4,w-labelWidth-4);
    ctx.lineWidth=3;ctx.strokeStyle='#142127e8';
    ctx.strokeText(label,labelX,y);ctx.fillStyle=reached?'#ffe6ad':'#ffffff';ctx.fillText(label,labelX,y);
  });
  const [x,y]=xy(positionAt(points,metres));
  const pulse=animationTime?(1+Math.sin(animationTime/220))/2:0;
  ctx.beginPath();ctx.arc(x,y,7+pulse*3,0,Math.PI*2);ctx.fillStyle='#d1f38c50';ctx.fill();
  ctx.beginPath();ctx.arc(x,y,4.2,0,Math.PI*2);ctx.fillStyle='#d9fc99';ctx.fill();
  ctx.strokeStyle='#1a352c';ctx.lineWidth=1.4;ctx.stroke();
}
function draw(amount, t){
  const {width:w,height:h}=canvas.getBoundingClientRect();
  const dpr=Math.min(1.5,devicePixelRatio||1);
  if(!w||!h) return;
  const key=[activePeak(),w,h,dpr,art[activePeak()]?.state].join(':');
  const animated=!reduced.matches&&!$('lowMotion').checked&&mode==='typing';
  const frameKey=[key,amount,animated,summitAt!==null].join(':');
  if(!animated&&frameKey===lastMapFrame) return;
  lastMapFrame=frameKey;
  if(key!==terrainKey){
    terrainKey=key;
    canvas.width=terrain.width=Math.round(w*dpr);
    canvas.height=terrain.height=Math.round(h*dpr);
    paintTerrain(terrainCtx);
  }
  ctx.setTransform(1,0,0,1,0,0);
  ctx.drawImage(terrain,0,0);
  ctx.setTransform(dpr,0,0,dpr,0,0);
  drawRoute(w,h,amount,animated?t:0);
  drawCount++;
}

function openPeakInfo(){
  const route=activeRoute();
  $('peakInfoTitle').textContent=route.peak;
  $('peakInfoEnglish').textContent=route.english;
  $('peakInfoDescription').textContent=route.description;
  $('peakInfoRegion').textContent=route.region;
  $('peakInfoHeight').textContent=fmt(route.camps.at(-1).m)+' 米';
  $('peakInfoRoute').textContent=route.name;
  $('peakInfoCamps').textContent=route.camps.map(camp=>camp.label==='BC'?'BC 大本营':camp.label==='ABC'?'ABC 前进营地':camp.label).join(' → ');
  $('peakInfoSource').href=route.source;
  $('peakDialog').showModal();
}

const pending = new Map();
let rpcId = 0;
function rpc(action, data = {}) {
  const id = ++rpcId;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      pending.delete(id);
      reject(new Error('暂时无法连接，请重试。'));
    }, 8000);
    pending.set(id, { resolve, reject, timer });
    parent.postMessage({ channel:'typing-workspace', id, action, data }, location.origin);
  });
}
window.addEventListener('message', event => {
  if (event.origin !== location.origin || event.source !== parent || event.data?.channel !== 'typing-response') return;
  const reply = pending.get(event.data.id);
  if (!reply) return;
  clearTimeout(reply.timer);
  pending.delete(event.data.id);
  if (event.data.error) reply.reject(new Error(event.data.error));
  else reply.resolve(event.data.value);
});

const gradeLabels = {3:'三',4:'四',5:'五',6:'六',7:'七',8:'八'};
const unit = () => lang === 'en' ? 'WPM' : '字/分钟';
const languageName = () => lang === 'zh' ? '中文' : '英文';
let activity, attempt, result, deadline, syncDue = 0, busy = false, starting = false;
let controlling = false;
let sequenceNumber = 0, segments = [], goals = [];
let rendered = -1, correct = 0, firstCorrect = 0, firstCount = 0, announced = false;
const notice = text => { $('connection').textContent = text; };
const currentIndex = () => segments.length - 1;
const goalAt = index => goals[index % goals.length];
const setup = () => activity?.languages[lang];
const fraction = () => result ? result.progress : attempt ? clamp(correct / (Number(attempt.target)*5), 0, 1) : 0;
const isHan = character => /\p{Unified_Ideograph}|〇/u.test(character);

function countInput() {
  correct = 0;
  firstCorrect = 0;
  firstCount = 0;
  segments.forEach((segment, index) => {
    const expected = goalAt(index).chars;
    [...segment.text].forEach((character, position) => {
      if (character === expected[position] && (lang === 'en' || isHan(character))) correct++;
    });
    [...segment.first].forEach((character, position) => {
      if (character === expected[position]) firstCorrect++;
      firstCount++;
    });
  });
  if (lang === 'en') correct /= 5;
}

function renderRank(entries) {
  const list = $('rows'), scroll = list.scrollTop;
  list.replaceChildren();
  $('pinned').replaceChildren();
  for (const item of entries) {
    const row = document.createElement('div');
    row.className = item.self ? 'row self' : 'row';
    const n = Object.assign(document.createElement('span'), {className:'rank',textContent:item.rank});
    const name = Object.assign(document.createElement('div'), {textContent:item.self ? '我 · '+item.label : item.label});
    const bar = Object.assign(document.createElement('div'), {className:'bar'});
    const fill = document.createElement('i');
    fill.style.width = item.progress * 100 + '%';
    bar.append(fill);
    name.append(bar);
    row.append(n, name, Object.assign(document.createElement('span'), {className:'alt',textContent:fmt(item.altitude)+' m'}));
    list.append(row);
    if (item.self) $('pinned').append(row.cloneNode(true));
  }
  if (!entries.length) list.append(Object.assign(document.createElement('div'), {
    className:'boardfoot',textContent:'本组暂无练习记录。',
  }));
  list.scrollTop = scroll;
}

function routeHeader() {
  $('zh').setAttribute('aria-pressed', lang === 'zh');
  $('en').setAttribute('aria-pressed', lang === 'en');
  $('zh').disabled = Boolean(attempt);
  $('en').disabled = Boolean(attempt);
  $('zone').textContent = activeRoute().name;
  $('peak').textContent = activeRoute().peak;
  $('peakInfo').setAttribute('aria-label', activeRoute().peak+'介绍');
  $('unit').textContent = unit();
  $('headerScope').textContent = activity ? gradeLabels[activity.grade]+'年级 '+activity.class_num+' 班' : '';
  $('rankscope').textContent = [$('headerScope').textContent,languageName()].filter(Boolean).join(' · ');
  canvas.setAttribute('aria-label', activeRoute().name+'，'+activeRoute().camps.map(camp=>camp.label).join(' → '));
  loadArt();
}

function showLobby() {
  mode = 'idle';
  $('desk').dataset.paused = false;
  $('pause').disabled = true;
  $('pause').textContent = '暂停';
  attempt = result = null;
  summitAt = null;
  seconds = shown = correct = firstCorrect = firstCount = 0;
  rendered = -1;
  announced = false;
  $('reviewResult').hidden = true;
  $('answer').disabled = true;
  $('answer').value = '';
  $('articleTitle').textContent = languageName()+'练习';
  $('passage').replaceChildren(Object.assign(document.createElement('p'), {
    textContent: activity ? '点击「开始打字」后，文章和输入会逐字对齐显示在这里。' : '本年级暂无可用练习文章，请联系老师。',
  }));
  $('pinyin').textContent = setup()?.pinyin ? '点击原文中的汉字查看拼音。' : '';
  $('tip').textContent = '上行是原文，下行显示你的输入。';
  const select = $('articleSelect');
  select.replaceChildren(...(setup()?.articles || []).map(article => new Option(article.title, article.id)));
  $('articlePicker').hidden = setup()?.mode !== 'free';
  $('start').disabled = !activity || (setup()?.mode === 'free' && !select.options.length);
  $('start').textContent = '开始打字 · 5 分钟';
  routeHeader();
  renderRank([]);
  syncDue = 0;
}

function positionInput(follow = false) {
  const p = $('passage');
  const current = p.querySelector('.pair.current .typed');
  if (!current || mode !== 'typing') return;
  const rect=current.getBoundingClientRect(), box=p.getBoundingClientRect();
  if (follow && rect.bottom>box.bottom-5) p.scrollTop+=rect.bottom-box.bottom+14;
  if (follow && rect.top<box.top) p.scrollTop-=box.top-rect.top+6;
  const caret=current.getBoundingClientRect(), desk=$('desk').getBoundingClientRect();
  $('answer').style.left=clamp(caret.left-desk.left,5,desk.width-5)+'px';
  $('answer').style.top=clamp(caret.top-desk.top,5,desk.height-24)+'px';
}

function passage() {
  const index = currentIndex();
  const article = goalAt(index);
  const p = $('passage');
  const value = [...input];
  if (rendered !== index) {
    rendered = index;
    $('articleTitle').textContent = article.title;
    $('pinyin').textContent = article.pinyin ? '点击原文中的汉字查看拼音。' : '';
    p.className = lang === 'en' ? 'english' : '';
    p.replaceChildren();
    chars = [];
    let group = null;
    for (const [i,c] of article.chars.entries()) {
      const pronunciation = article.pinyin?.[i];
      const glyph = document.createElement(pronunciation ? 'button' : 'span');
      glyph.className = 'ref';
      glyph.textContent = c;
      if (pronunciation) {
        glyph.type = 'button';
        glyph.onmousedown = event => event.preventDefault();
        glyph.onclick = () => {
          $('pinyin').replaceChildren(c+'　',Object.assign(document.createElement('b'),{textContent:pronunciation}));
          focusInput();
        };
      }
      const pair = Object.assign(document.createElement('span'), {className:'pair'});
      const typed = Object.assign(document.createElement('span'), {className:'typed'});
      typed.setAttribute('aria-hidden','true');
      pair.append(glyph,typed);
      if (lang==='en' && c!==' ') {
        if (!group) { group=Object.assign(document.createElement('span'),{className:'word'});p.append(group); }
        group.append(pair);
      } else {
        group=null;
        p.append(pair);
      }
      chars.push({pair,typed});
    }
    p.scrollTop = 0;
  }
  chars.forEach(({pair,typed},i) => {
    pair.className='pair'+(i<value.length ? (value[i]===article.chars[i] ? ' ok' : ' bad') : i===value.length ? ' current' : '');
    typed.textContent=value[i]??' ';
  });
  positionInput(true);
}

function focusInput() {
  if (mode !== 'typing') return;
  const answer = $('answer');
  window.focus();
  answer.focus({preventScroll:true});
}

function updateControls() {
  const paused = mode === 'paused';
  $('desk').dataset.paused = paused;
  $('pause').disabled = controlling || (mode !== 'typing' && !paused);
  $('pause').textContent = paused ? '继续练习' : '暂停';
  $('start').disabled = controlling || paused || mode === 'finishing';
  $('start').textContent = mode === 'done' ? '返回训练' : mode === 'typing' ? '点此输入' : paused ? '训练已暂停' : '结算中';
}

function openAttempt(record, focus) {
  attempt = record;
  activity = record.activity;
  lang = record.language;
  for (const language of ['zh','en']) peakPair[language] = activity.languages[language].peak.id;
  goals = record.articles.map(article => ({
    ...article, chars:[...article.paragraphs.join(lang === 'en' ? ' ' : '')],
  }));
  segments = record.checkpoint.length ? record.checkpoint : [{text:'', first:''}];
  sequenceNumber = record.checkpoint_seq;
  const current = segments.at(-1);
  if ([...current.text].length === goalAt(currentIndex()).chars.length && !record.result) segments.push({text:'',first:''});
  input = segments.at(-1).text;
  deadline = performance.now() + record.remaining_ms;
  seconds = clamp(300 - record.remaining_ms / 1000, 0, 300);
  result = record.result;
  summitAt = record.summit_seconds;
  mode = result ? 'done' : record.paused ? 'paused' : record.expired ? 'finishing' : 'typing';
  composing = false;
  syncDue = 0;
  shown = 0;
  rendered = -1;
  updateControls();
  $('articlePicker').hidden = true;
  $('answer').disabled = mode !== 'typing';
  $('answer').value = input;
  $('tip').textContent = mode === 'paused'
    ? '练习已暂停，点击「继续练习」回到原位置。'
    : '点一下打字区或「点此输入」，对照上行原文输入。红色标出错字，按退格修改。';
  routeHeader();
  countInput();
  passage();
  if (focus) {
    $('answer').setSelectionRange(input.length, input.length);
    focusInput();
  }
}

function acceptInput() {
  if (mode !== 'typing' || controlling || composing || performance.now() >= deadline) return;
  const started = performance.now();
  const goal = goalAt(currentIndex());
  const segment = segments.at(-1);
  let value = [...$('answer').value.replace(/[\r\n]/g,' ')].slice(0, goal.chars.length);
  input = value.join('');
  if ($('answer').value !== input) $('answer').value = input;
  const first = [...segment.first];
  for (let index = first.length; index < value.length; index++) first[index] = value[index];
  segment.first = first.join('');
  segment.text = input;
  if (value.length === goal.chars.length && segments.length < 200) {
    segments.push({text:'', first:''});
    $('answer').value = input = '';
  }
  countInput();
  passage();
  requestAnimationFrame(()=>{$('latency').textContent=Math.round(performance.now()-started);});
}

function showResult() {
  $('resultTitle').textContent = result.summit ? '成功登顶' : '本次攀登结束';
  $('resultElevation').textContent = fmt(result.altitude)+' m';
  $('resultClimb').textContent = activeRoute().peak+' · '+(result.summit ? '登顶用时 '+clock(result.summit_seconds ?? 300) : '完成路线 '+(result.progress*100).toFixed(1)+'%');
  $('score').textContent = result.score+' 分';
  $('points').textContent = result.points;
  $('resultSpeed').textContent = Number(result.speed).toFixed(1)+' '+unit();
  $('resultAccuracy').textContent = result.accuracy+'%';
  $('resultnote').textContent = '五分钟打字练习';
  if ($('peakDialog').open) $('peakDialog').close();
  if (!$('result').open) $('result').showModal();
}

async function setPaused() {
  if (controlling || (mode !== 'typing' && mode !== 'paused')) return;
  const paused = mode === 'paused';
  controlling = true;
  updateControls();
  $('answer').disabled = true;
  try {
    const record = await rpc(paused ? 'resume' : 'pause', {
      attempt: attempt.id,
      ...(paused ? {} : { seq: ++sequenceNumber, segments }),
    });
    openAttempt(record, paused);
    notice('');
  } catch (error) {
    $('answer').disabled = mode !== 'typing';
    focusInput();
    notice(error.message);
  } finally {
    controlling = false;
    updateControls();
  }
}

async function sync() {
  if (busy || controlling || !activity) return;
  busy = true;
  const syncedAttempt = attempt;
  const syncedLang = lang;
  try {
    if (syncedAttempt && (mode === 'typing' || mode === 'finishing')) {
      const reply = await rpc('sync', { attempt: syncedAttempt.id, seq: ++sequenceNumber, segments });
      renderRank(reply.board);
      if (reply.summit_seconds !== null) summitAt = reply.summit_seconds;
      if (reply.result) {
        result = reply.result;
        mode = 'done';
        updateControls();
        $('answer').disabled = true;
      }
    } else {
      const entries = await rpc('board',{ activity:activity.id, language:lang });
      if (syncedAttempt === attempt && syncedLang === lang) renderRank(entries);
    }
    notice(mode === 'finishing' ? '正在等待结算…' : '');
  } catch (error) {
    notice(error.message + ' 将自动重试。');
  } finally { busy=false; }
}

function update(t) {
  requestAnimationFrame(update);
  if (t-lastDraw<30) return;
  lastDraw=t;
  if (mode==='typing' || mode==='finishing') seconds=clamp(300-(deadline-t)/1000,0,300);
  if (mode==='typing' && t>=deadline) {
    mode='finishing';
    $('answer').disabled=true;
    updateControls();
    syncDue=0;
  }
  const p=fraction();
  $('summit').hidden=summitAt===null || p<1;
  if (!$('summit').hidden) $('summit').textContent='已登顶 · '+clock(summitAt);
  $('timer').textContent=clock(Math.ceil(300-seconds));
  $('progress').textContent=(p*100).toFixed(1)+'%';
  $('speed').textContent=result ? Number(result.speed).toFixed(1) : seconds>0?(correct/(Math.max(1,seconds)/60)).toFixed(1):'—';
  $('accuracy').textContent=result ? result.accuracy+'%' : firstCount?Math.round(100*firstCorrect/firstCount)+'%':'—';
  if (t>=syncDue && !busy) {
    syncDue=t+2000;
    sync();
  }
  if (result) {
    $('reviewResult').hidden=false;
    if (!announced) {
      announced=true;
      showResult();
    }
  }
  shown=reduced.matches||$('lowMotion').checked?p:shown+(p-shown)*.15;
  if (Math.abs(shown-p)<.0002) shown=p;
  draw(shown,t);
  if(t-meterStart>=1000){
    $('fps').textContent=mode==='typing'?Math.round(drawCount*1000/(t-meterStart)):'—';
    drawCount=0;meterStart=t;
  }
}

async function load() {
  try {
    const data = await rpc('load');
    if (data.attempt) openAttempt(data.attempt, true);
    else {
      activity = data.activity;
      if (activity) for (const language of ['zh','en']) peakPair[language] = activity.languages[language].peak.id;
      showLobby();
    }
  } catch(error) {notice(error.message);}
}
for(const language of ['zh','en']) $(language).onclick=()=>{
  if (attempt || starting || language===lang) return;
  lang=language;
  showLobby();
};
$('pause').onclick = setPaused;
$('start').onclick=async()=>{
  if (mode === 'typing') {
    focusInput();
    return;
  }
  if (starting || controlling) return;
  starting=true;
  $('start').disabled=true;
  try {
    if (mode==='done') {
      await rpc('clear');
      await load();
      return;
    }
    if (!activity) return;
    $('start').textContent = '正在开始…';
    const selected = $('articleSelect').value;
    const record = await rpc('start',{
      activity_id:activity.id, language:lang,
      ...(setup().mode==='free' && selected ? {article_id:Number(selected)} : {}),
    });
    openAttempt(record,true);
  } catch(error) {
    await load();
    notice(error.message);
  } finally {starting=false;}
};
$('peakInfo').onclick=openPeakInfo;
$('peakDialog').onclose=focusInput;
$('reviewResult').onclick=showResult;
$('desk').onpointerdown=event=>{
  if (mode==='typing' && event.pointerType === 'mouse' && !event.target.closest('button')) {
    event.preventDefault();
    focusInput();
  }
};
$('desk').onclick=focusInput;
$('passage').onscroll=()=>positionInput();
window.onresize=()=>positionInput();
$('answer').addEventListener('compositionstart', () => { composing=true; });
$('answer').addEventListener('compositionend', () => { composing=false; acceptInput(); });
$('answer').oninput=event=>{if(!event.isComposing)acceptInput();};
$('answer').onpaste=event=>{event.preventDefault();$('tip').textContent='请用键盘输入，粘贴内容不计入练习。';};
$('answer').ondrop=event=>event.preventDefault();
$('answer').onkeydown=event=>{if(event.key==='Enter'&&!composing&&!event.isComposing&&event.keyCode!==229)event.preventDefault();};
showLobby();
load();
requestAnimationFrame(update);
