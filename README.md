# Paper Sieve

LLM-powered research paper relevance screening tool.

Upload a CSV of papers, configure keyword conditions for your domain, and let an LLM filter them for relevance — all from the browser.

## Local development

```bash
npm install
npm run dev
```

Open http://localhost:5173

## Deploy to Netlify (step by step)

### Option A: Git-based deploy (recommended)

1. **Push this folder to GitHub**
   ```bash
   git init
   git add .
   git commit -m "initial commit"
   git remote add origin https://github.com/YOUR_USERNAME/paper-sieve.git
   git push -u origin main
   ```

2. **Go to [app.netlify.com](https://app.netlify.com)**
   - Sign up / log in (GitHub login is easiest)
   - Click **"Add new site"** → **"Import an existing project"**
   - Choose **GitHub** and select your `paper-sieve` repo

3. **Netlify auto-detects the settings from `netlify.toml`:**
   - Build command: `npm run build`
   - Publish directory: `dist`
   - Click **"Deploy site"**

4. **Done!** Your site is live at `https://random-name.netlify.app`
   - Rename it: Site configuration → Change site name

Every future `git push` auto-redeploys.

### Option B: Manual drag-and-drop deploy

1. Run `npm install && npm run build` locally
2. Go to [app.netlify.com](https://app.netlify.com)
3. Click **"Add new site"** → **"Deploy manually"**
4. Drag the `dist/` folder onto the upload area
5. Done — site is live instantly

### Option C: Netlify CLI

```bash
npm install -g netlify-cli
netlify login
netlify init
netlify deploy --prod
```

## Project structure

```
paper-sieve/
├── index.html          # Entry point
├── netlify.toml        # Netlify build config + SPA redirects
├── package.json
├── vite.config.js
├── public/
│   └── favicon.svg
└── src/
    ├── main.jsx        # React mount
    └── App.jsx         # Full application
```

## How it works

- All LLM API calls go directly from the browser to whatever base URL you configure (e.g. OpenAI, ChatAnywhere)
- No backend, no proxy — your API key stays in your browser session
- CSV parsing happens client-side
- Results can be exported as CSV
