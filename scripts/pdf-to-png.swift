// Renders the first page of a PDF to a PNG of the given width, keeping
// transparent areas transparent. Used by optimize-images.sh for vector artwork.
// Usage: swift scripts/pdf-to-png.swift input.pdf output.png 2560

import CoreGraphics
import Foundation
import ImageIO
import UniformTypeIdentifiers

let args = CommandLine.arguments
let input = URL(fileURLWithPath: args[1])
let output = URL(fileURLWithPath: args[2])
let width = Int(args[3])!

guard let document = CGPDFDocument(input as CFURL), let page = document.page(at: 1) else {
  FileHandle.standardError.write("Could not read \(input.path)\n".data(using: .utf8)!)
  exit(1)
}

let box = page.getBoxRect(.cropBox)
let scale = CGFloat(width) / box.width
let height = Int((box.height * scale).rounded())

let context = CGContext(
  data: nil, width: width, height: height, bitsPerComponent: 8, bytesPerRow: 0,
  space: CGColorSpace(name: CGColorSpace.sRGB)!,
  bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
context.interpolationQuality = .high
context.scaleBy(x: scale, y: scale)
context.translateBy(x: -box.minX, y: -box.minY)
context.drawPDFPage(page)

let destination = CGImageDestinationCreateWithURL(output as CFURL, UTType.png.identifier as CFString, 1, nil)!
CGImageDestinationAddImage(destination, context.makeImage()!, nil)
CGImageDestinationFinalize(destination)
