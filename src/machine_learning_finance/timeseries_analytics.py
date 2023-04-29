import pandas as pd
import numpy as np
from scipy.stats import norm
from scipy.signal import find_peaks, peak_prominences
from scipy.stats import poisson

from .plotly_utils import prob_chart, graph_pdf_bar, bar_chart


def calc_durations_with_extremes(df_raw):
    # get last index
    last_index = df_raw.iloc[-1].name

    # get the first index that is the beginning of a high probability window
    start_index = df_raw['high_prob_start'].first_valid_index()
    df_durations = pd.DataFrame(columns=['start', 'end', 'duration', 'extreme'])

    # loop through all high probability windows
    while start_index < last_index:
        start_pos = df_raw.index.get_loc(start_index)

        # loop through all indexes after the high probability window starts, searching for a cross to mark its end
        for index in df_raw.index[start_pos + 1:]:
            cross1 = df_raw.loc[index, 'cross_over_positive']
            cross2 = df_raw.loc[index, 'cross_over_negative']

            # continue until one of these is not nan
            if np.isnan(cross1) and np.isnan(cross2):
                continue

            # we found a cross, calculate how far it was from the probability start
            duration = (index - start_index).days

            # get the extreme value in the duration
            if (np.isnan(cross1)):
                extreme_value = df_raw.loc[start_index:index, "Close"].max()
                extreme_index = df_raw.loc[start_index:index, "Close"].idxmax()
            else:
                extreme_value = df_raw.loc[start_index:index, "Close"].min()
                extreme_index = df_raw.loc[start_index:index, "Close"].idxmin()

            # Create a new row using a dictionary
            row = {'start': start_index, 'end': index, 'duration': duration, 'extreme': extreme_value,
                   'extreme_index': extreme_index}
            df_durations = pd.concat([df_durations, pd.DataFrame([row])], ignore_index=True)

            # once we find a cross, we need to exit. Get the position of the exit.
            start_pos = df_raw.index.get_loc(index)

            break

        # find the next high probability window start AFTER the exit
        start_index = df_raw['high_prob_start'].iloc[start_pos + 1:].first_valid_index()

        if start_index is None:
            break

    # Create a box plot of the duration data
    return df_durations


def attach_markers(df_raw, trend, prob_above_trend):
    threshold = 0.85
    threshold_low = 0.15
    prob_above_trend = pd.Series(prob_above_trend, index=df_raw.index)
    high_prob_zones = (prob_above_trend > threshold) | (prob_above_trend < threshold_low)
    high_prob_starts = high_prob_zones[high_prob_zones == 1].index

    df_raw['high_prob_start'] = np.nan
    # Iterate over the high probability start dates
    for i, start_date in enumerate(high_prob_starts):
        df_raw.loc[start_date, 'high_prob_start'] = df_raw.loc[start_date, 'Close']

    # Calculate the sign of the difference between Close and trend at each point in time
    diff_sign = np.sign(trend - df_raw["Close"])

    # Take the difference of the sign values to detect when the sign changes
    cross_over = diff_sign.diff().fillna(0)

    # Detect when the sign changes from positive to negative or negative to positive
    cross_over_positive = (cross_over == -2).astype(int).diff().fillna(0)
    cross_over_negative = (cross_over == 2).astype(int).diff().fillna(0)

    # Create empty columns in df_raw
    df_raw['cross_over_positive'] = np.nan
    df_raw['cross_over_negative'] = np.nan

    # Set the values of the new columns based on cross_over_positive and cross_over_negative
    df_raw.loc[cross_over_positive == 1, 'cross_over_positive'] = df_raw.loc[cross_over_positive == 1, 'Close']
    df_raw.loc[cross_over_negative == 1, 'cross_over_negative'] = df_raw.loc[cross_over_negative == 1, 'Close']

    return df_raw


def calculate_and_graph_price_probabilities(percentage_differences):
    # Fit percentage differences to a normal distribution
    mean, std = norm.fit(percentage_differences)

    # Define the percentage deviation range
    min_percentage = int(np.floor(percentage_differences.min()))
    max_percentage = int(np.ceil(percentage_differences.max()))
    num_points = max_percentage - min_percentage + 1
    percentage_range = np.linspace(min_percentage, max_percentage, num_points)

    # Calculate the PDF of the normal distribution for the range of percentage deviations
    pdf_values = norm.pdf(percentage_range, mean, std)

    # Create a DataFrame with the percentage deviations and their corresponding PDF values
    pdf_df = pd.DataFrame({"Percentage Deviation": percentage_range, "PDF Value": pdf_values})

    graph_pdf_bar(pdf_df)
    print("Current price diff:", percentage_differences[-1])


def calculate_and_graph_duration_probabilities(start_date, df_raw, df_durations):
    # seed 60 days from the start of when we want to predict when the
    # mean regression will happen
    n_periods = 60
    dates = [start_date + pd.DateOffset(days=i) for i in range(n_periods)]
    df = pd.DataFrame({'date': dates})

    # Calculate duration windows, filter where anything is < 5
    df_durations = df_durations[df_durations["duration"] >= 5]
    durations = df_durations['duration'].values.tolist()
    print("Last duration:", durations[-1])

    # Fit a Poisson distribution to the durations
    # Then figure out the probability of a cross in n days
    rate = np.mean(durations)
    poisson_dist = poisson(rate)
    numbers = np.arange(1, n_periods + 1)
    cdf_values = poisson_dist.cdf(numbers)

    # Calculate the probabilities for each duration window
    window_probabilities = np.diff(cdf_values, prepend=0)

    # Graph as bars so we can predict when the price will
    total_probability = np.sum(window_probabilities)
    print("total:", total_probability)
    df['probability'] = window_probabilities
    df = df.set_index("date")
    bar_chart(df, False)


def calc_extreme_percentage_deviations(df_durations, trend):
    extreme_percentage_deviations = []

    for index, row in df_durations.iterrows():
        start_date = row['start']
        end_date = row['end']
        extreme_price = row['extreme']
        extreme_index = row['extreme_index']

        trend_value = trend.loc[extreme_index]

        deviation_percentage = (extreme_price - trend_value) / trend_value * 100
        extreme_percentage_deviations.append(deviation_percentage)

    return extreme_percentage_deviations


def analyze_extreme_deviations(df_durations, trend):
    extreme_percentage_deviations = calc_extreme_percentage_deviations(df_durations, trend)
    mean, std = norm.fit(extreme_percentage_deviations)
    numbers = np.arange(np.min(extreme_percentage_deviations), np.max(extreme_percentage_deviations))
    pdf_values = norm.pdf(numbers, mean, std)
    prob_chart(df_durations, pdf_values)