const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const inputFile = process.argv[2];
if (!inputFile) { console.error('Usage: node render.js <file.excalidraw.json>'); process.exit(1); }

const outputFile = inputFile.replace('.excalidraw.json', '.png').replace('.excalidraw', '.png');
const templatePath = path.join(__dirname, 'render_template.html');
const data = JSON.parse(fs.readFileSync(inputFile, 'utf8'));

const elements = (data.elements || []).filter(e => !e.isDeleted);
let minX=Infinity, minY=Infinity, maxX=-Infinity, maxY=-Infinity;
for (const el of elements) {
  const x = el.x||0, y = el.y||0, w = el.width||0, h = el.height||0;
  if ((el.type==='arrow'||el.type==='line') && el.points) {
    for (const [px,py] of el.points) { minX=Math.min(minX,x+px); minY=Math.min(minY,y+py); maxX=Math.max(maxX,x+px); maxY=Math.max(maxY,y+py); }
  } else { minX=Math.min(minX,x); minY=Math.min(minY,y); maxX=Math.max(maxX,x+Math.abs(w)); maxY=Math.max(maxY,y+Math.abs(h)); }
}
const pad=80;
const vpW = Math.min(Math.ceil(maxX-minX+pad*2), 2400);
const vpH = Math.max(Math.ceil(maxY-minY+pad*2), 600);

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: vpW, height: vpH }, deviceScaleFactor: 2 });
  await page.goto('file://' + templatePath);
  await page.waitForFunction('window.__moduleReady === true', { timeout: 30000 });
  const result = await page.evaluate(`window.renderDiagram(${JSON.stringify(data)})`);
  if (!result || !result.success) { console.error('Render failed:', result?.error); await browser.close(); process.exit(1); }
  await page.waitForFunction('window.__renderComplete === true', { timeout: 15000 });
  const svg = await page.$('#root svg');
  if (!svg) { console.error('No SVG found'); await browser.close(); process.exit(1); }
  await svg.screenshot({ path: outputFile });
  await browser.close();
  console.log(outputFile);
})();
