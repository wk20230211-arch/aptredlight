(function () {
  'use strict';
  const root = document.getElementById('aptgd-root');
  const button = document.getElementById('aptgd-read-test');
  const result = document.getElementById('aptgd-read-result');
  if (!root || !button || !result || button.disabled) return;
  const config = window.APTGrowthDeskConfig;
  let previous = null;
  let controller = null;

  function node(tag, text, className) {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = String(text);
    if (className) element.className = className;
    return element;
  }

  function productEndpoint() {
    if (!config || typeof config.productsUrl !== 'string' || typeof config.nonce !== 'string' || !config.nonce) {
      throw new Error('页面未取得有效的 WordPress 读取配置，请重新打开本页。');
    }
    const url = new URL(config.productsUrl, window.location.href);
    const queryRoute = url.searchParams.get('rest_route');
    if (url.origin !== window.location.origin || url.username || url.password ||
        !(url.pathname.endsWith('/wc/v3/products') || queryRoute === '/wc/v3/products')) {
      throw new Error('REST 地址与当前后台不一致，已停止发送登录凭据。请由管理员核对 WordPress 地址。');
    }
    // Retain only the server-generated WordPress plain-permalink route when needed.
    url.search = '';
    url.hash = '';
    if (queryRoute === '/wc/v3/products') url.searchParams.set('rest_route', queryRoute);
    url.searchParams.set('per_page', '10');
    url.searchParams.set('page', '1');
    url.searchParams.set('status', 'any');
    url.searchParams.set('context', 'edit');
    url.searchParams.set('_fields', 'id,name,sku,status,type');
    return url;
  }

  async function boundedJSON(response) {
    if (!/application\/(?:[\w.+-]*\+)?json/i.test(response.headers.get('Content-Type') || '')) {
      throw new Error('接口没有返回 JSON。请核对 WooCommerce 安装和 REST 路由；此结果不代表零商品。');
    }
    if (!response.body) throw new Error('接口未返回可读取的商品内容。');
    const reader = response.body.getReader();
    const chunks = [];
    let size = 0;
    for (;;) {
      const item = await reader.read();
      if (item.done) break;
      size += item.value.byteLength;
      if (size > 1024 * 1024) {
        await reader.cancel();
        throw new Error('只读测试响应超过 1 MiB 限制，请由管理员检查接口。');
      }
      chunks.push(item.value);
    }
    const bytes = new Uint8Array(size);
    let offset = 0;
    for (const part of chunks) { bytes.set(part, offset); offset += part.byteLength; }
    try { return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes)); }
    catch (_) { throw new Error('接口返回内容无法解析，尚未完成商品读取。'); }
  }

  function validateProducts(value) {
    if (!Array.isArray(value) || value.length > 10 || !value.every(product =>
      product && typeof product === 'object' && Number.isSafeInteger(product.id) && product.id > 0 &&
      typeof product.name === 'string' && typeof product.sku === 'string' && typeof product.status === 'string')) {
      throw new Error('接口商品结构不符合预期，尚未通过只读验证。');
    }
    return value;
  }

  function table(products) {
    const wrap = node('div', undefined, 'aptgd-table-wrap');
    const grid = node('table');
    const head = node('thead');
    const heading = node('tr');
    for (const label of ['ID', '标题', 'SKU', '状态']) heading.appendChild(node('th', label));
    head.appendChild(heading);
    grid.appendChild(head);
    const body = node('tbody');
    for (const product of products) {
      const row = node('tr');
      for (const value of [product.id, product.name, product.sku || '未填写', product.status]) row.appendChild(node('td', value));
      body.appendChild(row);
    }
    grid.appendChild(body);
    wrap.appendChild(grid);
    return wrap;
  }

  function renderSuccess(products) {
    result.replaceChildren();
    result.appendChild(node('p', '只读检查通过 · 本次读取 ' + products.length + ' 个商品', 'aptgd-success'));
    result.appendChild(node('p', '没有新增、修改或删除商品。本次结果只证明当前 WP 用户可以读取此接口；云端服务凭据仍需单独绑定。'));
    if (products.length) result.appendChild(table(products));
    else result.appendChild(node('p', '当前授权请求成功返回空列表。请结合商品状态及账号权限判断，不推算业务数据。'));
  }

  function renderFailure(message) {
    result.replaceChildren(node('p', message, 'aptgd-error'));
    if (previous) {
      result.appendChild(node('p', '上次成功读取的结果，仅供参考；本次刷新未通过。', 'aptgd-stale'));
      if (previous.length) result.appendChild(table(previous));
    }
  }

  button.addEventListener('click', async function () {
    if (controller) return;
    button.disabled = true;
    result.setAttribute('aria-busy', 'true');
    result.replaceChildren(node('p', '正在读取 WooCommerce 前 10 个商品…'));
    controller = new AbortController();
    const timer = window.setTimeout(() => controller && controller.abort(), 20000);
    try {
      const endpoint = productEndpoint();
      const response = await window.fetch(endpoint.href, {
        method: 'GET', credentials: 'same-origin', mode: 'same-origin', redirect: 'error', cache: 'no-store',
        referrerPolicy: 'same-origin', headers: { Accept: 'application/json', 'X-WP-Nonce': config.nonce }, signal: controller.signal
      });
      if (response.status === 401 || response.status === 403) throw new Error('当前 WordPress 登录已过期或缺少商品读取权限，请重新登录后再测试。');
      if (response.status === 404) throw new Error('未找到 WooCommerce 商品接口。请检查现有 WooCommerce 安装与 REST 路由，不要重建官网来绕过此错误。');
      if (!response.ok) throw new Error('接口读取失败（HTTP ' + response.status + '），请由管理员核对。');
      const products = validateProducts(await boundedJSON(response));
      if (!root.isConnected) return;
      previous = products;
      renderSuccess(products);
    } catch (error) {
      if (!root.isConnected) return;
      renderFailure(error && error.name === 'AbortError' ? '读取超时或已离开页面。此测试没有执行商品写入，可核对后手动重试。' : error.message || '商品读取尚未完成。');
    } finally {
      window.clearTimeout(timer);
      controller = null;
      if (root.isConnected) { button.disabled = false; result.setAttribute('aria-busy', 'false'); }
    }
  });
  window.addEventListener('pagehide', function () { if (controller) controller.abort(); }, { once: true });
})();
