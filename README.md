# Data Processing Script for DBC and Log Files
This script processes CAN bus data from DBC and log files, decodes the signals, and saves the results to CSV files. It also provides functionalities such as deleting the previous day's folder and handling missing data.

## Requirements
* Python 3.x
* os module
* csv module
* datetime module

## Usage
1. Directory Setup:

    * Place your log files in a directory named logs.
    * Ensure you have a directory named csv where the processed CSV files will be saved.

2. Script Execution:

Run the script using a Python interpreter. You will be prompted to enter the sample rate in milliseconds.

```
python dbc_parser.py

```

Replace dbc_parser.py with the actual name of your script.

## Script Structure

#### Functions

1. parse_dbc(file_path):

    * Parses a DBC file to extract message and signal details.
    * Returns a dictionary of messages with their respective signals.

2. parse_log(file_path, messages):

    * Parses a log file and decodes the messages using the information from the DBC file.
    * Returns a list of decoded messages.

3. split_string(string):

    * Splits a multiplexer string into prefix and suffix.

4. check_mux_equality(mux_value, mux_signal):

    * Checks if the multiplexer value matches the signal.

5. convert_number(num):

    * Converts a string number to an integer.

6. extract_mux_value(data_bytes):

    * Extracts the multiplexer value from data bytes.

7. extract_signal_value(data_bytes, start_bit, length, byte_order):

    * Extracts the signal value from data bytes.

8. evaluate_msb(data_bytes):

    * Evaluates the most significant bit of each byte in the data.

9. overall_sign(sign_values):

    * Determines the overall sign of the signal based on the MSB evaluation.

10. convert_to_signed_even_negative(raw_value, signal_length):

    * Converts a raw value to a signed value considering even negative condition.

11. convert_to_signed(raw_value, signal_length):

    * Converts a raw value to a signed value.

12. extract_signal(file_path):

    * Extracts signal names from a DBC file.

13. extract_signal_names(file_path, dbc_file_path):

    * Extracts signal names from both log and DBC files.

14. save_to_csv(decoded_messages, decoded_signals_keys, csv_file_path):

    * Saves decoded messages to a CSV file.

15. save_to_csv2(decoded_messages, decoded_signals_keys, csv_file_path, csv_file_name, sample_rate_ms):

    * Saves decoded messages to a CSV file with sample rate consideration.

16. delete_folder_previous_day(folder_path):

    * Deletes the previous day's folder from the specified path.

17. process_data(sample_rate_ms):

    * Placeholder function to process data with a given sample rate.

## Main Script
The main script performs the following actions:

1. Sets up the log and CSV directories.
2. Parses the DBC file to extract message and signal information.
3. Asks the user for the sample rate in milliseconds.
4. Processes each log file, decodes the messages, and saves the results to a CSV file.
5. Optionally deletes the previous day's folder.

## Notes
* Ensure that the log files and DBC file paths are correctly specified in the script.
* The script assumes a specific format for the log and DBC files. Modify the parsing logic if your files have a different 

```

Copy code
.
├── script_name.py
├── logs
│   ├── log_file1.log
│   ├── log_file2.log
│   └── ...
├── csv
└── dbc
    └── foxbms 6.dbc

```

## Sample Execution

``` 
$ python script_name.py
Enter the sample rate in milliseconds: 100
Sample rate is: 100
Data from log_file1.log saved to CSV successfully.
Data from log_file2.log saved to CSV successfully.

```

This will process the log files in the logs directory, decode the signals using the foxbms 6.dbc file, and save the results to the csv directory.