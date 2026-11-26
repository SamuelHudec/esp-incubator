// Exercise the real page handlers without loading user images or a browser.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const html = fs.readFileSync(path.join(__dirname, '../annotator/index.html'), 'utf8');
const elements = new Map();
const element = selector => {
  if (!elements.has(selector)) elements.set(selector, {hidden:true, getContext:()=>({clearRect(){}})});
  return elements.get(selector);
};
const context = vm.createContext({document:{querySelector:element}, window:{},
  fetch:()=>new Promise(()=>{}), console});
vm.runInContext(html.split('<script>')[1].split('</script>')[0], context);
async function scenario(filtered) {
  vm.runInContext(`
    rows=Array.from({length:5},(_,i)=>({image:i+'.jpg',boxes:[],reviewed:false}));
    filtered=${filtered}; selectImages();
    // Earlier review changed filter membership, but the snapshot must stay stable.
    rows[0].boxes=[[0,0,1,1]]; rows[1].boxes=[[0,0,1,1]];
    index=2;busy=false;drag=null;
    load=async()=>{dirty=false;};
    fetch=async(url,options)=>{const payload=JSON.parse(options.body);
      if(payload.image!==rows[payload.index].image)throw Error('Wrong image');
      return {ok:true,json:async()=>({...payload,excluded:true})};};
  `, context);
  await element('#delete-image').onclick();
  assert.equal(vm.runInContext('JSON.stringify(visible)',context),'[0,1,3,4]');
  assert.equal(vm.runInContext('index',context),3);
  await element('#delete-image').onclick();
  assert.equal(vm.runInContext('JSON.stringify(visible)',context),'[0,1,4]');
  assert.equal(vm.runInContext('index',context),4);
  await element('#delete-image').onclick();
  assert.equal(vm.runInContext('index',context),1);
  assert.match(element('#status').textContent,/End of list/);
  await element('#delete-image').onclick();
  await element('#delete-image').onclick();
  assert.equal(vm.runInContext('visible.length',context),0);
  assert.equal(vm.runInContext('index',context),-1);
  vm.runInContext(`rows=[{image:'keep.jpg',boxes:[]}];visible=[0];index=0;busy=false;
    fetch=async()=>({ok:false,text:async()=> 'Disk write failed'});`,context);
  await element('#delete-image').onclick();
  assert.equal(vm.runInContext('JSON.stringify(visible)',context),'[0]');
  assert.equal(vm.runInContext('rows[0].excluded',context),undefined);
}
async function reviewFilterScenario(){
  vm.runInContext(`rows=[
    {image:'a',boxes:[],reviewed:false},
    {image:'b',boxes:[],reviewed:true},
    {image:'c',boxes:[[0,0,1,1]],reviewed:false},
    {image:'d',boxes:[],reviewed:false,excluded:true}];
    filtered=false;unreviewedOnly=false;dirty=false;busy=false;index=0;selectImages();`,context);
  element('#filter').checked=false;
  element('#unreviewed-filter').checked=true;
  await element('#unreviewed-filter').onchange();
  assert.equal(vm.runInContext('JSON.stringify(visible)',context),'[0,2]');
  element('#filter').checked=true;
  await element('#filter').onchange();
  assert.equal(vm.runInContext('JSON.stringify(visible)',context),'[0]');
  vm.runInContext('rows[0].reviewed=true;',context);
  assert.equal(vm.runInContext('JSON.stringify(visible)',context),'[0]');
  await element('#unreviewed-filter').onchange();
  assert.equal(vm.runInContext('visible.length',context),0);
  assert.equal(vm.runInContext('index',context),-1);
  element('#unreviewed-filter').checked=false;
  await element('#unreviewed-filter').onchange();
  assert.equal(vm.runInContext('JSON.stringify(visible)',context),'[0,1]');
}
(async()=>{await scenario(true);await scenario(false);await reviewFilterScenario();console.log('Annotator navigation checks passed');})().catch(e=>{console.error(e);process.exitCode=1;});
