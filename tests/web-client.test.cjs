// Offline DOM doubles: no browser or network is started by these tests.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname,'../backend/web/assets/app.js'),'utf8');
function fixture(handler) {
  class Element {
    constructor(tag='div') { this.tagName=tag; this.children=[]; this.value=''; this.hidden=false; this.open=false; this.checked=false; this.disabled=false; this.textContent=''; this.dataset={}; this.events={}; this.classList={toggle(){},add(){},remove(){}}; }
    append(...values) {this.children.push(...values);}
    replaceChildren(...values) {this.children=values;}
    addEventListener(name,callback) {this.events[name]=callback;}
    showModal(){this.open=true;}
    close(){this.open=false;}
    focus(){}
    scrollIntoView(){}
  }
  const elements=new Map(), calls=[], saved=[];
  const document={documentElement:{lang:''}, getElementById(id){if(!elements.has(id))elements.set(id,new Element());return elements.get(id);}, querySelectorAll(){return [];}, createElement(tag){return new Element(tag);}, createTextNode(text){return {textContent:text};}, addEventListener(){}};
  const context={document, window:{matchMedia(){return {matches:false};},addEventListener(){}},navigator:{userAgent:'test',clipboard:{async writeText(){}}},location:{protocol:'file:'},localStorage:{getItem(){return null;},setItem(...values){saved.push(values);}},AbortController,SpeechSynthesisUtterance:class{},setInterval(){return 1;},clearInterval(){},setTimeout(){return 2;},clearTimeout(){},URL, console,
    async fetch(url,options){calls.push({url,options});const value=await handler(url,options);const status=typeof value.status==='number'?value.status:200;return {ok:status<400,status,async json(){return value.body||value;}};}};
  vm.runInNewContext(source,context);
  return {get:id=>document.getElementById(id),calls,saved};
}
const tick=()=>new Promise(resolve=>setImmediate(resolve));
async function login(app){app.get('pair-code').value='12345678';await app.get('login-form').events.submit({preventDefault(){}});}
test('pairing clears sensitive fields and does not put credentials in local storage',async()=>{
 const app=fixture(url=>url==='/capabilities'?{indexed_passages:25}:{status:'ok'});
 await login(app);
 assert.equal(app.get('login-dialog').open,false);
 assert.equal(app.get('pair-code').value,'');
 assert.equal(app.get('access-token').value,'');
 assert.ok(app.calls.every(call=>!call.url.includes('12345678')));
 assert.ok(!JSON.stringify(app.saved).includes('12345678'));
 assert.equal(app.calls[0].options.headers['X-NOR-Client'],'pwa');
});
test('question uses existing research API and untrusted source text remains text',async()=>{
 const app=fixture(url=>url==='/research'?{answer:'Une réponse [S1]',duration_ms:1000,sources:[{source_id:'S1',network:'i2p',title:'<img src=x onerror=alert(1)>',url:'http://example.i2p/',excerpt:'Text'}],research_gaps:['Un point ouvert']} : url==='/capabilities'?{indexed_passages:25}:{status:'ok'});
 await login(app);app.get('question').value='Une question I2P ?';app.get('network').value='i2p';
 app.get('ask-form').onsubmit({preventDefault(){}});await tick();await tick();
 const sent=JSON.parse(app.calls.find(call=>call.url==='/research').options.body);
 assert.equal(sent.language,'fr');assert.equal(sent.network,'i2p');assert.equal(sent.question,'Une question I2P ?');
 const tree=JSON.stringify(app.get('messages').children);
 assert.ok(tree.includes('<img src=x onerror=alert(1)>'));assert.ok(!tree.includes('"tagName":"img"'));
 assert.ok(tree.includes('Une réponse [S1]'));assert.ok(tree.includes('Un point ouvert'));
 assert.equal(app.get('send').disabled,false);
});
test('rate limit is presented as a useful localized message',async()=>{
 const app=fixture(()=>({status:429}));app.get('pair-code').value='12345678';
 await app.get('login-form').events.submit({preventDefault(){}});
 assert.match(app.get('login-error').textContent,/occupé/);
 assert.equal(app.get('login-submit').disabled,false);
});
test('a late response cannot repopulate a cleared conversation',async()=>{
 let finish;
 const app=fixture(url=>url==='/research'?new Promise(resolve=>{finish=resolve;}) : url==='/capabilities'?{indexed_passages:25}:{status:'ok'});
 await login(app);app.get('question').value='Une question ?';app.get('ask-form').onsubmit({preventDefault(){}});
 await tick();app.get('new-chat').onclick();finish({answer:'Late answer',sources:[]});await tick();await tick();
 assert.equal(app.get('messages').children.length,0);assert.equal(app.get('welcome').hidden,false);
});
test('service worker never handles authenticated API requests',()=>{
 const events={};vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../backend/web/sw.js'),'utf8'),{self:{location:{origin:'https://nor.example'},addEventListener(name,fn){events[name]=fn;}},URL});
 for(const route of ['/session','/research','/capabilities']){
  let intercepted=false;events.fetch({request:{url:'https://nor.example'+route,method:'GET'},respondWith(){intercepted=true;}});assert.equal(intercepted,false);
 }
});
