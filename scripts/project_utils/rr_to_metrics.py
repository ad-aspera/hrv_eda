import pandas as pd
from typing import Union
import sys
sys.path.append('.')

import metrics.HRV_Metrics as HRV_Metrics
Numeric = Union[float, int]
import xlwings as xw


def signal_as_series_enforcer(func):
    def wrapper(signal: pd.Series | list[Numeric] | tuple[Numeric], *args, **kwargs):
        """Forces signal into series with RR_interval values in milliseconds and index as seconds"""
        signal = pd.Series(signal).astype(float)
        signal.index = signal.cumsum()

        # Make sure that indexing is in seconds rather than milliseconds
        if signal.mean() >= 10:
            signal.index = signal.index / 1000

        # Make sure that RR_intervals are in milliseconds
        if signal.mean() < 10:
            signal = signal * 1000

        return func(signal, *args, **kwargs)
    return wrapper

@signal_as_series_enforcer
def time_portion_signal(signal: pd.Series, fragment_s: float = 300):
    """Divides signal into 5 minutes internals.
    Signal index has to be in seconds"""
    five_min = []
    segments_info = []  # To store original start and end timestamps
    
    start_idx = 0
    while start_idx < len(signal):
        end_idx = start_idx
        while end_idx < len(signal) and (signal.index[end_idx] - signal.index[start_idx]) < fragment_s:
            end_idx += 1

        if end_idx == len(signal):
            break

        segment = signal.iloc[start_idx:end_idx]
        # Store original start and end timestamps
        t_start = signal.index[start_idx]
        t_end = signal.index[end_idx-1]
        segments_info.append((t_start, t_end))
        
        segment.index = segment.index - segment.index[0]

        if segment.index[-1] < fragment_s / 2:
            break

        five_min.append(segment)
        start_idx = end_idx

    if len(five_min) == 0:
        raise ValueError(f"The signal is too short to fraction into fragments of {fragment_s}s")

    return five_min, segments_info


def patients_metrics(signal:pd.Series, sub_signal_duration_s=300)->pd.Series:
    metrics = pd.DataFrame()
    subsignals, segments_info = time_portion_signal(signal, sub_signal_duration_s)
    
    for i, (subsignal, (t_start, t_end)) in enumerate(zip(subsignals, segments_info)):
        metrics_dict = HRV_Metrics.get_all_metrics(subsignal)
        metrics_dict = {'t_start': t_start, 't_end': t_end, **metrics_dict}
        metrics = pd.concat([metrics, pd.DataFrame([metrics_dict])], ignore_index=True)
       # print(metrics)

    return metrics


if __name__ == "__main__":
    import pickle

    # Load the pickled file
    with open('actionable_data/data.pkl', 'rb') as f:
        peaks = pickle.load(f)

    # Select 3 patients
    selected_patients = list(peaks.keys())[:3]
    DS_RR = {}
    for patient_id in selected_patients:
        patient_ds = peaks[patient_id]['DS'][0]
        # Update to handle the tuple return value (segments, segments_info)
        patient_segments, patient_segments_info = time_portion_signal(patient_ds)
        print(f"Patient {patient_id} has {len(patient_segments)} segments")
        for i, (segment, (t_start, t_end)) in enumerate(zip(patient_segments, patient_segments_info)):
            print(f"  Segment {i}: start={t_start:.2f}s, end={t_end:.2f}s, duration={t_end-t_start:.2f}s")


def df_from_excel(path):
    wb = xw.Book(path)
    wb.app.api.Visible = False
    wb.app.calculate()
    wb.save()
    #wb.close()
    wb.app.quit()    
    return pd.read_excel(path)