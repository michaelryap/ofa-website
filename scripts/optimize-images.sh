#!/bin/bash
# Makes web versions of full-size images for the site.
#
# Usage: scripts/optimize-images.sh assets/originals/pussypedia/Site\ Map.png [more files…]
#
# Each original in assets/originals/<project>/ becomes a web version in
# assets/images/<project>/, with a lowercase, hyphenated file name:
#   - JPEG and PNG wider than 2560px are scaled down to 2560px wide
#   - JPEG is saved at quality 80
#   - PNG with no see-through pixels (screenshots, illustrations) is saved as
#     JPEG, which is far smaller; PNG with real transparency stays PNG
#   - if the result is bigger than the original, the original is used as is,
#     in its original format
#   - PDF (vector artwork) is rendered to a 2560px-wide PNG, keeping transparency
#   - SVG, GIF, AVIF and WebP are copied as they are (AVIF and WebP are already
#     compressed for the web; resizing would break GIF animation)
# Originals are never changed. Uses sips and swift, which come with macOS.

set -euo pipefail

MAX_WIDTH=2560
JPEG_QUALITY=80

cd "$(dirname "$0")/.."

for original in "$@"; do
  if [[ ! -f "$original" ]]; then
    echo "Not found: $original" >&2
    continue
  fi

  project=$(basename "$(dirname "$original")")
  filename=$(basename "$original")
  ext=$(echo "${filename##*.}" | tr '[:upper:]' '[:lower:]')
  [[ "$ext" == "jpeg" ]] && ext="jpg"

  # "Site Map.png" -> "site-map", "MM_Phone_PH-01.jpg" -> "mm-phone-ph-01"
  slug=$(echo "${filename%.*}" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+|-+$//g')

  mkdir -p "assets/images/$project"

  case "$ext" in
    jpg|png)
      if [[ "$ext" == "png" && $(swift scripts/has-transparency.swift "$original") == "no" ]]; then
        ext="jpg"
      fi
      output="assets/images/$project/$slug.$ext"

      args=()
      width=$(sips -g pixelWidth "$original" | awk '/pixelWidth/ {print $2}')
      if (( width > MAX_WIDTH )); then
        args+=(--resampleWidth "$MAX_WIDTH")
      fi
      # Always name the format, so sips writes a file even when nothing is resized
      if [[ "$ext" == "jpg" ]]; then
        args+=(-s format jpeg -s formatOptions "$JPEG_QUALITY")
      else
        args+=(-s format png)
      fi

      rm -f "$output"
      sips "${args[@]}" "$original" --out "$output" > /dev/null

      # Keep the original instead if re-saving made it bigger
      if (( $(stat -f %z "$output") > $(stat -f %z "$original") )); then
        rm "$output"
        original_ext=$(echo "${original##*.}" | tr '[:upper:]' '[:lower:]' | sed 's/jpeg/jpg/')
        output="assets/images/$project/$slug.$original_ext"
        cp "$original" "$output"
      fi
      ;;
    pdf)
      output="assets/images/$project/$slug.png"
      swift scripts/pdf-to-png.swift "$original" "$output" "$MAX_WIDTH"
      ;;
    svg|gif|avif|webp)
      output="assets/images/$project/$slug.$ext"
      cp "$original" "$output"
      ;;
    *)
      echo "Skipped (not JPEG, PNG, PDF, SVG, GIF, AVIF or WebP): $original" >&2
      continue
      ;;
  esac

  size=$(sips -g pixelWidth -g pixelHeight "$output" 2>/dev/null | awk '/pixelWidth/ {w=$2} /pixelHeight/ {h=$2} END {if (w) print w "×" h}')
  echo "$output  ${size:-vector}  $(du -h "$original" | cut -f1) -> $(du -h "$output" | cut -f1)"
done
