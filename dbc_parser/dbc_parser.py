import csv
from datetime import datetime, timedelta
import os

def parse_dbc(file_path):
    messages = {}
    with open(file_path) as f:
        message_id = None
        for line in f:
            parts = line.strip().split()
            if len(parts) > 0:
                if parts[0] == "BO_":
                    message_id = int(parts[1])
                    message_name = parts[2]
                    message_length = int(parts[3])
                    message_id = message_id & 0x1FFFFFFF
                    message_id = hex(message_id).upper()
                    message_id = int(message_id, 16)
                    message_id = message_id & 0x1FFFFFFF
                    messages[message_id] = {"name": message_name, "length": message_length, "signals": {}}
                elif parts[0] == "SG_" and message_id is not None and len(parts) > 3:
                    signal_name_parts = parts[1].split()
                    signal_name = signal_name_parts[0]
                    if len(signal_name_parts) > 1 and signal_name_parts[-1] != 'm0':
                        signal_name += '_' + signal_name_parts[-1]
                    signal_mux = parts[2] if len(parts) > 4 and parts[3] == ':' else None
                    if signal_mux is None:
                        signal_start_bit = int(parts[3].split("|")[0])
                        signal_length = int(parts[3].split("|")[1].split("@")[0])
                        signal_byte_order = parts[3].split("@")[1][0]
                    else:
                        signal_start_bit = int(parts[4].split("|")[0])
                        signal_length = int(parts[4].split("|")[1].split("@")[0])
                        signal_byte_order = parts[4].split("@")[1][0]
                    if signal_byte_order == "1":
                        signal_byte_order = "little_endian"
                    else:
                        signal_byte_order = "big_endian"
                    signal_value_type = None
                    for char in parts[3 if signal_mux is None else 4]:
                        if char in "+-":
                            signal_value_type = char
                        if signal_value_type == "+":
                            signal_value_type = "unsigned"
                        else:
                            signal_value_type = "signed"
                    factor, offset = parts[4 if signal_mux is None else 5].strip('()').split(',')
                    signal_offset = float(offset)
                    signal_factor = float(factor)
                    min, max = parts[5 if signal_mux is None else 6].strip('[]').split('|')   
                    signal_min = float(min)
                    signal_max = float(max)
                    signal_unit = parts[6 if signal_mux is None else 7][1:-1]
                    signal_placeholder = parts[7 if signal_mux is None else 8]
                    messages[message_id]["signals"][signal_name] = {
                        "multiplexer": signal_mux,
                        "start_bit": signal_start_bit,
                        "length": signal_length,
                        "byte_order": signal_byte_order,
                        "value_type": signal_value_type,
                        "factor": signal_factor,
                        "offset": signal_offset,
                        "min": signal_min,
                        "max": signal_max,
                        "unit": signal_unit,
                        "placeholder": signal_placeholder
                    }
    return messages

def parse_log(file_path, messages):
    decoded_messages = []

    with open(file_path) as f:
        for _ in range(14):
            next(f)
        for line in f:
            try:
                TIME_STAMP_str, _, _, _ = line.strip().split(maxsplit=3)
                TIME_STAMP = datetime.strptime(TIME_STAMP_str, "%H:%M:%S:%f")
                TIME_STAMP_str = TIME_STAMP.strftime("%H:%M:%S:%f")[:-2]
                TIME_STAMP = TIME_STAMP_str
            except ValueError:
                continue

            if "Rx" in line:
                parts = line.strip().split()
                channel = int(parts[2])
                message_id_str = parts[3]
                if message_id_str.startswith("0x"):
                    message_id = int(message_id_str, 16)
                else:
                    message_id = int(message_id_str)
                type = parts[4]
                data_bytes = parts[6:]

                if message_id in messages:
                    message_length = messages[message_id]["length"]
                    message_name = messages[message_id]["name"]
                    decoded_signals = {}
                    error_condition = None

                    msb_values = evaluate_msb(data_bytes)
                    overall_sign_result = overall_sign(msb_values)

                    for signal_name, signal_info in messages[message_id]["signals"].items():
                        multiplexer = signal_info["multiplexer"]
                        start_bit = signal_info["start_bit"]
                        signal_length = signal_info["length"]
                        byte_order = signal_info["byte_order"]
                        value_type = signal_info["value_type"]
                        factor = signal_info["factor"]
                        offset = signal_info["offset"]
                        signal_min = signal_info["min"]
                        signal_max = signal_info["max"]
                        signal_unit = signal_info["unit"]
                        signal_placeholder = signal_info["placeholder"]

                        raw_value = extract_signal_value(data_bytes, start_bit, signal_length, byte_order)
                        if multiplexer:
                            if "M" in multiplexer:
                                continue 
                            mux_value = extract_mux_value(data_bytes) 
                            prefix, suffix = split_string(multiplexer)
                            mux_signal = convert_number(suffix)
                            multiplexer_value = check_mux_equality(mux_value, mux_signal)
                            if multiplexer_value:
                                mux_signal_name = f"{signal_name}"
                                if mux_signal_name not in decoded_signals:
                                    decoded_signals[mux_signal_name] = {}
                                  
                                if value_type == "unsigned":
                                    physical_value = (raw_value * factor) + offset
                                else:
                                    if overall_sign_result == "Even Negative":
                                        decimal_value = convert_to_signed_even_negative(raw_value, signal_length)
                                        physical_value = (decimal_value * factor) + offset
                                    else:
                                        if value_type == "signed":
                                            physical_value = convert_to_signed(raw_value, signal_length)
                                            physical_value = (physical_value * factor) + offset
                                        else:
                                            physical_value = convert_to_signed(raw_value, signal_length)
                                            physical_value = (physical_value * factor) + offset
                                physical_value = min(max(physical_value, signal_min), signal_max)

                                decoded_signals[mux_signal_name] = physical_value
                        else:
                            if signal_name not in decoded_signals:
                                decoded_signals[signal_name] = {}

                            if value_type == "unsigned":
                                physical_value = (raw_value * factor) + offset
                            else:
                                if overall_sign_result == "Even Negative":
                                    decimal_value = convert_to_signed_even_negative(raw_value, signal_length)
                                    physical_value = (decimal_value * factor) + offset
                                else:
                                    if value_type == "signed":
                                        physical_value = convert_to_signed(raw_value, signal_length)
                                        physical_value = (physical_value * factor) + offset
                                    else:
                                        physical_value = convert_to_signed(raw_value, signal_length)
                                        physical_value = (physical_value * factor) + offset
                            physical_value = min(max(physical_value, signal_min), signal_max)

                            decoded_signals[signal_name] = physical_value

                    decoded_messages.append({
                        "TIME_STAMP": TIME_STAMP,
                        "MESSAGE_NAME": message_name,
                        "DECODED_SIGNALS": decoded_signals
                    })

    return decoded_messages

def split_string(string):
    if string[0] == 'm':
        prefix = 'm'
        suffix = string[1:]
    else:
        prefix = ''
        suffix = string

    return prefix, suffix

def check_mux_equality(mux_value, mux_signal):
    return mux_value == mux_signal

def convert_number(num):
    if num.startswith('0'):
        return int(num)
    else:
        return int(num.lstrip('0'))
    
# Function to extract multiplexer value
def extract_mux_value(data_bytes):
    return int(data_bytes[0],16)

def extract_signal_value(data_bytes, start_bit, length, byte_order):
    byte_index = start_bit // 8
    bit_offset = start_bit % 8
    raw_value = 0
    
    for i in range(length):
        if byte_index >= len(data_bytes):
            break
        byte_value = int(data_bytes[byte_index], 16)
        if byte_order == "big_endian":
            byte_value >>= bit_offset
            raw_value |= (byte_value & 0x01) << (length - i - 1)
            bit_offset -= 1
            if bit_offset < 0:
                byte_index += 1
                bit_offset = 7
        elif byte_order == "little_endian":
            byte_value >>= bit_offset
            raw_value |= (byte_value & 0x01) << i
            bit_offset += 1
            if bit_offset >= 8:
                byte_index += 1
                bit_offset = 0

    return raw_value

def evaluate_msb(data_bytes):
    sign_values = []

    for data_byte in data_bytes:
        msb = (int(data_byte, 16) & 0x80) >> 7  # Extract the MSB (Most Significant Bit)
        sign = "Negative" if msb == 1 else "Positive"
        sign_values.append(sign)

    return sign_values

def overall_sign(sign_values):
    count_positive = sign_values.count("Positive")
    count_negative = sign_values.count("Negative")

    if count_positive % 2 == 0:
        return "Even Negative"
    else:
        return "Odd Positive"

def convert_to_signed_even_negative(raw_value, signal_length):
    binary_str = format(raw_value, f"0{signal_length}b")
    decimal_value = int(binary_str, 2)
    if decimal_value >= 2 ** (signal_length - 1):
        decimal_value -= 2 ** signal_length
    return decimal_value

def convert_to_signed(raw_value, signal_length):
    if raw_value >= 2 ** (signal_length - 1):
        return raw_value - 2 ** signal_length
    else:
        return raw_value


def extract_signal(file_path):
    signal_names = []
    with open(file_path) as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) > 0 and parts[0] == "SG_":
                signal_name_parts = parts[1].split()
                signal_name = signal_name_parts[0]
                if len(signal_name_parts) > 1 and signal_name_parts[-1] != 'm0':
                    signal_name += '_' + signal_name_parts[-1]
                signal_names.append(signal_name)
    return signal_names

def extract_signal_names(file_path, dbc_file_path):
    messages = parse_dbc(dbc_file_path)
    decoded_signals = set()

    with open(file_path) as f:
        for _ in range(14):
            next(f)
        for line in f:
            try:
                TIME_STAMP_str, _, _, _ = line.strip().split(maxsplit=3)
                TIME_STAMP = TIME_STAMP_str
                
            except ValueError:
                continue

            if "Rx" in line:
                parts = line.strip().split()
                message_id_str = parts[3]
                if message_id_str.startswith("0x"):
                    message_id = int(message_id_str[2:], 16)
                else:
                    message_id = int(message_id_str)
                if message_id in messages:
                    for signal_name in messages[message_id]["signals"].keys():
                        decoded_signals.add(signal_name)

    return list(decoded_signals)

def save_to_csv(decoded_messages, decoded_signals_keys, csv_file_path):
    try:
        date_folder = datetime.now().strftime('%d-%m-%Y')
        folder_path = os.path.join(csv_file_path, date_folder)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        # Create CSV file path with date folder
        counter = 1
        csv_file_name = datetime.now().strftime('%d-%m-%Y') + "_LOG_DBC_PROCESSED_" + str(counter) + ".csv"
        csv_file_path = os.path.join(folder_path, csv_file_name)

        with open(csv_file_path, 'w', newline='') as csvfile:
            fieldnames = ["TIME_STAMP"] + decoded_signals_keys
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for message in decoded_messages:
                # Convert TIME_STAMP string to datetime object
                TIME_STAMP = datetime.strptime(message["TIME_STAMP"], "%H:%M:%S:%f").time()
                # Format TIME_STAMP with milliseconds
                formatted_TIME_STAMP = TIME_STAMP.strftime("%H:%M:%S:%f")[:-2]
                row = {"TIME_STAMP": formatted_TIME_STAMP}
                row.update({signal_name: message["DECODED_SIGNALS"].get(signal_name, "nan") for signal_name in decoded_signals_keys})
                # Check if row has any non-zero signal data
                if sum([float(val) for key, val in row.items() if key in decoded_signals_keys and val != "nan"]):
                    writer.writerow(row)
        return True
    except Exception as e:
        print(f"Error saving to CSV: {str(e)}")
        return False

def save_to_csv2(decoded_messages, decoded_signals_keys, csv_file_path, csv_file_name, sample_rate_ms):
    # Initialize a dictionary to store the previous values
    previous_values = {signal_name: None for signal_name in decoded_signals_keys}

    try:
        with open(os.path.join(csv_file_path, csv_file_name), 'w', newline='') as csvfile:
            fieldnames = ["TIME_STAMP"] + decoded_signals_keys
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            last_write_time = None

            for message in decoded_messages:
                TIME_STAMP = datetime.strptime(message["TIME_STAMP"], "%H:%M:%S:%f").time()
                formatted_TIME_STAMP = TIME_STAMP.strftime("%H:%M:%S:%f")[:-2]
                row = {"TIME_STAMP": formatted_TIME_STAMP}

                for signal_name in decoded_signals_keys:
                    current_value = message["DECODED_SIGNALS"].get(signal_name, None)
                    if current_value is None or current_value == "nan":
                        current_value = previous_values[signal_name]

                    row[signal_name] = current_value
                    previous_values[signal_name] = current_value

                if any(val is not None and val != "nan" for val in row.values()):
                    if last_write_time is None or (datetime.strptime(formatted_TIME_STAMP, "%H:%M:%S:%f") - last_write_time) >= timedelta(milliseconds=sample_rate_ms):
                        writer.writerow(row)
                        last_write_time = datetime.strptime(formatted_TIME_STAMP, "%H:%M:%S:%f")

        return True
    except Exception as e:
        print(f"Error saving to CSV: {str(e)}")
        return False

    
def delete_folder_previous_day(folder_path):
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%d-%m-%Y')
    folder_path_yesterday = os.path.join(folder_path, yesterday)

    # Check if the folder exists
    if os.path.exists(folder_path_yesterday):
        os.system(f"rm -rf {folder_path_yesterday}")
        print(f"The folder {folder_path_yesterday} has been deleted.")
    else:
        print(f"The folder {folder_path_yesterday} does not exist.")

def process_data(sample_rate_ms):
    # Your code here
    print("Sample rate is:", sample_rate_ms)
    
if __name__ == "__main__":
    log_directory = 'logs'  # Specify the directory where log files are located
    csv_file_path = 'csv'  # Specify the directory where CSV files will be saved

    # Ensure that the CSV directory exists; create it if it doesn't
    if not os.path.exists(csv_file_path):
        os.makedirs(csv_file_path)

    # Get a list of log files in the log directory
    log_files = [f for f in os.listdir(log_directory) if f.endswith('.log')]

    for log_file in log_files:
        # Parse the DBC file and extract signal names (assuming they are the same for all logs)
        file_path = 'dbc/foxbms 6.dbc'  # You can specify the DBC file path
        messages = parse_dbc(file_path)
        sample_rate_ms = int(input("Enter the sample rate in milliseconds: "))
        process_data(sample_rate_ms)
        # with open('frontend.txt', 'r') as file:
        #     data = file.read().splitlines()
            
        # formatted_names = [f'"{name}"' for name in data]
        # decoded_signals_keys = [name.strip('"') for name in formatted_names]
        decoded_signals_keys = extract_signal(file_path)
        log_file_path = os.path.join(log_directory, log_file)
        decoded_messages = parse_log(log_file_path, messages)

        # Use the log file name as the CSV file name
        csv_file_name = os.path.splitext(log_file)[0] + ".csv"
        csv_file_path_full = os.path.join(csv_file_path, csv_file_name)

        if save_to_csv2(decoded_messages, decoded_signals_keys, csv_file_path, csv_file_name, sample_rate_ms):
            print(f"Data from {log_file} saved to CSV successfully.")
        else:
            print(f"Error saving data from {log_file} to CSV.")

    # Delete the previous day's folder (uncomment this line if needed)
    # delete_folder_previous_day(csv_file_path)
