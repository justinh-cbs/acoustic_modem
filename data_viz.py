import matplotlib.pyplot as plt
import pandas as pd
import os
import numpy as np
from datetime import datetime


csv_file = "uwave_data.csv"
if not os.path.exists(csv_file):
    print(f"CSV file {csv_file} not found.")
    exit()

data = pd.read_csv(csv_file)
print(f"Loaded {len(data)} rows from CSV")
print("Available columns:", list(data.columns))

if "Timestamp" in data.columns:
    data["Timestamp"] = pd.to_datetime(data["Timestamp"])
    timestamp_col = "Timestamp"
    print(f"Using Timestamp column for x-axis")
else:
    timestamp_col = None
    print("No timestamp column found, using row index instead")

fig, axes = plt.subplots(2, 2, figsize=(14, 10))
plt.suptitle("uWave Modem Data Analysis", fontsize=16)

# plot 1: distance measurements
ax1 = axes[0, 0]
ax1.set_title("Distance Measurements")
ax1.set_ylabel("Distance (meters)")
ax1.grid(True)

# slant range
if "Slant Range (m)" in data.columns:
    ax1.plot(
        data["Timestamp"],
        data["Slant Range (m)"],
        "-",
        color="blue",
        label="Slant Range",
    )

# horizontal distance
if "Horizontal Dist (m)" in data.columns:
    ax1.plot(
        data["Timestamp"],
        data["Horizontal Dist (m)"],
        "-",
        color="green",
        label="Horizontal Distance",
    )

ax1.legend()

# plot 2: signal quality
ax2 = axes[0, 1]
ax2.set_title("Signal Quality")
ax2.set_ylabel("Signal Strength (dB)")
ax2.grid(True)

if "Signal Quality" in data.columns:
    ax2.plot(
        data["Timestamp"],
        data["Signal Quality"],
        "-",
        color="red",
        label="Signal Quality",
    )
    ax2.legend()

# plot 3: temperature data
ax3 = axes[1, 0]
ax3.set_title("Temperature")
ax3.set_ylabel("Temperature (°C)")
ax3.grid(True)

if "Value" in data.columns:
    ax3.plot(
        data["Timestamp"], data["Value"], "-", color="magenta", label="Temperature"
    )
    ax3.legend()

# plot 4: velocity
ax4 = axes[1, 1]
ax4.set_title("Relative Velocity")
ax4.set_ylabel("Velocity (m/s)")
ax4.grid(True)

if "Velocity (m/s)" in data.columns:
    ax4.plot(
        data["Timestamp"], data["Velocity (m/s)"], "-", color="cyan", label="Velocity"
    )
    ax4.axhline(y=0, color="black", linestyle="--", alpha=0.3)
    ax4.legend()

# adjust x-axis formatting
for ax in axes.flatten():
    ax.tick_params(axis="x", rotation=45)
    ax.xaxis.set_major_locator(plt.MaxNLocator(6))

plt.tight_layout()
fig.subplots_adjust(top=0.92)
plt.figtext(
    0.5,
    0.01,
    f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
    ha="center",
    fontsize=9,
)

# uncomment these next two lines if you want to save as a PNG
# plt.savefig('uwave_visualization.png', dpi=300, bbox_inches='tight')
# print("Saved visualization to uwave_visualization.png")
plt.show()
