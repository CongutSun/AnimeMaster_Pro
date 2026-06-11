# Bangumi Gateway

Cloudflare Worker gateway for AnimeMaster Pro.

## Routes

- `/bangumi/api/*` proxies `https://api.bgm.tv/*`
- `/bangumi/web/*` proxies `https://bgm.tv/*`
- `/bangumi/chii/*` proxies `https://chii.in/*`
- `/bangumi/image?url=...` proxies Bangumi image hosts only
- `/proxy/rss?url=...` proxies Mikan and DMHY RSS endpoints
- `/proxy/torrent?url=...` proxies Mikan and DMHY `.torrent` endpoints

Only Bangumi, Mikan and DMHY upstream hosts are reachable. Authenticated requests are not cached.

## Deploy

```powershell
cd tools\bangumi_gateway
npm install
npm run dry-run
npm run deploy
```

Set the application `访问网关` value to the deployed Worker domain, for example `https://auth.congutsun.com`.
