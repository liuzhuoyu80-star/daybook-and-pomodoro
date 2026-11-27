const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const addresses = Object.values(os.networkInterfaces()).flat();
const available = addresses.filter(a => a.family === 'IPv4');
const preferred = available.find(a => !a.internal && /^(192\.168\.|10\.|172\.(1[6-9]|2\d|3[01])\.)/.test(a.address));
const host = process.env.DAYBOOK_HOST || preferred?.address || '127.0.0.1';
const port = Number(process.env.DAYBOOK_PORT || 8768);
if (!available.some(a => a.address === host)) throw Error('DAYBOOK_HOST 必须是本机的 IPv4 地址。');
if (!Number.isInteger(port) || port < 1 || port > 65535) throw Error('DAYBOOK_PORT 需要为 1–65535 的整数。');
const archive = require('./archive.cjs').archiveHandler(host, port);
http.createServer((req, res) => {
  if (req.url.startsWith('/api/archive')) return archive(req,res);
  if (!['/', '/index.html'].includes(req.url.split('?')[0])) return res.writeHead(404).end();
  if (!['GET', 'HEAD'].includes(req.method)) return res.writeHead(405).end();
  fs.readFile(path.join(__dirname, 'dist', 'index.html'), (err, data) => {
    if (err) return res.writeHead(500).end();
    res.writeHead(200, {'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-cache'}).end(req.method === 'HEAD' ? undefined : data);
  });
})
.on('error', err => {
  console.error(err.code === 'EADDRINUSE' ? '端口已占用。请关闭重复运行的服务，或通过 DAYBOOK_PORT 设置其他端口。' : err.message);
  process.exitCode = 1;
})
.listen(port, host, () => console.log('日程簿已启动，请在浏览器打开 http://' + host + ':' + port + '/'));
