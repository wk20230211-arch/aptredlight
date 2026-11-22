<?php
/**
 * Plugin Name: APTREDLIGHT Growth Desk Bridge
 * Description: Product-only WordPress administration and private Growth Desk navigation. Preserves the existing storefront.
 * Version: 1.0.0
 * Requires at least: 6.0
 * Requires PHP: 7.4
 * Requires Plugins: woocommerce
 * Author: APTREDLIGHT
 * License: GPL-2.0-or-later
 */

namespace APTREDLIGHT\GrowthDesk;

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

const VERSION      = '1.0.0';
const MENU_SLUG    = 'apt-growth-desk';
const CLOUD_ORIGIN = 'https://aptredlight-growth-desk.wk20230211.chatgpt.site';
const ROLE_SLUG    = 'apt_growth_product_operator';

$aptgd_page_hook = '';

/** This optional plugin creates only a missing product role, never a user or key. */
function role_capabilities() {
	return array(
		'read'                      => true,
		'edit_products'             => true,
		'edit_others_products'       => true,
		'edit_private_products'      => true,
		'edit_published_products'    => true,
		'publish_products'          => true,
		'read_private_products'     => true,
		'delete_products'           => true,
		'delete_private_products'   => true,
		'delete_published_products' => true,
		'delete_others_products'     => true,
		'assign_product_terms'       => true,
		'manage_product_terms'       => true,
		'edit_product_terms'         => true,
		'upload_files'              => true,
	);
}

function activate() {
	if ( get_role( ROLE_SLUG ) ) {
		return;
	}
	add_role( ROLE_SLUG, 'APT 产品运营（仅商品）', role_capabilities() );
}

/** Server-owned destinations only; this is navigation, not a credential proxy. */
function cloud_modules() {
	return array(
		array( 'overview', '经营总览', '增长、任务与业务状态', '总览与信任' ),
		array( 'trustBoard', '全链路制造信任看板', '研发、产品、证据与交付', '总览与信任' ),
		array( 'wooProducts', '云端商品管理', '商品、SKU、库存、图片与保存回执', '产品与资料' ),
		array( 'productsLibrary', '产品资料库', '型号参数与证据关联', '产品与资料' ),
		array( 'assetsLibrary', '图库与视频', '按 SKU 管理视觉资产', '产品与资料' ),
		array( 'certificatesLibrary', '证书管理', '证书范围与单品核验', '产品与资料' ),
		array( 'evidence', '证据中心', '可核验资料与来源', '产品与资料' ),
		array( 'search', '搜索表现', 'Google 自然搜索数据', '增长与内容' ),
		array( 'ga4Analytics', 'GA4 网站统计', '网站访问与转化数据', '增长与内容' ),
		array( 'keywords', '关键词机会', '关键词、长尾词与意图', '增长与内容' ),
		array( 'articles', '文章一览', '内容资产与发布状态', '增长与内容' ),
		array( 'aiFunnel', 'AI 来源与漏斗', 'AI 引荐与询盘归因', '增长与内容' ),
		array( 'geoBrandOfficer', 'GEO 品牌运营', '内容与 AI 引荐复盘', '增长与内容' ),
		array( 'campaignDrafts', '广告草稿与素材', '创意、文案与投放准备', '增长与内容' ),
		array( 'competitors', '竞品情报', '采购比较与市场信息', '增长与内容' ),
		array( 'buyerObjections', '采购异议监测', '品牌负面信息与采购疑问', '增长与内容' ),
		array( 'crmLeads', '真实询盘 CRM', '线索确认、来源与跟进', '销售与转化' ),
		array( 'erpPipeline', '客户成交全链路', '客户、报价、样品与订单跟进', '销售与转化' ),
		array( 'pipeline', '转化工作流', '触达、询盘与销售转化', '销售与转化' ),
		array( 'growthExecution', '执行路线图', '负责人、任务与验收记录', '协作与交付' ),
		array( 'actions', '优化交付', '已完成动作与待办', '协作与交付' ),
		array( 'teamWorkflow', '协作规范与岗位职责', '美工、工程、品质与销售对齐', '协作与交付' ),
		array( 'standardsLibrary', '建设规范与验收', '交付标准和待办', '协作与交付' ),
	);
}

function cloud_module_groups() {
	$groups = array();
	foreach ( cloud_modules() as $module ) {
		$groups[ $module[3] ][] = $module;
	}
	return $groups;
}

function register_menu() {
	global $aptgd_page_hook;
	$aptgd_page_hook = add_menu_page(
		'APTREDLIGHT 运营工作台', 'APTREDLIGHT 工作台', 'edit_products',
		MENU_SLUG, __NAMESPACE__ . '\\render_page', 'dashicons-screenoptions', 56
	);
	add_submenu_page( MENU_SLUG, '运营总览', '运营总览', 'edit_products', MENU_SLUG, __NAMESPACE__ . '\\render_page' );
	add_submenu_page( MENU_SLUG, '所有商品', '所有商品（WooCommerce）', 'edit_products', 'edit.php?post_type=product' );
	add_submenu_page( MENU_SLUG, '新增商品', '新增商品', 'edit_products', 'post-new.php?post_type=product' );
	add_submenu_page( MENU_SLUG, '媒体资料', '媒体资料', 'upload_files', 'upload.php' );
}

function enqueue_assets( $hook ) {
	global $aptgd_page_hook;
	if ( ! $aptgd_page_hook || $hook !== $aptgd_page_hook || ! current_user_can( 'edit_products' ) ) {
		return;
	}
	wp_enqueue_style( 'aptgd-admin', plugins_url( 'assets/admin.css', __FILE__ ), array(), VERSION );
	wp_enqueue_script( 'aptgd-admin', plugins_url( 'assets/admin.js', __FILE__ ), array(), VERSION, true );
	$config = array(
		'productsUrl' => rest_url( 'wc/v3/products' ),
		'nonce'       => wp_create_nonce( 'wp_rest' ),
		'cloudOrigin' => CLOUD_ORIGIN,
	);
	wp_add_inline_script(
		'aptgd-admin',
		'window.APTGrowthDeskConfig=' . wp_json_encode( $config, JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT ) . ';',
		'before'
	);
}

/** Query permissions follow the existing WordPress account, never browser role text. */
function product_query_scope() {
	$args = array( 'post_type' => 'product', 'perm' => 'readable', 'suppress_filters' => false );
	if ( ! current_user_can( 'edit_others_products' ) ) {
		$args['author'] = get_current_user_id();
	}
	return $args;
}

function product_counts() {
	$counts = array();
	foreach ( array( 'publish', 'draft' ) as $status ) {
		$args = array_merge( product_query_scope(), array(
			'post_status' => $status, 'posts_per_page' => 1, 'fields' => 'ids',
			'no_found_rows' => false, 'cache_results' => false,
		) );
		$query = new \WP_Query( $args );
		if ( ! isset( $query->found_posts ) || ! is_numeric( $query->found_posts ) || $query->found_posts < 0 ) {
			throw new \RuntimeException( 'Product count unavailable.' );
		}
		$counts[ $status ] = (int) $query->found_posts;
	}
	return $counts;
}

function recent_products() {
	$statuses = array( 'publish', 'draft', 'pending', 'future' );
	if ( current_user_can( 'read_private_products' ) ) {
		$statuses[] = 'private';
	}
	$ids = get_posts( array_merge( product_query_scope(), array(
		'post_status' => $statuses, 'numberposts' => 10, 'posts_per_page' => 10,
		'fields' => 'ids', 'orderby' => 'date', 'order' => 'DESC', 'no_found_rows' => true,
	) ) );
	if ( ! is_array( $ids ) ) {
		throw new \RuntimeException( 'Product list unavailable.' );
	}
	$products = array();
	foreach ( array_slice( $ids, 0, 10 ) as $id ) {
		$product = wc_get_product( (int) $id );
		if ( $product ) {
			$products[] = $product;
		}
	}
	return $products;
}

function status_label( $status ) {
	$labels = array( 'publish' => '已发布', 'draft' => '草稿', 'pending' => '待审核', 'private' => '私有', 'future' => '定时发布' );
	return isset( $labels[ $status ] ) ? $labels[ $status ] : $status;
}

function render_page() {
	if ( ! current_user_can( 'edit_products' ) ) {
		wp_die( esc_html( '当前账号没有商品管理权限。' ), '', array( 'response' => 403 ) );
		return;
	}
	$ready = function_exists( 'wc_get_product' );
	$counts = null;
	$products = null;
	if ( $ready ) {
		try { $counts = product_counts(); } catch ( \Throwable $error ) { $counts = null; }
		try { $products = recent_products(); } catch ( \Throwable $error ) { $products = null; }
	}
	$scope = current_user_can( 'edit_others_products' ) ? '当前账号可读取的商品范围' : '仅当前账号拥有的商品';
	?>
	<div class="wrap" id="aptgd-root">
		<header class="aptgd-header">
			<div><p class="aptgd-eyebrow">APTREDLIGHT · WORDPRESS OPERATIONS</p><h1>产品与增长运营后台</h1><p>保留现有 WordPress 与 WooCommerce 结构，将商品操作和私有云工作台放在同一个入口。</p></div>
			<a class="aptgd-button aptgd-button-light" href="<?php echo esc_url( CLOUD_ORIGIN . '/#wooProducts' ); ?>" target="_blank" rel="noopener noreferrer">打开云端商品管理</a>
		</header>
		<div class="aptgd-alert"><strong>两个后台，分别授权</strong><p>WordPress 登录只授予当前 WP 账号的权限。云端工作台仍使用原 ChatGPT 账号和工作台白名单；本插件不复制客户数据、不转移 API 密钥，也不绕过云端访问控制。</p></div>
		<?php if ( ! $ready ) : ?>
			<div class="aptgd-alert aptgd-alert-warning"><strong>WooCommerce 尚未就绪</strong><p>未检测到可用的 WooCommerce 商品函数。本插件不会安装或启用 WooCommerce，也不会重建站点。请由站点管理员先核实当前安装。</p></div>
		<?php endif; ?>
		<section class="aptgd-stats" aria-label="当前 WordPress 商品状态">
			<article><span>已发布商品</span><strong><?php echo null === $counts ? '—' : esc_html( number_format_i18n( $counts['publish'] ) ); ?></strong><small><?php echo esc_html( $scope ); ?></small></article>
			<article><span>草稿商品</span><strong><?php echo null === $counts ? '—' : esc_html( number_format_i18n( $counts['draft'] ) ); ?></strong><small>真实查询；读取失败不填零</small></article>
			<article><span>当前账号操作范围</span><strong class="aptgd-stat-text"><?php echo current_user_can( 'publish_products' ) ? '可编辑与发布' : '按现有权限审核'; ?></strong><small>全部操作仍由 WordPress 能力检查决定</small></article>
			<article><span>云端访问状态</span><strong class="aptgd-stat-text">独立登录</strong><small>不以 WordPress 登录冒充云端授权</small></article>
		</section>
		<div class="aptgd-main-grid">
			<section class="aptgd-panel">
				<div class="aptgd-panel-head"><div><h2>最近 10 个商品</h2><p>使用既有 WooCommerce 数据，按当前 WP 权限读取。</p></div><a class="aptgd-button" href="<?php echo esc_url( admin_url( 'edit.php?post_type=product' ) ); ?>">所有商品</a></div>
				<?php if ( ! $ready || null === $products ) : ?>
					<p class="aptgd-empty">商品列表尚未读取成功；这里不会生成示例商品。</p>
				<?php elseif ( ! $products ) : ?>
					<p class="aptgd-empty">真实读取成功，当前账号可见范围内没有商品。</p>
				<?php else : ?>
					<div class="aptgd-table-wrap"><table><thead><tr><th>ID</th><th>商品</th><th>SKU</th><th>状态</th><th>操作</th></tr></thead><tbody>
					<?php foreach ( $products as $product ) : $id = (int) $product->get_id(); ?>
						<tr><td><?php echo esc_html( $id ); ?></td><td><?php echo esc_html( $product->get_name() ); ?></td><td class="aptgd-mono"><?php echo esc_html( $product->get_sku() ?: '未填写' ); ?></td><td><span class="aptgd-tag"><?php echo esc_html( status_label( $product->get_status() ) ); ?></span></td><td><?php if ( current_user_can( 'edit_post', $id ) ) : ?><a href="<?php echo esc_url( get_edit_post_link( $id, 'raw' ) ); ?>">原生编辑</a><?php else : ?><span>只读</span><?php endif; ?></td></tr>
					<?php endforeach; ?>
					</tbody></table></div>
				<?php endif; ?>
			</section>
			<aside class="aptgd-panel">
				<div class="aptgd-panel-head"><div><h2>商品操作</h2><p>沿用 WooCommerce 原生编辑器。</p></div></div>
				<div class="aptgd-side-actions"><a class="aptgd-button aptgd-button-primary" href="<?php echo esc_url( admin_url( 'post-new.php?post_type=product' ) ); ?>">新增商品或草稿</a><?php if ( current_user_can( 'upload_files' ) ) : ?><a class="aptgd-button" href="<?php echo esc_url( admin_url( 'upload.php' ) ); ?>">打开 WordPress 媒体库</a><?php endif; ?></div>
				<ul class="aptgd-checklist"><li>主图与附图使用 WP 媒体附件。</li><li>发布前核对 SKU、库存、参数与证据。</li><li>变体商品继续使用原生编辑器，保留原有结构。</li><li>本页不提供网站设置、订单、主题或插件管理代理。</li></ul>
			</aside>
		</div>
		<section class="aptgd-panel" id="aptgd-rest-panel">
			<div class="aptgd-panel-head"><div><h2>WooCommerce 只读连接检查</h2><p>当前 WP 用户的 Cookie 与临时 REST nonce，读取前 10 个商品的标题、SKU 和 ID；不会写入商品。</p></div><button class="aptgd-button" type="button" id="aptgd-read-test" <?php disabled( ! $ready ); ?>>读取前 10 个商品</button></div>
			<div class="aptgd-rest-result" id="aptgd-read-result" role="status" aria-live="polite"><p>尚未执行真实接口测试。WordPress 后台读取成功，也不代表云端服务凭据已绑定。</p></div>
		</section>
		<section class="aptgd-panel">
			<div class="aptgd-panel-head"><div><h2>私有云工作台模块</h2><p>固定入口；打开后按原云端账号独立登录，不在此页复制 ERP 或客户数据。</p></div></div>
			<?php foreach ( cloud_module_groups() as $group => $modules ) : ?>
				<h3 class="aptgd-group-title"><?php echo esc_html( $group ); ?></h3><div class="aptgd-module-grid">
				<?php foreach ( $modules as $module ) : ?>
					<a class="aptgd-module" href="<?php echo esc_url( CLOUD_ORIGIN . '/#' . $module[0] ); ?>" target="_blank" rel="noopener noreferrer"><strong><?php echo esc_html( $module[1] ); ?></strong><span><?php echo esc_html( $module[2] ); ?></span><small>需原云端账号权限</small></a>
				<?php endforeach; ?>
				</div>
			<?php endforeach; ?>
		</section>
		<footer class="aptgd-footer"><p>本插件提供 WordPress 原生管理入口与私有云深链联动，不迁移云端数据库、不更换主题、不重建商品页。</p><a href="<?php echo esc_url( CLOUD_ORIGIN . '/woocommerce/setup.html' ); ?>" target="_blank" rel="noopener noreferrer">配置说明与运营手册</a></footer>
	</div>
	<?php
}

register_activation_hook( __FILE__, __NAMESPACE__ . '\\activate' );
add_action( 'admin_menu', __NAMESPACE__ . '\\register_menu' );
add_action( 'admin_enqueue_scripts', __NAMESPACE__ . '\\enqueue_assets' );
