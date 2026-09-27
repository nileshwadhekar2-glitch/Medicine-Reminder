const fs = require('fs'), vm = require('vm');
for (const file of fs.readdirSync('frontend').filter(f=>f.endsWith('.html'))) {
 const html=fs.readFileSync('frontend/'+file,'utf8');
 for(const m of html.matchAll(/<script>([\s\S]*?)<\/script>/g)) new vm.Script(m[1],{filename:file});
 console.log('Syntax OK:',file);
}
const context={window:{fetch: async()=>({ok:true})},Date}; vm.createContext(context);
vm.runInContext(fs.readFileSync('frontend/script.js','utf8'),context);
if(context.escapeHtml(`<img src=x onerror="alert('x')">`).includes('<')) throw Error('Unsafe HTML');
console.log('HTML escaping OK');
