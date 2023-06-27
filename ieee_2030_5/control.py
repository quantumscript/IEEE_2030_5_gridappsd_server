from ast import Dict
from pathlib import Path
import readline
import shlex
from typing import List

import yaml

import ieee_2030_5.models as m

data = {}

class CommandError(Exception):
    pass

def menu():
    
    print(f"""
Options are as follows:

{"help":<40} Show this message

Sections:
  {"controls":<38} Enter control editing mode
  {"devices":<38} Enter device editing mode
  {"programs":<38} Enter program editing mode

Commands:
  {"restore":<38} Restore from the cached config in case of a crash
  {"load config <filename>":<38} Load a config from yaml
  {"store config <filename>":<38} Store config <filename> to yaml
  {"quit (q)":<38} Exit Program
""")

    
def check_loaded(data):
    if not data:
        raise CommandError(f"Load the config before {cmd}")


def load_config(filename) -> Dict:
    pth = Path(filename)
    if not pth.exists():
        raise CommandError(f"Invalid filename ('{filename}')")
    data = yaml.safe_load(pth.read_text())
    print(f"Loaded {filename}")
    return data


def store_config(filename, data):
    pth = Path(filename)
    with pth.open('w') as fs:
        yaml.dump(data, fs) 
    print(f"Stored {filename}")


def print_list(heading, items: List):
    print(heading)
    print("-" * 30)
    for item in items:
        print(item)
            

def print_devices(devices):
    print_list("Devices", devices)
        

def print_programs(programs):
    print_list("Programs", programs) 
    

def print_controls(controls):
    print_list("Controls", controls)
          

def handle_controls():
    global data
    controls = data.get('controls', [])
    if not controls:
        data['controls'] = controls
    default_prompt = "controls>"
    prompt = default_prompt
    current_item = -1
    while True:
        
        cmd, *args = shlex.split(input(prompt))
        try:
            if cmd == "q":                
                if prompt == default_prompt:
                    break
                else:
                    prompt = default_prompt
            elif cmd == "new":
                try:
                    description, *other = args
                except ValueError:
                    raise CommandError("Must specify a description")
                if other:
                    raise CommandError("Only a description passed to new")
                controls.append(dict(description=description))
                prompt = f"{default_prompt}{len(controls)}>{description}>"
                current_item = len(controls) - 1
            elif cmd == "set":
                args
                key, value = args
                controls[current_item][key] = value
            elif cmd in ("ls", "show"):
                print_controls(controls)
            else:
                raise CommandError(f"Invalid command specified {cmd}")
                
        except CommandError as ex:
            print(ex)
        finally:
            store_working()

def handle_device_settings(device_index: int):
    global data
    settings = data["devices"][device_index].get("settings", {})
    if not settings:
        data["devices"][device_index]["settings"] = settings
        
    default_prompt = f"devices>{data['devices'][device_index]['id']}>settings>"
    prompt = default_prompt
    
    while True:
        
        cmd, *args = shlex.split(input(prompt))
        try:
            if cmd in ("q", "quit"):
                if prompt == default_prompt:
                    break
                else:
                    prompt = default_prompt
            elif cmd == "set":
                try:
                    key, value = args
                    settings[key] = value
                except ValueError:
                    raise CommandError("Invalid arguments passed to set.")
        except CommandError as ex:
            print(ex.args[0])

def handle_end_devices():
    global data
    end_devices = data.get('devices', [])
    if not end_devices:
        data['devices'] = end_devices
    default_prompt = "devices>"
    prompt = default_prompt
    current_item = -1
    while True:
        
        cmd, *args = shlex.split(input(prompt))
        try:
            if cmd in ("q", "quit"):
                if prompt == default_prompt:
                    break
                else:
                    prompt = default_prompt
            elif cmd == "new":
                try:
                    id, *other = args
                except ValueError:
                    raise CommandError("Must specify an id")
                if other:
                    raise CommandError("Only a id passed to new")
                
                found_at = [index for index, dev in enumerate(end_devices) if dev['id'] == id]
                if found_at:
                    current_item = [found_at]
                else:
                    end_devices.append(dict(id=id))
                    current_item = len(end_devices) -1
                prompt = f"{default_prompt}{len(end_devices)}>{id}>"
                
            elif cmd == "set":
                key, value = args
                end_devices[current_item][key] = value
            elif cmd in ("ls", "show"):
                print_controls(end_devices)
            elif cmd == "settings":
                try:
                    current_item = int(args[0])
                    if current_item > len(end_devices) - 1 or current_item < 0:
                        raise CommandError("Invalid end device index")
                    
                    handle_device_settings(current_item)
                except (IndexError, ValueError):
                    raise CommandError("Missing index to end device")
                
            else:
                raise CommandError(f"Invalid command specified {cmd}")
                
        except CommandError as ex:
            print(ex)
        finally:
            store_working()
        

def handle_programs():
    global data
    devices = data.get("devices", [])
    if not devices:
        data["devices"] = devices
    controls = data.get('controls', [])
    if not controls:
        data['controls'] = controls
    programs = data.get('programs', [])
    if not programs:
        data['programs'] = programs
    default_prompt = "programs>"
    prompt = default_prompt
    current_item = -1
    while True:
        
        cmd, *args = shlex.split(input(prompt))
        try:
            if cmd == "q":
                if prompt == default_prompt:
                    break
                else:
                    prompt = default_prompt
            elif cmd == "new":
                try:
                    description, *other = args
                except ValueError:
                    raise CommandError("Must specify a description")
                if other:
                    raise CommandError("Only a description passed to new")
                programs.append(dict(description=description))
                prompt = f"programs>{len(programs)}>{description}>"
                current_item = len(programs) - 1
            elif cmd == "set":
                key, value = args
                programs[current_item][key] = value
            elif cmd == "control":
                try:
                    op, index, *other = args
                    
                    index = int(index)
                    if index >= len(controls):
                        raise CommandError(f"Invalid control index specified for default control {index}")
                    if op == "default":
                        programs[current_item]["default_control"] = index
                    elif op == "add":
                        current_controls = programs[current_item].get("controls", [])
                        if not current_controls:
                            programs[current_item]["controls"] = current_controls
                        if index in current_controls:
                            raise CommandError("Index already present in controls")
                        programs[current_item]["controls"].append(index)
                        
                except ValueError:
                    raise CommandError("Specify index of control to be default") 
            elif cmd in ("ls", "show"):
                print_programs(programs)
            else:
                raise CommandError(f"Invalid command specified {cmd}")
                
        except CommandError as ex:
            print(ex)
        finally:
            store_working()
    

def store_working():
    pth = Path("/tmp/.working_data")
    with pth.open('w') as fs:
        yaml.dump(data, fs)


def load_working():
    pth = Path("/tmp/.working_data")
    if pth.exists():
        with pth.open('r') as fs:
            working = yaml.safe_load(fs)
            data.update(working)

def print_all():
    global_items = [{"id": k, "value": data[k]} for k in sorted(data) if data not in ('devices', 'controls', 'programs')]
    print_list("Global", global_items)
    print_controls(data.get('controls', []))
    print_devices(data.get('devices', []))
    print_programs(data.get('programs', []))
    
    
def _main():
    global data
    
    file_type = ""
    
    while True:
        cmd, *args = shlex.split(input('> '))
        try:
            if cmd == "q" or cmd == "quit":
                break
            elif cmd == "help":
                menu()
            elif cmd == "load":
                file_type, file = args 
                if file_type == "config":
                    data = load_config(file)
                else:
                    raise CommandError(f"Invalid file_type {file_type}")
            elif cmd == "store":
                check_loaded(data)
                new_file_type, file = args 
                if new_file_type == "config":
                    store_config(file, data)
                else:
                    raise CommandError(f"Invalid file_type {new_file_type}")
            elif cmd == "devices":
                handle_end_devices()
            elif cmd == "programs":
                handle_programs()
            elif cmd == "controls":
                handle_controls()
            elif cmd == "show":
                print_all()
            elif cmd == "set":
                try:
                    key, value = args
                except ValueError:
                    raise CommandError("Not enough arguments to set.  set key value is the format.")
                    
                available_keys = ['proxy_hostname', 'server_hostname', "server_mode", "tls_repository"]
                if key not in available_keys:
                    raise CommandError(f"{key} was not in the available list of properties that can be set.")
                data[key] = value
            elif cmd == "restore":
                load_working()
            else:
                raise CommandError(f"Invalid command {cmd}")
            
        except CommandError as ex:
            print(ex.args[0])                 
        finally:
            store_working()
if __name__ == '__main__':
    _main()
        

