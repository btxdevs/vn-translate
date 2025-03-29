import asyncio
from winsdk.windows.media.ocr import OcrEngine
from winsdk.windows.graphics.imaging import BitmapDecoder
from winsdk.windows.storage import StorageFile
from winsdk.windows.globalization import Language

async def extract_japanese_text_from_image(image_path):
    # Open the image file
    file = await StorageFile.get_file_from_path_async(image_path)

    # Create a decoder from the stream
    stream = await file.open_async(0)  # 0 means read-only access
    decoder = await BitmapDecoder.create_async(stream)

    # Get the bitmap
    bitmap = await decoder.get_software_bitmap_async()

    # Create Japanese language object
    japanese_lang = Language("ja-JP")

    # Check if Japanese is available
    if not OcrEngine.is_language_supported(japanese_lang):
        return "Japanese OCR is not supported on this device."

    # Create the OCR engine with Japanese language
    ocr_engine = OcrEngine.try_create_from_language(japanese_lang)

    # Recognize text
    result = await ocr_engine.recognize_async(bitmap)

    # Extract and return the text
    extracted_text = ""
    for line in result.lines:
        extracted_text += line.text + "\n"

    return extracted_text

# Example usage
async def main():
    image_path = r"C:\Users\Jhon\Desktop\Screenshot 2025-03-28 192555.png"  # Replace with your image path
    text = await extract_japanese_text_from_image(image_path)
    print(text)

# Run the async function
if __name__ == "__main__":
    asyncio.run(main())