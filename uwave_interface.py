import serial
import csv
import time
import math
import os
from datetime import datetime


LOG_FILE = "uwave_log.txt"
CSV_FILE = "uwave_data.csv"
DEFAULT_SALINITY = 0.0  # PSU
DEFAULT_DEPTH = 0.0  # meters
NMEA_PREFIX = "$PUWV"


class UwaveMonitor:
    def __init__(self, port=None, baudrate=9600, timeout=8):
        """start up the UWave monitor with port selection."""
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None
        self.last_range = None
        self.last_range_time = None
        self.salinity = DEFAULT_SALINITY

        if not os.path.exists(CSV_FILE):
            with open(CSV_FILE, "w", newline="") as csv_file:
                csv_writer = csv.writer(csv_file)
                csv_writer.writerow(
                    [
                        "Timestamp",
                        "Command",
                        "Response Type",
                        "Remote Addr",
                        "Cmd ID",
                        "Prop Time",
                        "Signal Quality",
                        "Value",
                        "Slant Range (m)",
                        "Horizontal Dist (m)",
                        "Velocity (m/s)",
                    ]
                )

        if not os.path.exists(LOG_FILE):
            with open(LOG_FILE, "w") as log_file:
                log_file.write("========== uWave Communication Log ==========\n")
                log_file.write(f"Started: {datetime.now()}\n\n")

    def list_available_ports(self):
        """List all available serial ports."""
        import serial.tools.list_ports

        ports = serial.tools.list_ports.comports()
        usb_ports = []

        print("Available ports:")
        for port in ports:
            if "USB" in port.description:
                print(f"  * {port.device} - {port.description}")
                usb_ports.append(port.device)
            else:
                print(f"    {port.device} - {port.description}")

        return usb_ports

    def connect(self, port=None):
        """Connect to the specified port or auto-detect if none specified."""
        if port:
            self.port = port
        elif not self.port:
            ports = self.list_available_ports()
            if ports:
                self.port = ports[0]
                print(f"Auto-selected port: {self.port}")
            else:
                print("No USB serial ports found. Please specify a port manually.")
                return False

        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout,
            )
            print(f"Connected to {self.port} at {self.baudrate} baud.")
            return True
        except Exception as e:
            print(f"Error connecting to {self.port}: {e}")
            return False

    def disconnect(self):
        """Close the serial connection."""
        if self.ser and self.ser.is_open:
            self.ser.close()
            print(f"Disconnected from {self.port}")

    def calculate_sound_velocity(self, temperature, salinity=None, depth=None):
        """Calculate sound velocity in water"""
        if salinity is None:
            salinity = self.salinity
        if depth is None:
            depth = DEFAULT_DEPTH

        # Mackenzie equation, fancy math stuff
        c = (
            1448.96
            + 4.591 * temperature
            - 5.304e-2 * temperature**2
            + 2.374e-4 * temperature**3
        )
        c += 1.340 * (salinity - 35) + 1.63e-2 * depth + 1.675e-7 * depth**2
        c += (
            -1.025e-2 * temperature * (salinity - 35)
            - 7.139e-13 * temperature * depth**3
        )

        return c

    def calculate_slant_range(self, propagation_time, sound_velocity):
        """Calculate slant range from propagation time and sound velocity."""
        return abs(float(propagation_time)) * sound_velocity / 2

    def calculate_horizontal_distance(self, slant_range, depth_difference=0):
        """Calculate horizontal distance using slant range and depth difference."""
        # if depth_difference is greater than slant_range, it's probably a measurement error
        if abs(depth_difference) >= slant_range:
            return 0

        return math.sqrt(slant_range**2 - depth_difference**2)

    def calculate_velocity(self, current_range, current_time):
        """Calculate velocity from two range measurements."""
        if self.last_range is None or self.last_range_time is None:
            self.last_range = current_range
            self.last_range_time = current_time
            return 0

        time_diff = (current_time - self.last_range_time).total_seconds()

        if time_diff <= 0:
            return 0

        velocity = (current_range - self.last_range) / time_diff

        self.last_range = current_range
        self.last_range_time = current_time

        return velocity

    def parse_puwv3(self, response):
        """Parse a PUWV3 response (remote command response)."""
        try:
            parts = response.split("*")[0].split(",")

            cmd_type = parts[0][:5]  # $PUWV
            remote_addr = parts[1]
            cmd_id = parts[2]
            prop_time = parts[3]
            signal_quality = parts[4]
            value = parts[5] if len(parts) > 5 else ""
            azimuth = parts[6] if len(parts) > 6 else ""

            return {
                "cmd_type": cmd_type,
                "remote_addr": remote_addr,
                "cmd_id": cmd_id,
                "prop_time": prop_time,
                "signal_quality": signal_quality,
                "value": value,
                "azimuth": azimuth,
            }
        except Exception as e:
            print(f"Error parsing PUWV3 response: {e}")
            return None

    def parse_puwve(self, response):
        """Parse a PUWVE response (packet mode settings)."""
        try:
            parts = response.split("*")[0].split(",")

            cmd_type = parts[0][:5]  # $PUWV
            is_pt_mode = parts[1]
            pt_local_address = parts[2]

            return {
                "cmd_type": cmd_type,
                "is_pt_mode": is_pt_mode,
                "pt_local_address": pt_local_address,
            }
        except Exception as e:
            print(f"Error parsing PUWVE response: {e}")
            return None

    def parse_puwv_bang(self, response):
        """Parse a PUWV! response (device information)."""
        try:
            parts = response.split("*")[0].split(",")

            cmd_type = parts[0][:5]  # $PUWV
            serial_number = parts[1]
            system_moniker = parts[2]
            system_version = parts[3]
            core_moniker = parts[4]
            core_version = parts[5]
            baudrate = parts[6]
            rx_channel = parts[7]
            tx_channel = parts[8]
            max_channels = parts[9]
            salinity = parts[10]
            has_pts = parts[11]
            cmd_mode = parts[12]

            self.salinity = float(salinity)

            return {
                "cmd_type": cmd_type,
                "serial_number": serial_number,
                "system_moniker": system_moniker,
                "system_version": system_version,
                "core_moniker": core_moniker,
                "core_version": core_version,
                "baudrate": baudrate,
                "rx_channel": rx_channel,
                "tx_channel": tx_channel,
                "max_channels": max_channels,
                "salinity": salinity,
                "has_pts": has_pts,
                "cmd_mode": cmd_mode,
            }

        except Exception as e:
            print(f"Error parsing PUWV! response: {e}")
            return None

    def calculate_nmea_checksum(self, sentence):
        """calculate the checksum for an NMEA sentence because I'm tired of getting it wrong."""

        checksum_part = sentence.lstrip("$").split("*")[0]

        checksum = 0
        for char in checksum_part:
            checksum ^= ord(char)

        return "{:02X}".format(checksum)

    def format_command(self, command, include_checksum=True):
        """Format a command with proper checksum"""
        if not include_checksum or "*" in command:
            return command

        checksum = self.calculate_nmea_checksum(command)
        return f"{command}*{checksum}"

    def send_command(self, command, wait_for_response=True, wait_for_puwv3=False):
        """Send a command to the modem and wait for response."""
        if not self.ser or not self.ser.is_open:
            print("Serial port not open.")
            return None, []

        full_command = self.format_command(command)

        print(f"\nSending command: {full_command}")
        self.ser.write((full_command + "\n").encode("ascii"))

        responses = []
        main_response = None
        additional_responses = []
        now = datetime.now()

        if wait_for_response:
            line = self.ser.readline().decode("ascii", errors="ignore").strip()
            if line:
                print(f"Initial response: {line}")
                main_response = line
                responses.append(line)
                self.log_communication(full_command, line, now)

            if wait_for_puwv3 and command.startswith("$PUWV2"):
                timeout_count = 0
                max_timeout = 5  # 5 seconds max wait

                while timeout_count < max_timeout:
                    line = self.ser.readline().decode("ascii", errors="ignore").strip()
                    if line:
                        print(f"Additional response: {line}")
                        additional_responses.append(line)

                        if line.startswith("$PUWV3"):
                            parsed = self.parse_puwv3(line)
                            if parsed:
                                if parsed["cmd_id"] == "3" and parsed["value"]:
                                    temp = float(parsed["value"])
                                    prop_time = float(parsed["prop_time"])
                                    sound_vel = self.calculate_sound_velocity(temp)
                                    slant_range = self.calculate_slant_range(
                                        prop_time, sound_vel
                                    )
                                    horiz_dist = self.calculate_horizontal_distance(
                                        slant_range
                                    )
                                    velocity = self.calculate_velocity(
                                        slant_range, datetime.now()
                                    )

                                    print(f"\nCalculated metrics:")
                                    print(f"  Temperature: {temp:.1f}°C")
                                    print(f"  Sound velocity: {sound_vel:.1f} m/s")
                                    print(
                                        f"  Propagation time: {abs(prop_time)*1000:.2f} ms"
                                    )
                                    print(f"  Slant range: {slant_range:.2f} m")
                                    print(f"  Horizontal distance: {horiz_dist:.2f} m")
                                    if abs(velocity) > 0.001:
                                        print(
                                            f"  Relative velocity: {velocity:.3f} m/s"
                                        )
                                        if velocity > 0:
                                            print("  (moving away)")
                                        else:
                                            print("  (approaching)")

                                    self.log_metrics(
                                        timestamp=now,
                                        command=full_command,
                                        response_type="PUWV3",
                                        remote_addr=parsed["remote_addr"],
                                        cmd_id=parsed["cmd_id"],
                                        prop_time=prop_time,
                                        signal_quality=float(parsed["signal_quality"]),
                                        value=temp,
                                        slant_range=slant_range,
                                        horiz_dist=horiz_dist,
                                        velocity=velocity,
                                    )

                        if line.startswith("$PUWV3"):
                            self.log_communication(None, line, now)
                            break
                    else:
                        timeout_count += 1
                        time.sleep(0.2)

        return main_response, additional_responses

    def log_communication(self, command, response, timestamp=None):
        """Log the command and response to the log file."""
        if timestamp is None:
            timestamp = datetime.now()

        with open(LOG_FILE, "a") as log_file:
            if command:
                log_file.write(f"{timestamp} TX: {command}\n")
            if response:
                log_file.write(f"{timestamp} RX: {response}\n")

    def log_metrics(
        self,
        timestamp,
        command,
        response_type,
        remote_addr,
        cmd_id,
        prop_time,
        signal_quality,
        value,
        slant_range,
        horiz_dist,
        velocity,
    ):
        """Log detailed metrics to the CSV file."""
        with open(CSV_FILE, "a", newline="") as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(
                [
                    timestamp.strftime("%Y-%m-%d %H:%M:%S.%f"),
                    command,
                    response_type,
                    remote_addr,
                    cmd_id,
                    prop_time,
                    signal_quality,
                    value,
                    f"{slant_range:.4f}",
                    f"{horiz_dist:.4f}",
                    f"{velocity:.4f}",
                ]
            )

    def get_device_info(self):
        """Get device information."""
        command = "$PUWV?,0"
        response, _ = self.send_command(command)

        if response and response.startswith("$PUWV!"):
            parsed = self.parse_puwv_bang(response)
            if parsed:
                print("\nDevice Information:")
                print(f"  Serial Number: {parsed['serial_number']}")
                print(
                    f"  System: {parsed['system_moniker']} v{parsed['system_version']}"
                )
                print(f"  Core: {parsed['core_moniker']} v{parsed['core_version']}")
                print(
                    f"  Channels: TX {parsed['tx_channel']}, RX {parsed['rx_channel']} (max: {parsed['max_channels']})"
                )
                print(f"  Acoustic Baudrate: {parsed['baudrate']} bit/s")
                print(f"  Salinity: {parsed['salinity']} PSU")
                print(
                    f"  Has Pressure/Temp Sensor: {'Yes' if parsed['has_pts'] == '1' else 'No'}"
                )
                print(
                    f"  Command Mode by Default: {'Yes' if parsed['cmd_mode'] == '1' else 'No'}"
                )

                return parsed

        return None

    def get_packet_mode_settings(self):
        """Get packet mode settings."""
        command = "$PUWVD,0"
        response, _ = self.send_command(command)

        if response and response.startswith("$PUWVE"):
            parsed = self.parse_puwve(response)
            if parsed:
                print("\nPacket Mode Settings:")
                print(
                    f"  Packet Mode Enabled: {'Yes' if parsed['is_pt_mode'] == '1' else 'No'}"
                )
                print(f"  Local Address: {parsed['pt_local_address']}")

                return parsed

        return None

    def get_remote_data(self, remote_cmd_id):
        """Get data from the remote modem."""
        # Map of command IDs to descriptions
        cmd_descriptions = {
            "0": "Ping",
            "2": "Depth",
            "3": "Temperature",
            "4": "Battery Voltage",
        }

        description = cmd_descriptions.get(
            str(remote_cmd_id), f"Command {remote_cmd_id}"
        )
        print(f"\nRequesting remote {description}...")

        command = f"$PUWV2,0,0,{remote_cmd_id}"
        _, responses = self.send_command(command, wait_for_puwv3=True)

        return responses

    def monitor_remote_temperature(self, interval=5, count=10):
        """Monitor remote temperature at regular intervals."""
        print(
            f"\nStarting remote temperature monitoring ({count} readings every {interval} seconds)..."
        )

        for i in range(count):
            print(f"\nReading {i+1}/{count}")
            self.get_remote_data(3)  # 3 = temperature

            if i < count - 1:  # Don't sleep after the last reading
                time.sleep(interval)

        print("\nMonitoring complete.")


def main():
    monitor = UwaveMonitor()
    monitor.list_available_ports()
    if not monitor.connect():
        return

    try:
        device_info = monitor.get_device_info()

        packet_settings = monitor.get_packet_mode_settings()

        monitor.get_remote_data(0)  # 0 = ping

        monitor.get_remote_data(2)  # 2 = depth

        monitor.get_remote_data(3)  # 3 = temperature

        monitor.get_remote_data(4)  # 4 = battery voltage

        monitor_choice = input(
            "\nDo you want to monitor temperature at regular intervals? (y/n): "
        )
        if monitor_choice.lower() == "y":
            try:
                interval = int(input("Enter interval in seconds (default: 5): ") or "5")
                count = int(input("Enter number of readings (default: 10): ") or "10")
                monitor.monitor_remote_temperature(interval, count)
            except ValueError:
                print("Invalid input. Using defaults: 5 seconds interval, 10 readings.")
                monitor.monitor_remote_temperature(5, 10)

        print("\nAll commands completed.")

    finally:
        monitor.disconnect()


if __name__ == "__main__":
    main()
