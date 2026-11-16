# Deploy the approved Sites website

Canonical domain: https://www.aptredlight.com
Hostinger account: u469397229, domain aptredlight.com.
Publish branch: production. Release control branch: main.

## Publish

1. Edit the APTREDLIGHT Sites source and validate pages, assets, links, JSON-LD and affected interactions. Preserve official canonical URLs, legacy redirects and the buyer-checklist PDF.
2. Run `python scripts/release-manifest.py` in the Sites checkout. Save its manifest SHA-256. Package and deploy this exact source using Sites.
3. After successful Sites publication, update `.openai/site-release.json` on main with the source commit, Sites version and manifest SHA-256. Retain the approved project and origin.
4. Wait for `Sync Sites release to production` to succeed. It verifies the release then pushes production. If verification fails, correct the release instead of weakening verification.
5. Deploy production with Hostinger `hosting_deploy`: domain aptredlight.com, type static, git repository wk20230211-arch/aptredlight, branch production. When Git integration is connected this also enables deployment on subsequent pushes. Otherwise use the supported Hostinger upload and static archive deployment for an archive of production; never use the old main-branch HTML.
6. Verify official `/source-release.json`, the homepage and changed article. Do not report official publication from Sites success alone.

Do not change DNS or mail records. Do not restore the bouncing mailbox. RFQ prepares a WhatsApp message and offers Alibaba; sending is a deliberate visitor action.

## Rollback

The previous public files were downloaded on 2026-11-16, checked against Hostinger's file sizes, and committed on `backup-production-20261116` at `49356ac303fdb04b670e46dad8708897840e188d`. Its website files include `.htaccess`, HTML, assets, robots.txt, sitemap.xml and resources. Keep this branch.

Suspend conflicting publication if necessary, select a verified production commit and deploy its static archive. The pre-cutover backup also contains repository tooling; package only public website files if restoring it. Verify the official domain and align the release pointer before resuming automation.
