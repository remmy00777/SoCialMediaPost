const api = '/api';
const pages = [
  ['Core','dashboard','◫','Dashboard'],['Core','onboarding','◎','Onboarding'],['Core','accounts','⌁','Connected Accounts'],
  ['Intelligence','trends','↗','Trend Explorer'],['Intelligence','creator-discovery','★','Top Creator Discovery'],['Intelligence','creator-watch','◌','Creator Watchlist'],['Intelligence','trend-detail','◉','Trend Detail'],['Intelligence','concepts','✦','Content Concepts'],
  ['Production','studio','▣','Content Studio'],['Production','preview','▶','Video Preview'],['Production','review','✓','Review & Approval'],['Production','ready','⇩','Ready to Post'],
  ['Publishing','calendar','◷','Publishing Calendar'],['Publishing','published','●','Published Content'],
  ['Learning','analytics','⌁','Analytics'],['Learning','comparison','⇄','Cross-platform'],['Learning','experiments','⚗','Experiments'],
  ['Configuration','brand','B','Brand Profile'],['Configuration','rules','⚑','Content Rules'],['Configuration','schedules','◴','Schedules'],['Configuration','providers','⚙','Providers'],
  ['Operations','health','♥','API Health'],['Operations','jobs','≡','Job History'],['Operations','logs','⌘','Logs'],['Operations','notifications','♢','Notifications'],['Operations','security','◇','Security'],['Operations','backup','↺','Backup & Restore'],['Operations','settings','⚙','Settings']
];
let state = {page:'dashboard', overview:null, trends:[], packages:[]};
const q = s => document.querySelector(s);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function cookie(name){return document.cookie.split('; ').find(v=>v.startsWith(name+'='))?.split('=').slice(1).join('=') || ''}
async function request(path, options={}){
  const method = options.method || 'GET';
  const headers = {'Content-Type':'application/json', ...(options.headers||{})};
  if(!['GET','HEAD','OPTIONS'].includes(method)) headers['X-CSRF-Token']=decodeURIComponent(cookie('smp_csrf'));
  const response = await fetch(api+path,{credentials:'same-origin',...options,method,headers});
  const payload = response.headers.get('content-type')?.includes('json') ? await response.json() : await response.text();
  if(!response.ok) throw new Error(payload.detail || payload || `Request failed: ${response.status}`);
  return payload;
}
async function uploadRequest(path, formData){
  const response=await fetch(api+path,{method:'POST',credentials:'same-origin',headers:{'X-CSRF-Token':decodeURIComponent(cookie('smp_csrf'))},body:formData});
  const payload=response.headers.get('content-type')?.includes('json')?await response.json():await response.text();
  if(!response.ok)throw new Error(payload.detail||payload||`Request failed: ${response.status}`);
  return payload;
}
function notify(message,error=false){const el=q('#notice');el.textContent=message;el.classList.remove('hidden');el.style.borderColor=error?'rgba(255,107,122,.45)':'rgba(140,123,255,.35)';setTimeout(()=>el.classList.add('hidden'),6000)}
function fmtBytes(bytes=0){const units=['B','KB','MB','GB','TB'];let i=0,n=Number(bytes||0);while(n>=1024&&i<units.length-1){n/=1024;i++}return `${n.toFixed(i?1:0)} ${units[i]}`}
function fmtNumber(value){const number=Number(value||0);return new Intl.NumberFormat('en-US',{notation:number>=1000000?'compact':'standard',maximumFractionDigits:1}).format(number)}
function nav(){let last='';q('#nav').innerHTML=pages.map(([group,id,icon,label])=>{const head=group!==last?`<div class="nav-group">${esc(group)}</div>`:'';last=group;return head+`<a class="nav-link ${state.page===id?'active':''}" href="#${id}" data-page="${id}"><span class="nav-icon">${icon}</span><span>${esc(label)}</span></a>`}).join('');q('#nav').onclick=e=>{const a=e.target.closest('[data-page]');if(a){e.preventDefault();location.hash=a.dataset.page}}}
function setTitle(title,kicker='OPERATIONS'){q('#section-title').textContent=title;q('#section-kicker').textContent=kicker}
function card(title,body,klass=''){return `<article class="card ${klass}"><h2>${esc(title)}</h2>${body}</article>`}
function json(value){return `<pre class="json">${esc(JSON.stringify(value,null,2))}</pre>`}
function table(rows,cols){if(!rows?.length)return '<div class="empty">No records yet.</div>';return `<div class="table-wrap"><table><thead><tr>${cols.map(c=>`<th>${esc(c[0])}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${cols.map(c=>`<td>${typeof c[1]==='function'?c[1](r):esc(r[c[1]])}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`}
async function loadCommon(){state.overview=await request('/system/overview');q('#status-pill').textContent=state.overview.system_status;q('#status-pill').className='status '+(state.overview.system_status==='operational'?'good':'paused');q('#pause-toggle').textContent=state.overview.system_status==='paused'?'Resume Automation':'Pause All Automation'}
function hero(text,actions=''){return `<div class="hero"><div><p>${esc(text)}</p></div><div class="action-row">${actions}</div></div>`}
async function dashboard(){setTitle('Dashboard','SYSTEM OVERVIEW');await loadCommon();const o=state.overview;const latest=o.latest_trends||[];q('#content').innerHTML=hero('A single view of discovery, production, publishing controls, analytics, and system health.',`<button data-act="demo">Run Demo Workflow</button><button class="secondary" data-act="trends">Discover Trends</button>`)+`<div class="grid">${card('System Status',`<div class="metric">${esc(o.system_status)}</div><p class="muted">Internet: ${esc(o.internet_status)} · Scheduler: ${esc(o.scheduler_status)}</p>`)}${card('Pending Approval',`<div class="metric">${o.pending_approvals}</div><p class="muted">Packages requiring review or export.</p>`)}${card('Storage Used',`<div class="metric">${fmtBytes(o.storage_usage?.used_bytes)}</div><p class="muted">${esc(o.storage_usage?.file_count||0)} files under managed storage.</p>`)}${card('Latest Trends',latest.length?`<div class="list">${latest.map(t=>`<div class="list-item"><div><strong>${esc(t.title)}</strong><small>${esc(t.platform)}</small></div><span class="tag">${Number(t.score).toFixed(1)}</span></div>`).join('')}</div>`:'<div class="empty">Run discovery to populate trends.</div>','wide')}${card('Workflow',o.last_successful_workflow?json(o.last_successful_workflow):'<div class="empty">No workflow has run.</div>')}${card('Guardrails',`<div class="list"><div class="list-item"><span>Demo mode</span><strong>${o.demo_mode?'ON':'OFF'}</strong></div><div class="list-item"><span>Automatic publishing</span><strong>${o.auto_publish_enabled?'ON':'OFF'}</strong></div><div class="list-item"><span>Publishing failures</span><strong>${o.publishing_failures}</strong></div></div>`)}</div>`;bindActions()}
async function onboarding(){setTitle('Onboarding','SETUP');const brand=await request('/brand-profile');q('#content').innerHTML=hero('Define the brand, target audience, languages, topics, and approval posture before content is generated.')+card('Brand Profile',`<form id="brand-form" class="form-grid"><div class="field"><label>Brand name</label><input name="name" value="${esc(brand.name||'')}" required></div><div class="field"><label>Niche</label><input name="niche" value="${esc(brand.niche||'')}"></div><div class="field full"><label>Target audience</label><textarea name="target_audience">${esc(brand.target_audience||'')}</textarea></div><div class="field"><label>Brand voice</label><input name="brand_voice" value="${esc(brand.brand_voice||'clear, expert, human')}"></div><div class="field"><label>Preferred duration, seconds</label><input type="number" min="5" max="3600" name="preferred_duration_seconds" value="${esc(brand.preferred_duration_seconds||30)}"></div><div class="field"><label>Countries, comma separated</label><input name="countries" value="${esc((brand.countries||['US']).join(','))}"></div><div class="field"><label>Languages, comma separated</label><input name="languages" value="${esc((brand.languages||['en']).join(','))}"></div><div class="field full"><button type="submit">Save and approve brand profile</button></div></form>`,'full');q('#brand-form').onsubmit=saveBrand}
async function saveBrand(e){e.preventDefault();const d=new FormData(e.target);const payload={name:d.get('name'),niche:d.get('niche'),target_audience:d.get('target_audience'),brand_voice:d.get('brand_voice'),countries:String(d.get('countries')).split(',').map(v=>v.trim()).filter(Boolean),languages:String(d.get('languages')).split(',').map(v=>v.trim()).filter(Boolean),topics_include:[],topics_exclude:[],approval_mode:'manual_export',preferred_duration_seconds:Number(d.get('preferred_duration_seconds')),preferred_voice:'local',approved:true};await request('/brand-profile',{method:'PUT',body:JSON.stringify(payload)});notify('Brand profile saved and approved.')}
function connectedAccountName(account, platform){
  const instagram = account.raw_profile?.instagram_business_account || {};
  const current = String(account.display_name || '').trim();

  if(platform === 'instagram' && instagram.username){
    return `@${String(instagram.username).replace(/^@/, '')}`;
  }

  if(current && current.toLowerCase() !== platform){
    return current;
  }

  return account.external_account_id || `${platform} account`;
}

async function accounts(){
  setTitle('Connected Accounts','PLATFORM ACCESS');
  const rows = await request('/accounts');

  const cards = ['youtube','tiktok','instagram'].map(platform => {
    const record = rows.find(item => item.platform === platform);
    const accounts = record?.accounts || [];
    const connectedAccounts = accounts.filter(
      account => account.authorization_status === 'connected'
    );
    const connected = connectedAccounts.length > 0;
    const label = platform[0].toUpperCase() + platform.slice(1);

    const statusBar = connected
      ? `<div class="account-status-bar connected">
           <span class="account-status-dot"></span>
           <span>Connected</span>
         </div>`
      : '';

    const accountList = connected
      ? `<div class="list">
          ${connectedAccounts.map(account => `
            <div class="list-item">
              <div class="account-summary">
                <strong>${esc(connectedAccountName(account, platform))}</strong>
                <small>
                  ${esc(account.account_type || 'Professional account')}
                  · ${esc(account.token_health || 'unknown')}
                </small>
              </div>
              <div class="action-row">
                <button
                  class="secondary"
                  data-test-account="${esc(account.id)}"
                >Test</button>
                <button
                  class="danger"
                  data-disconnect-account="${esc(account.id)}"
                >Disconnect</button>
              </div>
            </div>
          `).join('')}
        </div>`
      : `<p class="muted">
           Not connected. Configure client credentials before authorization.
         </p>`;

    const connectButton = connected
      ? `<button class="secondary" data-connect="${platform}">
           Connect another ${label} account
         </button>`
      : `<button data-connect="${platform}">
           Connect ${label}
         </button>`;

    const body = `
      ${statusBar}
      ${accountList}
      <div class="action-row account-card-actions">
        ${connectButton}
      </div>
      <details class="integration-health">
        <summary>Integration health</summary>
        ${json(record?.health || {})}
      </details>
    `;

    return card(label, body);
  }).join('');

  q('#content').innerHTML =
    hero(
      'Connect multiple accounts under one application login. OAuth credentials are encrypted, and platform passwords are never stored.'
    ) +
    `<div class="grid">${cards}</div>`;

  document.querySelectorAll('[data-connect]').forEach(button => {
    button.onclick = async () => {
      button.disabled = true;
      try {
        const result = await request(
          `/accounts/${button.dataset.connect}/connect`,
          {method: 'POST'}
        );

        if(result.authorization_url){
          location.href = result.authorization_url;
        } else {
          notify(JSON.stringify(result));
        }
      } catch(error) {
        notify(error.message, true);
        button.disabled = false;
      }
    };
  });

  document.querySelectorAll('[data-test-account]').forEach(button => {
    button.onclick = async () => {
      try {
        const result = await request(
          `/platform-accounts/${button.dataset.testAccount}/test`,
          {method: 'POST'}
        );
        notify('Account connection verified successfully.');
        console.log(result);
        await accounts();
      } catch(error) {
        notify(error.message, true);
      }
    };
  });

  document.querySelectorAll('[data-disconnect-account]').forEach(button => {
    button.onclick = async () => {
      if(!confirm('Disconnect this social-media account?')){
        return;
      }

      try {
        await request(
          `/platform-accounts/${button.dataset.disconnectAccount}/disconnect`,
          {method: 'POST'}
        );
        notify('Account disconnected.');
        await accounts();
      } catch(error) {
        notify(error.message, true);
      }
    };
  });
}

async function waitForCreatorDiscovery(runId){
  for(let attempt=0;attempt<180;attempt++){
    const run=await request(`/creator-discovery/runs/${runId}`);
    if(['succeeded','failed'].includes(run.status)) return run;
    await new Promise(resolve=>setTimeout(resolve,5000));
  }
  throw new Error('Creator discovery is still running. Refresh this page in a few minutes.');
}

async function creatorDiscovery(){
  setTitle('Top Creator Discovery','YOUTUBE AND INSTAGRAM');
  const [rows,brand]=await Promise.all([
    request('/creator-discovery/results?limit=200'),
    request('/brand-profile')
  ]);
  const defaultQuery=brand.niche||'technology';
  const form=`
    <form id="creator-discovery-form" class="form-grid">
      <div class="field">
        <label>Platforms</label>
        <select name="platform">
          <option value="both">YouTube and Instagram</option>
          <option value="youtube">YouTube only</option>
          <option value="instagram">Instagram only</option>
        </select>
      </div>
      <div class="field">
        <label>Top creators per platform</label>
        <input type="number" name="top_n" min="1" max="100" value="100">
      </div>
      <div class="field full">
        <label>Niche or YouTube search query</label>
        <input name="query" value="${esc(defaultQuery)}" required>
      </div>
      <div class="field full">
        <label>Instagram hashtags, comma separated</label>
        <input name="hashtags" value="viral,reels,trending,explorepage">
        <small class="muted">Instagram discovery uses permitted hashtag media to find Professional creators, then enriches them through Business Discovery.</small>
      </div>
      <div class="field full">
        <label>Optional Instagram Professional usernames, comma separated</label>
        <textarea name="instagram_usernames" placeholder="creatorone, creatortwo"></textarea>
      </div>
      <div class="field">
        <label>Recent posts per creator</label>
        <input type="number" name="recent_posts_per_creator" min="1" max="10" value="10">
      </div>
      <div class="field">
        <label><input type="checkbox" name="import_latest_as_trends" checked> Prepare each creator's latest post for analysis</label>
      </div>
      <div class="field full">
        <button type="submit">Search and rank top creators</button>
      </div>
    </form>`;

  q('#content').innerHTML=
    hero('Search official platform metadata, rank up to 100 creators per platform, extract each latest public content link, and create analysis candidates. Full platform video files are not downloaded; editing the complete clip still requires authorized source media.')+
    card('Discovery Configuration',form,'full')+
    card('Ranked Creator Results',table(rows,[
      ['Rank',row=>`#${esc(row.rank||'–')}`],
      ['Platform','platform'],
      ['Creator',row=>`<strong>${esc(row.name||row.username||'Unknown')}</strong><br><small class="muted">${esc(row.username?`@${row.username}`:row.external_creator_id)}</small>`],
      ['Followers',row=>fmtNumber(row.follower_count)],
      ['Score',row=>`<span class="tag">${Number(row.creator_score||0).toFixed(1)}</span>`],
      ['Recent median views',row=>row.platform==='instagram'?'Not exposed':fmtNumber(row.recent_median_views)],
      ['Latest content',row=>row.latest_content?.canonical_url?`<a href="${esc(row.latest_content.canonical_url)}" target="_blank" rel="noopener">Open latest</a>`:'Unavailable'],
      ['Action',row=>`<button class="secondary" data-prepare-creator="${esc(row.id)}">Analyze and edit</button>`]
    ]),'full');

  q('#creator-discovery-form').onsubmit=async event=>{
    event.preventDefault();
    const data=new FormData(event.target);
    const split=name=>String(data.get(name)||'').split(',').map(value=>value.trim().replace(/^[@#]/,'')).filter(Boolean);
    const payload={
      platform:data.get('platform'),
      query:String(data.get('query')||'').trim()||null,
      hashtags:split('hashtags'),
      instagram_usernames:split('instagram_usernames'),
      top_n:Number(data.get('top_n')||100),
      recent_posts_per_creator:Number(data.get('recent_posts_per_creator')||10),
      import_latest_as_trends:data.get('import_latest_as_trends')==='on'
    };
    const submit=event.submitter;
    if(submit){submit.disabled=true;submit.textContent='Discovery queued...'}
    try{
      const started=await request('/creator-discovery/run',{method:'POST',body:JSON.stringify(payload)});
      notify('Creator discovery started. This can take several minutes for 100 creators per platform.');
      const run=started.status==='queued'?await waitForCreatorDiscovery(started.run_id):started;
      if(run.status!=='succeeded') throw new Error(run.error_message||'Creator discovery failed');
      const summary=run.summary||run;
      notify(`Discovery completed. ${summary.creator_count||0} creators and ${summary.latest_content_candidates||0} latest-content candidates prepared.`);
      await creatorDiscovery();
    }catch(error){
      notify(error.message,true);
      if(submit){submit.disabled=false;submit.textContent='Search and rank top creators'}
    }
  };

  document.querySelectorAll('[data-prepare-creator]').forEach(button=>{
    button.onclick=async()=>{
      button.disabled=true;
      try{
        const result=await request(`/creator-discovery/${button.dataset.prepareCreator}/prepare-latest`,{method:'POST'});
        sessionStorage.setItem('selectedTrendCandidate',result.candidate_id);
        notify('Latest creator content is ready for analysis.');
        location.hash='trend-detail';
      }catch(error){
        notify(error.message,true);
        button.disabled=false;
      }
    };
  });
}

async function creatorWatch(){
  setTitle('Creator Watchlist','AUTHORIZED MONITORING');
  const watches = await request('/creator-watchlist');

  const form = `
    <form id="creator-watch-form" class="form-grid">
      <div class="field">
        <label>Platform</label>
        <select name="platform">
          <option value="youtube">YouTube</option>
          <option value="instagram">Instagram</option>
          <option value="tiktok">TikTok</option>
        </select>
      </div>
      <div class="field">
        <label>Creator name</label>
        <input name="creator_name" required>
      </div>
      <div class="field full">
        <label>External creator ID</label>
        <input name="external_creator_id" placeholder="YouTube channel ID, Instagram Professional username, or TikTok Open ID" required>
      </div>
      <div class="field full">
        <label>Creator profile URL</label>
        <input name="profile_url" type="url">
      </div>
      <div class="field">
        <label>Rights status</label>
        <select name="rights_status">
          <option value="licensed">Licensed</option>
          <option value="explicit_permission">Explicit permission</option>
          <option value="user_owned">User owned</option>
          <option value="public_domain">Public domain</option>
        </select>
      </div>
      <div class="field">
        <label>Rights owner</label>
        <input name="rights_owner" required>
      </div>
      <div class="field full">
        <label>License or permission reference</label>
        <input name="license_reference" required>
      </div>
      <div class="field full">
        <label>Attribution text</label>
        <input name="attribution_text" placeholder="Original creator: @creatorname">
      </div>
      <div class="field full">
        <label>Authorized media URL template</label>
        <input name="authorized_media_url_template" placeholder="https://media.example.com/{external_video_id}.mp4">
        <small class="muted">The host must be listed in AUTHORIZED_MEDIA_HOSTS. Platform URLs and platform CDNs are rejected.</small>
      </div>
      <div class="field full">
        <label><input type="checkbox" name="allow_full_reuse"> Full reuse and editing are authorized</label>
      </div>
      <div class="field full">
        <label><input type="checkbox" name="auto_capture_and_prepare"> Automatically capture authorized source and create manual ready-to-post packages</label>
      </div>
      <div class="field full">
        <button type="submit">Add creator watch</button>
      </div>
    </form>
  `;

  const rows = watches.map(watch => ({
    ...watch,
    creator: watch.label,
    creator_id: watch.configuration?.external_creator_id,
    last_check: watch.configuration?.last_checked_at || 'Never',
    automatic: watch.configuration?.auto_capture_and_prepare ? 'Yes' : 'No'
  }));

  q('#content').innerHTML =
    hero('Track creator uploads through official metadata APIs. Full media is accepted only from an allowlisted creator, licensor, or approved delivery host. Generated packages remain manual-post only.') +
    card('Add Authorized Creator', form, 'full') +
    card('Watched Creators', table(rows, [
      ['Platform','platform'],
      ['Creator','creator'],
      ['Creator ID','creator_id'],
      ['Auto prepare','automatic'],
      ['Last check','last_check'],
      ['Action', row => `<div class="action-row"><button class="secondary" data-check-watch="${esc(row.id)}">Check now</button><button class="danger" data-disable-watch="${esc(row.id)}">Disable</button></div>`]
    ]), 'full');

  q('#creator-watch-form').onsubmit = async event => {
    event.preventDefault();
    const data = new FormData(event.target);
    const payload = {
      platform: data.get('platform'),
      creator_name: String(data.get('creator_name') || '').trim(),
      external_creator_id: String(data.get('external_creator_id') || '').trim(),
      profile_url: String(data.get('profile_url') || '').trim() || null,
      rights_status: data.get('rights_status'),
      rights_owner: String(data.get('rights_owner') || '').trim(),
      license_reference: String(data.get('license_reference') || '').trim() || null,
      attribution_text: String(data.get('attribution_text') || '').trim() || null,
      allow_full_reuse: data.get('allow_full_reuse') === 'on',
      authorized_media_url_template: String(data.get('authorized_media_url_template') || '').trim() || null,
      auto_capture_and_prepare: data.get('auto_capture_and_prepare') === 'on'
    };
    try {
      await request('/creator-watchlist', {method:'POST', body:JSON.stringify(payload)});
      notify('Creator watch added.');
      await creatorWatch();
    } catch(error) {
      notify(error.message, true);
    }
  };

  document.querySelectorAll('[data-check-watch]').forEach(button => {
    button.onclick = async () => {
      button.disabled = true;
      try {
        const result = await request(`/creator-watchlist/${button.dataset.checkWatch}/check`, {method:'POST'});
        notify(`Creator check completed. ${result.new_candidates?.length || 0} new post(s), ${result.prepared_packages?.length || 0} package(s) prepared.`);
        await creatorWatch();
      } catch(error) {
        notify(error.message, true);
      } finally {
        button.disabled = false;
      }
    };
  });

  document.querySelectorAll('[data-disable-watch]').forEach(button => {
    button.onclick = async () => {
      if(!confirm('Disable this creator watch?')) return;
      try {
        await request(`/creator-watchlist/${button.dataset.disableWatch}`, {method:'DELETE'});
        notify('Creator watch disabled.');
        await creatorWatch();
      } catch(error) {
        notify(error.message, true);
      }
    };
  });
}

async function trends(){
  setTitle('Trend Explorer','DISCOVERY');

  state.trends = await request('/trends');

  const importForm = `
    <form id="trend-import-form" class="form-grid">
      <div class="field">
        <label>Platform</label>
        <select name="platform">
          <option value="youtube">YouTube</option>
          <option value="instagram">Instagram</option>
        </select>
      </div>

      <div class="field full">
        <label>Viral post URL</label>
        <input
          name="url"
          type="url"
          placeholder="Paste a YouTube video, Short, or Instagram Reel URL"
          required
        >
      </div>

      <div class="field">
        <label>Title</label>
        <input name="title">
      </div>

      <div class="field">
        <label>Topic</label>
        <input name="topic">
      </div>

      <div class="field">
        <label>Visible views</label>
        <input name="views" type="number" min="0">
      </div>

      <div class="field">
        <label>Visible likes</label>
        <input name="likes" type="number" min="0">
      </div>

      <div class="field">
        <label>Visible comments</label>
        <input name="comments" type="number" min="0">
      </div>

      <div class="field full">
        <button type="submit">
          Import viral reference
        </button>
      </div>
    </form>
  `;

  q('#content').innerHTML =
    hero(
      'Discover YouTube popularity signals or import a YouTube or Instagram reference. The application generates a new post and does not copy unlicensed source footage.',
      `<button data-act="trends">
         Discover YouTube Trends
       </button>`
    ) +
    card(
      'Import YouTube or Instagram Reference',
      importForm,
      'full'
    ) +
    card(
      'Ranked Opportunities',
      table(
        state.trends,
        [
          ['Rank', row => esc(row.rank || '–')],
          ['Platform', 'platform'],
          [
            'Title',
            row => `
              <strong>
                ${esc(row.title || row.caption || 'Untitled')}
              </strong>
              <br>
              <small class="muted">
                ${esc(row.source_label || row.data_source)}
              </small>
            `
          ],
          [
            'Score',
            row => `
              <span class="tag">
                ${Number(row.score || 0).toFixed(1)}
              </span>
            `
          ],
          [
            'Confidence',
            row => `
              ${Math.round(
                Number(row.score_confidence || 0) * 100
              )}%
            `
          ],
          [
            'Action',
            row => `
              <button
                class="secondary"
                data-remix-trend="${esc(row.candidate_id)}"
              >
                Create New Post
              </button>
            `
          ]
        ]
      ),
      'full'
    );

  bindActions();

  q('#trend-import-form').onsubmit = async event => {
    event.preventDefault();

    const form = new FormData(event.target);

    const numericValue = name => {
      const value = String(form.get(name) || '').trim();
      return value ? Number(value) : null;
    };

    const payload = {
      platform: form.get('platform'),
      url: String(form.get('url') || '').trim(),
      title: String(form.get('title') || '').trim() || null,
      topic: String(form.get('topic') || '').trim() || null,
      metrics: {
        views: numericValue('views'),
        likes: numericValue('likes'),
        comments: numericValue('comments')
      }
    };

    try {
      await request('/trends/import', {
        method: 'POST',
        body: JSON.stringify(payload)
      });

      notify('Viral reference imported successfully.');
      await trends();

    } catch(error) {
      notify(error.message, true);
    }
  };

  document
    .querySelectorAll('[data-remix-trend]')
    .forEach(button => {
      button.onclick = async () => {
        button.disabled = true;
        button.textContent = 'Creating...';

        try {
          const result = await request(
            `/trends/${button.dataset.remixTrend}/remix`,
            {method: 'POST'}
          );

          notify(
            `New post package created: ${
              result.title || result.package_id
            }`
          );

          location.hash = 'ready';

        } catch(error) {
          notify(error.message, true);
          button.disabled = false;
          button.textContent = 'Create New Post';
        }
      };
    });
}

async function detail(){
  setTitle('Trend Detail','EVIDENCE AND AUTHORIZED MEDIA');
  const trends = await request('/trends');
  if(!trends.length){
    q('#content').innerHTML = '<div class="empty">No trend is available. Run discovery or check a creator watch first.</div>';
    return;
  }

  const selectedCandidate = sessionStorage.getItem('selectedTrendCandidate');
  const candidateId = trends.some(item => item.candidate_id === selectedCandidate)
    ? selectedCandidate
    : trends[0].candidate_id;
  const [item, media] = await Promise.all([
    request(`/trends/${candidateId}`),
    request(`/trends/${candidateId}/source-media`)
  ]);

  const commonRights = `
    <div class="field">
      <label>Rights status</label>
      <select name="rights_status">
        <option value="licensed">Licensed</option>
        <option value="explicit_permission">Explicit permission</option>
        <option value="user_owned">User owned</option>
        <option value="public_domain">Public domain</option>
      </select>
    </div>
    <div class="field">
      <label>Rights owner</label>
      <input name="rights_owner" required>
    </div>
    <div class="field full">
      <label>License or permission reference</label>
      <input name="license_reference" required>
    </div>
    <div class="field full">
      <label>Attribution text</label>
      <input name="attribution_text" placeholder="Original creator: @creatorname">
    </div>
    <div class="field full">
      <label><input type="checkbox" name="allow_full_reuse" value="true" required> I confirm that full reuse, editing, and reposting are authorized</label>
    </div>
  `;

  const uploadForm = `
    <form id="source-media-form" class="form-grid">
      <div class="field full">
        <label>Authorized source video file</label>
        <input type="file" name="file" accept="video/mp4,video/quicktime,video/webm,video/x-m4v" required>
      </div>
      ${commonRights}
      <div class="field full"><button type="submit">Upload complete authorized video</button></div>
    </form>
  `;

  const captureForm = `
    <form id="source-url-form" class="form-grid">
      <div class="field full">
        <label>Authorized delivery URL</label>
        <input type="url" name="source_url" placeholder="https://media.example.com/video.mp4" required>
        <small class="muted">Only an exact host listed in AUTHORIZED_MEDIA_HOSTS is accepted. YouTube, Instagram, TikTok, and platform CDN URLs are rejected.</small>
      </div>
      ${commonRights}
      <div class="field full"><button type="submit">Capture complete authorized video</button></div>
    </form>
  `;

  const currentMedia = media.source_media
    ? `${json(media.source_media)}<div class="action-row"><button data-remix-current="${esc(candidateId)}">Create manual ready-to-post package</button><button type="button" class="danger" id="delete-source-media">Delete source media</button></div>`
    : '<p class="muted">No authorized full source is stored. Upload a file or use an allowlisted creator-delivery URL.</p>';

  q('#content').innerHTML = `<div class="grid">
    ${card('Source Observation', json(item.video || {}), 'half')}
    ${card('Transparent Score', json(item.score || {}), 'half')}
    ${card('Current Authorized Source', currentMedia, 'full')}
    ${card('Upload Authorized File', uploadForm, 'full')}
    ${card('Capture from Authorized Delivery Host', captureForm, 'full')}
    ${card('Model Interpretation', json(item.analysis || {status:'Generate content to create an analysis.'}), 'full')}
  </div>`;

  q('#source-media-form').onsubmit = async event => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      await uploadRequest(`/trends/${candidateId}/source-media`, form);
      notify('Complete authorized source uploaded.');
      await detail();
    } catch(error) {
      notify(error.message, true);
    }
  };

  q('#source-url-form').onsubmit = async event => {
    event.preventDefault();
    const data = new FormData(event.target);
    const payload = {
      source_url: String(data.get('source_url') || '').trim(),
      rights_status: data.get('rights_status'),
      rights_owner: String(data.get('rights_owner') || '').trim(),
      license_reference: String(data.get('license_reference') || '').trim() || null,
      attribution_text: String(data.get('attribution_text') || '').trim() || null,
      allow_full_reuse: data.get('allow_full_reuse') === 'true'
    };
    try {
      await request(`/trends/${candidateId}/source-media/capture-url`, {method:'POST', body:JSON.stringify(payload)});
      notify('Complete authorized source captured.');
      await detail();
    } catch(error) {
      notify(error.message, true);
    }
  };

  document.querySelectorAll('[data-remix-current]').forEach(button => {
    button.onclick = async () => {
      button.disabled = true;
      try {
        const result = await request(`/trends/${button.dataset.remixCurrent}/remix`, {method:'POST'});
        notify(`Manual ready-to-post package created: ${result.title || result.package_id}`);
        location.hash = 'ready';
      } catch(error) {
        notify(error.message, true);
        button.disabled = false;
      }
    };
  });

  const remove = q('#delete-source-media');
  if(remove){
    remove.onclick = async () => {
      if(prompt('Type DELETE to permanently remove the source video.') !== 'DELETE') return;
      try {
        await request(`/trends/${candidateId}/source-media`, {method:'DELETE', body:JSON.stringify({confirmation:'DELETE'})});
        notify('Authorized source deleted.');
        await detail();
      } catch(error) {
        notify(error.message, true);
      }
    };
  }
}

async function packagesPage(mode){const titles={concepts:'Content Concepts',studio:'Content Studio',preview:'Video Preview',review:'Review & Approval',ready:'Ready to Post',calendar:'Publishing Calendar',published:'Published Content'};setTitle(titles[mode],'CONTENT OPERATIONS');state.packages=await request('/content-packages');const filtered=mode==='published'?state.packages.filter(p=>p.status==='published'):mode==='ready'?state.packages.filter(p=>['ready_to_post','review','draft','approved'].includes(p.status)):state.packages;q('#content').innerHTML=hero('Inspect, download, or permanently delete packages. Permanent deletion removes all generated variants and cannot be undone.',`<button data-act="content">Generate Content</button>`)+card('Content Packages',table(filtered,[['Created',r=>esc((r.created_at||'').replace('T',' ').slice(0,19))],['ID',r=>`<code>${esc(String(r.id).slice(0,12))}</code>`],['Status',r=>`<span class="tag">${esc(r.status)}</span>`],['Storage',r=>fmtBytes(r.storage_bytes||0)],['Actions',r=>`<div class="action-row"><button class="secondary" data-package="${esc(r.id)}">Inspect</button><button class="danger" data-delete-package="${esc(r.id)}">Delete permanently</button></div>`]]),'full');bindActions();document.querySelectorAll('[data-package]').forEach(b=>b.onclick=()=>inspectPackage(b.dataset.package,mode));document.querySelectorAll('[data-delete-package]').forEach(b=>b.onclick=()=>permanentDeletePackage(b.dataset.deletePackage))}
async function inspectPackage(id, mode){
  const [packageData, accountGroups] = await Promise.all([
    request(`/content-packages/${id}`),
    request('/accounts')
  ]);

  const accountsByPlatform = Object.fromEntries(
    accountGroups.map(group => [
      group.platform,
      (group.accounts || []).filter(
        account =>
          account.authorization_status === 'connected'
      )
    ])
  );

  const variantCards = (packageData.variants || [])
    .map(variant => {
      const source = variant.media_path
        ? `/api/files?path=${
            encodeURIComponent(variant.media_path)
          }`
        : '';

      const thumbnail = variant.thumbnail_path
        ? `/api/files?path=${
            encodeURIComponent(variant.thumbnail_path)
          }`
        : '';

      const accounts =
        accountsByPlatform[variant.platform] || [];

      const accountOptions = accounts.map(account => `
        <option value="${esc(account.id)}">
          ${esc(
            account.display_name ||
            account.external_account_id ||
            account.id
          )}
        </option>
      `).join('');

      const controls = source
        ? `
          <div class="field">
            <label>Destination account</label>
            <select id="publish-account-${esc(variant.id)}">
              <option value="">
                Default connected account
              </option>
              ${accountOptions}
            </select>
          </div>

          <div class="action-row">
            <a
              class="button secondary"
              href="${esc(source)}"
              download
            >
              Download MP4
            </a>

            <button
              class="secondary"
              data-publish-package="${esc(id)}"
              data-publish-platform="${esc(variant.platform)}"
              data-publish-variant="${esc(variant.id)}"
              data-simulate="true"
            >
              Simulate
            </button>

            <button
              data-publish-package="${esc(id)}"
              data-publish-platform="${esc(variant.platform)}"
              data-publish-variant="${esc(variant.id)}"
              data-simulate="false"
            >
              Publish New Post
            </button>
          </div>
        `
        : `
          <div class="empty">
            No rendered media is attached.
          </div>
        `;

      return card(
        variant.platform?.toUpperCase() || 'Variant',
        `
          ${
            source
              ? `
                <video
                  class="video"
                  controls
                  preload="metadata"
                  poster="${esc(thumbnail)}"
                  src="${esc(source)}"
                ></video>
              `
              : ''
          }

          ${controls}
          ${json(variant.metadata_json || {})}
        `,
        'full'
      );
    })
    .join('');

  q('#content').innerHTML =
    hero(
      packageData.title,
      `
        <button
          class="danger"
          id="delete-current-package"
        >
          Delete permanently
        </button>
      `
    ) +
    variantCards +
    card(
      'Package Metadata',
      json(packageData),
      'full'
    );

  q('#delete-current-package').onclick = () =>
    permanentDeletePackage(id);

  document
    .querySelectorAll('[data-publish-package]')
    .forEach(button => {
      button.onclick = async () => {
        const simulate =
          button.dataset.simulate === 'true';

        const platform =
          button.dataset.publishPlatform;

        const variantId =
          button.dataset.publishVariant;

        const accountSelect = document.getElementById(
          `publish-account-${variantId}`
        );

        const platformAccountId =
          accountSelect?.value || null;

        if(
          !simulate &&
          !confirm(
            `Publish this newly generated post to ${platform}?`
          )
        ){
          return;
        }

        button.disabled = true;

        try {
          await request(
            `/content-packages/${
              button.dataset.publishPackage
            }/publish`,
            {
              method: 'POST',
              body: JSON.stringify({
                platform,
                platform_account_id:
                  platformAccountId,
                simulate
              })
            }
          );

          notify(
            simulate
              ? `${platform} publishing simulation completed.`
              : `${platform} publication was submitted.`
          );

        } catch(error) {
          notify(error.message, true);

        } finally {
          button.disabled = false;
        }
      };
    });
}

async function permanentDeletePackage(id){const value=prompt('Type DELETE to permanently remove this package and all local media files. Published posts on social platforms will not be removed.');if(value!=='DELETE')return;try{const result=await request(`/content-packages/${id}/permanent`,{method:'DELETE',body:JSON.stringify({confirmation:'DELETE'})});notify(`Package deleted. ${fmtBytes(result.bytes_freed||0)} recovered.`);await packagesPage('ready')}catch(e){notify(e.message,true)}}
async function analytics(){setTitle('Analytics','PERFORMANCE');const d=await request('/analytics/overview');q('#content').innerHTML=hero('Official metrics remain null when a platform does not expose them. Demonstration metrics are clearly labeled.',`<button data-act="analytics-demo">Load Demo Analytics</button>`)+`<div class="grid">${card('Account Metrics',json(d.account_metrics||[]),'half')}${card('Post Metrics',json(d.post_metrics||[]),'half')}${card('Normalized Performance',json(d.normalized||d),'full')}</div>`;bindActions()}
async function experiments(){setTitle('Experiments','CONTROLLED OPTIMIZATION');const d=await request('/experiments');q('#content').innerHTML=hero('Experiments change versioned content configurations only. Production code and safety gates are never rewritten automatically.')+card('Experiment Registry',table(d,[['Name','name'],['Status','status'],['Hypothesis','hypothesis'],['Metric','target_metric'],['Decision','decision']]),'full')}
async function brand(){return onboarding()}
async function schedules(){setTitle('Schedules','AMERICA/CHICAGO');const d=await request('/schedules');q('#content').innerHTML=hero('Default discovery runs at 7:00 AM and 1:00 PM. Content production runs at 8:00 AM, 2:00 PM, and 8:00 PM, all configurable.')+card('Persistent Schedules',table(d,[['Name','name'],['Workflow','workflow_type'],['Cron','cron_expression'],['Timezone','timezone'],['Enabled',r=>r.enabled?'Yes':'No'],['Last run','last_run_at'],['Next run','next_run_at']]),'full')}
async function providers(){setTitle('Provider Configuration','COST CONTROL');const d=await request('/providers');q('#content').innerHTML=hero('Local fallbacks support basic operation. Paid providers require explicit configuration and budget controls.')+card('Configured Providers',table(d,[['Type','provider_type'],['Provider','provider_name'],['Enabled',r=>r.enabled?'Yes':'No'],['Validated',r=>r.validated?'Yes':'No'],['Health','health_status'],['Cost','cost_limits']]),'full')}
async function health(){setTitle('API Health','READINESS');const [live,ready,security]=await Promise.all([request('/health/liveness'),request('/health/readiness'),request('/security/status')]);q('#content').innerHTML=`<div class="grid">${card('Liveness',json(live),'half')}${card('Readiness',json(ready),'half')}${card('Security Controls',json(security),'full')}</div>`}
async function simplePage(id,title,path){setTitle(title,'OPERATIONS');const d=await request(path);q('#content').innerHTML=card(title,Array.isArray(d)?table(d,[['Timestamp',r=>esc(r.created_at||r.occurred_at||'')],['Type',r=>esc(r.event_type||r.level||r.title||'')],['Status',r=>esc(r.status||r.severity||'')],['Detail',r=>esc(r.message||r.action||JSON.stringify(r).slice(0,160))]]):json(d),'full')}
async function backup(){setTitle('Backup & Restore','DATA PROTECTION');q('#content').innerHTML=hero('Create an encrypted archive of the database, configuration metadata, and managed storage. Restore requires an explicit local command.',`<button data-act="backup">Create Backup</button>`)+card('Backup Policy','<p class="muted">Backups are written under <code>storage/exports/backups</code>. Use <code>scripts/restore.sh</code> for an explicit restore.</p>','full');bindActions()}
async function generic(title,text){setTitle(title,'CONFIGURATION');q('#content').innerHTML=card(title,`<p class="muted">${esc(text)}</p>`,'full')}
async function route(){state.page=(location.hash||'#dashboard').slice(1);nav();try{const map={dashboard,onboarding,accounts,'creator-discovery':creatorDiscovery,'creator-watch':creatorWatch,trends,'trend-detail':detail,concepts:()=>packagesPage('concepts'),studio:()=>packagesPage('studio'),preview:()=>packagesPage('preview'),review:()=>packagesPage('review'),ready:()=>packagesPage('ready'),calendar:()=>packagesPage('calendar'),published:()=>packagesPage('published'),analytics,comparison:analytics,experiments,brand,rules:()=>generic('Content Rules','Manage included and excluded topics, disclosure rules, rights requirements, brand-safety thresholds, and publishing gates through the brand profile and environment configuration.'),schedules,providers,health,jobs:()=>simplePage('jobs','Job History','/workflows'),logs:()=>simplePage('logs','Logs','/audit-events'),notifications:()=>simplePage('notifications','Notifications','/notifications'),security:health,backup,settings:()=>generic('Settings','Runtime configuration is validated from .env. Use the documented environment keys and restart the local stack after changes.')};await (map[state.page]||dashboard)()}catch(e){if(String(e.message).includes('Authentication'))return showAuth();q('#content').innerHTML=`<div class="empty danger-text">${esc(e.message)}</div>`}}
function bindActions(){document.querySelectorAll('[data-act]').forEach(b=>b.onclick=async()=>{b.disabled=true;try{const a=b.dataset.act;if(a==='demo')await request('/workflows/demo',{method:'POST'});if(a==='trends')await request('/workflows/trends?max_candidates=10&select_limit=10',{method:'POST'});if(a==='content')await request('/workflows/content?max_items=10',{method:'POST'});if(a==='analytics-demo')await request('/analytics/demo',{method:'POST'});if(a==='backup')await request('/backup',{method:'POST'});notify(`${a.replace('-',' ')} completed.`);await route()}catch(e){notify(e.message,true)}finally{b.disabled=false}})}
function showAuth(){q('#app').classList.add('hidden');q('#auth-screen').classList.remove('hidden')}
function showApp(){q('#auth-screen').classList.add('hidden');q('#app').classList.remove('hidden');route()}
q('#login-form').onsubmit=async e=>{e.preventDefault();try{await request('/auth/login',{method:'POST',body:JSON.stringify({email:q('#email').value,password:q('#password').value})});showApp()}catch(err){q('#auth-message').textContent=err.message}};
q('#bootstrap').onclick=async()=>{try{const r=await request('/auth/bootstrap',{method:'POST'});q('#auth-message').textContent=`Initialized ${r.email}. Sign in with the password configured in .env.`;showApp()}catch(err){q('#auth-message').textContent=err.message}};
q('#logout').onclick=async()=>{try{await request('/auth/logout',{method:'POST'})}catch{}showAuth()};
q('#refresh').onclick=route;q('#pause-toggle').onclick=async()=>{try{await request(state.overview?.system_status==='paused'?'/system/resume':'/system/pause',{method:'POST'});await route()}catch(e){notify(e.message,true)}};
window.addEventListener('hashchange',route);
request('/auth/me').then(r=>r.authenticated?showApp():showAuth()).catch(showAuth);
