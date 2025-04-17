import matplotlib.pyplot as plt
import matplotlib.animation as animation
import pandas as pd
import numpy as np
import os
import time
from datetime import datetime, timedelta
from matplotlib.dates import DateFormatter


class UwaveRealtimeMonitor:
    def __init__(self, csv_file="uwave_data.csv", update_interval=1000, max_points=30):
        """Initialize the real-time monitor with settings."""
        self.csv_file = csv_file
        self.update_interval = update_interval  # milliseconds
        self.max_points = max_points  # maximum number of points to display
        self.last_modified = None
        self.previous_size = 0
        self.data = None

        self.fig = plt.figure(figsize=(12, 8))
        self.fig.canvas.manager.set_window_title("uWave Real-time Monitor")
        self.setup_plots()

        self.load_data()

    def setup_plots(self):
        """Initialize the matplotlib subplots."""
        self.axes = {}

        # distance plot
        self.axes["distance"] = self.fig.add_subplot(2, 2, 1)
        self.axes["distance"].set_title("Distance Measurements")
        self.axes["distance"].set_ylabel("Distance (meters)")
        self.axes["distance"].grid(True)

        # signal quality plot
        self.axes["signal"] = self.fig.add_subplot(2, 2, 2)
        self.axes["signal"].set_title("Signal Quality")
        self.axes["signal"].set_ylabel("Signal Quality (dB)")
        self.axes["signal"].grid(True)

        # temperature plot
        self.axes["temp"] = self.fig.add_subplot(2, 2, 3)
        self.axes["temp"].set_title("Temperature")
        self.axes["temp"].set_ylabel("Temperature (°C)")
        self.axes["temp"].grid(True)

        # velocity plot
        self.axes["velocity"] = self.fig.add_subplot(2, 2, 4)
        self.axes["velocity"].set_title("Relative Velocity")
        self.axes["velocity"].set_ylabel("Velocity (m/s)")
        self.axes["velocity"].grid(True)

        self.timestamp_text = self.fig.text(
            0.5,
            0.01,
            "",
            ha="center",
            fontsize=9,
            bbox=dict(facecolor="white", alpha=0.5),
        )

        plt.tight_layout()
        self.fig.subplots_adjust(bottom=0.15)

    def load_data(self):
        """Load or reload data from CSV file."""
        try:
            if os.path.exists(self.csv_file):
                current_modified = os.path.getmtime(self.csv_file)
                current_size = os.path.getsize(self.csv_file)

                if (
                    self.last_modified is None
                    or current_modified > self.last_modified
                    or current_size != self.previous_size
                ):

                    print(
                        f"Data file changed, reloading... (Size: {current_size} bytes)"
                    )
                    self.data = pd.read_csv(self.csv_file)
                    self.data["Timestamp"] = pd.to_datetime(self.data["Timestamp"])

                    if len(self.data) > self.max_points:
                        self.data = self.data.tail(self.max_points)

                    self.last_modified = current_modified
                    self.previous_size = current_size
                    return True
            return False
        except Exception as e:
            print(f"Error loading data: {e}")
            return False

    def update_plot(self, frame):
        """Update the plot with new data."""
        if not self.load_data() and self.data is not None:
            return

        if self.data is None or len(self.data) == 0:
            return

        for ax in self.axes.values():
            ax.clear()
            ax.grid(True)

        self.axes["distance"].set_title("Distance Measurements")
        self.axes["distance"].set_ylabel("Distance (meters)")

        self.axes["signal"].set_title("Signal Quality")
        self.axes["signal"].set_ylabel("Signal Quality (dB)")

        self.axes["temp"].set_title("Temperature")
        self.axes["temp"].set_ylabel("Temperature (°C)")

        self.axes["velocity"].set_title("Relative Velocity")
        self.axes["velocity"].set_ylabel("Velocity (m/s)")

        time_min = self.data["Timestamp"].min()
        time_max = self.data["Timestamp"].max() + timedelta(seconds=5)  # Add buffer

        if "Slant Range (m)" in self.data.columns:
            self.axes["distance"].plot(
                self.data["Timestamp"],
                self.data["Slant Range (m)"],
                "-o",
                color="blue",
                label="Slant Range",
                markersize=4,
            )

        if "Horizontal Dist (m)" in self.data.columns:
            self.axes["distance"].plot(
                self.data["Timestamp"],
                self.data["Horizontal Dist (m)"],
                "-s",
                color="green",
                label="Horizontal Distance",
                markersize=4,
            )

        self.axes["distance"].legend()
        self.axes["distance"].set_xlim(time_min, time_max)

        if "Signal Quality" in self.data.columns:
            self.axes["signal"].plot(
                self.data["Timestamp"],
                self.data["Signal Quality"],
                "-",
                color="red",
                label="Signal Quality",
            )
            self.axes["signal"].legend()
            self.axes["signal"].set_xlim(time_min, time_max)

            signal_min = self.data["Signal Quality"].min()
            signal_max = self.data["Signal Quality"].max()
            buffer = (signal_max - signal_min) * 0.1  # 10% buffer
            self.axes["signal"].set_ylim(signal_min - buffer, signal_max + buffer)

        if "Value" in self.data.columns:
            self.axes["temp"].plot(
                self.data["Timestamp"],
                self.data["Value"],
                "-",
                color="magenta",
                label="Temperature",
            )
            self.axes["temp"].legend()
            self.axes["temp"].set_xlim(time_min, time_max)

            temp_min = self.data["Value"].min()
            temp_max = self.data["Value"].max()
            buffer = max(0.5, (temp_max - temp_min) * 0.1)  # At least 0.5°C buffer
            self.axes["temp"].set_ylim(temp_min - buffer, temp_max + buffer)

        if "Velocity (m/s)" in self.data.columns:
            self.axes["velocity"].plot(
                self.data["Timestamp"],
                self.data["Velocity (m/s)"],
                "-",
                color="cyan",
                label="Velocity",
            )
            self.axes["velocity"].axhline(y=0, color="black", linestyle="--", alpha=0.3)
            self.axes["velocity"].legend()
            self.axes["velocity"].set_xlim(time_min, time_max)

            vel_max = max(
                abs(self.data["Velocity (m/s)"].max()),
                abs(self.data["Velocity (m/s)"].min()),
            )
            vel_max = max(0.05, vel_max * 1.2)  # At least ±0.05 with 20% buffer
            self.axes["velocity"].set_ylim(-vel_max, vel_max)

        for ax in self.axes.values():
            ax.xaxis.set_major_formatter(DateFormatter("%H:%M:%S"))
            ax.tick_params(axis="x", rotation=45)

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.timestamp_text.set_text(
            f"Last Updated: {current_time} | Displaying {len(self.data)} points"
        )

        plt.tight_layout()
        self.fig.subplots_adjust(bottom=0.15)

    def run(self):
        """Start the real-time monitoring."""
        print(f"Starting real-time monitoring of {self.csv_file}")
        print(f"Plots will update every {self.update_interval/1000:.1f} seconds")
        print("Close the plot window to stop monitoring")

        self.ani = animation.FuncAnimation(
            self.fig,
            self.update_plot,
            interval=self.update_interval,
            cache_frame_data=False,
        )

        plt.show()


def main():
    print("uWave Real-time Monitor")
    print("======================")

    csv_file = "uwave_data.csv"
    update_interval = 1000  # milliseconds
    max_points = 30

    custom = input("Use custom settings? (y/n, default: n): ").lower() == "y"

    if custom:
        csv_file = input(f"CSV file path (default: {csv_file}): ") or csv_file

        try:
            update_interval = int(
                input(f"Update interval in milliseconds (default: {update_interval}): ")
                or update_interval
            )
        except ValueError:
            print(f"Invalid value, using default: {update_interval}")

        try:
            max_points = int(
                input(f"Maximum points to display (default: {max_points}): ")
                or max_points
            )
        except ValueError:
            print(f"Invalid value, using default: {max_points}")

    if not os.path.exists(csv_file):
        print(f"CSV file {csv_file} not found.")
        wait = input("Wait for file to be created? (y/n, default: y): ").lower() != "n"

        if wait:
            print(f"Waiting for {csv_file} to be created...")
            while not os.path.exists(csv_file):
                time.sleep(1)
            print(f"File {csv_file} found! Starting monitor...")
        else:
            print("Exiting.")
            return

    monitor = UwaveRealtimeMonitor(csv_file, update_interval, max_points)
    monitor.run()


if __name__ == "__main__":
    main()
