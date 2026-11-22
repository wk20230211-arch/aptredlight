APTREDLIGHT Growth Desk Bridge 1.0.0
WordPress 原生后台入口与私有云工作台联动插件

交付范围
本插件是现有 WordPress／WooCommerce 的可安装后台扩展。它增加 APTREDLIGHT 运营总览、真实商品状态、最近 10 个商品、原生编辑及媒体库入口，并按分组提供现有 Growth Desk 的完整固定模块链接。
云端模块继续运行在 https://aptredlight-growth-desk.wk20230211.chatgpt.site；本插件不会把 R2／CRM／ERP 数据复制进 WordPress，也不把 WP 登录冒充云端授权。

安装前提
1. 已有真实可用的 WordPress 和 WooCommerce 安装。
2. 由有安装插件权限的管理员上传并激活本插件。
3. 不替换主题，不删除 index.html，不重装 WordPress，不更改既有商品、页面或订单。
当前交付没有实际安装或激活到正式站，真实 WordPress 位置及权限仍须先核实。

权限与激活行为
后台页面需要 WordPress 的 edit_products 能力。每个商品的编辑链接还会逐项检查 edit_post(商品ID)；没有 edit_others_products 时仅查询当前作者商品。
激活时仅在不存在 apt_growth_product_operator 角色的情况下新增该角色；存在同名角色时完全不改。它具有商品编辑／发布／删除、产品词条及媒体上传能力，没有 manage_options、manage_woocommerce、订单、主题、插件或用户管理能力。
产品词条的 manage_product_terms 也可能允许 Woo 原生全局属性管理，并非严格只读词条。WordPress 原生删除能力可允许永久删除；云端商品服务仍用自身固定路由将删除收紧为回收站，不能把二者粒度混为一谈。
插件不会创建用户、API Key 或应用程序密码；不会给现有用户自动分配角色。管理员需先审查用户的全部角色和权限，避免其他角色叠加过宽权限。
停用和删除插件不移除现有角色或商品。管理员可在审查用户分配后自行移除该角色。

实际后台页面
进入 WordPress 左侧「APTREDLIGHT 工作台」：
• 商品计数与列表查询现有数据；读取失败显示“尚未读取”，不会生成示例或把失败记为零。
• 商品编辑与新增使用 WooCommerce 原生界面，保留简单、变体等现有商品结构。
• 媒体库沿用 WordPress 原生媒体界面及其权限。
• 页面本身没有商品、订单、站点设置、插件或主题写入代理。

只读连接检查
点击「读取前 10 个商品」后，仅向本后台同源的 wc/v3/products 固定接口发送 GET。它使用当前 WP 登录 Cookie 和临时 X-WP-Nonce，不使用或暴露 Consumer Key、Consumer Secret、应用程序密码、Hostinger Token。
结果仅在当前后台页面安全回显 ID、标题、SKU、状态；不写到 GitHub 日志或交付文件。401／403、404、HTML 200、异常 JSON 和超时都不是成功读取；接口真实成功返回空数组时才显示零项。
此测试成功只证明当前 WP 用户可读该 API，不能替代云端服务凭据绑定和云端只读门槛。

云端联动
模块链接固定在已知的私有 Growth Desk origin，不接受用户输入任意外链或 API 地址。云端各模块仍需原有账号、Sites 访问授权及其自身角色白名单。
插件不使用 iframe，不嵌入长效 bearer token，不持久保存 WordPress nonce；ERP 和客户数据仍留在原有私有数据存储中。

验收清单
• 用无 edit_products 的 WP 用户验证不能打开后台页或加载其资产。
• 用权限受限的产品用户验证仅看到其允许的商品及操作。
• 核对同名角色激活时未被改动；没有创建用户或凭据。
• 验证原有主题、页面、商品、媒体、订单与设置保持原样。
• 单独执行 API 前 10 个商品只读检查，再验收云端连接。
• 点击云端模块后确认仍走原账号登录，不能因 WP 登录绕过私有工作台。

技术边界
PHP 7.4+、WordPress 6.0+；WooCommerce 必须已经启用。资产仅加载在本插件自己的后台页面，CSS 全部限定在 #aptgd-root，不影响原后台或前台。
本插件注册 admin_menu 和 admin_enqueue_scripts，没有前台钩子、公开 REST 代理或计划任务；激活钩子只新增缺失的专用角色。
