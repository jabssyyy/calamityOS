(() => {
  const dialog = document.createElement('dialog');
  dialog.className = 'evidence-desk';
  dialog.setAttribute('aria-labelledby', 'ev-title');
  dialog.innerHTML = `<header><div><small>AP-2026.1 · SOURCE REVIEW</small><h2 id="ev-title">Evidence desk</h2></div><button type="button" aria-label="Close evidence desk" class="ev-close">×</button></header>
    <p>Check the committee brief against the four terms in this demo rule pack. Each match points to the exact words used.</p>
    <label>Committee brief <textarea maxlength="16000" rows="6"></textarea></label>
    <div class="ev-actions"><label class="ev-file">Open text file<input type="file" accept=".txt,text/plain"></label><button class="ev-extract">Find source passages</button></div>
    <div class="ev-fields"></div><div class="ev-officers"><label>Maker<input class="ev-maker" value="Intake officer"></label><label>Checker<input class="ev-checker" value="Compliance officer"></label></div>
    <footer><span aria-live="polite"></span><button class="ev-save">Attach reviewed brief</button></footer>`;
  document.body.append(dialog);
  const q = sel => dialog.querySelector(sel);
  const body = q('textarea'), status = q('footer span');
  function render(fields) {
    const list = q('.ev-fields');
    list.replaceChildren();
    for (const f of fields) {
      const row = document.createElement('button');
      row.className = 'ev-row';
      const label = document.createElement('strong'), value = document.createElement('span');
      label.textContent = f.label;
      value.textContent = f.status === 'Matched' ? f.quote : 'Review required · expected ' + f.expected;
      row.append(label, value);
      row.disabled = !f.span;
      row.onclick = () => {body.focus(); body.setSelectionRange(...f.span);};
      list.append(row);
    }
    q('.ev-save').disabled = fields.some(f => f.status !== 'Matched') || fields.length === 0;
  }
  async function api(path, data) {
    const res = await fetch('/api/evidence'+path, data ? {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)} : {});
    const result = await res.json();
    if (!res.ok) throw Error(result.error);
    return result;
  }
  async function run(fn) { try { await fn(); } catch(e) { status.textContent = e.message; } }
  document.addEventListener('click', e => {
    if (!e.target.closest('[data-open-evidence]')) return;
    dialog.showModal();
    run(async () => {
      const saved = await api('');
      body.value = saved.body;
      q('.ev-maker').value = saved.maker || 'Intake officer';
      q('.ev-checker').value = saved.checker || 'Compliance officer';
      status.textContent = saved.checker ? 'Reviewed by ' + saved.checker : 'Illustrative brief · offline text matching';
      render(saved.fields);
    });
  });
  q('.ev-close').onclick = () => dialog.close();
  body.oninput = () => {render([]); status.textContent = 'Check the edited passages.';};
  q('input[type=file]').onchange = e => run(async () => {
    const file = e.target.files[0];
    if (!file) return;
    if (file.size > 16000) throw Error('Choose a text brief under 16 KB.');
    body.value = await file.text(); body.oninput(); e.target.value='';
  });
  q('.ev-extract').onclick = () => run(async () => {const {fields} = await api('/preview',{body:body.value}); render(fields); status.textContent = fields.filter(f=>f.status==='Matched').length + ' of 4 terms matched';});
  q('.ev-save').onclick = () => run(async () => {const result=await api('/approve',{body:body.value,maker:q('.ev-maker').value,checker:q('.ev-checker').value});status.textContent='Brief attached · reviewed by '+result.checker;});
})();
