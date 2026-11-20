# OFA Website

The website for Our Future Agency (OFA), a small design studio.

## Context

- This project lives in `projects/ofa/ofa-website/`. Other OFA projects sit alongside it in `projects/ofa/`.
- The remote repo name is `ofa-website`.

## Stack

Plain HTML and CSS, with no build step.

- `index.html`: the page
- `styles.css`: the styles

To preview the site, open `index.html` in a browser (`open index.html`).

## Conventions

- File and folder names are lowercase and hyphenated.
- The site represents a design studio, so visual quality and attention to detail matter.

## Images and video

- Full-size exports live in `assets/originals/<project>/`, which is in `.gitignore` and never committed.
- Pages only reference web versions in `assets/images/<project>/`, made with `scripts/optimize-images.sh <original>…`: max 2560px wide, JPEG quality 80, PNGs without transparency saved as JPEG, names lowercased and hyphenated.
- Short silent screen recordings are compressed with HandBrake (1080p, .mp4, aim for under 10 MB) and self-hosted in `assets/videos/<project>/`. Longer videos with sound go on Vimeo.
- GitHub rejects files over 100 MB, and every committed version stays in history, so commit only final exports.
