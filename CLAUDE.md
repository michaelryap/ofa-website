# OFA Website

The website for Our Future Agency (OFA), a small design studio.

## Context

- This project lives in `projects/ofa/ofa-website/`. Other OFA projects sit alongside it in `projects/ofa/`.
- The remote repo name is `ofa-website`.

## Stack

Plain HTML and CSS. The pages are built from the copy doc by a small Python script with no dependencies; there's no bundler or framework.

- `*.html`: the pages, generated from the copy doc (see "Copy and publishing")
- `styles.css`: the styles

To preview the site, run `python3 -m http.server` in this folder and open http://localhost:8000.

## Conventions

- File and folder names are lowercase and hyphenated.
- The site represents a design studio, so visual quality and attention to detail matter.

## Copy and publishing

The HTML pages are generated from the "OFA Website Copy" Google Doc. Don't edit page content in the HTML: it's overwritten on the next build.

- `content/copy.json` is a snapshot of the doc (Google Docs API format). `content/media.json` holds alt text and sizes for each image and video, keyed by `<page>/<file>`.
- `scripts/build-pages.py` turns the snapshot into the pages, following the rules in its docstring and the doc's README. Images and videos are placed in the doc with `[image: file.jpg]` or `[video: file.mp4]` on their own line.
- Publishing: the doc's **OFA > Publish to staging** menu (`scripts/google-apps-script/publish.gs`) commits a new `content/copy.json`. The "Build pages from Google Doc" GitHub Action (`.github/workflows/build-pages.yml`) then rebuilds the pages, commits them and starts a Pages build.
- Because the Action commits to `main`, run `git pull` before committing locally.
- Syncing by hand: save the doc's Docs API JSON as `content/copy.json` and run `python3 scripts/build-pages.py`.
- Adding an image: make the web version, add its alt text and size to `content/media.json`, and put its marker in the doc.

### Publish to staging setup (once)

1. In the doc, Extensions > Apps Script. Paste `publish.gs` into `Code.gs`, and under Services add "Google Docs API".
2. Create a fine-grained GitHub token for `michaelryap/ofa-website` only, with Contents: read and write. Save it in Project Settings > Script Properties as `GITHUB_TOKEN`.
3. Reload the doc and use OFA > Publish to staging. Google asks each person to approve the script the first time.

## Images and video

- Full-size exports live in `assets/originals/<project>/`, which is in `.gitignore` and never committed.
- Pages only reference web versions in `assets/images/<project>/`, made with `scripts/optimize-images.sh <original>…`: max 2560px wide, JPEG quality 80, PNGs without transparency saved as JPEG, names lowercased and hyphenated.
- Short silent screen recordings are compressed with HandBrake (1080p, .mp4, aim for under 10 MB) and self-hosted in `assets/videos/<project>/`. Longer videos with sound go on Vimeo.
- GitHub rejects files over 100 MB, and every committed version stays in history, so commit only final exports.
