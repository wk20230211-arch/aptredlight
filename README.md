# APTREDLIGHT unified website publishing

Official website: https://www.aptredlight.com

The approved website source is the APTREDLIGHT Sites project `appgprj_6addb8c872b081918d711d7bc0c5cbf4`, published at https://aptredlight-wellness.wk20230211.chatgpt.site.

- `main` contains release controls alongside retained legacy website files and tooling. The retained HTML is historical, not the current publication source. Edit in Sites, then update `.openai/site-release.json` after a successful Sites deployment.
- `production` contains verified website files for Hostinger. It is generated; do not make independent content changes there.
- `backup-production-20261116` preserves the previous official website and original `.htaccess` before cutover.

The workflow checks the pinned manifest SHA-256 and every file's size and hash before publishing production. Failed verification leaves production unchanged.

See [DEPLOYMENT.md](DEPLOYMENT.md) for publication and rollback. Website deployment does not publish LinkedIn posts.
