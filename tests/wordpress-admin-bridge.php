<?php
/** Isolated executable fixtures: no WordPress installation, network or real data. */
declare(strict_types=1);

define('ABSPATH', __DIR__ . '/fixture-wordpress/');
define('MINUTE_IN_SECONDS', 60);
$GLOBALS['fixture'] = array(
    'caps' => array(), 'roles' => array(), 'actions' => array(), 'menus' => array(),
    'submenus' => array(), 'activation' => null, 'added_roles' => array(),
    'styles' => array(), 'scripts' => array(), 'inline' => array(), 'localized' => array(),
    'queries' => array(), 'wp_queries' => array(), 'counts' => array(), 'edit_links' => array(), 'nonce_actions' => array(),
    'transients' => array(),
);

class FixtureDenied extends RuntimeException {}
function current_user_can($cap, ...$args) {
    $specific = $cap . ($args ? ':' . (string) $args[0] : '');
    return !empty($GLOBALS['fixture']['caps'][$specific]) || !empty($GLOBALS['fixture']['caps'][$cap]);
}
function add_action($hook, $callback, $priority = 10, $accepted_args = 1) {
    $GLOBALS['fixture']['actions'][$hook][] = $callback;
}
function register_activation_hook($file, $callback) { $GLOBALS['fixture']['activation'] = $callback; }
function add_menu_page($title, $menu, $cap, $slug, $callback = '', $icon = '', $position = null) {
    $hook = 'toplevel_page_' . $slug;
    $GLOBALS['fixture']['menus'][] = compact('title', 'menu', 'cap', 'slug', 'callback', 'hook');
    return $hook;
}
function add_submenu_page($parent, $title, $menu, $cap, $slug, $callback = '', $position = null) {
    $GLOBALS['fixture']['submenus'][] = compact('parent', 'title', 'menu', 'cap', 'slug', 'callback');
    return $parent . '_page_' . $slug;
}
function esc_html($value) { return htmlspecialchars((string) $value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); }
function esc_attr($value) { return esc_html($value); }
function esc_url($value) {
    $value = (string) $value;
    return preg_match('~^(https?://|/)~', $value) ? esc_attr($value) : '';
}
function __($value, $domain = '') { return $value; }
function esc_html__($value, $domain = '') { return esc_html($value); }
function esc_attr__($value, $domain = '') { return esc_attr($value); }
function absint($value) { return abs((int) $value); }
function wp_die($message = '', $title = '', $args = array()) { throw new FixtureDenied((string) $message); }
function admin_url($path = '') { return 'https://wordpress.example.test/wp-admin/' . ltrim((string) $path, '/'); }
function rest_url($path = '') { return 'https://wordpress.example.test/wp-json/' . ltrim((string) $path, '/'); }
function plugins_url($path = '', $file = '') { return 'https://wordpress.example.test/wp-content/plugins/aptredlight-growth-desk/' . ltrim((string) $path, '/'); }
function plugin_dir_url($file = '') { return plugins_url() . '/'; }
function plugin_dir_path($file) { return dirname($file) . '/'; }
function wp_enqueue_style($handle, $src = '', $deps = array(), $ver = false, $media = 'all') {
    $GLOBALS['fixture']['styles'][$handle] = compact('src', 'deps', 'ver', 'media');
}
function wp_enqueue_script($handle, $src = '', $deps = array(), $ver = false, $args = false) {
    $GLOBALS['fixture']['scripts'][$handle] = compact('src', 'deps', 'ver', 'args');
}
function wp_add_inline_script($handle, $data, $position = 'after') {
    $GLOBALS['fixture']['inline'][] = compact('handle', 'data', 'position');
    return true;
}
function wp_localize_script($handle, $object_name, $l10n) {
    $GLOBALS['fixture']['localized'][] = compact('handle', 'object_name', 'l10n');
    return true;
}
function wp_json_encode($value, $flags = 0, $depth = 512) { return json_encode($value, $flags, $depth); }
function disabled($disabled, $current = true, $display = true) {
    $value = ((string) $disabled === (string) $current) ? 'disabled="disabled"' : '';
    if ($display) echo $value;
    return $value;
}
function wp_create_nonce($action = -1) {
    $GLOBALS['fixture']['nonce_actions'][] = $action;
    return 'fixture-rest-nonce-ONLY';
}
function number_format_i18n($value, $decimals = 0) { return number_format((float) $value, $decimals); }
function get_current_user_id() { return 71; }
function wp_get_current_user() { return (object) array('ID' => 71, 'display_name' => 'Fixture Operator'); }
function get_role($name) { return $GLOBALS['fixture']['roles'][$name] ?? null; }
function add_role($name, $label, $caps = array()) {
    $GLOBALS['fixture']['added_roles'][] = compact('name', 'label', 'caps');
    if (isset($GLOBALS['fixture']['roles'][$name])) return null;
    return $GLOBALS['fixture']['roles'][$name] = (object) array('name' => $name, 'capabilities' => $caps);
}
function set_transient($key, $value, $expiration = 0) { $GLOBALS['fixture']['transients'][$key] = $value; return true; }
function get_transient($key) { return $GLOBALS['fixture']['transients'][$key] ?? false; }
function delete_transient($key) { unset($GLOBALS['fixture']['transients'][$key]); return true; }
function wp_count_posts($type = 'post', $perm = '') {
    $GLOBALS['fixture']['counts'][] = compact('type', 'perm');
    return (object) array('publish' => 7, 'draft' => 2, 'private' => 1, 'pending' => 0, 'trash' => 0);
}
function wp_count_attachments($mime_type = '', $perm = '') { return (object) array('image/jpeg' => 4, 'image/png' => 2); }
function get_edit_post_link($id, $context = 'display') {
    $GLOBALS['fixture']['edit_links'][] = (int) $id;
    return admin_url('post.php?post=' . (int) $id . '&action=edit');
}
function get_permalink($id) { return 'https://wordpress.example.test/product/' . (int) $id; }
function get_bloginfo($show = '', $filter = 'raw') { return 'Fixture WordPress'; }
function get_posts($args = array()) {
    $GLOBALS['fixture']['queries'][] = $args;
    return array(101, 102);
}
class WP_Query {
    public $found_posts = 9;
    public $post_count = 2;
    public $posts = array(101, 102);
    public function __construct($args = array()) { $GLOBALS['fixture']['wp_queries'][] = $args; }
}

class FixtureProduct {
    private $id;
    public function __construct($id) { $this->id = $id; }
    public function get_id() { return $this->id; }
    public function get_name() { return $this->id === 101 ? '<svg/onload=alert(1)> Panel & Co' : 'Uneditable product'; }
    public function get_sku() { return $this->id === 101 ? 'X"><img src=x onerror=alert(2)>' : 'SKU-102'; }
    public function get_status() { return $this->id === 101 ? 'publish' : 'draft'; }
    public function get_type() { return 'simple'; }
    public function get_permalink() { return get_permalink($this->id); }
}

$no_woo = in_array('--no-woo', $argv, true);
if (!$no_woo) {
    class WooCommerce {}
    function wc_get_products($args = array()) {
        $GLOBALS['fixture']['queries'][] = $args;
        return array(new FixtureProduct(101), new FixtureProduct(102));
    }
    function wc_get_product($id) { return new FixtureProduct((int) $id); }
    function get_woocommerce_currency() { return 'USD'; }
}

$plugin_arg = $argv[1] ?? (__DIR__ . '/../plugin/aptredlight-growth-desk');
$plugin = is_dir($plugin_arg) ? rtrim($plugin_arg, '/') . '/aptredlight-growth-desk.php' : $plugin_arg;
if (!is_file($plugin)) throw new RuntimeException('Plugin file not found: ' . $plugin);
require $plugin;

$checks = 0;
function expect($condition, $message) {
    global $checks;
    if (!$condition) throw new RuntimeException('FAIL: ' . $message);
    $checks++;
}
function invoke_plugin($name, ...$args) {
    $function = 'APTREDLIGHT\\GrowthDesk\\' . $name;
    if (!is_callable($function)) throw new RuntimeException('Missing plugin test entry point: ' . $function);
    return $function(...$args);
}
function render_plugin() {
    ob_start();
    try { invoke_plugin('render_page'); return ob_get_clean(); }
    catch (Throwable $error) { ob_end_clean(); throw $error; }
}

expect(!isset($GLOBALS['fixture']['actions']['wp_enqueue_scripts']), 'no frontend assets hook');
expect(!isset($GLOBALS['fixture']['actions']['template_redirect']), 'no frontend redirect hook');
expect(!isset($GLOBALS['fixture']['actions']['rest_api_init']), 'no generic external REST proxy');
expect(isset($GLOBALS['fixture']['actions']['admin_menu']), 'registers native admin menu');
expect(isset($GLOBALS['fixture']['actions']['admin_enqueue_scripts']), 'registers scoped admin assets');
expect(is_callable($GLOBALS['fixture']['activation']), 'activation callback registered');

$GLOBALS['fixture']['caps'] = array();
try { render_plugin(); throw new RuntimeException('Unauthorised render was not rejected'); }
catch (FixtureDenied $error) { expect(count($GLOBALS['fixture']['queries']) === 0 && count($GLOBALS['fixture']['wp_queries']) === 0, 'unauthorised user cannot query products'); }

$GLOBALS['fixture']['caps'] = array('edit_products' => true, 'edit_post:101' => true);
invoke_plugin('register_menu');
expect(count($GLOBALS['fixture']['menus']) === 1, 'one native top-level workspace');
$menu = $GLOBALS['fixture']['menus'][0];
expect($menu['cap'] === 'edit_products', 'top-level menu uses product capability');
expect(is_callable($menu['callback']), 'menu points to native renderer');
invoke_plugin('enqueue_assets', 'dashboard');
expect(count($GLOBALS['fixture']['styles']) === 0 && count($GLOBALS['fixture']['scripts']) === 0, 'unrelated WP screen receives no assets');
invoke_plugin('enqueue_assets', $menu['hook']);
expect(count($GLOBALS['fixture']['styles']) > 0 && count($GLOBALS['fixture']['scripts']) > 0, 'own screen receives assets');
expect(in_array('wp_rest', $GLOBALS['fixture']['nonce_actions'], true), 'WP nonce generated per session');
$configs = array();
foreach ($GLOBALS['fixture']['inline'] as $inline) {
    $prefix = 'window.APTGrowthDeskConfig=';
    if (strpos($inline['data'], $prefix) === 0) {
        $configs[] = json_decode(rtrim(substr($inline['data'], strlen($prefix)), ';'), true, 512, JSON_THROW_ON_ERROR);
    }
}
expect(count($configs) === 1, 'one request-scoped browser configuration');
expect(($configs[0]['productsUrl'] ?? null) === rest_url('wc/v3/products'), 'browser receives only the fixed local product endpoint');
expect(($configs[0]['nonce'] ?? null) === 'fixture-rest-nonce-ONLY', 'browser receives generated nonce, no API key');
expect(($configs[0]['cloudOrigin'] ?? null) === 'https://aptredlight-growth-desk.wk20230211.chatgpt.site', 'cloud origin is fixed server-owned value');
expect(count($configs[0]) === 3, 'privileged config includes no provider credentials or role text');
foreach (array_merge(array_values($GLOBALS['fixture']['styles']), array_values($GLOBALS['fixture']['scripts'])) as $asset) {
    expect(strpos($asset['src'], 'https://wordpress.example.test/wp-content/plugins/aptredlight-growth-desk/') === 0, 'asset is local plugin resource');
}
$GLOBALS['fixture']['styles'] = $GLOBALS['fixture']['scripts'] = array();
$GLOBALS['fixture']['caps'] = array();
invoke_plugin('enqueue_assets', $menu['hook']);
expect(count($GLOBALS['fixture']['styles']) === 0 && count($GLOBALS['fixture']['scripts']) === 0, 'unauthorised user does not receive privileged config');
$GLOBALS['fixture']['caps'] = array('edit_products' => true, 'edit_post:101' => true);

$existing = (object) array('name' => 'apt_growth_product_operator', 'capabilities' => array('read' => true, 'custom_existing' => true));
$GLOBALS['fixture']['roles']['apt_growth_product_operator'] = $existing;
invoke_plugin('activate');
expect($GLOBALS['fixture']['roles']['apt_growth_product_operator'] === $existing, 'existing role object retained');
expect(count($GLOBALS['fixture']['added_roles']) === 0, 'existing role not overwritten');
unset($GLOBALS['fixture']['roles']['apt_growth_product_operator']);
invoke_plugin('activate');
expect(count($GLOBALS['fixture']['added_roles']) === 1, 'missing role added exactly once');
$caps = $GLOBALS['fixture']['added_roles'][0]['caps'];
expect(!empty($caps['edit_products']) && !empty($caps['upload_files']), 'new role supports product work and media');
foreach (array('manage_options', 'manage_woocommerce', 'edit_shop_orders', 'read_private_shop_orders', 'edit_users', 'activate_plugins', 'edit_themes', 'install_plugins') as $forbidden) {
    expect(empty($caps[$forbidden]), 'new role excludes ' . $forbidden);
}

$html = render_plugin();
expect(stripos($html, '<iframe') === false, 'private cloud workspace is not silently framed');
expect(strpos($html, 'https://aptredlight-growth-desk.wk20230211.chatgpt.site') !== false, 'fixed cloud workspace linked');
foreach (array('wooProducts', 'productsLibrary', 'assetsLibrary', 'certificatesLibrary', 'growthExecution', 'geoBrandOfficer', 'erpPipeline', 'ga4Analytics', 'standardsLibrary') as $route) {
    expect(strpos($html, '#' . $route) !== false, 'cloud route exists: ' . $route);
}
if ($no_woo) {
    expect(count($GLOBALS['fixture']['queries']) === 0, 'Woo absence does not fabricate products');
    expect(stripos($html, 'WooCommerce') !== false, 'missing Woo dependency explained');
    expect(strpos($html, '<strong>—</strong>') !== false, 'unavailable live counts stay unknown');
    expect(preg_match('/id="aptgd-read-test"\s+disabled="disabled"/', $html) === 1, 'read-test control disabled while Woo unavailable');
} else {
    expect(count($GLOBALS['fixture']['queries']) === 1, 'native renderer reads products once');
    $query = $GLOBALS['fixture']['queries'][0];
    expect(($query['limit'] ?? $query['posts_per_page'] ?? $query['numberposts'] ?? null) === 10, 'native list bounded to ten');
    expect(($query['post_type'] ?? null) === 'product' && ($query['perm'] ?? null) === 'readable', 'native list keeps product and readable permission scope');
    expect(($query['author'] ?? null) === 71, 'limited operator list scoped to own author ID');
    foreach ($GLOBALS['fixture']['wp_queries'] as $count_query) {
        expect(($count_query['post_type'] ?? null) === 'product', 'stats query keeps product scope');
        expect(($count_query['author'] ?? null) === 71, 'limited operator stats scoped to own author ID');
    }
    expect(strpos($html, '<svg/onload=alert(1)>') === false && strpos($html, '&lt;svg/onload=alert(1)&gt;') !== false, 'product title safely escaped');
    expect(strpos($html, 'X"><img src=x onerror=alert(2)>') === false && strpos($html, '&lt;img src=x onerror=alert(2)&gt;') !== false, 'SKU safely escaped');
    expect(in_array(101, $GLOBALS['fixture']['edit_links'], true), 'editable product gets native edit link');
    expect(!in_array(102, $GLOBALS['fixture']['edit_links'], true), 'uneditable product does not get native edit link');
    $GLOBALS['fixture']['queries'] = $GLOBALS['fixture']['wp_queries'] = array();
    $GLOBALS['fixture']['caps']['edit_others_products'] = true;
    render_plugin();
    expect(!array_key_exists('author', $GLOBALS['fixture']['queries'][0]), 'broader product capability removes own-author restriction');
    foreach ($GLOBALS['fixture']['wp_queries'] as $count_query) {
        expect(!array_key_exists('author', $count_query), 'broader product capability permits scoped aggregate counts');
    }
}
echo json_encode(array('status' => 'passed', 'checks' => $checks, 'fixture' => $no_woo ? 'woo_missing' : 'woo_enabled', 'production_wordpress_activation_tested' => false), JSON_UNESCAPED_UNICODE) . "\n";
