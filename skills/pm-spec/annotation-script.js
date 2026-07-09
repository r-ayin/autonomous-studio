(function(){
  var API=location.origin+'/api/annotations';
  var UPLOAD=location.origin+'/api/upload';
  var D=[];
  function loadFromServer(){
    fetch(API).then(function(r){return r.json();}).then(function(list){
      if(Array.isArray(list)){D=list;nid=D.length?Math.max.apply(null,D.map(function(d){return typeof d.id==='number'?d.id:parseInt(String(d.id).replace(/\D/g,''))||0;}))+1:1;restore();ut();}
    }).catch(function(){});
  }
  var nid=1;
  function saveToServer(ann){
    fetch(API,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(ann)}).catch(function(){});
  }
  function deleteFromServer(id){
    fetch(API+'/'+encodeURIComponent(id),{method:'DELETE'}).catch(function(){});
  }
  function esc(s){return s.replace(/</g,'&lt;').replace(/\n/g,'<br/>');}
  var fab=document.createElement('button');
  fab.id='anno-fab';fab.textContent='💬 批注';fab.style.display='none';
  document.body.appendChild(fab);
  var pRange=null,pText='';
  document.addEventListener('mouseup',function(e){
    if(e.target.closest('#anno-fab,.anno-mask,#anno-bar,#anno-sb,#anno-ov'))return;
    setTimeout(function(){
      var sel=window.getSelection();
      if(!sel.rangeCount||sel.isCollapsed){fab.style.display='none';return;}
      var t=sel.toString().trim();
      if(t.length<2){fab.style.display='none';return;}
      pRange=sel.getRangeAt(0).cloneRange();pText=t;
      var r=pRange.getBoundingClientRect();
      fab.style.display='block';
      fab.style.left=(r.left+r.width/2-40+window.scrollX)+'px';
      fab.style.top=(r.bottom+8+window.scrollY)+'px';
    },10);
  });
  fab.onmousedown=function(e){e.preventDefault();e.stopPropagation();};
  fab.onclick=function(e){
    e.preventDefault();e.stopPropagation();
    if(!pRange||!pText)return;
    fab.style.display='none';showModal(pRange,pText);
  };
  function uploadImage(file,callback){
    var fd=new FormData();fd.append('file',file,file.name||'paste.png');
    fetch(UPLOAD,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(j){
      if(j.url)callback(j.url);
    }).catch(function(){});
  }
  function showModal(range,selText){
    var imgUrls=[];
    var mask=document.createElement('div');mask.className='anno-mask';
    mask.innerHTML='<div class="anno-modal"><div class="anno-mh">添加批注</div>'
      +'<div class="anno-ms">“'+esc(selText)+'”</div>'
      +'<textarea class="anno-mt" placeholder="输入批注意见…" rows="3"></textarea>'
      +'<div class="anno-img-zone" id="anno-drop">📎 拖拽或粘贴图片到此处（支持 Ctrl+V）</div>'
      +'<div class="anno-ma"><button class="cc">取消</button><button class="ok">添加</button></div></div>';
    document.body.appendChild(mask);
    var ta=mask.querySelector('textarea');ta.focus();
    var dropZone=mask.querySelector('#anno-drop');
    function handleFiles(files){
      for(var i=0;i<files.length;i++){
        if(!files[i].type.startsWith('image/'))continue;
        (function(f){
          uploadImage(f,function(url){
            imgUrls.push(url);
            var img=document.createElement('img');img.src=url;
            dropZone.appendChild(img);
            dropZone.childNodes[0].nodeType===3&&(dropZone.childNodes[0].textContent='');
          });
        })(files[i]);
      }
    }
    dropZone.addEventListener('dragover',function(e){e.preventDefault();e.stopPropagation();dropZone.classList.add('drag-over');});
    dropZone.addEventListener('dragleave',function(e){e.preventDefault();e.stopPropagation();dropZone.classList.remove('drag-over');});
    dropZone.addEventListener('drop',function(e){e.preventDefault();e.stopPropagation();dropZone.classList.remove('drag-over');if(e.dataTransfer.files.length)handleFiles(e.dataTransfer.files);});
    dropZone.addEventListener('click',function(){var inp=document.createElement('input');inp.type='file';inp.accept='image/*';inp.multiple=true;inp.onchange=function(){if(inp.files.length)handleFiles(inp.files);};inp.click();});
    document.addEventListener('paste',onPaste);
    function onPaste(e){
      if(!mask.parentNode)return;
      var items=e.clipboardData&&e.clipboardData.items;if(!items)return;
      for(var i=0;i<items.length;i++){
        if(items[i].type.indexOf('image')!==-1){
          e.preventDefault();
          var blob=items[i].getAsFile();if(blob)handleFiles([blob]);
          break;
        }
      }
    }
    mask.querySelector('.cc').onclick=function(){document.removeEventListener('paste',onPaste);document.body.removeChild(mask);};
    mask.onclick=function(e){if(e.target===mask){document.removeEventListener('paste',onPaste);document.body.removeChild(mask);}};
    ta.onkeydown=function(e){if(e.key==='Enter'&&(e.ctrlKey||e.metaKey))mask.querySelector('.ok').click();};
    mask.querySelector('.ok').onclick=function(){
      var comment=ta.value.trim();
      if(!comment&&imgUrls.length===0){ta.style.borderColor='#f87171';ta.focus();return;}
      var id='ann-'+Date.now();
      try{
        var mk=document.createElement('mark');mk.className='hl';mk.setAttribute('data-aid',id);mk.title=comment;
        range.surroundContents(mk);
        mk.onclick=function(){flash(id);openSB();};
      }catch(ex){
        try{var fg=range.extractContents();var mk2=document.createElement('mark');mk2.className='hl';mk2.setAttribute('data-aid',id);mk2.title=comment;mk2.appendChild(fg);range.insertNode(mk2);mk2.onclick=function(){flash(id);openSB();};}
        catch(ex2){}
      }
      var el=range.startContainer;if(el.nodeType===3)el=el.parentElement;
      var sec=el?el.closest('.node'):null,sn='其他';
      if(sec){var nt=sec.querySelector('.node-title');sn=nt?nt.textContent.trim():'其他';}
      var ann={id:id,selectedText:selText,comment:comment||'(图片批注)',images:imgUrls,contextBefore:'',contextAfter:'',section:sn,sk:selText.substring(0,60),time:new Date().toLocaleString('zh-CN')};
      D.push(ann);
      saveToServer(ann);
      document.removeEventListener('paste',onPaste);
      document.body.removeChild(mask);window.getSelection().removeAllRanges();ut();
    };
  }
  function restore(){
    D.forEach(function(d){
      if(document.querySelector('[data-aid="'+d.id+'"]'))return;
      var w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT),s=d.sk||d.selectedText&&d.selectedText.substring(0,60),nd;
      if(!s)return;
      while(nd=w.nextNode()){
        var idx=nd.textContent.indexOf(s);
        if(idx===-1)continue;
        if(nd.parentElement.closest('.hl,#anno-bar,#anno-sb'))continue;
        try{
          var rg=document.createRange();rg.setStart(nd,idx);rg.setEnd(nd,Math.min(idx+s.length,nd.textContent.length));
          var mk=document.createElement('mark');mk.className='hl';mk.setAttribute('data-aid',d.id);mk.title=d.comment;
          rg.surroundContents(mk);mk.onclick=function(){openSB();};
        }catch(e){}
        break;
      }
    });
  }
  function flash(id){var el=document.querySelector('[data-aid="'+id+'"]');if(el){el.scrollIntoView({behavior:'smooth',block:'center'});el.style.background='#fde047';setTimeout(function(){el.style.background='';},1500);}}
  function ut(){var el=document.getElementById('anno-tot');el.textContent=D.length;el.style.display=D.length>0?'inline':'none';}
  function openSB(){document.getElementById('anno-sb').classList.add('open');document.getElementById('anno-ov').classList.add('open');rsb();}
  function closeSB(){document.getElementById('anno-sb').classList.remove('open');document.getElementById('anno-ov').classList.remove('open');}
  function toggleSB(){document.getElementById('anno-sb').classList.contains('open')?closeSB():openSB();}
  function rsb(){
    var body=document.getElementById('anno-sbb');
    if(!D.length){body.innerHTML='<div class="sb-empty">暂无批注<br/><span style="font-size:12px;color:#b8b8b8">选中文字后点击「💬 批注」添加</span></div>';return;}
    var g={};D.forEach(function(d){var s=d.section||'其他';if(!g[s])g[s]=[];g[s].push(d);});
    var h='';for(var s in g){
      h+='<div class="sbg"><div class="sbg-t">'+esc(s)+'</div>';
      g[s].forEach(function(d){
        var qt=(d.selectedText||d.text||'').length>60?(d.selectedText||d.text).substring(0,60)+'…':(d.selectedText||d.text||'');
        var imgHtml='';
        if(d.images&&d.images.length){d.images.forEach(function(u){imgHtml+='<div class="ai"><img src="'+u+'"/></div>';});}
        h+='<div class="anno-item" onclick="A.go(\''+d.id+'\')"><div class="am">'+(d.time||d.createdAt||'')+(d.updatedAt?' <span style="color:#3b5bdb">已编辑</span>':'')+'</div><div class="aq">“'+esc(qt)+'”</div><div class="ac" id="ac-'+d.id+'">'+esc(d.comment||'')+'</div>'+imgHtml+'<button class="ad" onclick="event.stopPropagation();A.edit(\''+d.id+'\')">编辑</button><button class="ad" onclick="event.stopPropagation();A.del(\''+d.id+'\')">删除</button></div>';
      });
      h+='</div>';
    }
    body.innerHTML=h;
  }
  window.A={
    toggle:toggleSB,
    go:function(id){flash(id);},
    edit:function(id){
      var d=D.filter(function(x){return x.id===id;})[0];
      if(!d)return;
      var box=document.getElementById('ac-'+id);
      if(!box)return;
      var ta=document.createElement('textarea');
      ta.className='anno-mt';ta.value=d.comment||'';ta.style.margin='6px 0';ta.rows=3;
      box.replaceWith(ta);ta.focus();
      var save=document.createElement('button');save.textContent='保存';save.className='ad';save.style.cssText='position:static;opacity:1;margin-left:8px';
      var cancel=document.createElement('button');cancel.textContent='取消';cancel.className='ad';cancel.style.cssText='position:static;opacity:1;margin-left:4px';
      ta.after(save);save.after(cancel);
      function done(saveIt){
        if(saveIt&&ta.value.trim()){
          d.comment=ta.value.trim();
          fetch(API+'/'+encodeURIComponent(id),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({comment:d.comment})}).catch(function(){});
          var mk=document.querySelector('[data-aid="'+id+'"]');if(mk)mk.title=d.comment;
        }
        rsb();
      }
      save.onclick=function(e){e.stopPropagation();done(true);};
      cancel.onclick=function(e){e.stopPropagation();done(false);};
      ta.onkeydown=function(e){if(e.key==='Enter'&&(e.ctrlKey||e.metaKey))done(true);if(e.key==='Escape')done(false);};
    },
    del:function(id){
      var mk=document.querySelector('[data-aid="'+id+'"]');
      if(mk){var p=mk.parentNode;while(mk.firstChild)p.insertBefore(mk.firstChild,mk);p.removeChild(mk);p.normalize();}
      D=D.filter(function(d){return d.id!==id;});
      deleteFromServer(id);
      ut();rsb();
    },
    exp:function(){
      if(!D.length){alert('暂无批注');return;}
      var L=['# PRD 批注导出','导出时间：'+new Date().toLocaleString('zh-CN'),''];
      var g={};D.forEach(function(d){var s=d.section||'其他';if(!g[s])g[s]=[];g[s].push(d);});
      for(var s in g){L.push('## '+s);g[s].forEach(function(d){
        var t=d.selectedText||d.text||'';
        L.push('> “'+t.substring(0,80)+(t.length>80?'…':'')+'”');
        L.push('- ['+(d.time||d.createdAt||'')+'] '+(d.comment||''));
        if(d.images&&d.images.length){d.images.forEach(function(u){L.push('  - ![](' + location.origin + u + ')');});}
        L.push('');
      });}
      var blob=new Blob([L.join('\n')],{type:'text/markdown;charset=utf-8'});
      var a=document.createElement('a');a.href=URL.createObjectURL(blob);
      a.download='prd-批注-'+new Date().toISOString().slice(0,10)+'.md';
      a.click();URL.revokeObjectURL(a.href);
    },
    /* 历史批注回顾：拉取同大版本归档批注（只读），避免修改后不知道原先批了什么 */
    history:function(){
      var mask=document.createElement('div');mask.className='anno-mask';
      mask.innerHTML='<div class="anno-modal" style="width:560px;max-height:80vh;display:flex;flex-direction:column">'
        +'<div class="anno-mh" style="display:flex;justify-content:space-between;align-items:center">'
        +'<span>📜 历史批注回顾（只读）</span>'
        +'<button class="sbc" style="background:none;border:none;font-size:18px;cursor:pointer;color:#6b7280;padding:4px 8px" onclick="this.closest(\'.anno-mask\').parentNode.removeChild(this.closest(\'.anno-mask\'))">&#x2715;</button></div>'
        +'<div id="anno-hist-body" style="overflow-y:auto;padding:12px 20px 16px;font-size:13px">加载中…</div></div>';
      document.body.appendChild(mask);
      mask.onclick=function(e){ if(e.target===mask){ document.body.removeChild(mask); } };
      var body=mask.querySelector('#anno-hist-body');
      fetch(location.origin+'/api/annotations/history').then(function(r){return r.json();}).then(function(list){
        if(!Array.isArray(list)||!list.length){ body.innerHTML='<div style="text-align:center;color:#9ca3af;padding:30px 0">暂无历史批注<br/><span style="font-size:12px;color:#b8b8b8">同大版本归档后此处可回顾</span></div>'; return; }
        var h='';
        list.forEach(function(g){
          h+='<div style="margin-bottom:18px"><div style="font-size:12px;font-weight:600;color:#3b5bdb;margin-bottom:8px;border-bottom:1px solid #e2e8f0;padding-bottom:4px">'+g.version+' · '+g.count+' 条</div>';
          (g.annotations||[]).forEach(function(d){
            var qt=(d.selectedText||d.text||'').length>70?(d.selectedText||d.text).substring(0,70)+'…':(d.selectedText||d.text||'');
            h+='<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:8px 12px;margin-bottom:6px">'
              +'<div style="font-size:11px;color:#9ca3af;margin-bottom:4px">'+(d.time||d.createdAt||'')+'</div>'
              +'<div style="font-size:12px;color:#64748b;font-style:italic;margin-bottom:4px;padding-left:6px;border-left:2px solid #cbd5e1">“'+esc(qt)+'”</div>'
              +'<div>'+esc(d.comment||'')+'</div></div>';
          });
          h+='</div>';
        });
        body.innerHTML=h;
      }).catch(function(){ body.innerHTML='<div style="color:#dc2626;text-align:center;padding:20px">加载失败，请确认预览服务器已启动</div>'; });
    }
  };
  loadFromServer();
})();
