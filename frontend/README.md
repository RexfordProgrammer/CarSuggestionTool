# Node + TypeScript Static Website (Vite) — S3/CloudFront Ready

Minimal starter that builds to static files in `dist/`, perfect for S3 static hosting (fronted by CloudFront).

## Quick Start

1) **Install prerequisites**
- Node.js 18+ (LTS recommended)
- AWS CLI v2 (`aws --version`) and `aws configure` (or set `AWS_PROFILE`)
- VS Code (optional, but nice)

2) **Install and run locally**
```bash
npm install
npm run dev
# open the printed localhost URL
```

3) **Build**
```bash
npm run build
# static files in dist/
```

4) **Deploy to S3** (PowerShell on Windows)
```powershell
$env:S3_BUCKET="your-bucket-name"
$env:CLOUDFRONT_DISTRIBUTION_ID="DISTRIBUTIONID"   # optional
$env:AWS_PROFILE="rexford"                # optional
$env:AWS_REGION="us-east-1"                        # default if unset

./scripts/deploy.ps1
```

Or Bash/macOS/Linux:
```bash
export S3_BUCKET=your-bucket-name
export CLOUDFRONT_DISTRIBUTION_ID=DISTRIBUTIONID   # optional
export AWS_PROFILE=your-aws-profile                 # optional
export AWS_REGION=us-east-1

bash scripts/deploy.sh
```

The AWS CLI will set correct `Content-Type` headers automatically based on file extensions.
Use `--delete` to remove files in S3 that no longer exist locally.

## Pretty URLs

S3 + CloudFront will serve `index.html` when the request path ends with `/`.
This template includes `about/index.html` so `/about/` works out of the box.
- For **more pages**, add `foo/index.html`, `blog/index.html`, etc.
- For **single page apps (SPAs)** (client routing), set CloudFront/S3 to serve `index.html` on 403/404.

## CloudFront Tips

- Set **Default Root Object** to `index.html`.
- Origin: S3 bucket or S3 *website endpoint* (if you want S3 to handle redirects). Prefer OAC + S3 bucket origin.
- Behavior: Redirect HTTP to HTTPS, GET/HEAD, enable compression, a standard cache policy.
- After deploys, run an **invalidation** for `/*` (the scripts do this if `CLOUDFRONT_DISTRIBUTION_ID` is set).

## VS Code niceties

- Format-on-save enabled in `.vscode/settings.json`.
- TS strict mode on by default.

## GitHub Actions (optional)

You can deploy on every push to `main`. Save the values as GitHub repo secrets:
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`
- `S3_BUCKET`, `CLOUDFRONT_DISTRIBUTION_ID`

Workflow is provided in `.github/workflows/deploy.yml`.
