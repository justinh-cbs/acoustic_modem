import sys
import os
import time
import threading
import csv
import math
from datetime import datetime
import matplotlib

matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, StringVar
from ttkthemes import ThemedTk

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from uwave_interface import UwaveMonitor


class UwaveGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("uWave Modem Controller")
        self.root.geometry("1024x600")

        style = ttk.Style()
        print("Available themes:", style.theme_names())
        print("Current theme:", style.theme_use())
        style.theme_use("blue")

        default_font = ("TkDefaultFont", 12)
        self.monitor = UwaveMonitor()
        self.worker_thread = None
        self.csv_file = "/home/pi/divenet/uwave_data.csv"

        # top-down view
        self.base_modem_pos = (0, 0)  # Position of base modem (local)
        self.remote_modem_pos = None  # Position of remote modem (will be calculated)
        self.modem_trail = []  # Trail of remote modem positions
        self.max_trail_length = 20  # Maximum number of positions to show

        self.status_var = StringVar(value="Ready")

        self.setup_ui()
        self.scan_ports()

        self.root.after(2000, self.update_plots)  # update every 2 seconds

    def setup_ui(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        self.control_tab = ttk.Frame(self.notebook)
        self.monitor_tab = ttk.Frame(self.notebook)
        self.console_tab = ttk.Frame(self.notebook)
        self.topdown_tab = ttk.Frame(self.notebook)
        self.log_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.control_tab, text="Control")
        self.notebook.add(self.monitor_tab, text="Monitor")
        self.notebook.add(self.console_tab, text="Console")
        self.notebook.add(self.topdown_tab, text="Top-Down View")
        self.notebook.add(self.log_tab, text="Log")

        self.setup_control_tab()
        self.setup_monitor_tab()
        self.setup_console_tab()
        self.setup_topdown_tab()
        self.setup_log_tab()

        status_frame = ttk.Frame(self.root, relief=tk.SUNKEN, height=26)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        status_frame.pack_propagate(False)  # Prevent resizing

        self.status_label = ttk.Label(
            status_frame,
            textvariable=self.status_var,
            font=("TkDefaultFont", 9, "bold"),
            anchor=tk.CENTER,
        )
        self.status_label.pack(fill=tk.X, padx=3, pady=3)

    def setup_control_tab(self):
        main_frame = ttk.Frame(self.control_tab)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # two-column layout
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3, pady=3)

        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=3, pady=3)

        # ==== LEFT SIDE ====
        # connection frame
        connection_frame = ttk.LabelFrame(left_frame, text="Connection")
        connection_frame.pack(fill=tk.X, padx=3, pady=3)

        # port selection
        port_frame = ttk.Frame(connection_frame)
        port_frame.pack(fill=tk.X, padx=3, pady=3)

        ttk.Label(port_frame, text="Port:").pack(side=tk.LEFT, padx=2)
        self.port_combo = ttk.Combobox(port_frame, width=20)
        self.port_combo.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)

        self.scan_button = ttk.Button(
            port_frame, text="Scan", width=8, command=self.scan_ports
        )
        self.scan_button.pack(side=tk.LEFT, padx=2)

        # connect/disconnect buttons
        button_frame = ttk.Frame(connection_frame)
        button_frame.pack(fill=tk.X, padx=3, pady=3)

        self.connect_button = ttk.Button(
            button_frame, text="Connect", command=self.connect_modem
        )
        self.connect_button.pack(side=tk.LEFT, padx=2, pady=2, fill=tk.X, expand=True)

        self.disconnect_button = ttk.Button(
            button_frame,
            text="Disconnect",
            command=self.disconnect_modem,
            state=tk.DISABLED,
        )
        self.disconnect_button.pack(
            side=tk.LEFT, padx=2, pady=2, fill=tk.X, expand=True
        )

        # commands frame
        commands_frame = ttk.LabelFrame(left_frame, text="Commands")
        commands_frame.pack(fill=tk.X, padx=3, pady=3)

        # tnfo and packet setings buttons
        info_frame = ttk.Frame(commands_frame)
        info_frame.pack(fill=tk.X, padx=3, pady=3)

        self.info_button = ttk.Button(
            info_frame,
            text="Device Info",
            command=self.get_device_info,
            state=tk.DISABLED,
        )
        self.info_button.pack(side=tk.LEFT, padx=2, pady=2, fill=tk.X, expand=True)

        self.packet_button = ttk.Button(
            info_frame,
            text="Packet Settings",
            command=self.get_packet_settings,
            state=tk.DISABLED,
        )
        self.packet_button.pack(side=tk.LEFT, padx=2, pady=2, fill=tk.X, expand=True)

        # ==== RIGHT SIDE ====
        # remote commands frame
        remote_frame = ttk.LabelFrame(right_frame, text="Remote Commands")
        remote_frame.pack(fill=tk.X, padx=3, pady=3)

        # ping and Depth buttons
        remote_row1 = ttk.Frame(remote_frame)
        remote_row1.pack(fill=tk.X, padx=3, pady=3)

        self.ping_button = ttk.Button(
            remote_row1,
            text="Ping",
            command=lambda: self.get_remote_data(0),
            state=tk.DISABLED,
        )
        self.ping_button.pack(side=tk.LEFT, padx=2, pady=2, fill=tk.X, expand=True)

        self.depth_button = ttk.Button(
            remote_row1,
            text="Get Depth",
            command=lambda: self.get_remote_data(2),
            state=tk.DISABLED,
        )
        self.depth_button.pack(side=tk.LEFT, padx=2, pady=2, fill=tk.X, expand=True)

        # temperature and Battery buttons
        remote_row2 = ttk.Frame(remote_frame)
        remote_row2.pack(fill=tk.X, padx=3, pady=3)

        self.temp_button = ttk.Button(
            remote_row2,
            text="Get Temperature",
            command=lambda: self.get_remote_data(3),
            state=tk.DISABLED,
        )
        self.temp_button.pack(side=tk.LEFT, padx=2, pady=2, fill=tk.X, expand=True)

        self.battery_button = ttk.Button(
            remote_row2,
            text="Get Battery",
            command=lambda: self.get_remote_data(4),
            state=tk.DISABLED,
        )
        self.battery_button.pack(side=tk.LEFT, padx=2, pady=2, fill=tk.X, expand=True)

        monitor_frame = ttk.LabelFrame(right_frame, text="Temperature Monitoring")
        monitor_frame.pack(fill=tk.X, padx=3, pady=3)

        monitor_settings = ttk.Frame(monitor_frame)
        monitor_settings.pack(fill=tk.X, padx=3, pady=3)

        settings_grid = ttk.Frame(monitor_settings)
        settings_grid.pack(fill=tk.X, expand=True)

        ttk.Label(settings_grid, text="Interval (sec):").grid(
            row=0, column=0, padx=2, pady=2, sticky=tk.W
        )
        self.interval_var = tk.IntVar(value=5)
        interval_spinbox = ttk.Spinbox(
            settings_grid, from_=1, to=60, textvariable=self.interval_var, width=5
        )
        interval_spinbox.grid(row=0, column=1, padx=2, pady=2, sticky=tk.W)

        ttk.Label(settings_grid, text="Count:").grid(
            row=0, column=2, padx=2, pady=2, sticky=tk.W
        )
        self.count_var = tk.IntVar(value=10)
        count_spinbox = ttk.Spinbox(
            settings_grid, from_=1, to=100, textvariable=self.count_var, width=5
        )
        count_spinbox.grid(row=0, column=3, padx=2, pady=2, sticky=tk.W)

        self.monitor_button = ttk.Button(
            monitor_frame,
            text="Start Monitoring",
            command=self.start_monitoring,
            state=tk.DISABLED,
        )
        self.monitor_button.pack(fill=tk.X, padx=3, pady=3)

    def setup_monitor_tab(self):
        # create frame to hold plots
        plot_frame = ttk.Frame(self.monitor_tab)
        plot_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # create a grid for plots (2x2)
        plot_frame.columnconfigure(0, weight=1)
        plot_frame.columnconfigure(1, weight=1)
        plot_frame.rowconfigure(0, weight=1)
        plot_frame.rowconfigure(1, weight=1)

        # distance plot
        self.distance_frame = ttk.LabelFrame(plot_frame, text="Distance")
        self.distance_frame.grid(row=0, column=0, padx=3, pady=3, sticky="nsew")

        self.distance_fig = Figure(figsize=(4, 3), dpi=75)
        self.distance_ax = self.distance_fig.add_subplot(111)
        self.distance_canvas = FigureCanvasTkAgg(
            self.distance_fig, master=self.distance_frame
        )
        self.distance_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # signal quality plot
        self.signal_frame = ttk.LabelFrame(plot_frame, text="Signal Quality")
        self.signal_frame.grid(row=0, column=1, padx=3, pady=3, sticky="nsew")

        self.signal_fig = Figure(figsize=(4, 3), dpi=75)
        self.signal_ax = self.signal_fig.add_subplot(111)
        self.signal_canvas = FigureCanvasTkAgg(
            self.signal_fig, master=self.signal_frame
        )
        self.signal_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # temperature plot
        self.temp_frame = ttk.LabelFrame(plot_frame, text="Temperature")
        self.temp_frame.grid(row=1, column=0, padx=3, pady=3, sticky="nsew")

        self.temp_fig = Figure(figsize=(4, 3), dpi=75)
        self.temp_ax = self.temp_fig.add_subplot(111)
        self.temp_canvas = FigureCanvasTkAgg(self.temp_fig, master=self.temp_frame)
        self.temp_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # velocity plot
        self.velocity_frame = ttk.LabelFrame(plot_frame, text="Velocity")
        self.velocity_frame.grid(row=1, column=1, padx=3, pady=3, sticky="nsew")

        self.velocity_fig = Figure(figsize=(4, 3), dpi=75)
        self.velocity_ax = self.velocity_fig.add_subplot(111)
        self.velocity_canvas = FigureCanvasTkAgg(
            self.velocity_fig, master=self.velocity_frame
        )
        self.velocity_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        update_frame = ttk.Frame(self.monitor_tab, height=25)
        update_frame.pack(fill=tk.X, padx=5, pady=2)
        update_frame.pack_propagate(False)  # Prevent resizing

        self.update_time_label = ttk.Label(update_frame, text="No data available")
        self.update_time_label.pack(fill=tk.X, expand=True)

    def setup_console_tab(self):
        """Setup the command console tab"""
        main_frame = ttk.Frame(self.console_tab)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        input_frame = ttk.LabelFrame(main_frame, text="Command")
        input_frame.pack(fill=tk.X, padx=3, pady=3)

        command_frame = ttk.Frame(input_frame)
        command_frame.pack(fill=tk.X, padx=3, pady=3)

        ttk.Label(command_frame, text="NMEA Command:").pack(side=tk.LEFT, padx=2)
        self.command_entry = ttk.Entry(command_frame, width=40)
        self.command_entry.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)

        ttk.Label(command_frame, text="Presets:").pack(side=tk.LEFT, padx=2)
        self.preset_commands = [
            "Select a preset...",
            "$PUWV?,0 (Device Info)",
            "$PUWVD,0 (Packet Mode Settings)",
            "$PUWV2,0,0,0 (Ping)",
            "$PUWV2,0,0,2 (Get Depth)",
            "$PUWV2,0,0,3 (Get Temperature)",
            "$PUWV2,0,0,4 (Get Battery)",
        ]
        self.preset_combo = ttk.Combobox(
            command_frame, values=self.preset_commands, width=25
        )
        self.preset_combo.current(0)
        self.preset_combo.pack(side=tk.LEFT, padx=2)
        self.preset_combo.bind("<<ComboboxSelected>>", self.on_preset_selected)

        self.add_checksum_var = tk.BooleanVar(value=True)
        checksum_check = ttk.Checkbutton(
            command_frame, text="Add Checksum", variable=self.add_checksum_var
        )
        checksum_check.pack(side=tk.LEFT, padx=2)

        self.send_button = ttk.Button(
            input_frame, text="Send Command", command=self.send_custom_command
        )
        self.send_button.pack(fill=tk.X, padx=3, pady=3)
        self.send_button["state"] = tk.DISABLED

        response_frame = ttk.LabelFrame(main_frame, text="Response")
        response_frame.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)

        self.response_text = scrolledtext.ScrolledText(
            response_frame, wrap=tk.WORD, height=18
        )
        self.response_text.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)

        self.clear_response_button = ttk.Button(
            response_frame, text="Clear", command=self.clear_response
        )
        self.clear_response_button.pack(side=tk.RIGHT, padx=3, pady=3)

    def on_preset_selected(self, event):
        """Handle preset command selection"""
        selection = self.preset_combo.get()
        if selection != "Select a preset...":
            command_part = selection.split(" ")[0]
            self.command_entry.delete(0, tk.END)
            self.command_entry.insert(0, command_part)

        self.preset_combo.selection_clear()

    def send_custom_command(self):
        """Send a custom command from the console tab"""
        if self.worker_thread and self.worker_thread.is_alive():
            return

        command = self.command_entry.get().strip()
        if not command:
            messagebox.showwarning("Error", "No command entered")
            return

        add_checksum = self.add_checksum_var.get()

        self.update_status(f"Sending command: {command}")
        self.add_to_log(f"Sending custom command: {command}")

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.response_text.insert(tk.END, f"[{timestamp}] TX: {command}\n")

        self.worker_thread = threading.Thread(
            target=self._send_command_thread, args=(command, add_checksum)
        )
        self.worker_thread.daemon = True
        self.worker_thread.start()

    def _send_command_thread(self, command, add_checksum):
        """Thread to send custom command and get response"""
        try:
            response, additional = self.monitor.send_command(
                command,
                wait_for_response=True,
                wait_for_puwv3=command.startswith("$PUWV2"),
            )

            if add_checksum and not "*" in command:
                formatted_command = self.monitor.format_command(command)
            else:
                formatted_command = command

            if response:
                translation = self._translate_nmea_response(response)
                self.root.after(
                    0,
                    lambda: self._add_response_text(
                        f"RX: {response}\n    → {translation}"
                    ),
                )

            for resp in additional:
                translation = self._translate_nmea_response(resp)
                self.root.after(
                    0,
                    lambda resp=resp, trans=translation: self._add_response_text(
                        f"RX: {resp}\n    → {trans}"
                    ),
                )

            if not response and not additional:
                self.root.after(
                    0, lambda: self._add_response_text("No response received")
                )

        except Exception as e:
            self.root.after(0, lambda e=e: self._add_response_text(f"Error: {str(e)}"))
            self.root.after(
                0, lambda e=e: self.update_status(f"Command error: {str(e)}")
            )

    def _translate_nmea_response(self, response):
        """Translate NMEA response to human-readable format"""
        if not response or not response.startswith("$"):
            return "Invalid or empty NMEA response"

        try:
            parts = response.split(",")
            message_type = parts[0]

            if message_type == "$PUWV!":
                if len(parts) >= 13:
                    return (
                        f"Device Info: SN {parts[1]}, System {parts[2]} v{parts[3]}, "
                        f"Core {parts[4]} v{parts[5]}, Baudrate {parts[6]}, "
                        f"RX/TX Ch {parts[7]}/{parts[8]}, Salinity {parts[10]} PSU"
                    )
                else:
                    return "Device Info (incomplete data)"

            elif message_type == "$PUWVE":
                if len(parts) >= 3:
                    is_packet_mode = "Yes" if parts[1] == "1" else "No"
                    return f"Packet Mode Settings: Enabled: {is_packet_mode}, Local Address: {parts[2]}"
                else:
                    return "Packet Mode Settings (incomplete data)"

            elif message_type == "$PUWV3":
                if len(parts) >= 6:
                    remote_addr = parts[1]
                    cmd_id = parts[2]
                    prop_time = float(parts[3])
                    signal_quality = parts[4]
                    value = parts[5] if len(parts) > 5 else "N/A"

                    cmd_descriptions = {
                        "0": "Ping",
                        "2": "Depth",
                        "3": "Temperature",
                        "4": "Battery Voltage",
                    }
                    cmd_desc = cmd_descriptions.get(cmd_id, f"Command {cmd_id}")

                    if cmd_id == "3":  # temperature
                        value_with_unit = f"{value}°C"
                    elif cmd_id == "4":  # battery
                        value_with_unit = f"{value}V"
                    elif cmd_id == "2":  # depth
                        value_with_unit = f"{value}m"
                    else:
                        value_with_unit = value

                    return (
                        f"Remote Response: {cmd_desc} from addr {remote_addr}, "
                        f"Prop time {abs(prop_time)*1000:.2f}ms, Signal {signal_quality}dB, "
                        f"Value: {value_with_unit}"
                    )
                else:
                    return "Remote Response (incomplete data)"

            elif message_type == "$PUWV0":
                return "Command Acknowledged"

            else:
                # other NMEA message types
                return f"Message type: {message_type} (raw data)"

        except Exception as e:
            return f"Error parsing response: {str(e)}"

    def _add_response_text(self, text):
        """Add text to the response display with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.response_text.insert(tk.END, f"[{timestamp}] {text}\n")
        self.response_text.see(tk.END)

    def clear_response(self):
        """Clear the response text area"""
        self.response_text.delete(1.0, tk.END)

    def setup_topdown_tab(self):
        # create main frame
        main_frame = ttk.Frame(self.topdown_tab)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # controls frame at top
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, padx=2, pady=2)

        # reset view button
        self.reset_view_button = ttk.Button(
            controls_frame, text="Reset View", command=self.reset_topdown_view
        )
        self.reset_view_button.pack(side=tk.LEFT, padx=2, pady=2)

        # clear trail button
        self.clear_trail_button = ttk.Button(
            controls_frame, text="Clear Trail", command=self.clear_modem_trail
        )
        self.clear_trail_button.pack(side=tk.LEFT, padx=2, pady=2)

        # distance info
        self.distance_info_label = ttk.Label(controls_frame, text="Distance: N/A")
        self.distance_info_label.pack(side=tk.RIGHT, padx=2, pady=2)

        # top-down view plot
        self.topdown_frame = ttk.LabelFrame(main_frame, text="Top-Down Positioning")
        self.topdown_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.topdown_fig = Figure(figsize=(6, 5), dpi=75)
        self.topdown_ax = self.topdown_fig.add_subplot(111, aspect="equal")
        self.topdown_canvas = FigureCanvasTkAgg(
            self.topdown_fig, master=self.topdown_frame
        )
        self.topdown_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def setup_log_tab(self):
        log_frame = ttk.Frame(self.log_tab)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        button_frame = ttk.Frame(self.log_tab)
        button_frame.pack(fill=tk.X, padx=5, pady=2)

        self.clear_log_button = ttk.Button(
            button_frame, text="Clear Log", command=self.clear_log
        )
        self.clear_log_button.pack(side=tk.RIGHT, padx=2, pady=2)

    def scan_ports(self):
        self.port_combo["values"] = []
        ports = self.monitor.list_available_ports()
        self.add_to_log("Scanning for ports...")

        if ports:
            self.port_combo["values"] = ports
            self.port_combo.current(0)
            self.add_to_log(f"Found {len(ports)} ports")
        else:
            self.add_to_log("No USB serial ports found")

    def connect_modem(self):
        if self.worker_thread and self.worker_thread.is_alive():
            return

        port = self.port_combo.get()
        if not port:
            messagebox.showwarning("Error", "No port selected")
            return

        self.add_to_log(f"Connecting to {port}...")
        self.update_status(f"Connecting to {port}...")

        self.connect_button["state"] = tk.DISABLED
        self.port_combo["state"] = tk.DISABLED
        self.scan_button["state"] = tk.DISABLED

        self.worker_thread = threading.Thread(target=self._connect_thread, args=(port,))
        self.worker_thread.daemon = True
        self.worker_thread.start()

    def _connect_thread(self, port):
        success = self.monitor.connect(port)

        self.root.after(0, lambda: self._connection_done(success))

    def _connection_done(self, success):
        self.port_combo["state"] = "readonly"
        self.scan_button["state"] = tk.NORMAL

        if success:
            self.update_status("Connected successfully")

            if self.monitor.get_device_info():
                self.add_to_log("Device info retrieved")

            self.connect_button["state"] = tk.DISABLED
            self.disconnect_button["state"] = tk.NORMAL
            self.info_button["state"] = tk.NORMAL
            self.packet_button["state"] = tk.NORMAL
            self.ping_button["state"] = tk.NORMAL
            self.depth_button["state"] = tk.NORMAL
            self.temp_button["state"] = tk.NORMAL
            self.battery_button["state"] = tk.NORMAL
            self.monitor_button["state"] = tk.NORMAL
            self.send_button["state"] = tk.NORMAL
        else:
            self.update_status("Connection failed")
            self.connect_button["state"] = tk.NORMAL

    def disconnect_modem(self):
        if self.worker_thread and self.worker_thread.is_alive():
            # need to wait for current operation to complete
            return

        self.add_to_log("Disconnecting...")
        self.update_status("Disconnecting...")

        self.worker_thread = threading.Thread(target=self._disconnect_thread)
        self.worker_thread.daemon = True
        self.worker_thread.start()

        self.disconnect_button["state"] = tk.DISABLED

    def _disconnect_thread(self):
        self.monitor.disconnect()

        self.root.after(0, self._disconnection_done)

    def _disconnection_done(self):
        self.update_status("Disconnected")

        self.connect_button["state"] = tk.NORMAL
        self.disconnect_button["state"] = tk.DISABLED
        self.info_button["state"] = tk.DISABLED
        self.packet_button["state"] = tk.DISABLED
        self.ping_button["state"] = tk.DISABLED
        self.depth_button["state"] = tk.DISABLED
        self.temp_button["state"] = tk.DISABLED
        self.battery_button["state"] = tk.DISABLED
        self.monitor_button["state"] = tk.DISABLED
        self.send_button["state"] = tk.DISABLED

    def get_device_info(self):
        if self.worker_thread and self.worker_thread.is_alive():
            return

        self.add_to_log("Getting device information...")
        self.update_status("Getting device information...")

        self.worker_thread = threading.Thread(target=self._device_info_thread)
        self.worker_thread.daemon = True
        self.worker_thread.start()

    def _device_info_thread(self):
        device_info = self.monitor.get_device_info()

        if device_info:
            self.root.after(0, lambda: self.update_status("Device info retrieved"))
        else:
            self.root.after(0, lambda: self.update_status("Failed to get device info"))

    def get_packet_settings(self):
        if self.worker_thread and self.worker_thread.is_alive():
            return

        self.add_to_log("Getting packet mode settings...")
        self.update_status("Getting packet mode settings...")

        self.worker_thread = threading.Thread(target=self._packet_settings_thread)
        self.worker_thread.daemon = True
        self.worker_thread.start()

    def _packet_settings_thread(self):
        packet_settings = self.monitor.get_packet_mode_settings()

        if packet_settings:
            self.root.after(0, lambda: self.update_status("Packet settings retrieved"))
        else:
            self.root.after(
                0, lambda: self.update_status("Failed to get packet settings")
            )

    def get_remote_data(self, cmd_id):
        if self.worker_thread and self.worker_thread.is_alive():
            return

        cmd_descriptions = {
            0: "Ping",
            2: "Depth",
            3: "Temperature",
            4: "Battery Voltage",
        }

        description = cmd_descriptions.get(cmd_id, f"Command {cmd_id}")
        self.add_to_log(f"Requesting remote {description}...")
        self.update_status(f"Requesting remote {description}...")

        self.worker_thread = threading.Thread(
            target=self._remote_data_thread, args=(cmd_id,)
        )
        self.worker_thread.daemon = True
        self.worker_thread.start()

    def _remote_data_thread(self, cmd_id):
        responses = self.monitor.get_remote_data(cmd_id)

        if responses:
            self.root.after(
                0,
                lambda: self.update_status(
                    f"Remote data retrieved (Command ID: {cmd_id})"
                ),
            )
        else:
            self.root.after(
                0,
                lambda: self.update_status(
                    f"Failed to get remote data (Command ID: {cmd_id})"
                ),
            )

    def start_monitoring(self):
        if self.worker_thread and self.worker_thread.is_alive():
            return

        interval = self.interval_var.get()
        count = self.count_var.get()

        self.add_to_log(
            f"Starting temperature monitoring ({count} readings every {interval} seconds)..."
        )
        self.update_status("Monitoring temperature...")

        self.monitor_button["state"] = tk.DISABLED

        self.worker_thread = threading.Thread(
            target=self._monitoring_thread, args=(interval, count)
        )
        self.worker_thread.daemon = True
        self.worker_thread.start()

    def _monitoring_thread(self, interval, count):
        try:
            for i in range(count):
                self.root.after(
                    0, lambda i=i: self.update_status(f"Reading {i+1}/{count}")
                )

                self.monitor.get_remote_data(3)

                if i < count - 1:
                    time.sleep(interval)

            self.root.after(0, lambda: self.update_status("Monitoring complete"))
            self.root.after(0, lambda: self._enable_monitor_button())

        except Exception as e:
            self.root.after(0, lambda e=e: self.update_status(f"Error: {str(e)}"))
            self.root.after(0, lambda: self._enable_monitor_button())

    def _enable_monitor_button(self):
        self.monitor_button["state"] = tk.NORMAL

    def update_status(self, message):
        """Update the status bar with a message"""
        self.status_var.set(message)
        self.add_to_log(message)

    def add_to_log(self, message):
        """Add a message to the log tab"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)

    def clear_log(self):
        """Clear the log text area"""
        self.log_text.delete(1.0, tk.END)

    def reset_topdown_view(self):
        """Reset the top-down view to default zoom/pan"""
        self.update_topdown_plot(True)

    def clear_modem_trail(self):
        """Clear the trail of modem positions"""
        self.modem_trail = []
        self.update_topdown_plot()

    def update_plots(self):
        """Update all plots with new data from the CSV file"""
        if not os.path.exists(self.csv_file):
            self.root.after(2000, self.update_plots)
            return

        try:
            # read CSV data
            timestamps = []
            slant_ranges = []
            horiz_dists = []
            signal_qualities = []
            temperatures = []
            velocities = []

            with open(self.csv_file, "r") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    timestamps.append(
                        datetime.strptime(row["Timestamp"], "%Y-%m-%d %H:%M:%S.%f")
                    )

                    if "Slant Range (m)" in row:
                        slant_ranges.append(float(row["Slant Range (m)"]))

                    if "Horizontal Dist (m)" in row:
                        horiz_dists.append(float(row["Horizontal Dist (m)"]))

                    if "Signal Quality" in row:
                        signal_qualities.append(float(row["Signal Quality"]))

                    if "Value" in row:
                        temperatures.append(float(row["Value"]))

                    if "Velocity (m/s)" in row:
                        velocities.append(float(row["Velocity (m/s)"]))

            max_points = 30
            if len(timestamps) > max_points:
                timestamps = timestamps[-max_points:]
                if slant_ranges:
                    slant_ranges = slant_ranges[-max_points:]
                if horiz_dists:
                    horiz_dists = horiz_dists[-max_points:]
                if signal_qualities:
                    signal_qualities = signal_qualities[-max_points:]
                if temperatures:
                    temperatures = temperatures[-max_points:]
                if velocities:
                    velocities = velocities[-max_points:]

            self._update_distance_plot(timestamps, slant_ranges, horiz_dists)
            self._update_signal_plot(timestamps, signal_qualities)
            self._update_temp_plot(timestamps, temperatures)
            self._update_velocity_plot(timestamps, velocities)

            # update top-down view if we have horizontal distance
            if horiz_dists and len(horiz_dists) > 0:
                latest_dist = horiz_dists[-1]
                self.remote_modem_pos = (latest_dist, 0)

                self.modem_trail.append(self.remote_modem_pos)
                if len(self.modem_trail) > self.max_trail_length:
                    self.modem_trail = self.modem_trail[-self.max_trail_length :]

                self.update_topdown_plot()

                self.distance_info_label["text"] = f"Distance: {latest_dist:.2f} m"

            if timestamps:
                last_timestamp = timestamps[-1]
                self.update_time_label["text"] = (
                    f"Last Update: {last_timestamp.strftime('%Y-%m-%d %H:%M:%S')} | Displaying {len(timestamps)} data points"
                )

        except Exception as e:
            self.update_status(f"Plot update error: {str(e)}")

        self.root.after(2000, self.update_plots)

    def update_topdown_plot(self, reset_view=False):
        """Update the top-down visualization of modem positions"""
        self.topdown_ax.clear()

        self.topdown_ax.set_aspect("equal")

        self.topdown_ax.set_xlabel("Distance (meters)")
        self.topdown_ax.set_ylabel("Distance (meters)")
        self.topdown_ax.grid(True)

        self.topdown_ax.plot(
            self.base_modem_pos[0],
            self.base_modem_pos[1],
            "bs",
            markersize=12,
            label="Base Modem",
        )

        if self.remote_modem_pos:
            if self.modem_trail and len(self.modem_trail) > 1:
                trail_x = [pos[0] for pos in self.modem_trail]
                trail_y = [pos[1] for pos in self.modem_trail]
                self.topdown_ax.plot(trail_x, trail_y, "g-", alpha=0.5)

            self.topdown_ax.plot(
                [self.base_modem_pos[0], self.remote_modem_pos[0]],
                [self.base_modem_pos[1], self.remote_modem_pos[1]],
                "k--",
                alpha=0.7,
            )

            self.topdown_ax.plot(
                self.remote_modem_pos[0],
                self.remote_modem_pos[1],
                "ro",
                markersize=12,
                label="Remote Modem",
            )

            dist = math.sqrt(
                (self.remote_modem_pos[0] - self.base_modem_pos[0]) ** 2
                + (self.remote_modem_pos[1] - self.base_modem_pos[1]) ** 2
            )
            midpoint = (
                (self.base_modem_pos[0] + self.remote_modem_pos[0]) / 2,
                (self.base_modem_pos[1] + self.remote_modem_pos[1]) / 2,
            )
            self.topdown_ax.text(
                midpoint[0],
                midpoint[1],
                f"{dist:.2f} m",
                fontsize=9,
                ha="center",
                va="bottom",
                bbox=dict(facecolor="white", alpha=0.7),
            )

        if reset_view or not self.remote_modem_pos:
            self.topdown_ax.set_xlim(-5, 15)
            self.topdown_ax.set_ylim(-10, 10)
        elif self.remote_modem_pos:
            max_dist = max(abs(self.remote_modem_pos[0]), 10)  # at least 10m wide
            self.topdown_ax.set_xlim(-max_dist * 0.2, max_dist * 1.2)  # 20% padding
            self.topdown_ax.set_ylim(-max_dist * 0.6, max_dist * 0.6)

        self.topdown_ax.legend(loc="upper right")
        self.topdown_fig.tight_layout()
        self.topdown_canvas.draw()

    def _update_distance_plot(self, timestamps, slant_ranges, horiz_dists):
        self.distance_ax.clear()
        self.distance_ax.set_ylabel("Distance (meters)")
        self.distance_ax.grid(True)

        if timestamps and slant_ranges:
            self.distance_ax.plot(
                timestamps,
                slant_ranges,
                "-o",
                color="blue",
                label="Slant Range",
                markersize=4,
            )

        if timestamps and horiz_dists:
            self.distance_ax.plot(
                timestamps,
                horiz_dists,
                "-s",
                color="green",
                label="Horizontal",
                markersize=4,
            )

        if timestamps and (slant_ranges or horiz_dists):
            self.distance_ax.legend(fontsize=8)
            self.distance_ax.tick_params(axis="x", rotation=45, labelsize=8)
            self.distance_ax.tick_params(axis="y", labelsize=8)

        self.distance_fig.tight_layout()
        self.distance_canvas.draw()

    def _update_signal_plot(self, timestamps, signal_qualities):
        self.signal_ax.clear()
        self.signal_ax.set_ylabel("Quality (dB)")
        self.signal_ax.grid(True)

        if timestamps and signal_qualities:
            self.signal_ax.plot(timestamps, signal_qualities, "-", color="red")
            self.signal_ax.tick_params(axis="x", rotation=45, labelsize=8)
            self.signal_ax.tick_params(axis="y", labelsize=8)

        self.signal_fig.tight_layout()
        self.signal_canvas.draw()

    def _update_temp_plot(self, timestamps, temperatures):
        self.temp_ax.clear()
        self.temp_ax.set_ylabel("Temperature (°C)")
        self.temp_ax.grid(True)

        if timestamps and temperatures:
            self.temp_ax.plot(timestamps, temperatures, "-", color="magenta")
            self.temp_ax.tick_params(axis="x", rotation=45, labelsize=8)
            self.temp_ax.tick_params(axis="y", labelsize=8)

        self.temp_fig.tight_layout()
        self.temp_canvas.draw()

    def _update_velocity_plot(self, timestamps, velocities):
        self.velocity_ax.clear()
        self.velocity_ax.set_ylabel("Velocity (m/s)")
        self.velocity_ax.grid(True)

        if timestamps and velocities:
            self.velocity_ax.plot(timestamps, velocities, "-", color="cyan")
            self.velocity_ax.axhline(y=0, color="black", linestyle="--", alpha=0.3)
            self.velocity_ax.tick_params(axis="x", rotation=45, labelsize=8)
            self.velocity_ax.tick_params(axis="y", labelsize=8)

        self.velocity_fig.tight_layout()
        self.velocity_canvas.draw()


def main():
    root = ThemedTk(theme="blue")
    root.title("uWave Modem Controller")
    root.attributes("-zoomed", True)  # fullscreen on RPi

    app = UwaveGUI(root)
    root.protocol("WM_DELETE_WINDOW", lambda: on_closing(root))
    root.mainloop()


def on_closing(root):
    root.destroy()
    sys.exit(0)


if __name__ == "__main__":
    main()
