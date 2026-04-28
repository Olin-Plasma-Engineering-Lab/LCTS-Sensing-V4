"""Shared constants for the GUI submodules.

Kept in their own module so individual widgets can import them without
pulling in the main window (avoids circular imports).
"""

# Hardware defaults (mirror the CLI Config dataclass)
DEFAULT_PWM_DIO = 2
DEFAULT_CORE_FREQ_HZ = 80_000_000
DEFAULT_CLOCK_DIVISOR = 1
DEFAULT_PWM_FREQ_HZ = 50

DEFAULT_POSITION_ZERO = 90
DEFAULT_POSITION_UP = 135
DEFAULT_POSITION_DOWN = 45

# Sampling / plotting
SAMPLE_PERIOD_MS = 50           # 20 Hz
PLOT_BUFFER_SAMPLES = 2000      # ring-buffer length for the live plot
