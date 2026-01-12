# # agents/vision_agent.py
from api.ocr_engine import OCREngine

_engine = OCREngine()

def run_vision(image):
    return _engine.run(image)


# # agents/vision_agent.py
# # FIXED: Layout-aware OCR that preserves document structure
# from paddleocr import PaddleOCR
# import numpy as np

# # Initialize OCR with LAYOUT-AWARE settings
# ocr = PaddleOCR(
#     use_angle_cls=True,
#     lang='en',
#     use_gpu=False,
#     show_log=False,
#     det_db_score_mode='slow',  # Better text detection
#     det_db_thresh=0.3,         # Lower threshold for better recall
#     det_db_box_thresh=0.5,     # Box detection threshold
#     rec_batch_num=6,           # Batch processing
#     drop_score=0.3,            # Lower drop score to keep more text
#     use_space_char=True,       # CRITICAL: Preserve spaces
#     det_limit_side_len=1280,   # Higher resolution support
#     det_limit_type='max'       # Use max dimension
# )


# def run_vision(image):
#     """
#     Layout-aware OCR that preserves document structure.
#     Returns lines in reading order with proper spacing.
#     """
#     if image is None:
#         return [], 0.0
    
#     try:
#         # Run PaddleOCR
#         result = ocr.ocr(image, cls=True)
        
#         if not result or not result[0]:
#             return [], 0.0
        
#         # Extract boxes, text, and confidence
#         boxes_and_text = []
#         total_conf = 0.0
#         count = 0
        
#         for line in result[0]:
#             box = line[0]  # [top-left, top-right, bottom-right, bottom-left]
#             text_info = line[1]  # (text, confidence)
#             text = text_info[0]
#             conf = text_info[1]
            
#             # Get box coordinates
#             top_left = box[0]
#             bottom_right = box[2]
            
#             y_center = (top_left[1] + bottom_right[1]) / 2
#             x_left = top_left[0]
#             x_right = bottom_right[0]
            
#             boxes_and_text.append({
#                 'text': text,
#                 'confidence': conf,
#                 'y': y_center,
#                 'x_left': x_left,
#                 'x_right': x_right,
#                 'width': x_right - x_left
#             })
            
#             total_conf += conf
#             count += 1
        
#         avg_confidence = total_conf / count if count > 0 else 0.0
        
#         # Sort by Y position (top to bottom), then X position (left to right)
#         boxes_and_text.sort(key=lambda item: (item['y'], item['x_left']))
        
#         # Group into lines based on Y-coordinate proximity
#         lines = group_into_lines(boxes_and_text)
        
#         # Clean and return
#         cleaned_lines = [line.strip() for line in lines if line.strip()]
        
#         return cleaned_lines, avg_confidence
        
#     except Exception as e:
#         print(f"OCR Error: {e}")
#         return [], 0.0


# def group_into_lines(boxes_and_text, y_threshold=15):
#     """
#     Group text boxes into lines based on Y-coordinate proximity.
#     Preserves horizontal spacing for tabular layouts.
    
#     Args:
#         boxes_and_text: List of dicts with text, y, x_left, x_right
#         y_threshold: Max vertical distance to consider same line (pixels)
    
#     Returns:
#         List of strings (lines of text)
#     """
#     if not boxes_and_text:
#         return []
    
#     # Group boxes by line (similar Y coordinate)
#     line_groups = []
#     current_line = [boxes_and_text[0]]
    
#     for i in range(1, len(boxes_and_text)):
#         current_box = boxes_and_text[i]
#         prev_box = boxes_and_text[i-1]
        
#         # Check if on same line (Y coordinate close)
#         if abs(current_box['y'] - prev_box['y']) <= y_threshold:
#             current_line.append(current_box)
#         else:
#             # Start new line
#             line_groups.append(current_line)
#             current_line = [current_box]
    
#     # Add last line
#     if current_line:
#         line_groups.append(current_line)
    
#     # Reconstruct lines with proper spacing
#     lines = []
    
#     for line_group in line_groups:
#         # Sort boxes in line by X coordinate (left to right)
#         line_group.sort(key=lambda box: box['x_left'])
        
#         # Build line with spacing
#         line_text = reconstruct_line_with_spacing(line_group)
#         lines.append(line_text)
    
#     return lines


# def reconstruct_line_with_spacing(line_boxes):
#     """
#     Reconstruct a line preserving horizontal spacing between text boxes.
#     Important for tabular/columnar layouts.
#     """
#     if not line_boxes:
#         return ""
    
#     # Calculate average character width for spacing
#     total_width = sum(box['width'] for box in line_boxes)
#     total_chars = sum(len(box['text']) for box in line_boxes)
#     avg_char_width = total_width / total_chars if total_chars > 0 else 10
    
#     # Build line with spaces
#     line_parts = []
    
#     for i, box in enumerate(line_boxes):
#         if i == 0:
#             # First box - just add text
#             line_parts.append(box['text'])
#         else:
#             # Calculate gap from previous box
#             prev_box = line_boxes[i-1]
#             gap = box['x_left'] - prev_box['x_right']
            
#             # Convert gap to number of spaces
#             num_spaces = int(gap / avg_char_width)
            
#             # Add appropriate spacing
#             if num_spaces > 8:
#                 # Large gap = likely tabular column
#                 line_parts.append('  ' * 4)  # Use 8 spaces for columns
#             elif num_spaces > 2:
#                 # Medium gap = likely separate fields
#                 line_parts.append('  ')  # Use 2 spaces
#             else:
#                 # Small gap = normal word spacing
#                 line_parts.append(' ')
            
#             line_parts.append(box['text'])
    
#     return ''.join(line_parts)


# # ========================================
# # ALTERNATIVE: Simple version without spacing preservation
# # ========================================
# def run_vision_simple(image):
#     """
#     Simpler version that just extracts text in reading order.
#     Use this if spacing preservation causes issues.
#     """
#     if image is None:
#         return [], 0.0
    
#     try:
#         result = ocr.ocr(image, cls=True)
        
#         if not result or not result[0]:
#             return [], 0.0
        
#         # Extract and sort
#         items = []
#         total_conf = 0.0
        
#         for line in result[0]:
#             box = line[0]
#             text, conf = line[1]
            
#             y = (box[0][1] + box[2][1]) / 2
#             x = box[0][0]
            
#             items.append({
#                 'text': text,
#                 'conf': conf,
#                 'y': y,
#                 'x': x
#             })
#             total_conf += conf
        
#         # Sort top-to-bottom, left-to-right
#         items.sort(key=lambda item: (item['y'], item['x']))
        
#         # Extract lines
#         lines = [item['text'] for item in items]
#         avg_conf = total_conf / len(items) if items else 0.0
        
#         return lines, avg_conf
        
#     except Exception as e:
#         print(f"OCR Error: {e}")
#         return [], 0.0