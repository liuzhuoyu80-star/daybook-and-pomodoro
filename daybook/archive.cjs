'use strict';
const fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {randomUUID}=require('node:crypto');
const datePattern = /^\d{4}-\d{2}-\d{2}$/;
const fields = {thoughts:['known','stuck','guess','resume'], deliveries:['done','help','next']};
const problem = (status,message) => Object.assign(new Error(message),{status});

function descriptions(item){
  if(item.descriptions===undefined)return {};
  const notes=item.descriptions;
  if(!notes||typeof notes!=='object'||Array.isArray(notes))throw problem(400,'描述格式无效');
  const result={};
  for(const [kind,value] of Object.entries(notes)){
    if(!Object.hasOwn(fields,kind)||!value||fields[kind].some(key=>typeof value[key]!=='string'))throw problem(400,'描述字段无效');
    result[kind]=Object.fromEntries(fields[kind].map(key=>[key,value[key]]));
  }
  return {descriptions:result};
}
function validateRecord(input,date) {
  if(!input || input.date!==date) throw problem(400,'记录日期不一致');
  const result={date};
  for(const [kind,keys] of Object.entries(fields)){
    if(!Array.isArray(input[kind])) throw problem(400,'记录格式无效');
    result[kind]=input[kind].map(item=>{
      const values={};
      for(const key of ['title',...keys]){
        if(typeof item?.[key]!=='string') throw problem(400,'记录字段格式无效');
        values[key]=item[key];
      }
      return {...values,...descriptions(item)};
    });
  }
  for(const key of ['completed','pending']){
    if(typeof input[key]!=='string') throw problem(400,'任务摘要格式无效');
    result[key]=input[key];
  }
  if(input.hours!==undefined || input.tasks!==undefined){
    if(!Array.isArray(input.hours)||input.hours.length!==4||input.hours.some(n=>!Number.isFinite(n)||n<0||n>24)||!Array.isArray(input.tasks))throw problem(400,'精力配比或任务格式无效');
    result.hours=input.hours;
    const ids=new Set();
    result.tasks=input.tasks.map(t=>{
      if(typeof t?.id!=='string'||!t.id||ids.has(t.id)||typeof t.title!=='string'||!Number.isInteger(t.group)||t.group<0||t.group>3||typeof t.delivery!=='boolean'||!['open','done','paused'].includes(t.status))throw problem(400,'任务格式无效');
      ids.add(t.id);
      return {id:t.id,title:t.title,group:t.group,delivery:t.delivery,status:t.status,...descriptions(t)};
    });
  }
  return result;
}

async function body(req){
  let size=0,parts=[];
  for await(const part of req){
    size+=part.length;
    if(size>480000)throw problem(413,'单日记录超过 480 KB，请缩短后再上传。');
    parts.push(part);
  }
  try{return JSON.parse(Buffer.concat(parts).toString('utf8'))}
  catch{throw problem(400,'请求格式无效');}
}
function directory(kind,user){
  return path.join(process.env.LOCALAPPDATA||os.homedir(),'DaybookData',kind,user);
}
function days(folder){
  try{return fs.readdirSync(folder).filter(name=>/^\d{4}-\d{2}-\d{2}\.json$/.test(name)).sort().reverse()}
  catch(error){if(error.code==='ENOENT')return [];throw error}
}
const registryFile=()=>path.join(process.env.LOCALAPPDATA||os.homedir(),'DaybookData','users.json');
function profiles(){
  try{return JSON.parse(fs.readFileSync(registryFile(),'utf8'))}
  catch(error){if(error.code!=='ENOENT')throw error;return [{id:'user1',name:'用户1'},{id:'user2',name:'用户2'}]}
}
function inventory(id){
  const dates=kind=>days(directory(kind,id)).map(file=>file.slice(0,-5));
  return {drafts:dates('drafts'),history:dates('history')};
}
function changeProfiles(change){
  const list=profiles(),item=list.find(p=>p.id===change?.id);
  if(change?.op==='delete'){
    if(!item)throw problem(404,'此用户已移除。');
    if(JSON.stringify(inventory(item.id))!==JSON.stringify(change.dates))throw problem(409,'日期清单有变化，请重新查看后删除。');
    list.splice(list.indexOf(item),1);
  }else{
    const name=typeof change?.name==='string'?change.name.trim():'';
    if(!name||name.length>40)throw problem(400,'用户名需要 1 到 40 个字符。');
    if(list.some(p=>p.name===name&&(change.op!=='rename'||p.id!==change.id)))throw problem(409,'该名称已在使用。');
    if(change.op==='add')list.push({id:'u-'+randomUUID(),name});
    else if(change.op==='rename'&&item)item.name=name;
    else throw problem(400,'用户操作无效，请刷新重试。');
  }
  const file=registryFile(),tmp=file+'.'+randomUUID()+'.tmp';
  fs.mkdirSync(path.dirname(file),{recursive:true});
  try{fs.writeFileSync(tmp,JSON.stringify(list,null,2));fs.renameSync(tmp,file)}
  finally{fs.rmSync(tmp,{force:true})}
  return list;
}
function localRecord(kind,date,user,value){
  const folder=directory(kind,user);
  const file=path.join(folder,date+'.json');
  let current=null;
  try{current=JSON.parse(fs.readFileSync(file,'utf8'))}catch(error){if(error.code!=='ENOENT')throw error}
  if(value===undefined){
    if(current)return current;
    if(kind==='history')throw problem(404,'这一天还没有归档记录。');
    const previous=days(folder).find(name=>name<date+'.json');
    const carry=previous?JSON.parse(fs.readFileSync(path.join(folder,previous),'utf8')).record:null;
    return {version:null,record:null,carry:carry?{date:carry.date,thoughts:carry.thoughts}:null};
  }
  const record=validateRecord(value?.record,date);
  if(kind==='drafts'&&!record.tasks)throw problem(400,'草稿缺少整日工作台内容');
  if(value.version!==(current?.version??null))throw problem(409,'这一天已有其他版本。');
  const result={version:randomUUID(),record};
  fs.mkdirSync(folder,{recursive:true});
  const tmp=file+'.'+result.version+'.tmp';
  try{fs.writeFileSync(tmp,JSON.stringify(result));fs.renameSync(tmp,file)}
  finally{fs.rmSync(tmp,{force:true})}
  return result;
}
function archiveHandler(lan,port){
  return async(req,res)=>{
    function send(code,data){res.writeHead(code,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'});res.end(JSON.stringify(data))}
    try{
      const host=lan+':'+port;
      if(req.headers.host!==host || (req.headers.origin && req.headers.origin!=='http://'+host) || req.headers['sec-fetch-site']==='cross-site')
        throw problem(403,'请从局域网工作台访问。');
      if(['POST','PUT'].includes(req.method) && req.headers['content-type']!=='application/json')throw problem(415,'需要 JSON 内容');
      if(req.url==='/api/archive/users'){
        if(req.method==='GET')return send(200,profiles());
        if(req.method==='POST')return send(200,changeProfiles(await body(req)));
        throw problem(405,'操作无效');
      }
      const user=req.headers['x-daybook-user'];
      const membership=()=>{if(!profiles().some(p=>p.id===user))throw problem(404,'此用户已移除，请重新选择用户。')};
      membership();
      if(req.url==='/api/archive/user-dates'&&req.method==='GET')return send(200,inventory(user));
      const draft=req.url.startsWith('/api/archive/draft/');
      const date=req.url.slice((draft?'/api/archive/draft/':'/api/archive/').length);
      const listing=req.url==='/api/archive';
      if(!listing && (!req.url.startsWith('/api/archive/') || !datePattern.test(date) || new Date(date+'T12:00:00Z').toJSON()?.slice(0,10)!==date))throw problem(404,'日期无效');
      const kind=draft?'drafts':'history';
      if(listing&&req.method==='GET')return send(200,{dates:days(directory('history',user)).map(name=>name.slice(0,-5))});
      if(!listing&&req.method==='GET')return send(200,localRecord(kind,date,user));
      if(!listing&&req.method==='PUT'){const value=await body(req);membership();return send(200,localRecord(kind,date,user,value))}
      throw problem(405,'操作无效');
    }catch(error){send(error.status||500,{error:error.status?error.message:'服务电脑读写记录失败，请检查本机数据目录。'})}
  };
}
module.exports={archiveHandler};
