import os
import json
import threading
import time
from automation_utils import *
from pathlib import Path
from icecream import ic
with open('key_code.txt') as f:
    line = f.read()
exec(f'key_code = {eval(line.lower())}')
key_sequence = []
hot_keys = []
save=[]
exit_event = threading.Event()
key_states = {key: False for key in key_code.keys()}
hotkey_active = False
is_text_visible = False
COORDINATES_FILE = 'image_coordinates.json'
active_window = False
r = None
wi = None
windows = None
m = None
def monitor_hotkeys(res, hide_keys, search_keys,exit_key):
    global hot_keys, key_sequence, hotkey_active, is_text_visible, windows, r, wi, m
    hide = sorted(str(hide_keys).split('+'))
    search = sorted(str(search_keys).split('+'))
    while not exit_event.is_set():
        if is_key_pressed(key_code[exit_key]):
            if exit_process(windows, exit_event):
                break
        current_keys_pressed = []
        for key, code in key_code.items():
            if is_key_pressed(code):
                current_keys_pressed.append(key)
        if len(current_keys_pressed) >= 2:
            if hot_keys != sorted(current_keys_pressed):
                hot_keys = sorted(current_keys_pressed)
                hotkey = '+'.join(hot_keys)
                key_sequence.clear()
                hotkey_active = True
                if hot_keys == hide:
                    is_text_visible, r, key_sequence, m, windows = load_window(is_text_visible, COORDINATES_FILE, res, save, key, windows)
                if hot_keys == search and is_text_visible:
                    r, m, key_sequence, windows = run_search(COORDINATES_FILE, res, save, key, windows)
                if r is not None:
                    for fp, imk in r.items():
                        if hotkey == fp:
                            simulate_mouse_click(imk, m)
                            key_sequence.clear()
            time.sleep(0.5)
        else:
            hotkey_active = False
        time.sleep(0.01)
def monitor_key_sequence(res, hide_keys, search_keys,exit_key):
    global key_sequence, hotkey_active, is_text_visible, windows, r, wi, m
    hide = str(hide_keys).split(',')
    search = str(search_keys).split(',')
    last_released_key = None
    while not exit_event.is_set():
        if is_key_pressed(key_code[exit_key]):
            if exit_process(windows, exit_event):
                break
        current_keys_pressed = []
        for key, code in key_code.items():
            if is_key_pressed(code):
                if not key_states[key]:
                    current_keys_pressed.append(key)
                key_states[key] = True
            else:
                if key_states[key]:
                    last_released_key = key
                    key_states[key] = False
        if last_released_key is not None:
            if not hotkey_active:
                key_sequence.append(last_released_key)
                tpkey = key_sequence[-len(hide):] if len(key_sequence) >= len(hide) else key_sequence
                skey = key_sequence[-len(search):] if len(key_sequence) >= len(search) else key_sequence
                if tpkey == hide:
                    is_text_visible, r, key_sequence, m, windows = load_window(
                        is_text_visible, COORDINATES_FILE, res, save, key, windows
                    )
                if skey == search and is_text_visible:
                    r, m, key_sequence, windows = run_search(
                        COORDINATES_FILE, res, save, key, windows
                    )
                if is_text_visible:
                    for i in range(5, 0, -1):
                        if len(key_sequence) >= i:
                            last_keys = ','.join(key_sequence[-i:])
                            if r is not None:
                                for fp, imk in r.items():
                                    if fp == last_keys:
                                        simulate_mouse_click(imk, m)
                                        key_sequence.clear()
            last_released_key = None
            if len(key_sequence) == 5:
                key_sequence.pop(0)
        time.sleep(0.01)

def check_and_update_image_directories():
    img_dir = Path("img")
    img_list = {}
    
    for rot, dirs, files in os.walk(img_dir):
        folder_name = Path(rot).relative_to(img_dir).as_posix()
        if folder_name not in img_list and folder_name != '.':
            img_list[folder_name] = []
        for file in files:
            img_list[folder_name].append(Path(rot, file).as_posix())
    
    if os.path.exists('data.json'):
        with open('data.json', 'r') as f:
            line = json.load(f)
        
        hide, serch, exit_key = None, None, None
        for key, title in line.items():
            if title == 'hide':
                hide = key
            elif title == 'search':
                serch = key
            elif title == 'exit':
                exit_key = key
        
        key_mapping = {v: k for k, v in line.items()}
        result = compile_image_data(img_list, key_mapping) 

        keyadd = [folder for folder, key in result.items() if not key[1]]
        
        max_key_index = max(int(key[3:]) for key in line.keys() if key.startswith('key')) if any(key.startswith('key') for key in line.keys()) else 0
        
        for item in keyadd:
            new_key = f'key{max_key_index + 1}'
            line[new_key] = item
            max_key_index += 1 
        with open('data.json', 'w') as f:
            json.dump(line, f, indent=4)

        if __name__ == "__main__":
            hotkey_thread = threading.Thread(target=monitor_hotkeys, args=(result, hide, serch,exit_key,))
            sequence_thread = threading.Thread(target=monitor_key_sequence, args=(result, hide, serch,exit_key,))
            hotkey_thread.start()
            sequence_thread.start()
            hotkey_thread.join()
            sequence_thread.join()
    else:
        line = {f'key{i+1}': folder for i, folder in enumerate(img_list.keys())}
        line.update({
            "key26": "hide",
            "key27": "search",
            "key28": "exit"
        })
        with open('data.json', 'w') as f:
            json.dump(line, f, indent=4)
check_and_update_image_directories()