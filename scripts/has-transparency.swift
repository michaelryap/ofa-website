// Prints "yes" if any pixel in the image is see-through, otherwise "no".
// Used by optimize-images.sh to decide whether a PNG must stay a PNG.
// Usage: swift scripts/has-transparency.swift image.png

import CoreGraphics
import Foundation
import ImageIO

let url = URL(fileURLWithPath: CommandLine.arguments[1])
guard let source = CGImageSourceCreateWithURL(url as CFURL, nil),
      let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
  FileHandle.standardError.write("Could not read \(url.path)\n".data(using: .utf8)!)
  exit(1)
}

switch image.alphaInfo {
case .none, .noneSkipFirst, .noneSkipLast:
  print("no")
  exit(0)
default:
  break
}

// Draw into a plain RGBA buffer and look for any alpha below fully opaque
let width = image.width, height = image.height
var pixels = [UInt8](repeating: 0, count: width * height * 4)
let context = CGContext(
  data: &pixels, width: width, height: height, bitsPerComponent: 8,
  bytesPerRow: width * 4, space: CGColorSpaceCreateDeviceRGB(),
  bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
context.draw(image, in: CGRect(x: 0, y: 0, width: width, height: height))

var index = 3
while index < pixels.count {
  if pixels[index] < 255 {
    print("yes")
    exit(0)
  }
  index += 4
}
print("no")
