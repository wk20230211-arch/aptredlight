=== APTREDLIGHT Growth Desk Bridge ===
Contributors: aptredlight
Tags: woocommerce, administration, product-management
Requires at least: 6.0
Requires PHP: 7.4
Stable tag: 1.0.0
License: GPL-2.0-or-later
License URI: https://www.gnu.org/licenses/gpl-2.0.html

WordPress 原生商品管理入口与私有 Growth Desk 模块联动。

== Description ==

增加 APTREDLIGHT 运营总览、现有 WooCommerce 商品状态、最近 10 个商品、原生商品编辑与媒体库入口，以及完整私有云工作台模块的固定链接。

这是一套 WordPress 后台入口和云端深链联动；云端模块仍运行在原 Growth Desk，不复制 CRM／ERP／R2 数据、不自动代登录，也不把 WP 登录当成云端授权。

插件不替换主题、不重建页面、不改动既有商品和订单，不提供公开 REST 代理。后台页需要 edit_products 能力，每行编辑还检查 edit_post(ID)。没有编辑他人商品能力时只查询本人的商品。

只读接口按钮使用当前 WordPress Cookie 和动态 WP REST nonce，向同源固定 wc/v3/products 发送 GET。不会读取、保存或向浏览器传送 WooCommerce Key、应用程序密码或 Hostinger Token。

== Installation ==

1. 先确认已有可用的 WordPress 与 WooCommerce；不要以重装官网来修复连接。
2. 管理员上传本插件 ZIP 并激活。
3. 打开左侧 APTREDLIGHT 工作台，核对真实商品状态及逐项权限。
4. 点击“读取前 10 个商品”完成 WP 本地只读验证。
5. 云端服务连接与角色白名单需另行绑定，不能把本地测试等同云端已接通。

激活仅在专用角色 apt_growth_product_operator 不存在时新增该角色；同名角色不改，不创建用户或凭据。角色仅涉及产品、产品词条和媒体，无网站设置、订单、插件、主题或用户管理能力。产品词条能力可能覆盖 Woo 全局属性；WP 原生删除能力不等于云端服务的仅回收站限制。完整边界与验收清单见 README.zh-CN.txt。

== Frequently Asked Questions ==

= 是否会安装 WordPress 或 WooCommerce？ =

不会。目标安装及权限尚未就绪时保持未连接，不自动安装或重建站点。

= 是否把云端全部数据搬入 WordPress？ =

不会。全部真实模块列为固定入口，继续使用原有云端身份和私有数据存储。

= 是否修改正式站前台？ =

不会。仅在本插件自己的后台页面加载样式和脚本，没有前台钩子。

== Changelog ==

= 1.0.0 =
Initial product administration bridge and private Growth Desk navigation.
