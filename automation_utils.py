import sys
import mss
import multiprocessing
import numpy as np
import ctypes
import cv2
import os
import tkinter as tk
from numba import prange
import json
import pyautogui
from concurrent.futures import ThreadPoolExecutor
def capture_screen():
    with mss.mss() as sct:
        monitor = sct.monitors[0]
        return sct.grab(monitor)
def convert_to_grayscale(screenshot):
    return cv2.cvtColor(np.array(screenshot, dtype=np.uint8)[:, :, :3], cv2.COLOR_BGR2GRAY)
def screenshot():
    with mss.mss() as sct:
        if len(sct.monitors) < 2:
            return None
        with ThreadPoolExecutor(max_workers=2) as executor:
            screenshot = executor.submit(capture_screen).result()
            gray_screenshot = executor.submit(convert_to_grayscale, screenshot).result()
    return gray_screenshot
def simulate_mouse_click(click_position, monitor_config):
    if click_position is not None:
        offset = (monitor_config['left'], monitor_config['top'])
        current_mouse_x, current_mouse_y = pyautogui.position()
        pyautogui.leftClick(click_position[0] + offset[0], click_position[1] + offset[1] + 8)
        pyautogui.moveTo(current_mouse_x, current_mouse_y)
def compile_image_data(image_directory_list, metadata_dict):
    compiled_result = {}
    for folder_name, image_files in image_directory_list.items():
        compiled_result[folder_name] = [image_files, metadata_dict.get(folder_name, [])]
    compiled_result = {folder: data for folder, data in compiled_result.items() if data[0] or data[1]}
    return compiled_result
def click_on_image(image_file_paths, coordinate_map, output_list, grayscale_screenshot, search_for_image=False):
    if coordinate_map is None:
        coordinate_map = {}
    if output_list is None:
        output_list = []
    if isinstance(image_file_paths, str):
        image_file_paths = [[image_file_paths]]
    for image_file_path in image_file_paths:
        try:
            template_image = cv2.imread(image_file_path, cv2.IMREAD_GRAYSCALE)
            if template_image is None and not search_for_image:
                continue
            elif image_file_path in coordinate_map and not search_for_image:
                for coordinate in coordinate_map[image_file_path]:
                    try:
                        if is_template_found_at(coordinate, template_image, grayscale_screenshot):
                            output_list.append(image_file_path)
                            output_list.append(coordinate[0])
                            output_list.append(coordinate[1])
                            return coordinate, output_list
                    except Exception:
                        pass
            elif search_for_image:
                result_matrix = cv2.matchTemplate(grayscale_screenshot, template_image, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(result_matrix)
                if max_val >= 0.8:
                    height, width = template_image.shape[:2]
                    center_x = max_loc[0] + width // 2
                    center_y = max_loc[1] + height // 2
                    coordinate = [center_x, center_y]
                    output_list.append(image_file_path)
                    output_list.append(center_x)
                    output_list.append(center_y)
                    return coordinate, output_list
        except (FileNotFoundError, cv2.error):
            continue
    return None, None
def is_template_found_at(coordinates, template_image, grayscale_screenshot):
    height, width = template_image.shape[:2]
    x, y = coordinates
    search_region = (
        max(0, x - width // 2 - 1),
        max(0, y - height // 2 - 1),
        x + width // 2 + 1,
        y + height // 2 + 1
    )
    result_matrix = cv2.matchTemplate(
        grayscale_screenshot[search_region[1]:search_region[3], search_region[0]:search_region[2]],
        template_image,
        cv2.TM_CCOEFF_NORMED
    )
    _, maximum_value, _, _ = cv2.minMaxLoc(result_matrix)
    return maximum_value >= 0.8
def process_window(image_mapping, coordinates_map, output_list, grayscale_screenshot, coordinates_file_path, key_mapping, log_enabled=False):
    if key_mapping == 'oemclr':
        key_mapping = {}
    if os.path.exists(coordinates_file_path) and not log_enabled:
        for _, images in image_mapping.items():
            if images[0]:
                center_coordinates, saved_data = click_on_image(images[0], coordinates_map, output_list, grayscale_screenshot)
                output_list = saved_data
                if center_coordinates is not None:
                    try:
                        key_mapping[images[1]] = center_coordinates
                    except Exception:
                        continue
        return saved_data, key_mapping
    elif not os.path.exists(coordinates_file_path) or log_enabled:
        for _, images in image_mapping.items():
            if images:
                center_coordinates, saved_data = click_on_image(images[0], coordinates_map, output_list, grayscale_screenshot, True)
                if saved_data is not None and len(saved_data) > len(output_list):
                    output_list = saved_data
                if center_coordinates is not None:
                    key_mapping[images[1]] = center_coordinates
        save_coordinates_batch(output_list, coordinates_file_path)
        return output_list, key_mapping
    return None, None
def save_coordinates_batch(save,COORDINATES_FILE):
    if len(save) % 3 != 0:
        return
    coordinates_dict = load_coordinates(COORDINATES_FILE)
    for i in prange(0, len(save), 3):
        image_path = save[i]
        x = save[i + 1]
        y = save[i + 2]
        if image_path not in coordinates_dict:
            coordinates_dict[image_path] = []
        coord_set = set(tuple(c) for c in coordinates_dict[image_path])
        coord_set.add((x, y))
        new_coords_list = [list(c) for c in coord_set]
        if len(new_coords_list) > 3:
            new_coords_list.pop(0)
        coordinates_dict[image_path] = new_coords_list
    with open(COORDINATES_FILE, 'w') as f:
        json.dump(coordinates_dict, f)
def load_coordinates(COORDINATES_FILE):
    if os.path.exists(COORDINATES_FILE):
        with open(COORDINATES_FILE, 'r') as f:
            return json.load(f)
    return {}
def is_key_pressed(virtual_key_code):
    if sys.platform == "win32":
        # Windows
        state = ctypes.windll.user32.GetAsyncKeyState(virtual_key_code)
        return state & 0x8000 != 0
    elif sys.platform == "darwin":
        # macOS
        from AppKit import NSEvent
        # Применение NSEvent для проверки состояния клавиши
        current_event = NSEvent.pressingKeys()
        return virtual_key_code in current_event
    elif sys.platform == "linux":
        # Linux: использование с клавиатурой X11
        from Xlib import X, display
        from Xlib.protocol import request
        d = display.Display()
        root = d.screen().root
        key_state = root.query_keymap()
        return key_state[virtual_key_code % 256] != 0  # 256 - количество кнопок в X11
    else:
        raise NotImplementedError("Unsupported platform: {}".format(sys.platform))
def draw_text_with_background(canvas, center, text, text_color='red', bg_color='yellow', font=('Arial', 8)):
    text_id = canvas.create_text(center[0]-5, center[1]-5, text=text, fill=text_color, font=font)
    text_bbox = canvas.bbox(text_id)
    canvas.create_rectangle(
        text_bbox[0],
        text_bbox[1],
        text_bbox[2],
        text_bbox[3],
        fill=bg_color,
        outline=''
    )
    canvas.create_text(center[0]-5, center[1]-5, text=text, fill=text_color, font=font)
def creative_win():
    monitors = mss.mss().monitors
    if len(monitors) > 0:
        monitor = monitors[0]
        root = tk.Tk()
        root.overrideredirect(True)
        root.configure(background='black')
        root.wm_attributes('-topmost', True)
        root.wm_attributes("-transparentcolor", "black")
        root.geometry(f"{monitor['width']}x{monitor['height']}+{monitor['left']}+{monitor['top']}")
        root.focus_set()
        canvas = tk.Canvas(root, width=monitor['width'], height=monitor['height'], bg='black')
        canvas.pack()
        return root,canvas,monitor
    else:
        pass
def run_gui(res, coordinates, save, gray_screenshot, COORDINATES_FILE, key, qres, log=False):
    root, canvas, monitor = creative_win()
    savel, key1 = process_window(res, coordinates, save, gray_screenshot, COORDINATES_FILE, key, log)
    qres.put((key1, monitor))
    for keydown, coord in key1.items():
        draw_text_with_background(canvas, coord, keydown)
    root.mainloop()
def hide_def(is_text_visible, coordinates_file_path, result, save_data, key_mapping, gui_process):
    result_value = None
    message_value = None
    key_sequence = []
    if is_text_visible:
        coordinates = load_coordinates(coordinates_file_path)
        grayscale_screenshot = screenshot()
        queue_result = multiprocessing.Queue()
        gui_process = multiprocessing.Process(
            target=run_gui,
            args=(result, coordinates, save_data, grayscale_screenshot, coordinates_file_path, key_mapping, queue_result)
        )
        gui_process.start()
        while result_value is None:
            try:
                result_value, message_value = queue_result.get(timeout=1)
            except multiprocessing.queues.Empty:
                pass
    else:
        try:
            gui_process.terminate()
        except Exception:
            pass
    return result_value, key_sequence, gui_process, message_value
def search_definition(result, coordinates, save_data, grayscale_screenshot, coordinates_file_path, key_mapping):
    result_value = None
    coordinates = load_coordinates(coordinates_file_path)
    queue_result = multiprocessing.Queue()
    gui_process = multiprocessing.Process(
        target=run_gui,
        args=(result, coordinates, save_data, grayscale_screenshot, coordinates_file_path, key_mapping, queue_result, True)
    )
    gui_process.start()
    while result_value is None:
        try:
            result_value, message_value = queue_result.get(timeout=1)
        except multiprocessing.queues.Empty:
            pass
    return result_value, gui_process, message_value
def exit_process(gui_process, exit_event):
    try:
        gui_process.terminate()
    except Exception as e:
        pass
    finally:
        exit_event.set()
        return True
def load_window(is_text_visible, coordinates_file_path, result, save_data, key_mapping, gui_process):
    is_text_visible = not is_text_visible
    result_value, key_sequence, process_window, message_value = hide_def(
        is_text_visible,
        coordinates_file_path,
        result,
        save_data,
        key_mapping,
        gui_process
    )
    return is_text_visible, result_value, key_sequence, message_value, process_window
def run_search(coordinates_file_path, result, save_data, key_mapping, gui_process):
    coordinates = load_coordinates(coordinates_file_path)
    result_value, key_sequence, window_activation, message_value = hide_def(
        False,
        coordinates_file_path,
        result,
        save_data,
        key_mapping,
        gui_process
    )
    gray_screenshot = screenshot()
    result_value, window, message_value = search_definition(
        result,
        coordinates,
        save_data,
        gray_screenshot,
        coordinates_file_path,
        key_mapping
    )
    return result_value, message_value, key_sequence, window
