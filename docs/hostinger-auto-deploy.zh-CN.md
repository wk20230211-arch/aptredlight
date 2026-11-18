# APTREDLIGHT：一次绑定，后续自动覆盖

目标：把已核验的 Sites 网站自动发布到 `https://www.aptredlight.com`。官网发布仍由 `.openai/site-release.json` 指定项目、版本、源码提交与发布清单 SHA256。上传 ZIP 不再是日常步骤。

## 自动流程

1. Sites 新版发布完成，更新 GitHub `main` 的 `.openai/site-release.json`。
2. `Sync Sites release to production` 下载并逐文件验证发布，保留带校验索引的 `hostinger-static-release` artifact，并更新 `production` 分支。
3. `Deploy verified release to Hostinger` 从上一步的成功事件自动触发，下载同一个 artifact，再与当前指针核对。
4. 通过已绑定的 SSH 部署身份连接 Hostinger；先在网页根目录之外备份即将覆盖的文件，再覆盖已验证的发布文件。原有上传、后端和其他不属于本次发布的文件保留。
5. 检查正式域名的版本记录、首页与关键脚本字节。失败自动恢复本次备份，并保留失败回执；通过后才记录部署成功。

此流程用 `workflow_run` 串联，避免依赖 GitHub Actions 自己推送 `production` 后再触发另一个 push workflow。每次部署串行执行；相同旧版本或不匹配的发布不会被冒充为最新版本。

## 只需一次的 Hostinger / GitHub 绑定

这一步必须由有权管理该站点和 GitHub 仓库的人完成。不要把私钥或账号密码发送到聊天或写进代码。

1. 在 Hostinger 中打开 `aptredlight.com` 的 SSH Access，启用该站点可用的 SSH 访问，并添加专用于部署的公钥。该服务器需要 `python3` 和 `tar`。保留对应私钥用于下一步。
2. 打开 [GitHub Actions Secrets 设置](https://github.com/wk20230211-arch/aptredlight/settings/secrets/actions)，添加两个 secrets：

   | 名称 | 内容 |
   | --- | --- |
   | `HOSTINGER_SSH_PRIVATE_KEY` | 与 Hostinger 部署公钥配对的完整私钥 |
   | `HOSTINGER_KNOWN_HOSTS` | 从可信已有 SSH 连接或 Hostinger 核验过的服务器身份记录，不要直接信任未经核对的扫描结果 |

3. 打开同页的 Variables 标签，添加 `HOSTINGER_SSH_HOST`，填写 Hostinger SSH Access 显示的服务器地址。该地址不包含协议、用户名或路径。
4. 以下值来自项目保存的托管记录。端口可通过 `HOSTINGER_SSH_PORT` variable 覆盖；用户名和根目录锁定在当前配置，若 Hostinger 后台已变更，需先核对目标并同时更新 `.hostinger/deploy.json` 与脚本的目标用户约束：

   | 配置项 | 当前值 |
   | --- | --- |
   | `HOSTINGER_SSH_PORT` | `65002` |
   | SSH 用户 | `u469397229` |
   | 网站根目录 | `/home/u469397229/domains/aptredlight.com/public_html` |

5. 配置完成后，重新运行此前因 `needs_setup` 失败的部署 job，或在 [自动部署工作流](https://github.com/wk20230211-arch/aptredlight/actions/workflows/hostinger-deploy.yml) 使用 Run workflow，输入最近成功的同步 run ID。该同步 run 必须包含 `hostinger-static-release` artifact；旧的、不含此 artifact 的 run 需要先重跑同步。

绑定后，后续更新发布指针就自动完成覆盖、线上验证与失败回滚，不用再次填写连接信息或手动上传文件。当前 Hostinger MCP 连接返回 0 个站点并不等于以上 SSH 身份已绑定；自动化不能凭空取得站点凭据。

## 如何确认已上线

- `validate-automation` 成功：仅证明自动化代码通过测试。
- `needs_setup`：缺少一次性绑定，未部署。
- `hostinger-validation-receipt.json`：证明下载的 artifact 与指定发布一致。
- `hostinger-deployment-receipt.json`：记录真实部署、线上检查及回滚结果。以 `status` 和 HTTP 检查结果判断成功，不能仅看到 GitHub `production` 已更新就认为正式域名已更新。
- 正式站的 `/source-release.json` 必须与当前指针一致，首页与脚本必须通过字节核对。

## 恢复和回滚

部署备份位于站点根目录以外、同一 SSH 用户的私有目录，不提供公开下载。自动验证失败会尝试恢复本次修改。若连接中断导致结果未知，应先查回执和远端锁／备份，禁止把未确认状态记成成功。显式历史回滚需要使用经核验的旧发布与脚本提供的回滚命令，并重新完成线上验证。
