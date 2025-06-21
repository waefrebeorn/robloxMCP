import pytesseract
from PIL import Image
import pandas as pd # pytesseract.image_to_data output is well-handled by pandas
from typing import List, Dict, TypedDict, Optional
import logging

logger = logging.getLogger(__name__)

class OCRData(TypedDict):
    level: int
    page_num: int
    block_num: int
    par_num: int
    line_num: int
    word_num: int
    left: int
    top: int
    width: int
    height: int
    conf: float # Confidence, float because Tesseract often gives it as -1 or float
    text: str

def get_text_and_bounding_boxes(image: Image.Image, lang: Optional[str] = None) -> List[OCRData]:
    """
    Extracts text and bounding box information from an image using Tesseract OCR.

    Args:
        image: A PIL.Image.Image object to process.
        lang: Optional. Language string for Tesseract (e.g., 'eng', 'fra').
              If None, Tesseract will use its default.

    Returns:
        A list of OCRData dictionaries, where each dictionary contains
        information about a recognized text segment, including its bounding box
        (left, top, width, height), text content, and confidence score.
        Returns an empty list if OCR fails or no text is found.
    """
    results: List[OCRData] = []
    try:
        # Get verbose data including boxes, confidences, line and page numbers
        # Output type can be DataFrame, string, bytes, dict. We'll use DataFrame.
        ocr_df = pytesseract.image_to_data(image, lang=lang, output_type=pytesseract.Output.DATAFRAME)

        # Filter out entries with low confidence or no text
        # Tesseract uses -1 for confidence when it's not applicable (e.g. for structural elements like lines/blocks if not filtered)
        # or for words it's very unsure about. We might want to filter these.
        # Let's consider words with conf > 0 (or adjust threshold as needed, e.g. 40-60 for decent quality)
        # Also filter out rows that are just whitespace or don't have text.
        ocr_df = ocr_df[ocr_df.conf > 0] # Only consider positive confidence values
        ocr_df = ocr_df.dropna(subset=['text']) # Remove rows where text is NaN
        ocr_df['text'] = ocr_df['text'].astype(str).str.strip() # Ensure text is string and stripped
        ocr_df = ocr_df[ocr_df.text != ''] # Remove rows with empty string text after stripping

        for i, row in ocr_df.iterrows():
            results.append(OCRData(
                level=int(row['level']),
                page_num=int(row['page_num']),
                block_num=int(row['block_num']),
                par_num=int(row['par_num']),
                line_num=int(row['line_num']),
                word_num=int(row['word_num']),
                left=int(row['left']),
                top=int(row['top']),
                width=int(row['width']),
                height=int(row['height']),
                conf=float(row['conf']),
                text=str(row['text'])
            ))

        logger.info(f"OCR processed image, found {len(results)} text segments with positive confidence.")

    except pytesseract.TesseractNotFoundError:
        logger.error(
            "Tesseract is not installed or not in your PATH. "
            "Please install Tesseract OCR: https://tesseract-ocr.github.io/tessdoc/Installation.html"
        )
        # Optionally, re-raise or return a specific error code/message
        # For now, returns empty list, caller should check.
    except RuntimeError as e: # Can be raised by tesseract for various reasons
        logger.error(f"Runtime error during Tesseract OCR processing: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred in OCR processing: {e}", exc_info=True)

    return results

if __name__ == '__main__':
    # Example Usage:
    # This requires Tesseract OCR to be installed and Pillow for image creation.
    # And pandas for handling the DataFrame.
    logging.basicConfig(level=logging.INFO)
    logger.info("OCR Service Module Example")

    try:
        # 1. Create a dummy image with text
        img = Image.new('RGB', (500, 150), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        try:
            # Try to use a common font, fallback to default
            font = ImageFont.truetype("arial.ttf", size=40)
        except IOError:
            font = ImageFont.load_default()

        draw.text((10, 10), "Hello Tesseract!", fill=(0, 0, 0), font=font)
        draw.text((30, 70), "OCR Test Line 2", fill=(50, 50, 50), font=font)

        # Save it for inspection if needed
        # img.save("ocr_test_image.png")
        # logger.info("Created and saved 'ocr_test_image.png'")

        # 2. Process the image
        logger.info("Processing dummy image with Tesseract...")
        ocr_results = get_text_and_bounding_boxes(img)

        if ocr_results:
            logger.info(f"Found {len(ocr_results)} text segments:")
            for item in ocr_results:
                # Log only word-level results for brevity in example (level 5)
                if item['level'] == 5:
                    logger.info(
                        f"  Text: '{item['text']}', "
                        f"Conf: {item['conf']:.2f}, "
                        f"Box: (L:{item['left']}, T:{item['top']}, W:{item['width']}, H:{item['height']})"
                    )
        else:
            logger.warning("No text segments found by OCR or an error occurred.")
            logger.warning("Ensure Tesseract OCR is correctly installed and accessible in your system PATH.")
            logger.warning("On Windows, you might need to set tesseract_cmd, e.g.:")
            logger.warning("pytesseract.pytesseract.tesseract_cmd = r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'")


    except ImportError as ie:
        if 'ImageDraw' in str(ie) or 'ImageFont' in str(ie):
             logger.error(f"Pillow (PIL) is required for creating the test image: {ie}")
        elif 'pandas' in str(ie):
            logger.error(f"Pandas is required by this example for pytesseract.image_to_data: {ie}")
        else:
            logger.error(f"Import error: {ie}")
    except pytesseract.TesseractNotFoundError:
        # This specific error is also caught inside the function, but good to show here for direct testing.
        logger.error(
            "Tesseract is not installed or not in your PATH. "
            "This example cannot run without it. "
            "Please install Tesseract OCR: https://tesseract-ocr.github.io/tessdoc/Installation.html"
        )
    except Exception as e:
        logger.error(f"An error occurred during the example: {e}", exc_info=True)
