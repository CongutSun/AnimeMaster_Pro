const USER_AGENT =
  'AnimeMaster_Pro/1.4 (+https://github.com/CongutSun/AnimeMaster_Pro)';

const ROUTES = {
  '/bangumi/api/': 'https://api.bgm.tv',
  '/bangumi/web/': 'https://bgm.tv',
  '/bangumi/chii/': 'https://chii.in',
};

const HOP_BY_HOP_HEADERS = new Set([
  'connection',
  'content-length',
  'host',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailer',
  'transfer-encoding',
  'upgrade',
]);

const REQUEST_HEADER_ALLOWLIST = new Set([
  'accept',
  'accept-language',
  'authorization',
  'content-type',
  'if-none-match',
  'if-modified-since',
]);

const ALLOWED_IMAGE_HOSTS = [
  'bgm.tv',
  'bangumi.tv',
  'chii.in',
  'lain.bgm.tv',
  'lain.bangumi.tv',
  'lain.chii.in',
];

export default {
  async fetch(request, env, ctx) {
    try {
      const url = new URL(request.url);

      if (request.method === 'OPTIONS') {
        return corsResponse(null, 204);
      }

      if (url.pathname === '/health') {
        return jsonResponse({ status: 'ok', service: 'bangumi-gateway' });
      }

      if (url.pathname === '/bangumi/image') {
        return proxyImage(request, ctx);
      }

      for (const [prefix, origin] of Object.entries(ROUTES)) {
        if (url.pathname.startsWith(prefix)) {
          return proxyBangumi(request, ctx, prefix, origin);
        }
      }

      return jsonResponse({ error: 'not_found' }, 404);
    } catch (error) {
      console.error(
        JSON.stringify({
          level: 'error',
          message: error instanceof Error ? error.message : String(error),
        }),
      );
      return jsonResponse({ error: 'gateway_error' }, 502);
    }
  },
};

async function proxyBangumi(request, ctx, prefix, origin) {
  const sourceUrl = new URL(request.url);
  const upstreamPath = sourceUrl.pathname.slice(prefix.length - 1);
  const upstreamUrl = new URL(`${origin}${upstreamPath}`);
  upstreamUrl.search = sourceUrl.search;

  const headers = buildUpstreamHeaders(request.headers);
  const upstreamRequest = new Request(upstreamUrl.toString(), {
    method: request.method,
    headers,
    body: allowsBody(request.method) ? request.body : undefined,
    redirect: 'follow',
  });

  const ttl = cacheTtl(prefix, upstreamPath);
  return fetchWithCache(upstreamRequest, ctx, ttl, hasAuthorization(request.headers));
}

async function proxyImage(request, ctx) {
  if (!['GET', 'HEAD'].includes(request.method)) {
    return jsonResponse({ error: 'method_not_allowed' }, 405);
  }

  const sourceUrl = new URL(request.url);
  const rawTarget = sourceUrl.searchParams.get('url');
  if (!rawTarget) {
    return jsonResponse({ error: 'missing_url' }, 400);
  }

  let targetUrl;
  try {
    targetUrl = new URL(rawTarget);
  } catch {
    return jsonResponse({ error: 'invalid_url' }, 400);
  }

  if (!['http:', 'https:'].includes(targetUrl.protocol)) {
    return jsonResponse({ error: 'invalid_protocol' }, 400);
  }

  if (!isAllowedImageHost(targetUrl.hostname)) {
    return jsonResponse({ error: 'forbidden_host' }, 403);
  }

  const upstreamRequest = new Request(targetUrl.toString(), {
    method: request.method,
    headers: buildUpstreamHeaders(request.headers),
    redirect: 'follow',
  });

  return fetchWithCache(upstreamRequest, ctx, 604800, false);
}

async function fetchWithCache(upstreamRequest, ctx, ttl, bypassCache) {
  const shouldCache =
    ttl > 0 &&
    !bypassCache &&
    ['GET', 'HEAD'].includes(upstreamRequest.method);

  const cache = caches.default;
  const cacheKey = new Request(upstreamRequest.url, { method: 'GET' });

  if (shouldCache) {
    const cached = await cache.match(cacheKey);
    if (cached) {
      return withCors(cached);
    }
  }

  const upstreamResponse = await fetch(upstreamRequest);
  const response = buildClientResponse(upstreamResponse, ttl, shouldCache);

  if (shouldCache && upstreamResponse.ok) {
    ctx.waitUntil(cache.put(cacheKey, response.clone()));
  }

  return response;
}

function buildUpstreamHeaders(inputHeaders) {
  const headers = new Headers();
  headers.set('User-Agent', USER_AGENT);

  for (const [key, value] of inputHeaders.entries()) {
    const normalized = key.toLowerCase();
    if (HOP_BY_HOP_HEADERS.has(normalized)) {
      continue;
    }
    if (REQUEST_HEADER_ALLOWLIST.has(normalized)) {
      headers.set(key, value);
    }
  }

  return headers;
}

function buildClientResponse(upstreamResponse, ttl, cached) {
  const headers = new Headers(upstreamResponse.headers);
  for (const key of HOP_BY_HOP_HEADERS) {
    headers.delete(key);
  }
  headers.delete('set-cookie');

  if (cached) {
    headers.set('Cache-Control', `public, max-age=${ttl}`);
  } else {
    headers.set('Cache-Control', 'no-store');
  }

  addCorsHeaders(headers);
  return new Response(upstreamResponse.body, {
    status: upstreamResponse.status,
    statusText: upstreamResponse.statusText,
    headers,
  });
}

function cacheTtl(prefix, upstreamPath) {
  if (prefix === '/bangumi/web/' || prefix === '/bangumi/chii/') {
    return upstreamPath.includes('/subject/') ? 600 : 21600;
  }

  if (upstreamPath === '/calendar') {
    return 3600;
  }
  if (upstreamPath.startsWith('/v0/subjects/') || upstreamPath.startsWith('/v0/episodes')) {
    return 21600;
  }
  if (upstreamPath.startsWith('/search/')) {
    return 1800;
  }
  return 0;
}

function hasAuthorization(headers) {
  const value = headers.get('Authorization');
  return Boolean(value && value.trim());
}

function allowsBody(method) {
  return !['GET', 'HEAD'].includes(method);
}

function isAllowedImageHost(hostname) {
  const normalized = hostname.toLowerCase();
  return ALLOWED_IMAGE_HOSTS.some(
    (host) => normalized === host || normalized.endsWith(`.${host}`),
  );
}

function jsonResponse(payload, status = 200) {
  return corsResponse(JSON.stringify(payload), status, {
    'Content-Type': 'application/json; charset=utf-8',
  });
}

function corsResponse(body, status = 200, headersInit = {}) {
  const headers = new Headers(headersInit);
  addCorsHeaders(headers);
  return new Response(body, { status, headers });
}

function withCors(response) {
  const headers = new Headers(response.headers);
  addCorsHeaders(headers);
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

function addCorsHeaders(headers) {
  headers.set('Access-Control-Allow-Origin', '*');
  headers.set('Access-Control-Allow-Methods', 'GET,HEAD,POST,PUT,PATCH,DELETE,OPTIONS');
  headers.set('Access-Control-Allow-Headers', 'Authorization,Content-Type,Accept,Accept-Language');
  headers.set('Access-Control-Max-Age', '86400');
}
