import { chromium } from 'playwright';
import { writeFileSync, mkdirSync } from 'node:fs';
const BASE='https://www.aptredlight.com';
const browser=await chromium.launch({headless:true});
const ctx=await browser.newContext({viewport:{width:390,height:844},deviceScaleFactor:1,acceptDownloads:true});
const page=await ctx.newPage();
const problems=[];
try {
  const urls=['/','/rfq.html','/catalog.html','/quality-process.html','/resources/oem-private-label-buyers-checklist.pdf'];
  for(const path of urls) {
    const response=await ctx.request.get(BASE+path, {timeout:30000});
    console.log('HTTP',response.status(),path,'BYTES',(await response.body()).length);
    if(response.status()!==200)throw Error('HTTP non-200 '+path);
    if(path.endsWith('.pdf')){
      const buffer=await response.body();
      if(!buffer.subarray(0,4).equals(Buffer.from('%PDF')))throw Error('Checklist is not a PDF');
      if(buffer.length<4000)throw Error('Checklist PDF unexpectedly small');
    }
  }
  await page.goto(BASE+'/rfq.html?product=t300-ultra',{waitUntil:'domcontentloaded',timeout:30000});
  await page.locator('h1').getByText('Request a red light therapy OEM/ODM quotation.').waitFor();
  console.log('PREFILLED_MODEL', await page.locator('select[name=product]').inputValue());
  if((await page.locator('select[name=product]').inputValue())!=='T300 Ultra — flagship panel')throw Error('Product parameter did not preselect model');
  const form=page.locator('#rfq-form');
  if(await form.evaluate(el=>el.checkValidity()))throw Error('Empty RFQ form unexpectedly valid');
  await page.locator('input[name=company]').fill('APTREDLIGHT QA Test Buyer');
  await page.locator('input[name=contact]').fill('Internal Quality Tester');
  await page.locator('input[name=email]').fill('qa@example.com');
  await page.locator('select[name=market]').selectOption({label:'United Kingdom'});
  await page.locator('select[name=quantity]').selectOption({label:'100–499 units'});
  await page.locator('textarea[name=details]').fill('Request optical specification and private-label packaging proposal for testing only; do not treat as a live lead.');
  await page.locator('input[name=consent]').check();
  if(!(await form.evaluate(el=>el.checkValidity())))throw Error('Completed RFQ unexpectedly invalid');
  const submit=page.getByRole('button',{name:'Continue RFQ on WhatsApp'});
  const height=await submit.evaluate(el=>el.getBoundingClientRect().height);
  console.log('MOBILE_BUTTON_HEIGHT',height);
  if(height<44)throw Error('Touch button below 44px');
  await ctx.route('https://wa.me/**',route=>route.fulfill({status:200,contentType:'text/html',body:'<html>WhatsApp test intercepted — no message sent</html>'}));
  const popupPromise=page.waitForEvent('popup',{timeout:10000});
  await submit.click();
  const popup=await popupPromise;
  const link=popup.url();
  console.log('WHATSAPP_PREFILL_URL',link);
  if(!link.includes('wa.me/8618823435519')||!decodeURIComponent(link).includes('APTREDLIGHT QA Test Buyer')||!decodeURIComponent(link).includes('100–499 units'))throw Error('WhatsApp message missing lead details');
  if(!(await page.locator('#rfq-status').textContent()).includes('press Send'))throw Error('User-delivery notice missing');
  mkdirSync('artifacts',{recursive:true});
  await page.screenshot({path:'artifacts/aptredlight-rfq-mobile.png',fullPage:true});
  console.log('PASS: responsive RFQ, PDF download, HTML pages, required validation and WhatsApp handoff (NO ACTUAL MESSAGE SENT)');
} catch(error) {console.error('FAIL:',error.stack||error);process.exitCode=1;}
finally {await browser.close();}
