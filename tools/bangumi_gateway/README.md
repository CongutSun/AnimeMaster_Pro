# Bangumi Gateway

Cloudflare Worker gateway for AnimeMaster Pro.

## Routes

- `/bangumi/api/*` proxies `https://api.bgm.tv/*`
- `/bangumi/web/*` proxies `https://bgm.tv/*`
- `/bangumi/chii/*` proxies `https://chii.in/*`
- `/bangumi/image?url=...` proxies Bangumi image hosts only

Only Bangumi-related upstream hosts are reachable. Authenticated requests are not cached.

## Deploy

```powershell
cd tools\bangumi_gateway
npm install
npm run dry-run
npm run deploy
```

Set the application `Bangumi 网关` value to the deployed Worker domain, for example `https://auth.congutsun.com`.
