import handler from '@tanstack/react-start/server-entry'

// The SSR document must not be cached: it references content-hashed assets, so a stale
// shell makes the browser run old chunks until a hard refresh. Hashed assets keep their
// own immutable caching.
type Env = { API: { fetch: (r: Request) => Promise<Response> } }

export default {
  async fetch(request: Request, env: unknown, ctx: unknown): Promise<Response> {
    // Proxy the dashboard's data calls to the api worker over the service binding.
    const url = new URL(request.url)
    if (url.pathname.startsWith('/api/')) {
      const target = new URL(url.pathname.slice(4) + url.search, 'https://alpaca-agent-api')
      return (env as Env).API.fetch(new Request(target, request))
    }

    const res = await (handler as { fetch: (r: Request, e: unknown, c: unknown) => Promise<Response> }).fetch(
      request,
      env,
      ctx,
    )
    if (!(res.headers.get('content-type') || '').includes('text/html')) return res
    const headers = new Headers(res.headers)
    headers.set('Cache-Control', 'no-cache, must-revalidate')
    return new Response(res.body, { status: res.status, statusText: res.statusText, headers })
  },
}
