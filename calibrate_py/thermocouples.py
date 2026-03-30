import numpy as np
import warnings


def ktype_with_cjc(vm_mV, Tc_C):
    """Convert K-type thermocouple voltage (mV) to temperature (°C) with CJC.

    vm_mV : scalar or array-like
        Measured thermocouple voltage (hot minus cold) in millivolts.
    Tc_C : scalar or array-like
        Cold-junction temperature in degrees Celsius.

    Returns temperature in °C with the same shape as the broadcasted inputs.
    """
    vm = np.asarray(vm_mV, dtype=float)
    Tc = np.asarray(Tc_C, dtype=float)

    # Broadcast inputs
    try:
        vm, Tc = np.broadcast_arrays(vm, Tc)
    except Exception:
        vm = np.asarray(vm)
        Tc = np.asarray(Tc)

    # ---- Forward: Tc -> cold-junction equivalent EMF (µV) ----
    # Coefficients from NIST/ITS-90 (units: µV for polynomial output)
    a_neg = np.array(
        [
            0.000000000000e00,
            3.8748106364e01,
            4.4194434347e-02,
            1.1844323105e-04,
            2.0032973554e-05,
            9.0138019559e-07,
            2.2651156593e-08,
            3.6071154205e-10,
            3.8493939883e-12,
            2.8213521925e-14,
            1.4251594779e-16,
            4.8768662286e-19,
            1.0795539270e-21,
            1.3945027062e-24,
            7.9795153927e-28,
        ]
    )

    a_pos = np.array(
        [
            -1.7600413686e01,
            3.9450128025e01,
            2.3622373598e-02,
            -3.2858906784e-04,
            -4.9904828777e-06,
            -6.7509059173e-08,
            -5.7410327428e-10,
            -3.1088872894e-12,
            -1.0451609365e-14,
            -1.9889266878e-17,
            -1.6322697486e-20,
        ]
    )
    alpha0 = 1.185976e02
    alpha1 = -1.183432e-04
    alpha_center = 126.9686

    E_cj_uV = np.zeros_like(Tc, dtype=float)

    # negative Tc
    idx_neg = Tc < 0
    if np.any(idx_neg):
        Tn = Tc[idx_neg]
        # evaluate polynomial sum a_i * T^i
        powers = np.arange(a_neg.size)
        Eneg = np.zeros_like(Tn, dtype=float)
        for k, a in enumerate(a_neg):
            Eneg = Eneg + a * (Tn**k)
        E_cj_uV[idx_neg] = Eneg

    # non-negative Tc
    idx_pos = ~idx_neg
    if np.any(idx_pos):
        Tp = Tc[idx_pos]
        Epos = np.zeros_like(Tp, dtype=float)
        for k, a in enumerate(a_pos):
            Epos = Epos + a * (Tp**k)
        Epos = Epos + alpha0 * np.exp(alpha1 * (Tp - alpha_center) ** 2)
        E_cj_uV[idx_pos] = Epos

    # convert µV -> mV
    E_cj_mV = E_cj_uV / 1000.0

    # total EMF (mV)
    Em_total_mV = vm + E_cj_mV

    # ---- Inverse: Em_total_mV -> Temperature (°C) ----
    T = np.zeros_like(Em_total_mV, dtype=float)

    # inverse coefficients (ordered d0, d1, ...)
    d1 = np.array(
        [
            0.0000000e00,
            2.508355e01,
            7.860106e-02,
            -2.503131e-01,
            8.315270e-02,
            -1.228034e-02,
            9.804036e-04,
            -4.413030e-05,
            1.057734e-06,
            -1.052755e-08,
        ]
    )

    d2 = np.array(
        [
            0.000000e00,
            2.508355e01,
            7.860116e-02,
            -2.503131e-01,
            8.315270e-02,
            -1.228034e-02,
            9.804036e-04,
            -4.413030e-05,
            1.057734e-06,
            -1.052755e-08,
        ]
    )

    d3 = np.array(
        [
            -1.318058e02,
            4.830222e01,
            -1.646031e00,
            5.464731e-02,
            -9.650715e-04,
            8.802193e-06,
            -3.110810e-08,
        ]
    )

    # region bounds (mV)
    r1_lo, r1_hi = -5.891, 0.0
    r2_lo, r2_hi = 0.0, 20.644
    r3_lo, r3_hi = 20.644, 54.886

    # region 1
    idx_r1 = (Em_total_mV >= r1_lo) & (Em_total_mV < r1_hi)
    if np.any(idx_r1):
        E = Em_total_mV[idx_r1]
        Tr = np.zeros_like(E)
        for k, d in enumerate(d1):
            Tr = Tr + d * (E**k)
        T[idx_r1] = Tr

    # region 2
    idx_r2 = (Em_total_mV >= r2_lo) & (Em_total_mV <= r2_hi)
    if np.any(idx_r2):
        E = Em_total_mV[idx_r2]
        Tr = np.zeros_like(E)
        for k, d in enumerate(d2):
            Tr = Tr + d * (E**k)
        T[idx_r2] = Tr

    # region 3
    idx_r3 = (Em_total_mV > r3_lo) & (Em_total_mV <= r3_hi)
    if np.any(idx_r3):
        E = Em_total_mV[idx_r3]
        Tr = np.zeros_like(E)
        for k, d in enumerate(d3):
            Tr = Tr + d * (E**k)
        T[idx_r3] = Tr

    # warn if out of range
    out_of_range = (Em_total_mV < r1_lo) | (Em_total_mV > r3_hi)
    if np.any(out_of_range):
        warnings.warn(
            f"Resulting EMF outside ITS-90 inverse polynomial range ({r1_lo} .. {r3_hi} mV). Extrapolation used.",
            UserWarning,
        )

    # return scalar if inputs were scalars
    if np.isscalar(vm_mV) and np.isscalar(Tc_C):
        return float(T)
    return T
