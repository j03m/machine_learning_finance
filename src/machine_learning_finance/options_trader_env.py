import numpy as np
import gymnasium as gym
from gymnasium import logger, spaces
from statsmodels.tsa.seasonal import seasonal_decompose
from .logger import info, debug, error, verbose
from sklearn.preprocessing import MinMaxScaler
import math
from scipy.stats import norm
import pandas as pd
from machine_learning_finance import generate_probability, attach_markers, calculate_duration_probabilities, \
    calc_durations_with_extremes
from .trader_env import TraderEnv


# TODO FINISH ME

class OptionTraderEnv(TraderEnv):

    def __init__(self, product, test_period_df, historical_period_df, curriculum_code=1, cash=5000):
        super(OptionTraderEnv, self).__init__(product, test_period_df, historical_period_df, curriculum_code, cash)

    def expand(self, test_period_df, historical_period_df):
        # todo: never really finished or tested this fix and test me
        df = super().expand(test_period_df, historical_period_df)
        # apply the top 5 expiration window probabilities as columns
        trend, prob_above_trend, prob_below_trend, volatility, model = generate_probability(df)
        df_raw = attach_markers(df, trend, prob_above_trend)
        df_durations = calc_durations_with_extremes(df_raw)
        for i in range(1, 6):
            df_raw[f"revert_date_{i}"] = np.nan
            df_raw[f"revert_prob_{i}"] = np.nan

        for index, row in df.iterrows():
            df_top_prob = calculate_duration_probabilities(index, df_raw, df_durations) \
                .sort_values('probability', ascending=False).head(5)
            values = df_top_prob['probability'].tolist()
            dates = df_top_prob.index.tolist()
            for i in range(1, 6):
                df_raw.loc[index, f"revert_date_{i}"] = dates[i - 1]
                df_raw.loc[index, f"revert_prob_{i}"] = values[i - 1]
        return df_raw

    def _apply_action(self, action):
        # AI says hold
        if action == 0:
            pass
        elif action == 1 and self.in_long:
            #
            pass
        elif action == 1 and not self.in_position:
            pass
        # AI says long, but we're short. Close the short, open a long.
        elif action == 1 and self.in_short:
            pass
        # AI says short, but we're already short
        elif action == 2 and self.in_short:
            pass
        # AI says short, we're not in a position so exit
        elif action == 2 and not self.in_position:
            pass
        # AI says short but we're long, close it
        elif action == 2 and self.in_long:
            pass
        else:  # assume hold
            pass
        self.update_position_value()

    def make_ledger_row(self):
        pass

    def open_position(self):
        pass

    def open_short(self):
        pass

    def close_position(self):
        pass

    def close_short(self):
        pass

    def update_position_value(self):
        pass

    def total_value(self):
        pass
