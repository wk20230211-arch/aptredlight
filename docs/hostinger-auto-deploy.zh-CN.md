# APTREDLIGHT：一次绑定，后续自动覆盖

目标：把已核验的 Sites 网站自动发布到 `https://www.aptredlight.com`。官网发布仍由 `.openai/site-release.json` 指定项目、版本、源码提交与发布清单 SHA256。上传 ZIP 不再是日常步骤。

## 自动流程

1. Sites 新版发布完成，更新 GitHub `main` 的 `.openai/site-release.json`。
2. `Sync Sites release to production` 下载并逐文件验证发布，保留带校验索引的 `hostinger-static-release` artifact，并更新 `production` 分支。
3. `Deploy verified release to Hostinger` 从上一步的成功事件自动触发，下载同一个 artifact，再与当前指针核对。
4. 通过已绑定的 SSH 部署身份连接 Hostinger；先在网页根目录之外备份即将覆盖的文件，再覆盖已验证的发布文件。原有上传、后端和其他不属于本次发布的文件保留。
5. 检查正式域名的版本记录、首页与关键脚本字节。失败自动恢复本次备份，并保留失败回执；通过后才记录部署成功。

此流程用 `workflow_run` 串联，避免依赖 GitHub Actions 自己推送 `production` 后再触发另一个 push workflow。每次部署串行执行；相同旧版本或不匹配的发布不会被冒充为最新版本。

## 只需一次的部署密钥绑定

站点管理员已提供 hPanel SSH Access 截图。以下公开配置已登记在 `.hostinger/deploy.json`，不用再手动添加服务器地址变量或 `HOSTINGER_KNOWN_HOSTS` secret：

| 配置项 | 已登记值 |
| --- | --- |
| SSH 服务器 | `45.87.81.210` |
| 端口 | `65002` |
| 用户 | `u469397229` |
| 网站根目录 | `/home/u469397229/domains/aptredlight.com/public_html` |
| ED25519 指纹 | `SHA256:4mfb2c67Lhi/idZu+pyYocKONELisV4IInwlFdR8t98` |

每次部署先读取服务器的公开 ED25519 主机密钥，与 hPanel 提供的 SHA256 指纹逐字符比对。匹配后才加载部署私钥；不匹配即停止，不自动接受新的主机身份。服务器迁移或主机密钥轮换时，先通过 hPanel 核对并更新该指纹。

剩下只需要一对专用部署密钥：**公钥授权给 Hostinger；配套私钥放入 GitHub Secrets**。密码、私钥都不要发送到聊天或提交到代码。

### Windows 一次性操作

1. 在自己的 Windows 电脑下载并阅读 [Connect-APTREDLIGHT-v2.ps1](../setup/Connect-APTREDLIGHT-v2.ps1)，按 [Windows 配置说明](../setup/WINDOWS-SETUP.zh-CN.txt)运行。脚本先核验服务器身份，再在本机生成或安全复用专用密钥。Hostinger SSH 密码仅由你在原生 SSH 密码提示中输入，用于一次性授权公钥。脚本只安装这一条受限公钥，校验服务器端文件所有者、保留既有公钥、避免重复添加，并在检测到并发变更时停止。
2. 若本机已有登录的 GitHub CLI，脚本可直接把私钥通过标准输入保存到正确的 GitHub secret；否则会打开 GitHub 新建 secret 页面，并把私钥仅放到本机剪贴板。Name 填 `HOSTINGER_SSH_PRIVATE_KEY`，Secret 粘贴，点击 Add secret。脚本不把私钥打印到聊天、控制台或上传为文件。
3. 配置完成后回复“已配置”，由助手检查并重跑**最新**的部署任务。此后每次更新发布指针即自动覆盖与验收，无需重复此绑定或上传 ZIP。

GitHub 设置入口：[Actions Secrets](https://github.com/wk20230211-arch/aptredlight/settings/secrets/actions)。服务器需有 `python3` 和 `tar`；脚本及部署流程会检查可用性。Windows 脚本的实际登录步骤必须在站点管理员自己的电脑完成，执行受设备策略限制时联系设备管理员，不更改系统安全策略。

### 已有专用部署密钥

如果 Hostinger 已授权该专用公钥，只需在上述 GitHub 设置中添加一个 secret：

| 名称 | 内容 |
| --- | --- |
| `HOSTINGER_SSH_PRIVATE_KEY` | 与已授权部署公钥配对的完整、适用于无人值守 CI 的 SSH 私钥 |

选择新配置提交后的最新自动部署运行；历史运行使用当时旧版工作流，可能仍要求旧的三项设置。也可以在 [工作流](https://github.com/wk20230211-arch/aptredlight/actions/workflows/hostinger-deploy.yml) 使用 Run workflow，输入最近成功、且包含 `hostinger-static-release` artifact 的同步 run ID。

`HOSTINGER_SSH_HOST` 和 `HOSTINGER_SSH_PORT` variables 只用于经管理员核对的迁移覆盖，日常不需要设置。迁移后的服务器仍须匹配已核验的主机指纹，且用户与网站根目录约束必须一致。

## 如何确认已上线

- `validate-automation` 与 `validate-windows-setup` 成功：分别证明部署逻辑检查通过、Windows PowerShell 5.1 脚本语法可解析；不证明管理员已完成实际密钥绑定或正式域名更新。
- `needs_setup`：缺少一次性绑定，未部署。
- `hostinger-validation-receipt.json`：证明下载的 artifact 与指定发布一致。
- `hostinger-deployment-receipt.json`：记录真实部署、线上检查及回滚结果。以 `status` 和 HTTP 检查结果判断成功，不能仅看到 GitHub `production` 已更新就认为正式域名已更新。
- 正式站的 `/source-release.json` 必须与当前指针一致，首页与脚本必须通过字节核对。

## 恢复和回滚

部署备份位于站点根目录以外、同一 SSH 用户的私有目录，不提供公开下载。自动验证失败会尝试恢复本次修改。若连接中断导致结果未知，应先查回执和远端锁／备份，禁止把未确认状态记成成功。显式历史回滚需要使用经核验的旧发布与脚本提供的回滚命令，并重新完成线上验证。

## Windows 第2步 SeSecurityPrivilege 错误

旧版使用 Set-Acl 写入全新安全描述符，可能触发不必要的审计权限请求。v2只读取Owner与Access，确认现有所有者为当前用户，保留所有者，只用.NET持久化DACL并回读核验。新增Windows测试在专门测试进程移除SeSecurityPrivilege后，用临时普通文本文件验证真实ACL操作；不生成或读取真实SSH私钥。这个测试证明该操作不需要此项特权，不代表所有设备管理策略均已验收。

请改用v2文件；原有专用密钥会安全复用。文件所有者不符时停止并由设备管理员核查，不自动修改所有权或提权。
